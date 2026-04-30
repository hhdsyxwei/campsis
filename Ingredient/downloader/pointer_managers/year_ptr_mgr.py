# year_ptr_mgr.py
# 按年份划分的指针管理器

from Ingredient.config import DownloadBlockConfig
from .generic_pointer_manager import GenericPointerManager
from KitchenBase import DownloadParameters
from KitchenBase.block_pointer import BlockPointer
from KitchenBase.download_enums import PointerField
from typing import Optional
from Ingredient.config import DlTaskType
from KitchenBase.logger_config import get_logger
from Ingredient.downloader.core.abs_collection_manager import StockCollectionManager

class YearPtrMgr(GenericPointerManager):
    """
    按年份划分的指针管理器
    
    职责：
    1. 管理按年份划分的下载指针
    2. 实现年份的迭代逻辑
    3. 提供指针验证和转换功能
    """
    
    def __init__(self, db_conn, task_type: DlTaskType, 
                 collection_manager: StockCollectionManager, 
                 global_manager=None,
                 time_frame=None):
        """
        初始化年份指针管理器
        
        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型（可选）
            collection_manager: 股票集合管理器
            global_manager: GlobalDlCtrlBlockManager 实例（可选，用于依赖注入）
            time_frame: 时间周期（可选）
        """
        super().__init__(db_conn, task_type, collection_manager, global_manager, time_frame)
        self.logger = get_logger(__name__)

    def get_next_blk_pointer(self, params: DownloadParameters, current_block: Optional[BlockPointer] = None, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个待下载区块的指针
        
        按年份顺序迭代：
        1. 从当前年份递增到结束年份
        2. 超出年份范围返回 None
        
        Args:
            params: 下载参数
            current_block: 当前区块指针
            **kwargs: 额外参数
        
        Returns:
            Optional[BlockPointer]: 下一个区块的指针
        """
        pointer_fields = DownloadBlockConfig.get_pointer_fields(self.task_type)
        if current_block is None:
            # 创建第一个年份的指针
            pointer_values = (params.start_year,)
            return BlockPointer(pointer_fields, pointer_values)
        
        try:
            # 解析当前区块指针中的年份值
            current_year = current_block.get_value(PointerField.YEAR)
            
            # 计算下一个年份
            next_year = current_year + 1
            
            # 检查是否在年份范围内
            if next_year >= params.end_year:
                return None
            
            # 创建下一个区块指针
            pointer_values = (next_year,)
            return BlockPointer(pointer_fields, pointer_values)
        except Exception as e:
            self.logger.error(f"获取下一个区块指针失败: {str(e)}")
            return None
    
    def is_dl_pointer_valid(self, dl_pointer: Optional[BlockPointer], params: DownloadParameters) -> bool:
        """
        判断下载指针是否合法有效
        
        Args:
            dl_pointer: 下载指针
            params: 下载参数
        
        Returns:
            bool: 指针是否有效
        """
        if not dl_pointer:
            return False
        
        try:
            # 验证年份是否在年份范围内
            year = dl_pointer.get_value(PointerField.YEAR)
            return params.start_year <= year < params.end_year
        except Exception as e:
            self.logger.error(f"验证指针有效性失败: {str(e)}")
            return False
    
    def get_completed_block_count(self, params: DownloadParameters, dl_pointer: BlockPointer) -> int:
        """
        基于指针获取已完成区块数
        
        计算方法：
        已完成区块数 = 当前年份 - 开始年份
        
        Args:
            params: 下载参数
            dl_pointer: 当前下载指针
        
        Returns:
            int: 已完成区块数
        """
        if not dl_pointer:
            return 0
        
        try:
            # 解析当前指针
            current_year = dl_pointer.get_value(PointerField.YEAR)
            
            # 计算已完成区块数
            completed_count = current_year - params.start_year
            
            return completed_count
        except Exception as e:
            self.logger.error(f"计算已完成区块数失败: {str(e)}")
            return 0
