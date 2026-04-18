# abs_block_manager.py
# 区块管理器抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Tuple

class BlockManager(ABC):
    """
    区块管理器抽象基类，定义区块管理的统一接口
    """
    
    @abstractmethod
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
        pass
    
    @abstractmethod
    def get_completed_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已完成区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            int: 已完成区块数
        """
        pass
    
    @abstractmethod
    def get_skipped_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已跳过区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            int: 已跳过区块数
        """
        pass