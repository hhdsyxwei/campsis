# abs_pointer_manager.py
# 指针管理器抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Tuple

class PointerManager(ABC):
    """
    指针管理器抽象基类，定义指针管理的统一接口
    """
    
    @abstractmethod
    def get_dl_pointer(self) -> Optional[Tuple]:
        """
        获取当前下载指针
        
        Returns:
            Optional[Tuple]: 当前下载区块的标识
        """
        pass
    
    @abstractmethod
    def set_dl_pointer(self, block_identifier: Tuple):
        """
        设置当前下载指针
        
        Args:
            block_identifier: 区块标识元组
        """
        pass
    
    @abstractmethod
    def is_dl_pointer_valid(self, dl_pointer: Optional[Tuple], start_year: int, end_year: int) -> bool:
        """
        判断下载指针是否合法有效
        
        Args:
            dl_pointer: 下载指针
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            bool: 指针是否有效
        """
        pass
    
    @abstractmethod
    def clear_dl_pointer(self):
        """
        清空下载指针
        """
        pass
    
    @abstractmethod
    def get_first_blk_pointer(self, start_year: int, end_year: int) -> Optional[Tuple]:
        """
        获取第一个待下载区块的指针
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            Optional[Tuple]: 第一个区块的标识
        """
        pass
    
    @abstractmethod
    def get_next_blk_pointer(self, start_year: int, end_year: int, current_block: Optional[Tuple] = None) -> Optional[Tuple]:
        """
        获取下一个待下载区块的指针
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            current_block: 当前区块标识（首次调用传None，返回第一个区块）
            
        Returns:
            Optional[Tuple]: 下一个区块的标识
        """
        pass
    
    @abstractmethod
    def get_completed_block_count(self, start_year: int, end_year: int, dl_pointer: Tuple) -> int:
        """
        基于指针获取已完成区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            dl_pointer: 当前下载指针，包含当前处理的区块信息
            
        Returns:
            int: 已完成区块数
        """
        pass
    
    @abstractmethod
    def get_skipped_block_count(self, start_year: int, end_year: int, dl_pointer: Tuple) -> int:
        """
        基于指针获取已跳过区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            dl_pointer: 当前下载指针，包含当前处理的区块信息
            
        Returns:
            int: 已跳过区块数
        """
        pass