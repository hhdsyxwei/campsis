# config.py
# 下载器配置

from KitchenBase.download_enums import DlTaskType, PointerField
from KitchenBase.stock_enums import KLinePeriod

class KLineConfig:
    DEFAULT_TIME_FRAMES = [
        KLinePeriod.MIN_5
    ]

# 下载股票池类型配置

# 下载区块对应字段列表配置
class DownloadBlockConfig:
    """下载配置"""
    # 下载类型与区块字段列表的映射
    TASK_TYPE_TO_POINTER_FIELDS = {
        DlTaskType.KLINE: (
            PointerField.STOCK_CODE,
            PointerField.TIME_FRAME,
            PointerField.QUARTER
        ),
        DlTaskType.DAILY: (
            PointerField.STOCK_CODE,
            PointerField.YEAR
        ),
        DlTaskType.ADJ_FACTOR: (
            PointerField.YEAR,
            PointerField.STOCK_CODE
        ),
        DlTaskType.XRXD: (
            PointerField.YEAR,
            PointerField.STOCK_CODE
        ),
        DlTaskType.INDUSTRY: (
            PointerField.YEAR, #必须加逗号，否则括号不会识别成元组
        ),
        DlTaskType.COMPANY_PROFIT: (
            PointerField.QUARTER,
            PointerField.STOCK_CODE
        ),
        DlTaskType.COMPANY_BALANCE: (
            PointerField.QUARTER,
            PointerField.STOCK_CODE
        ),
        DlTaskType.COMPANY_CASH_FLOW: (
            PointerField.QUARTER,
            PointerField.STOCK_CODE
        )
    }
    
    @classmethod
    def get_pointer_fields(cls, task_type: DlTaskType) -> tuple:
        """
        获取指定下载类型的区块字段列表
        
        Args:
            task_type: 下载类型
            
        Returns:
            tuple: 区块字段列表
        """
        return cls.TASK_TYPE_TO_POINTER_FIELDS.get(task_type, ())