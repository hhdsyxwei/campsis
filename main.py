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
from Ingredient.downloader import download_csi300_components
from Ingredient.downloader import download_stock_basic
from CookingEngine.next_day_bullish_strategy import main_filter
from CookingEngine.Strategies.obs import (
    BoxBreakoutStrategy,
    BottomReverseStrategy,
    TrendPullbackStrategy,
    MultiIndicatorResonanceStrategy
)


os.environ["CAMPSIS_ENV"] = "dev"   # 开发环境
# os.environ["CAMPSIS_ENV"] = "prod" # 生产环境

logger = get_logger(__name__)


logger.debug("这是调试信息（灰色）")
logger.info("这是普通信息（蓝色）")
logger.warning("这是警告（黄色）")
logger.error("这是错误（红色）")
logger.info("初始化成功！【会加粗】")


def get_csi300_stock_codes(db_conn) -> list:
    """
    从数据库获取沪深300成分股股票代码列表
    
    Args:
        db_conn: 数据库连接对象
    
    Returns:
        股票代码列表，如果数据库中没有数据则返回空列表
    """
    from Ingredient.DataNest.dm_index_csi300 import IndexCsi300Manager
    
    manager = IndexCsi300Manager(db_conn)
    codes = manager.get_csi300_stock_codes()
    
    if not codes:
        logger.warning("数据库 index_csi300_component 表中未找到沪深300成分股数据")
    
    logger.info(f"从数据库获取到 {len(codes)} 只沪深300成分股")
    return codes


def main():
    # Count project code lines
    # count_project_code()

    # 1. 建立与本地数据库的连接
    conn = create_database_and_tables()

    # 2. 登录 Baostock 服务 
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
    stock_codes = get_csi300_stock_codes(conn)  # 从数据库获取沪深300成分股股票代码
    params = DownloadParameters(start_year=start_year, end_year=end_year, stock_codes=stock_codes)

    try:
        #download_basic_data(conn, params)
        download_stock_data(conn,params)
        #run_backtest(conn)
        run_bullish_strategies_backtest(conn)
        main_filter(conn)

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


def run_bullish_strategies_backtest(db_conn, stock_code="000001.SZ", start_date="2020-01-01", end_date="2024-12-31", initial_cash=1000000):
    """
    运行4个次日看涨策略的回测

    Args:
        db_conn: 数据库连接对象
        stock_code: 回测股票代码，默认 "000001.SZ"
        start_date: 回测开始日期，默认 "2020-01-01"
        end_date: 回测结束日期，默认 "2024-12-31"
        initial_cash: 初始资金，默认 100万
    """
    logger.info("=" * 60)
    logger.info("开始运行4个次日看涨策略回测")
    logger.info(f"回测股票: {stock_code}")
    logger.info(f"回测区间: {start_date} 至 {end_date}")
    logger.info(f"初始资金: {initial_cash}")
    logger.info("=" * 60)
    
    runner = ParallelBacktestRunner(db_conn)
    
    configs = [
        {
            "strategy": {
                "name": "box_breakout",
                "params": {
                    "box_range_days": 20,
                    "box_fluctuation_rate": 0.15,
                    "box_break_threshold": 1.03,
                    "box_volume_multiple": 2.0,
                    "holding_days": 5,
                    "stop_loss_ratio": 0.05,
                    "take_profit_ratio": 0.10,
                }
            },
            "data": {
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date
            },
            "initial_cash": initial_cash
        },
        {
            "strategy": {
                "name": "bottom_reverse",
                "params": {
                    "reverse_fall_days": 60,
                    "reverse_max_fall_rate": 0.5,
                    "reverse_build_days": 20,
                    "reverse_rise_threshold": 0.03,
                    "reverse_volume_multiple": 2.0,
                    "reverse_rsi_oversold": 20,
                    "holding_days": 5,
                    "stop_loss_ratio": 0.05,
                    "take_profit_ratio": 0.10,
                }
            },
            "data": {
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date
            },
            "initial_cash": initial_cash
        },
        {
            "strategy": {
                "name": "trend_pullback",
                "params": {
                    "trend_pullback_volume_ratio": 0.8,
                    "trend_rebound_volume_multiple": 1.5,
                    "holding_days": 5,
                    "stop_loss_ratio": 0.05,
                    "take_profit_ratio": 0.10,
                }
            },
            "data": {
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date
            },
            "initial_cash": initial_cash
        },
        {
            "strategy": {
                "name": "multi_indicator_resonance",
                "params": {
                    "resonance_rsi_lower": 50,
                    "resonance_rsi_upper": 70,
                    "min_signal_count": 4,
                    "holding_days": 5,
                    "stop_loss_ratio": 0.05,
                    "take_profit_ratio": 0.10,
                }
            },
            "data": {
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date
            },
            "initial_cash": initial_cash
        }
    ]
    
    results = runner.run_batch(configs)
    
    print("\n" + "=" * 60)
    print("4个次日看涨策略回测结果对比")
    print("=" * 60)
    
    for result in results:
        if 'error' in result:
            logger.error(f"回测出错: {result['error']}")
            continue
        strategy = result['strategy']
        
        print(f"\n--- {strategy} ---")
        
        if 'trades' in result and result['trades']:
            total_trades = len(result['trades'])
            winning_trades = len([t for t in result['trades'] if t['net'] > 0])
            losing_trades = len([t for t in result['trades'] if t['net'] <= 0])
            win_rate = winning_trades / total_trades * 100 if total_trades > 0 else 0
            
            total_profit = sum(t['net'] for t in result['trades'])
            
            print(f"  总交易次数: {total_trades}")
            print(f"  盈利交易: {winning_trades}")
            print(f"  亏损交易: {losing_trades}")
            print(f"  胜率: {win_rate:.2f}%")
            print(f"  总收益: {total_profit:.2f} 元")
        else:
            print(f"  无交易记录")
    
    analyzer = PerformanceAnalyzer()
    analysis = analyzer.compare(results)
    logger.info("回测分析结果:")
    logger.info(json.dumps(analysis, indent=4, ensure_ascii=False))
    
    return results


