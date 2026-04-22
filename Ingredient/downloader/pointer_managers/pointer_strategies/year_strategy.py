# year_strategy.py
# 年份指针策略，适用于按年份迭代的下载器

from ...core.abs_block_pointer_strategy import BlockPointerStrategy
from typing import Optional, Tuple
from KitchenBase.block_pointer import BlockPointer, BlockPointerFactory

class YearStrategy(BlockPointerStrategy):
    """
    年份指针策略，适用于按年份迭代的下载器

    迭代规则：
    1. 按年份顺序递增
    2. 达到结束年份时返回 None
    """

    def get_first_blk_pointer(self, start_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个年份的指针

        Args:
            start_year: 开始年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 年份指针
        """
        return BlockPointerFactory.create_year(start_year)

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
        year = current_pointer.get_value('year')
        next_year = year + 1
        if next_year >= end_year:
            return None
        return BlockPointerFactory.create_year(next_year)

    def get_pointer_fields(self) -> Tuple:
        """
        获取指针字段

        Returns:
            Tuple: 指针字段元组
        """
        return ('year',)

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
        if not pointer:
            return False

        year = pointer.get_value('year')
        if not isinstance(year, int) or year < start_year or year >= end_year:
            return False

        return True

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
        if not current_pointer:
            return 0

        current_year = current_pointer.get_value('year')
        return current_year - start_year