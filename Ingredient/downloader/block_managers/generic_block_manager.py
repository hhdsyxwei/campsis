# general_block_manager.py
# 通用区块管理器实现

from KitchenBase.download_enums import DlTaskType
from typing import Tuple
from KitchenBase import DownloadParameters
from ..core.abs_block_manager import BlockManager
from ..core.abs_collection_manager import StockCollectionManager
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlBlockStatus
from Ingredient.DataNest import GenericBlockStatusDM
from Ingredient.config import DownloadBlockConfig



class GenericBlockManager(BlockManager):
    """
    不支持直接实例化，必须通过派生类创建实例。
    通用区块管理器依然是抽象类。只实现通用的区块管理功能，不通用的由派生类实现。
    注意区块总数的算法无法在通用区块管理器中实现，需要在派生类中实现。
    因为不同的任务类型和指针字段，需要不同的算法来计算区块总数。
    职责：
    1. 管理区块的存储和获取
    2. 获取已完成区块数
    3. 获取已跳过区块数
    4. 查询区块状态
    5. 更新区块状态
    """
    
    def __init__(self, db_conn, task_type: DlTaskType, collection_manager: StockCollectionManager):
        """
        初始化通用区块管理器
        
        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型枚举值
            collection_manager: 股票集合管理器，必须提供
        """
        self.db_conn = db_conn
        self.task_type = task_type
        self.collection_manager = collection_manager
        self.logger = get_logger(__name__)
        # 创建状态管理器
        self.status_dm = GenericBlockStatusDM(db_conn) if db_conn else None
    
    @property
    def collection_manager(self):
        """股票集合管理器（只读属性）"""
        return self._collection_manager
    
    @collection_manager.setter
    def collection_manager(self, value):
        """设置股票集合管理器（仅在 __init__ 中调用）"""
        # 检查是否已经设置过（防止后续修改）
        if hasattr(self, '_collection_manager') and self._collection_manager is not None:
            raise AttributeError("collection_manager 是只读属性，不能被修改")
        self._collection_manager = value
    
    def get_completed_block_count(self, params: DownloadParameters) -> int:
        """
        获取已完成区块数
        
        Args:
            params: 下载参数
            
        Returns:
            int: 已完成区块数
        """
        if not self.status_dm or not self.task_type:
            return 0
        try:
            pointer_fields = DownloadBlockConfig.get_pointer_fields(self.task_type)
            return self.status_dm.get_block_count(
                task_type=self.task_type, 
                year_range=(params.start_year, params.end_year), 
                pointer_fields=pointer_fields,
                status=[DlBlockStatus.COMPLETED],
                stock_table=self.collection_manager.get_stock_list()
            )
        except Exception as e:
            self.logger.error(f"获取已完成区块数失败: {str(e)}")
            return 0
    
    def get_skipped_block_count(self, params: DownloadParameters) -> int:
        """
        获取已跳过区块数
        
        Args:
            params: 下载参数
            
        Returns:
            int: 已跳过区块数
        """
        if not self.status_dm or not self.task_type:
            return 0
        try:
            pointer_fields = DownloadBlockConfig.get_pointer_fields(self.task_type)
            return self.status_dm.get_block_count(
                task_type=self.task_type, 
                year_range=(params.start_year, params.end_year), 
                pointer_fields=pointer_fields,
                status=[DlBlockStatus.SKIPPED],
                stock_table=self.collection_manager.get_stock_list()
            )
        except Exception as e:
            self.logger.error(f"获取已跳过区块数失败: {str(e)}")
            return 0
    
    def get_block_status(self, *block_identifier) -> DlBlockStatus:
        """
        获取区块状态
        
        Args:
            *block_identifier: 区块标识
            
        Returns:
            DlBlockStatus: 区块状态
        """
        if not self.status_dm or not self.task_type:
            return DlBlockStatus.NOT_COMPLETED
        try:
            # 解析block_identifier，格式为 (block_key_1, block_key_2, block_key_3)
            block_key_1 = str(block_identifier[0]) if len(block_identifier) > 0 else ""
            block_key_2 = str(block_identifier[1]) if len(block_identifier) > 1 else ""
            block_key_3 = str(block_identifier[2]) if len(block_identifier) > 2 else ""
            
            status = self.status_dm.get_block_status(
                block_key_1=block_key_1,
                task_type=self.task_type,
                block_key_2=block_key_2,
                block_key_3=block_key_3
            )
            return status
        except Exception as e:
            self.logger.error(f"获取区块状态失败: {str(e)}")
            return DlBlockStatus.NOT_COMPLETED
    
    def update_block_status(self, block_pointer, status: DlBlockStatus, **kwargs):
        """
        更新区块状态

        Args:
            block_pointer: 区块指针
            status: 区块状态
            **kwargs: 额外参数
        """
        if not self.status_dm or not self.task_type:
            return
        try:
            # 解析block_pointer
            if hasattr(block_pointer, 'to_tuple'):
                # 如果是 BlockPointer 对象
                values = block_pointer.to_tuple()
            else:
                # 兼容旧的 tuple 格式
                values = block_pointer
            
            # 解析为 block_key
            block_key_1 = str(values[0]) if len(values) > 0 else ""
            block_key_2 = str(values[1]) if len(values) > 1 else ""
            block_key_3 = str(values[2]) if len(values) > 2 else ""
            
            self.status_dm.update_block_status(
                block_key_1=block_key_1,
                task_type=self.task_type,
                status=status,
                block_key_2=block_key_2,
                block_key_3=block_key_3,
                **kwargs
            )
        except Exception as e:
            self.logger.error(f"更新区块状态失败: {str(e)}")

    def get_stock_count(self) -> int:
        """
        获取股票数量
        
        Returns:
            int: 股票数量
        """
        try:
            return self.collection_manager.get_stock_count()
        except Exception as e:
            self.logger.error(f"获取股票数量异常：{e}", exc_info=True)
            return 5000