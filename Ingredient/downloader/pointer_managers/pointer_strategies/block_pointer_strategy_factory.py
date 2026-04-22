# block_pointer_strategy_factory.py
# 区块指针策略工厂，用于创建不同类型的策略

from .year_stock_strategy import YearStockStrategy
from .quarter_stock_period_strategy import QuarterStockPeriodStrategy
from .quarter_stock_strategy import QuarterStockStrategy
from .year_strategy import YearStrategy
from ...core.abs_block_pointer_strategy import BlockPointerStrategy
from KitchenBase.block_pointer import BlockPointer
from typing import Tuple, Optional
from KitchenBase.download_enums import PointerField

class BlockPointerStrategyFactory:
    """
    区块指针策略工厂，用于创建不同类型的策略

    工厂根据指针字段的组合自动选择合适的策略实现
    """

    @staticmethod
    def create_strategy(pointer_fields: Tuple[PointerField, ...], db_conn=None, time_frame=None) -> BlockPointerStrategy:
        """
        根据指针字段创建相应的策略

        Args:
            pointer_fields: 指针字段枚举元组
            db_conn: 数据库连接对象
            time_frame: 时间周期（仅 QuarterStockPeriodStrategy 需要）

        Returns:
            BlockPointerStrategy: 对应的策略实例
        """
        field_set = set(pointer_fields)

        if field_set == {PointerField.YEAR, PointerField.STOCK_CODE}:
            return YearStockStrategy(db_conn)
        elif field_set == {PointerField.QUARTER, PointerField.STOCK_CODE, PointerField.TIME_FRAME} and time_frame:
            return QuarterStockPeriodStrategy(db_conn, time_frame)
        elif field_set == {PointerField.QUARTER, PointerField.STOCK_CODE}:
            return QuarterStockStrategy(db_conn)
        elif field_set == {PointerField.YEAR}:
            return YearStrategy()
        else:
            return DefaultBlockPointerStrategy(pointer_fields, db_conn)


class DefaultBlockPointerStrategy(BlockPointerStrategy):
    """
    默认区块指针策略，适用于其他字段组合

    提供基本的实现，子类可以根据需要重写
    """

    def __init__(self, pointer_fields: Tuple[PointerField, ...], db_conn=None):
        """
        初始化默认策略

        Args:
            pointer_fields: 指针字段枚举元组
            db_conn: 数据库连接对象
        """
        self._pointer_fields = pointer_fields
        self.db_conn = db_conn

    def get_first_blk_pointer(self, start_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个区块指针

        简单实现，返回 None

        Args:
            start_year: 开始年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 第一个区块的指针
        """
        return None

    def get_next_blk_pointer(self, current_pointer: BlockPointer, start_year: int, end_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个区块指针

        简单实现，返回 None

        Args:
            current_pointer: 当前区块指针
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 下一个区块的指针
        """
        return None

    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return self._pointer_fields

    def is_valid_pointer(self, pointer: BlockPointer, start_year: int, end_year: int) -> bool:
        """
        验证指针是否有效

        简单实现，只验证指针长度

        Args:
            pointer: 要验证的指针
            start_year: 开始年份
            end_year: 结束年份

        Returns:
            bool: 指针是否有效
        """
        if not pointer:
            return False

        return len(pointer) == len(self._pointer_fields)

    def get_completed_block_count(self, start_year: int, end_year: int, current_pointer: BlockPointer) -> int:
        """
        计算已完成的区块数量

        默认实现，返回 0

        Args:
            start_year: 开始年份
            end_year: 结束年份
            current_pointer: 当前区块指针

        Returns:
            int: 已完成的区块数量
        """
        return 0