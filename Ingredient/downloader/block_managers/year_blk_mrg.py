# year_block_manager.py
# 年份区块管理器，适用于按年份划分区块的下载器

from KitchenBase.download_enums import PointerField
from KitchenBase.block_pointer import BlockPointerFactory
from KitchenBase.download_enums import DlTaskType
from .generic_block_manager import GenericBlockManager
from ...DataNest.dm_unified import UnifiedDataManager as udm

class YearBlkMgr(GenericBlockManager):
    """
    年份区块管理器，适用于按年份划分区块的下载器
    """
    
    def __init__(self, db_conn, task_type: DlTaskType):
        """
        初始化年份区块管理器
        
        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型枚举值
            
        """
        super().__init__(db_conn, task_type)
    
    def get_total_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        计算总区块数：结束年份 - 开始年份
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数
        """
        return end_year - start_year


