# general_pointer_manager.py
# 通用指针管理器实现

from .abs_pointer_manager import PointerManager
from typing import Optional, Tuple, Dict, Any

class GeneralPointerManager(PointerManager):
    """
    通用指针管理器实现，提供基础指针管理功能
    """
    
    def __init__(self, db_conn):
        """
        初始化通用指针管理器
        
        Args:
            db_conn: 数据库连接对象
        """
        self.db_conn = db_conn
        self.dl_pointer = None
        self.pointer_fields = ()
    
    def get_dl_pointer(self) -> Optional[Tuple]:
        """
        获取当前下载指针
        
        Returns:
            Optional[Tuple]: 当前下载区块的标识
        """
        # 通用实现，子类需要根据具体情况重写
        return self.dl_pointer
    
    def set_dl_pointer(self, block_identifier: Tuple):
        """
        设置当前下载指针
        
        Args:
            block_identifier: 区块标识元组
        """
        # 通用实现，子类需要根据具体情况重写
        self.dl_pointer = block_identifier
    
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
        # 通用实现，子类需要根据具体情况重写
        return dl_pointer is not None
    
    def clear_dl_pointer(self):
        """
        清空下载指针
        """
        # 通用实现，子类需要根据具体情况重写
        self.dl_pointer = None
    
    def get_first_blk_pointer(self, start_year: int, end_year: int) -> Optional[Tuple]:
        """
        获取第一个待下载区块的指针
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            Optional[Tuple]: 第一个区块的标识
        """
        return self.get_next_blk_pointer(start_year, end_year, None)
    
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
        # 通用实现，子类需要根据具体情况重写
        return None
    
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
        # 通用实现，子类需要根据具体情况重写
        return 0
    
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
        # 无区块状态表时无法统计跳过的区块数，返回0
        return 0
    
    def pointer_to_dict(self, block_identifier: Tuple) -> Dict[str, Any]:
        """
        将指针元组转换为字段到值的映射字典
        
        Args:
            block_identifier: 区块标识元组
            
        Returns:
            Dict[str, Any]: 字段到值的映射字典
        """
        if not block_identifier:
            return {}
        
        # 确保字段元组和指针元组长度一致
        if len(self.pointer_fields) != len(block_identifier):
            # 使用默认字段名
            return {f"field_{i}": value for i, value in enumerate(block_identifier)}
        
        # 构建字段到值的映射
        return dict(zip(self.pointer_fields, block_identifier))
    
    def log_pointer_info(self, block_identifier: Tuple, message: str = "当前下载指针"):
        """
        输出指针信息到日志
        
        Args:
            block_identifier: 区块标识元组
            message: 日志消息前缀
        """
        if not block_identifier:
            return
        
        pointer_dict = self.pointer_to_dict(block_identifier)
        # 构建友好的日志消息
        pointer_info = ", ".join([f"{k}={v}" for k, v in pointer_dict.items()])
        return f"{message}: {pointer_info}"