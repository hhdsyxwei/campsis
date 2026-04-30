# main.py
# ==============================================
# 1. 必须放在所有其他导入 【最前面】
# ==============================================
from KitchenBase.package_manager import PackageManager
from KitchenBase.logger_config import setup_logging,get_logger
setup_logging()
PackageManager.install_missing_requirements()

import os
import sys
import json

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import KitchenBase.baostock_wrapper as bs
from KitchenBase.baostock_wrapper import BaostockErrorCode
from Ingredient.DataNest import create_database_and_tables
from Ingredient.downloader import download_trade_date_map
from KitchenBase.stock_enums import KLinePeriod, MarketType
from CookingEngine.Picker.stock_scorer import score_single_stock
from CookingEngine.Analysis.performance_analyzer import PerformanceAnalyzer
from CookingEngine.Backtest.parallel_runner import ParallelBacktestRunner
from tools.count_code import count_project_code
from Ingredient.downloader.core import DownloadParameters
from Ingredient.downloader import start_new_daily_download
from Ingredient.downloader import start_new_balance_download
from Ingredient.downloader import start_new_profit_download
from Ingredient.downloader import start_new_cash_flow_download
from Ingredient.downloader import start_new_adj_factor_download
from Ingredient.downloader import start_new_xrxd_download
from Ingredient.downloader import start_new_kline_download
from Ingredient.downloader import download_stock_basic



os.environ["CAMPSIS_ENV"] = "dev"   # 开发环境
# os.environ["CAMPSIS_ENV"] = "prod" # 生产环境

logger = get_logger(__name__)

logger.debug("这是调试信息（灰色）")
logger.info("这是普通信息（蓝色）")
logger.warning("这是警告（黄色）")
logger.error("这是错误（红色）")
logger.info("初始化成功！【会加粗】")

def main():
    # Count project code lines
    count_project_code()
    
    # 建立与本地数据库的连接
    conn = create_database_and_tables()


    try:
        download_stock_data(conn)
        run_backtest(conn)

    except Exception as e:
        # 捕获主流程中的任何异常，并记录详细错误信息
        logger.error(f"主程序执行出错: {e}", exc_info=True)
    finally:
        # 程序结束前，确保关闭数据库连接和 Baostock 登录会话
        conn.close()
        bs.logout()
        logger.info("已断开数据库连接并退出 Baostock。")

def run_backtest(db_conn):

    # 1. Create backtest runner
    runner = ParallelBacktestRunner(db_conn)

    # 2. Configure backtest tasks
    configs = [
        {
            "strategy": {
                "name": "factor_strategy",
                "params": {
                    "trend_weight": 0.25,
                    "momentum_weight": 0.25,
                    "quality_weight": 0.25,
                    "timing_weight": 0.25,
                    "buy_threshold": 0.6,
                    "sell_threshold": 0.4
                }
            },
            "data": {
                "stock_code": "000001.SZ",
                "start_date": "2020-01-01",
                "end_date": "2025-12-31"
            },
            "initial_cash": 1000000
        }
    ]
    
    # 3. Execute backtest
    results = runner.run_batch(configs)

    # 交易净收益列表
    for result in results:
        if 'error' in result:
            logger.error(f"回测出错: {result['error']}")
            continue
        strategy = result['strategy']
        
        # 打印交易记录（成交记录）
        if 'transactions' in result and result['transactions']:
            print(f"\n=== {strategy} 买卖记录 ===")
            txs = result['transactions']
            
            # 解析 Backtrader Transactions 格式
            # 格式: OrderedDict({datetime: [[amount, price, commission, stock_code, total_amount]]})
            for dt, tx_list in txs.items():
                for tx_sub_list in tx_list:
                    if len(tx_sub_list) >= 4:
                        amount = tx_sub_list[0]
                        price = tx_sub_list[1]
                        comm = tx_sub_list[2]
                        tx_type = "买入" if amount > 0 else "卖出"
                        date_str = dt.date().isoformat() if hasattr(dt, 'date') else str(dt)
                        print(f"  {date_str} | {tx_type:4} | 数量: {abs(amount):5} | 价格: {price:8.2f} | 佣金: {comm:6.2f}")
        
        # 打印交易盈亏
        if 'trades' in result and result['trades']:
            print(f"\n=== {strategy} 交易盈亏 ===")
            for trade in result['trades']:
                print(f"  日期: {trade['date']}, 净收益: {trade['net']:.2f}")

            print(f"\n--- {strategy} 统计 ---")
            print(f"  总交易次数: {len(result['trades'])}")
            print(f"  盈利交易: {len([t for t in result['trades'] if t['net'] > 0])}")
            print(f"  亏损交易: {len([t for t in result['trades'] if t['net'] < 0])}")

    # 4. Analyze results
    analyzer = PerformanceAnalyzer()
    analysis = analyzer.compare(results)
    logger.info(json.dumps(analysis, indent=4, ensure_ascii=False))

