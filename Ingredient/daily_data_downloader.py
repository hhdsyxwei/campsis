# daily_data_downloader.py
from datetime import datetime, timedelta
import pymysql
from KitchenBase.baostock_wrapper import query_history_k_data_plus
import time
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest import DailyDataManager, get_nearest_trade_date_before # 导入新的管理器

logger = get_logger(__name__)

def download_daily_data(conn, ts_code: str, start_date: str, end_date: str):
    """
    下载单只股票在指定时间范围内的日线数据，并存入 stock_daily 表。
    """
    # 将数据库格式的股票代码 (600000.SH) 转换回 Baostock 格式 (sh.600000)
    parts = ts_code.split('.')
    if len(parts) != 2:
        logger.warning(f"股票代码格式错误: {ts_code}")
        return
    symbol, market = parts
    market_map = {'SH': 'sh', 'SZ': 'sz'}
    bs_code = f"{market_map.get(market.lower(), market)}.{symbol}"

    # 定义需要查询的日线数据字段
    fields = "date,code,open,high,low,close,volume,amount,adjustflag,turn,tradestatus,pctChg,peTTM,pbMRQ,psTTM,pcfNcfTtm,isST"
    # 调用 Baostock API 查询历史 K 线数据
    rs = query_history_k_data_plus(
        bs_code, 
        fields, 
        start_date=start_date, 
        end_date=end_date,
        frequency="d",      # 频率为日线
        adjustflag="3"      # 复权标志: 3=不复权, 1=前复权, 2=后复权
    )

    if rs is None:
        logger.warning(f"获取 {ts_code} 数据超时或发生错误，返回结果为 None。")
        return

    logger.info(f"查询 {ts_code} 日线数据结果: {rs.error_code} - {rs.error_msg}")

    if rs.error_code != '0':
        logger.warning(f"获取 {ts_code} 数据失败: {rs.error_msg}")
        return

    # 使用数据管理器来保存数据
    manager = DailyDataManager(conn)
    success = manager.save_daily_data(ts_code, rs)
    if not success:
        logger.warning(f"保存 {ts_code} 的数据到数据库失败。")


def _check_date_range_exists(dm: DailyDataManager, ts_code: str, start_date: str, end_date: str) -> bool:
    """
    检查指定股票的指定日期范围是否已存在
    """
    if start_date:
        # 如果用户指定了全局 start_date，则检查该范围是否已存在
        if dm.check_date_range_exists(ts_code, start_date, end_date):
            logger.info(f"股票 {ts_code} 在 {start_date} 到 {end_date} 的数据已存在，跳过下载。")
            return True
    return False


def _calculate_download_dates(conn, dm: DailyDataManager, ts_code: str, global_start_date: str = None, end_date: str = None) -> tuple:
    """
    计算某只股票日线数据下载所需的 start_date 和 end_date
    返回 (start_date, end_date) 元组，如果不需要下载则返回 (None, None)
    """
    # 1. 查询数据库中该股票的最新交易日期
    latest_date_in_db = dm.get_latest_tradedate_for_stock(ts_code)
    
    if latest_date_in_db:
        # 如果数据库中有记录，则从下一天开始下载
        start_date_obj = datetime.strptime(latest_date_in_db, '%Y-%m-%d')
        s_date = (start_date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
        logger.info(f"股票 {ts_code} 已存在数据，从 {s_date} 开始增量下载。")
    else:
        # 如果数据库中没有记录，且提供了全局起始日期，则使用它；否则跳过
        if global_start_date:
            s_date = global_start_date
            logger.info(f"股票 {ts_code} 无历史数据，从 {global_start_date} 开始全量下载。")
        else:
            # 使用数据管理器获取上市日期
            listing_date = dm.get_stock_listing_date(ts_code)
            if listing_date:
                s_date = listing_date
                logger.info(f"股票 {ts_code} 无历史数据，从上市日期 {s_date} 开始全量下载。")
            else:
                logger.warning(f"股票 {ts_code} 的上市日期未知，跳过下载。")
                return None, None

    # 再次检查：如果计算出的 s_date 已经大于 end_date，说明没有新数据需要下载
    if datetime.strptime(s_date, '%Y-%m-%d') > datetime.strptime(end_date, '%Y-%m-%d'):
        logger.info(f"股票 {ts_code} 已同步至最新日期，无需下载。")
        return None, None

    return s_date, end_date


def download_all_stocks_daily_data(conn, start_date=None, end_date=None):
    """
    下载所有活跃股票的日线数据。
    Args:
        conn: 数据库连接对象。
        start_date (str, optional): 全局起始日期，格式 'YYYY-MM-DD'。
                                   如果未指定，则从数据库已有数据的下一天开始。
        end_date (str, optional): 全局结束日期，格式 'YYYY-MM-DD'。
                                  如果未指定，则默认为今天。
                                  如果指定的日期不是交易日，则会调整为该日期之前的最后一个交易日。
    """
    # 初始化数据管理器
    dm = DailyDataManager(conn)

    if end_date:
        # 如果指定了 end_date，则将其调整为最近的交易日
        # 使用 download_utils 中定义的函数
        original_end_date = end_date
        end_date = get_nearest_trade_date_before(conn, end_date)
        if original_end_date != end_date:
            logger.info(f"指定的结束日期 {original_end_date} 不是交易日，已调整为最近的交易日 {end_date}。")
    else:
        # 如果未指定，则默认为今天
        end_date = datetime.now().strftime('%Y-%m-%d')

    # 使用数据管理器获取活跃股票列表
    stocks = dm.get_active_stocks()

    logger.info(f"开始下载日线数据，结束日期: {end_date}，共 {len(stocks)} 只活跃股票。")

    count = 0  # 计数器，用于显示进度
    total = len(stocks)

    # 遍历所有活跃股票，逐个下载日线数据
    for ts_code in stocks:
        # 检查指定的日期范围是否已存在
        if _check_date_range_exists(dm, ts_code, start_date, end_date):
            continue  # 直接进入下一只股票的循环

        # 计算这只股票的下载日期范围
        s_date, e_date = _calculate_download_dates(conn, dm, ts_code, start_date, end_date)
        if s_date is None or e_date is None:
            # 表示这只股票不需要下载
            continue

        count += 1
        # 每处理 50 只股票，打印一次进度日志
        if count % 50 == 0:
            logger.info(f"进度: {count}/{total}，当前处理: {ts_code}")

        # 调用函数，下载并保存这只股票的日线数据
        download_daily_data(conn, ts_code, s_date, e_date)

        # 可选：为避免触发 API 限流，可以在每次请求后短暂休眠
        time.sleep(0.5)

    logger.info("所有股票数据下载完成！")