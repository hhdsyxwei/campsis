# daily_data_downloader.py
from datetime import datetime, timedelta
import pymysql
from KitchenBase.baostock_wrapper import query_history_k_data_plus
import time
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest import DailyDataManager, get_nearest_trade_date_before # 导入新的管理器
from Ingredient.DataNest import UnifiedDataManager as dm_unified
from Ingredient.DataNest.dm_stock_seq import StockFixedSeqManager

logger = get_logger(__name__)

def download_daily_data(conn, ts_code: str, start_date: str, end_date: str):
    """
    下载单只股票在指定时间范围内的日线数据，并存入 stock_daily 表。
    """

    # 执行流程
    valid, bs_code = _validate_parameters(ts_code, start_date, end_date)
    if not valid:
        return
    
    rs = _download_raw_data(bs_code, start_date, end_date)
    if rs is None:
        return
    
    df = _clean_data(rs)
    if df is None:
        return
    
    _save_data(conn, ts_code, df)

def _validate_parameters(ts_code: str, start_date: str, end_date: str):
    """
    验证参数有效性
    """
    # 验证股票代码格式
    parts = ts_code.split('.')
    if len(parts) != 2:
        logger.warning(f"股票代码格式错误: {ts_code}")
        return False, None
    
    # 验证日期格式
    try:
        datetime.strptime(start_date, '%Y-%m-%d')
        datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        logger.warning(f"日期格式错误: start_date={start_date}, end_date={end_date}")
        return False, None
    
    # 转换股票代码为 Baostock 格式
    symbol, market = parts
    market_map = {'SH': 'sh', 'SZ': 'sz'}
    bs_code = f"{market_map.get(market.upper(), market)}.{symbol}"
    
    return True, bs_code

def _download_raw_data(bs_code, start_date: str, end_date: str):
    """
    从 Baostock API 下载原始数据
    """
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
        logger.warning(f"获取 {bs_code} 数据超时或发生错误，返回结果为 None。")
        return None
    logger.info(f"查询 {bs_code} 日线数据结果: {rs.error_code} - {rs.error_msg}")
    if rs.error_code != '0':
        logger.warning(f"获取 {bs_code} 数据失败: {rs.error_msg}")
        return None
    
    return rs

def _clean_data(bs_rs):
    """
    清洗数据并转换为 DataFrame
    """
    import pandas as pd
    
    data_list = []
    while bs_rs.next():
        data_list.append(bs_rs.get_row_data())
    
    if not data_list:
        logger.info(f"股票在指定日期范围内无数据")
        return None
    
    #logger.warning(f"第1行数据内容：{data_list[0]}")
    #logger.warning(f"第2行数据内容：{data_list[1]}")
    
    # 转换为 DataFrame
    df = pd.DataFrame(data_list, columns=bs_rs.fields)
    
    # 数据清洗和类型转换
    df['date'] = pd.to_datetime(df['date'])
    numeric_columns = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg', 'peTTM', 'pbMRQ', 'psTTM', 'pcfNcfTtm']
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # 计算前收盘价
    df['pre_close'] = df['close'].shift(1)

    # 处理 NaN 值
    # 将所有数值列的 NaN 转换为 None
    for col in numeric_columns + ['pre_close']:
        if col in df.columns:
            df[col] = df[col].where(pd.notna(df[col]), None)

    return df

def _save_data(conn, ts_code: str, df):
    """
    保存数据到数据库
    """
    manager = DailyDataManager(conn)
    # 传递股票代码和 DataFrame 给 save_daily_data 方法
    success = manager.save_daily_data(ts_code, df)
    if not success:
        logger.warning(f"保存 {ts_code} 的数据到数据库失败。")
    return success


def download_all_stocks_daily_data(conn, start_date, end_date):
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
    seq_manager = StockFixedSeqManager(conn)

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

    # 获取股票总数
    total = seq_manager.count_stocks()
    logger.info(f"开始下载日线数据，结束日期: {end_date}，共 {total} 只股票。")

    count = 0  # 计数器，用于显示进度
    current_stock = None

    # 通过单层循环体下载所有日线数据，每次循环下载一只股票
    while True:
        # 获取下一只股票
        ts_code = seq_manager.get_next_stock(current_stock)
        if ts_code is None:
            # 所有股票处理完毕
            break

        count += 1
        # 每处理 50 只股票，打印一次进度日志
        if count % 50 == 0:
            logger.info(f"进度: {count}/{total}，当前处理: {ts_code}")

        # 直接使用用户指定的固定日期范围进行下载
        # 不进行日期范围计算和存在性检查，以保证下载完整数据
        download_daily_data(conn, ts_code, start_date, end_date)

        # 更新当前股票为下一只
        current_stock = ts_code

        # 可选：为避免触发 API 限流，可以在每次请求后短暂休眠
        time.sleep(0.5)

    logger.info("所有股票数据下载完成！")