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
import argparse

# Add current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import KitchenBase.baostock_wrapper as bs
from KitchenBase.baostock_wrapper import BaostockErrorCode
from Ingredient.DataNest import BacktestResultManager, create_database_and_tables
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
from Ingredient.downloader import start_new_industry_download
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


def persist_backtest_results(db_conn, stock_code, start_date, end_date, initial_cash,
                             results, analysis, run_name=None,
                             commission_rate=0.0003, risk_free_rate=0.03):
    manager = BacktestResultManager(db_conn)
    run_id = manager.create_run(
        stock_code=stock_code,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        run_name=run_name,
        commission_rate=commission_rate,
        risk_free_rate=risk_free_rate
    )

    has_error = any(result.get("error") for result in results)
    if manager.save_results(run_id, stock_code, results, analysis):
        if has_error:
            manager.mark_run_failed(run_id, "部分策略回测失败")
        else:
            manager.mark_run_success(run_id)
    else:
        manager.mark_run_failed(run_id, "回测结果保存失败")

    logger.info(f"回测结果已保存到数据库: run_id={run_id}")
    return run_id


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


def login_baostock() -> bool:
    """登录 Baostock 并统一处理常见错误。"""
    try:
        lg = bs.login()
    except ConnectionError as e:
        logger.error(str(e))
        logger.error("Baostock 使用 www.baostock.com:10030 TCP端口；若80/443可通但10030超时，多半是网络出口或防火墙拦截该端口。")
        return False

    if BaostockErrorCode.IP_BLACKLIST == lg.error_code:
        logger.error("IP已经加入黑名单, 需要去QQ群里求助")
        return False

    if lg.error_code in {BaostockErrorCode.CONNECTION_REFUSED, BaostockErrorCode.CONNECT_FAIL, BaostockErrorCode.CONNECT_TIMEOUT}:
        logger.error("连接被拒绝, 请检查网络设置")
        return False

    if BaostockErrorCode.SUCCESS != lg.error_code:
        logger.error(f"Baostock 登录失败: {lg.error_msg}")
        return False

    logger.info("Baostock 登录成功。")
    return True


def main():
    # Count project code lines
    # count_project_code()

    # 1. 建立与本地数据库的连接
    conn = create_database_and_tables()

    # 2. 登录 Baostock 服务
    if not login_baostock():
        return

    start_year = 2025
    end_year = 2027
    stock_codes = get_csi300_stock_codes(conn)  # 从数据库获取沪深300成分股股票代码
    params = DownloadParameters(start_year=start_year, end_year=end_year, stock_codes=stock_codes)

    try:
        #download_basic_data(conn, params)
        download_stock_data(conn,params)
        #run_backtest(conn)

        # 3. 运行看涨策略回测
        run_bullish_strategies_backtest(conn)
        #main_filter(conn)

    except Exception as e:
        # 捕获主流程中的任何异常，并记录详细错误信息
        logger.error(f"主程序执行出错: {e}", exc_info=True)
    finally:
        # 程序结束前，确保关闭数据库连接和 Baostock 登录会话
        conn.close()
        bs.logout()
        logger.info("已断开数据库连接并退出 Baostock。")

def run_backtest(db_conn, stock_code="000001.SZ", start_date="2020-01-01", end_date="2025-12-31", initial_cash=1000000):

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
                "stock_code": stock_code,
                "start_date": start_date,
                "end_date": end_date
            },
            "initial_cash": initial_cash
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
    persist_backtest_results(
        db_conn,
        stock_code=stock_code,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        results=results,
        analysis=analysis,
        run_name=f"factor_{stock_code}_{start_date}_{end_date}"
    )


