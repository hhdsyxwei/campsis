# download_enums.py
from enum import Enum

class DlTaskType(Enum):
    """下载任务类型枚举"""
    KLINE = "kline"  # K线数据
    XRXD = "xrxd"  # 分红送配数据
    ADJUSTMENT_FACTOR = "adjustment_factor"  # 复权因子
    STOCK_BASIC = "stock_basic"  # 股票基本信息
    TRADE_DATE = "trade_date"  # 交易日数据


class DlTaskStatus(Enum):
    """
    下载任务状态枚举
    """
    NOT_STARTED = "not_started"  # 未开始
    IN_PROGRESS = "in_progress"  # 正在进行中
    COMPLETED = "completed"  # 已下载完成


class DlBlockStatus(Enum):
    """
    区块状态枚举，适用于所有下载器的区块状态
    """
    COMPLETED = "completed"  # 已完成
    NOT_COMPLETED = "not_completed"  # 未完成
    SKIPPED = "skipped"  # 跳过（未上市或已退市）
