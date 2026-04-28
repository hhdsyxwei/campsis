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
    
    def get_total_block_count(self, params, **kwargs) -> int:
        """
        计算总区块数：结束年份 - 开始年份
        
        Args:
            params: 下载参数（包含 start_year 和 end_year）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数
        """
        return params.end_year - params.start_year


