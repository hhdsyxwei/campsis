# abs_pointer_manager.py
# 指针管理器抽象基类

from KitchenBase.block_pointer import BlockPointer
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from KitchenBase.download_enums import PointerField
from KitchenBase import DownloadParameters

class PointerManager(ABC):
    """
    指针管理器抽象基类，定义指针管理的统一接口
    """
    
    @abstractmethod
    def get_dl_pointer(self) -> Optional[BlockPointer]:
        """
        获取当前下载指针
        
        Returns:
            Optional[BlockPointer]: 当前下载区块指针
        """
        pass
    
    @abstractmethod
    def set_dl_pointer(self, block_identifier: BlockPointer):
        """
        设置当前下载指针
        
        Args:
            block_identifier: 区块标识元组
        """
        pass
    
    @abstractmethod
    def is_dl_pointer_valid(self, dl_pointer: Optional[BlockPointer], params: DownloadParameters) -> bool:
        """
        判断下载指针是否合法有效
        
        Args:
            dl_pointer: 下载指针
            params: 下载参数
            
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
    def get_first_blk_pointer(self, params: DownloadParameters) -> BlockPointer:
        """
        获取第一个待下载区块的指针
        
        Args:
            params: 下载参数
            
        Returns:
            BlockPointer: 第一个区块指针
        """
        pass
    
    @abstractmethod
    def get_next_blk_pointer(self, params: DownloadParameters, current_block: Optional[BlockPointer] = None) -> Optional[BlockPointer]:
        """
        获取下一个待下载区块的指针
        
        Args:
            params: 下载参数
            current_block: 当前区块指针（首次调用传None，返回第一个区块）
            
        Returns:
            Optional[BlockPointer]: 下一个区块指针
        """
        pass
    
    @abstractmethod
    def get_completed_block_count(self, params: DownloadParameters, dl_pointer: BlockPointer) -> int:
        """
        基于指针获取已完成区块数
        
        Args:
            params: 下载参数
            dl_pointer: 当前下载指针，包含当前处理的区块信息
            
        Returns:
            int: 已完成区块数
        """
        pass
    
    @abstractmethod
    def get_skipped_block_count(self, params: DownloadParameters, dl_pointer: BlockPointer) -> int:
        """
        基于指针获取已跳过区块数
        
        Args:
            params: 下载参数
            dl_pointer: 当前下载指针，包含当前处理的区块信息
            
        Returns:
            int: 已跳过区块数
        """
        pass