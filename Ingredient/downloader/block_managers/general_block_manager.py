# general_block_manager.py
# 通用区块管理器实现

from Ingredient.downloader.block_managers.block_strategies.block_strategy_factory import BlockStrategyFactory
from ..core.abs_block_manager import BlockManager
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlBlockStatus
from Ingredient.DataNest import GenericBlockStatusDM


class GeneralBlockManager(BlockManager):
    """
    通用区块管理器实现，提供基础区块管理功能
    """
    
    def __init__(self, db_conn, task_type=None, pointer_fields=()):
        """
        初始化通用区块管理器
        
        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型枚举值
            pointer_fields: 指针字段元组
        """
        self.db_conn = db_conn
        self.task_type = task_type
        self.logger = get_logger(__name__)
        # 创建策略实例
        self.strategy = BlockStrategyFactory.create_strategy(
            pointer_fields, db_conn=db_conn
        )
        # 创建状态管理器
        self.status_dm = GenericBlockStatusDM(db_conn) if db_conn else None
    
    def get_total_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取总区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数
        """
        # 通用实现，子类需要根据具体情况重写
        return self.strategy.get_total_block_count(start_year, end_year, **kwargs)
    
    def get_completed_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已完成区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            int: 已完成区块数
        """
        if not self.status_dm or not self.task_type:
            return 0
        try:
            return self.status_dm.get_block_count(
                task_type=self.task_type, 
                start_year=start_year, 
                end_year=end_year, 
                status=[DlBlockStatus.COMPLETED]
            )
        except Exception as e:
            self.logger.error(f"获取已完成区块数失败: {str(e)}")
            return 0
    
    def get_skipped_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已跳过区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            int: 已跳过区块数
        """
        if not self.status_dm or not self.task_type:
            return 0
        try:
            return self.status_dm.get_block_count(
                task_type=self.task_type, 
                start_year=start_year, 
                end_year=end_year, 
                status=[DlBlockStatus.SKIPPED]
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