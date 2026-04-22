# block_strategy_factory.py
# 区块策略工厂，用于创建不同类型的策略

from .quarter_stock_strategy import QuarterStockStrategy
from ...core.abs_block_strategy import BlockStrategy
from typing import Tuple, Optional
from KitchenBase.block_pointer import BlockPointer
from KitchenBase.download_enums import PointerField



class BlockStrategyFactory:
    """
    区块策略工厂，用于创建不同类型的策略

    工厂根据策略类型自动选择合适的策略实现
    """

    @staticmethod
    def create_strategy(pointer_fields: Tuple[PointerField, ...], db_conn=None, **kwargs) -> BlockStrategy:
        """
        根据区块指针策略创建相应的策略

        Args:
            pointer_fields: 区块指针策略字段枚举列表
            db_conn: 数据库连接对象
            **kwargs: 额外参数

        Returns:
            BlockStrategy: 对应的策略实例
        """
        
        if pointer_fields == (PointerField.QUARTER, PointerField.STOCK_CODE):
            return QuarterStockStrategy(db_conn, **kwargs)
        else:
            return DefaultBlockStrategy()


class DefaultBlockStrategy(BlockStrategy):
    """
    默认区块策略，适用于其他策略类型

    提供基本的实现，子类可以根据需要重写
    """

    def get_total_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取总区块数量

        默认实现，返回 0

        Args:
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 额外参数

        Returns:
            int: 总区块数量
        """
        return 0
    
    def get_completed_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已完成区块数

        默认实现，返回 0

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）

        Returns:
            int: 已完成区块数
        """
        return 0
