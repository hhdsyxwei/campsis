# general_block_manager.py
# 通用区块管理器实现

from .abs_block_manager import BlockManager

class GeneralBlockManager(BlockManager):
    """
    通用区块管理器实现，提供基础区块管理功能
    """
    
    def __init__(self, db_conn):
        """
        初始化通用区块管理器
        
        Args:
            db_conn: 数据库连接对象
        """
        self.db_conn = db_conn
    
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
        return 0
    
    def get_completed_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已完成区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            int: 已完成区块数
        """
        # 通用实现，子类需要根据具体情况重写
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
        # 通用实现，子类需要根据具体情况重写
        return 0