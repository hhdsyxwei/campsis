# abs_block_pointer_strategy.py
# 区块指针策略抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Tuple, Dict, Any
from KitchenBase.block_pointer import BlockPointer

class BlockPointerStrategy(ABC):
    """
    区块指针策略抽象基类，定义获取下一个区块指针的算法

    职责：
    1. 定义获取第一个区块指针的接口
    2. 定义获取下一个区块指针的接口
    3. 提供指针字段信息
    4. 提供指针验证功能

    注意：
    - db_conn 不是所有子类的依赖，因此不在基类中定义
    - 需要 db_conn 的子类应在自己的 __init__ 中接收
    """

    @abstractmethod
    def get_first_blk_pointer(self, start_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个区块指针

        Args:
            start_year: 开始年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 第一个区块的指针
        """
        pass

    @abstractmethod
    def get_next_blk_pointer(self, current_pointer: BlockPointer, start_year: int, end_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个区块指针

        Args:
            current_pointer: 当前区块指针
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 下一个区块的指针
        """
        pass

    @abstractmethod
    def get_pointer_fields(self) -> Tuple:
        """
        获取指针字段

        Returns:
            Tuple: 指针字段元组
        """
        pass

    @abstractmethod
    def get_completed_block_count(self, start_year: int, end_year: int, current_pointer: BlockPointer) -> int:
        """
        计算已完成的区块数量

        Args:
            start_year: 开始年份
            end_year: 结束年份
            current_pointer: 当前区块指针

        Returns:
            int: 已完成的区块数量
        """
        pass

    def is_valid_pointer(self, pointer: BlockPointer, start_year: int, end_year: int) -> bool:
        """
        验证指针是否有效

        Args:
            pointer: 要验证的指针
            start_year: 开始年份
            end_year: 结束年份

        Returns:
            bool: 指针是否有效
        """
        return True