def download_stock_data(conn):

    """主函数，协调整个数据下载流程。"""
    # 1. 登录 Baostock 服务
    lg = bs.login()
    if BaostockErrorCode.IP_BLACKLIST == lg.error_code:
        logger.error("IP已经加入黑名单, 需要去QQ群里求助")
        return

    if BaostockErrorCode.CONNECTION_REFUSED == lg.error_code:
        logger.error("连接被拒绝, 请检查网络设置")
        return

    if BaostockErrorCode.SUCCESS != lg.error_code:
        logger.error(f"Baostock 登录失败: {lg.error_msg}")
        return
    logger.info("Baostock 登录成功。")

    start_year = 2025
    end_year = 2027
    stock_codes = ["000300.SH", "000001.SZ", "000002.SZ", "000004.SZ", "000006.SZ"]
    params = DownloadParameters(start_year=start_year, end_year=end_year, stock_codes=stock_codes)

    download_trade_date_map(conn, params)  # 下载交易日映射表，覆盖start_year-end_year年
    # 2. 第一步：同步并更新股票的基础信息表 (stock_basic)
    download_stock_basic(conn, params, [MarketType.INDEX,MarketType.SZ_MAIN_BOARD])  # 下载股票详细信息（行业、上市日期等）
    # 3. 第二步：下载所有活跃股票的日线数据
    # start_date 参数是可选的。如果不提供，download_all_stocks_daily_data 会尝试从 stock_basic 表中获取上市日期。
    start_new_daily_download(conn, params)
    # 4. 第三步：下载行业分类数据
    # start_new_industry_download(conn, 2020, 2025)  # 从头开始下载2020-2025年的行业分类数据
    # continue_download_industry(conn, 2020, 2025)  # 继续下载2020-2025年的行业分类数据
    # 5. 第四步：下载5分钟K线数据（示例）
    # start_new_kline_download(conn, start_year, end_year)  # 下载5分钟K线数据，示例股票代码
    # continue_download_kline(conn, start_year, end_year, KLinePeriod.MIN_5)  # 继续下载2026-2027年的5分钟K线数据
    # 6. 第五步：下载分红送配数据
    # start_new_xrxd_download(conn, start_year, end_year)  # 下载2026-2027年的分 红送配数据  
    # continue_download_xrxd(conn, start_year, end_year)  # 下载2026-2027年的分红送配数据
    # 7. 第六步：下载复权因子数据
    # start_new_adj_factor_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的复权因子数据
    # continue_download_adj_factor(conn, start_year, end_year)  # 继续下载2026-2027年的复权因子数据
    # 8. 第七步：下载股票利润数据
    # start_new_profit_download(conn, params)  # 从头开始下载2026-2027年的股票利润数据

    # 9. 第八步：下载公司偿债能力数据
    # start_new_balance_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的公司偿债能力数据
    # continue_download_company_balance(conn, start_year, end_year)  # 继续下载2026-2027年的公司偿债能力数据
    
    # 10. 第九步：下载公司现金流量数据
    # start_new_cash_flow_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的公司现金流量数据
    # continue_download_company_cash_flow(conn, start_year, end_year)  # 继续下载2026-2027年的公司现金流量数据
    # 11. 第十步：为公司股票数据打分
    score_single_stock(conn, stock_codes[0])

# 程序入口点，当直接运行此脚本时，会执行 main() 函数
if __name__ == '__main__':
    main()