def download_basic_data(conn, params):
    """下载基础数据"""

    # 1.第一步：下载沪深300成分股数据
    download_csi300_components(conn)  # 下载沪深300_components(conn, params)

    # 2. 第二步：下载交易日映射表
    download_trade_date_map(conn, params)  # 下载交易日映射表，覆盖start_year-end_year年

    # 3. 第三步：下载股票基础信息
    download_stock_basic(conn, params, [MarketType.INDEX,MarketType.SZ_MAIN_BOARD])  # 下载股票详细信息（行业、上市日期等）

def download_stock_data(conn,params):

    """主函数，协调整个数据下载流程。"""
    # 1. 第一步：下载股票的日线数据，股票范围由params['stock_code']指定
    start_new_daily_download(conn, params)

    # 2. 第二步：下载行业分类数据
    # start_new_industry_download(conn, 2020, 2025)  # 从头开始下载2020-2025年的行业分类数据
    # continue_download_industry(conn, 2020, 2025)  # 继续下载2020-2025年的行业分类数据

    # 3. 第三步：下载5分钟K线数据（示例）
    # start_new_kline_download(conn, start_year, end_year)  # 下载5分钟K线数据，示例股票代码
    # continue_download_kline(conn, start_year, end_year, KLinePeriod.MIN_5)  # 继续下载2026-2027年的5分钟K线数据

    # 4. 第四步：下载分红送配数据
    # start_new_xrxd_download(conn, start_year, end_year)  # 下载2026-2027年的分 红送配数据  
    # continue_download_xrxd(conn, start_year, end_year)  # 下载2026-2027年的分红送配数据

    # 5. 第五步：下载复权因子数据
    # start_new_adj_factor_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的复权因子数据
    # continue_download_adj_factor(conn, start_year, end_year)  # 继续下载2026-2027年的复权因子数据

    # 6. 第六步：下载股票利润数据
    start_new_profit_download(conn, params)  # 从头开始下载2026-2027年的股票利润数据

    # 7. 第七步：下载公司偿债能力数据
    # start_new_balance_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的公司偿债能力数据
    # continue_download_company_balance(conn, start_year, end_year)  # 继续下载2026-2027年的公司偿债能力数据
    
    # 8. 第八步：下载公司现金流量数据
    # start_new_cash_flow_download(conn, start_year, end_year)  # 从头开始下载2026-2027年的公司现金流量数据
    # continue_download_company_cash_flow(conn, start_year, end_year)  # 继续下载2026-2027年的公司现金流量数据

    # 9. 第九步：为公司股票数据打分
    # score_single_stock(conn, stock_codes[0])

# 程序入口点，当直接运行此脚本时，会执行 main() 函数
if __name__ == '__main__':
    main()