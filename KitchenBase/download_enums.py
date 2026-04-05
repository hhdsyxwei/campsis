# download_enums.py
from enum import Enum

class DlTaskType(Enum):
    """下载任务类型枚举"""
    KLINE = "kline"  # K线数据
    XRXD = "xrxd"  # 分红送配数据
    ADJUSTMENT_FACTOR = "adjustment_factor"  # 复权因子
    STOCK_BASIC = "stock_basic"  # 股票基本信息
    TRADE_DATE = "trade_date"  # 交易日数据