def run_bullish_strategies_backtest(db_conn, stock_code="000001.SZ", start_date="2020-01-01", end_date="2026-5-21", initial_cash=1000000):
    """
    运行4个次日看涨策略的回测

    Args:
        db_conn: 数据库连接对象
        stock_code: 回测股票代码，默认 "000001.SZ"
        start_date: 回测开始日期，默认 "2020-01-01"
        end_date: 回测结束日期，默认 "2026-5-21"
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
                    "risk_per_trade": 1.0,  # 全仓模式（单股票回测）
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
                    "risk_per_trade": 1.0,  # 全仓模式（单股票回测）
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
                    "risk_per_trade": 1.0,  # 全仓模式（单股票回测）
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
                    "risk_per_trade": 1.0,  # 全仓模式（单股票回测）
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
    persist_backtest_results(
        db_conn,
        stock_code=stock_code,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        results=results,
        analysis=analysis,
        run_name=f"bullish_{stock_code}_{start_date}_{end_date}"
    )
    
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


def parse_stock_codes(stock_codes_arg):
    if not stock_codes_arg:
        return None
    return [code.strip() for code in stock_codes_arg.split(",") if code.strip()]


def parse_kline_periods(period_args):
    if not period_args:
        return None

    periods = []
    supported = {period.value: period for period in KLinePeriod}
    for value in period_args:
        if value not in supported:
            raise ValueError(f"不支持的K线周期: {value}，支持值: {', '.join(sorted(supported))}")
        periods.append(supported[value])
    return periods


def build_download_params(args, conn=None):
    stock_codes = parse_stock_codes(getattr(args, "stock_codes", None))

    if stock_codes is None and getattr(args, "stock_source", None) == "csi300" and conn is not None:
        stock_codes = get_csi300_stock_codes(conn)
        if not stock_codes:
            logger.warning("沪深300股票池为空，将使用 stock_fixed_seq 表作为下载股票池")
            stock_codes = None

    return DownloadParameters(
        start_year=args.start_year,
        end_year=args.end_year,
        stock_codes=stock_codes,
        kline_period_list=parse_kline_periods(getattr(args, "kline_period", None))
    )


def run_download_tasks(conn, params, tasks):
    if "all" in tasks:
        tasks = ["daily", "profit", "balance", "cash-flow", "adj-factor", "xrxd", "kline", "industry"]

    task_handlers = {
        "daily": start_new_daily_download,
        "profit": start_new_profit_download,
        "balance": start_new_balance_download,
        "cash-flow": start_new_cash_flow_download,
        "adj-factor": start_new_adj_factor_download,
        "xrxd": start_new_xrxd_download,
        "kline": start_new_kline_download,
        "industry": start_new_industry_download,
    }

    for task in tasks:
        logger.info(f"开始执行下载任务: {task}")
        task_handlers[task](conn, params)
        logger.info(f"下载任务完成: {task}")


def add_common_download_args(parser):
    parser.add_argument("--start-year", type=int, default=2025, help="开始年份，包含该年")
    parser.add_argument("--end-year", type=int, default=2027, help="结束年份，不包含该年")
    parser.add_argument(
        "--stock-codes",
        default=None,
        help="逗号分隔的股票代码列表，例如 000001.SZ,600000.SH；为空时按 --stock-source 获取"
    )
    parser.add_argument(
        "--stock-source",
        choices=["csi300", "fixed-seq"],
        default="csi300",
        help="未显式指定 --stock-codes 时的股票池来源"
    )
    parser.add_argument(
        "--kline-period",
        action="append",
        choices=[period.value for period in KLinePeriod],
        help="K线周期，可重复传入，例如 --kline-period 5m --kline-period 1d"
    )


def create_arg_parser():
    parser = argparse.ArgumentParser(description="Campsis A股量化数据与回测命令行入口")
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("init-db", help="只初始化 MySQL 数据库和表结构")

    basic_parser = subparsers.add_parser("download-basic", help="下载沪深300、交易日历和股票基础信息")
    add_common_download_args(basic_parser)

    data_parser = subparsers.add_parser("download-data", help="按任务下载行情/财务/行业等数据")
    add_common_download_args(data_parser)
    data_parser.add_argument(
        "--task",
        action="append",
        choices=["daily", "profit", "balance", "cash-flow", "adj-factor", "xrxd", "kline", "industry", "all"],
        default=None,
        help="下载任务，可重复传入；默认执行 daily 和 profit"
    )

    backtest_parser = subparsers.add_parser("backtest", help="运行回测")
    backtest_parser.add_argument("--kind", choices=["factor", "bullish"], default="bullish")
    backtest_parser.add_argument("--stock-code", default="000001.SZ")
    backtest_parser.add_argument("--start-date", default="2020-01-01")
    backtest_parser.add_argument("--end-date", default="2026-05-21")
    backtest_parser.add_argument("--initial-cash", type=float, default=1000000)

    filter_parser = subparsers.add_parser("filter", help="运行次日看涨策略筛选")
    filter_parser.add_argument(
        "--strategy",
        action="append",
        choices=["box_breakout", "bottom_reverse", "trend_pullback", "multi_indicator_resonance"],
        default=None,
        help="筛选策略，可重复传入；默认运行全部"
    )

    subparsers.add_parser("full", help="运行原 main() 全流程")
    return parser


def cli_main(argv=None):
    parser = create_arg_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "full":
        main()
        return 0

    conn = None
    baostock_logged_in = False
    try:
        conn = create_database_and_tables()

        if args.command == "init-db":
            logger.info("数据库和表结构初始化完成")
            return 0

        if args.command in {"download-basic", "download-data"}:
            if not login_baostock():
                return 1
            baostock_logged_in = True

        if args.command == "download-basic":
            params = build_download_params(args, conn)
            download_basic_data(conn, params)
            return 0

        if args.command == "download-data":
            params = build_download_params(args, conn)
            run_download_tasks(conn, params, args.task or ["daily", "profit"])
            return 0

        if args.command == "backtest":
            if args.kind == "factor":
                run_backtest(
                    conn,
                    stock_code=args.stock_code,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    initial_cash=args.initial_cash
                )
            else:
                run_bullish_strategies_backtest(
                    conn,
                    stock_code=args.stock_code,
                    start_date=args.start_date,
                    end_date=args.end_date,
                    initial_cash=args.initial_cash
                )
            return 0

        if args.command == "filter":
            main_filter(conn, strategy_list=args.strategy or [
                "box_breakout",
                "bottom_reverse",
                "trend_pullback",
                "multi_indicator_resonance"
            ])
            return 0

        parser.error(f"未知命令: {args.command}")
        return 2

    except Exception as e:
        logger.error(f"命令执行失败: {e}", exc_info=True)
        return 1
    finally:
        if conn:
            conn.close()
        if baostock_logged_in:
            bs.logout()
            logger.info("已退出 Baostock。")


# 程序入口点
if __name__ == '__main__':
    sys.exit(cli_main())
