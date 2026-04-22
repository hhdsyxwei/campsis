# year_stock_strategy.py
# 年份-股票指针策略，适用于按年份和股票代码迭代的下载器

from ...core.abs_block_pointer_strategy import BlockPointerStrategy
from typing import Optional, Tuple
from KitchenBase.block_pointer import BlockPointer, BlockPointerFactory
from KitchenBase.download_enums import PointerField

class YearStockStrategy(BlockPointerStrategy):
    """
    年份-股票指针策略，适用于按年份和股票代码迭代的下载器

    迭代规则：
    1. 同一年份内，按股票代码固定顺序迭代
    2. 年份内所有股票迭代完毕后，切换到下一年份
    3. 达到结束年份时返回 None
    """

    def __init__(self, db_conn):
        """
        初始化策略

        Args:
            db_conn: 数据库连接对象
        """
        self.db_conn = db_conn

    def get_first_blk_pointer(self, start_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个年份和第一个股票的指针

        Args:
            start_year: 开始年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 年份-股票指针
        """
        from Ingredient.DataNest import UnifiedDataManager as dm
        first_stock = dm.next_fixed_stock(self.db_conn, None)
        return BlockPointerFactory.create_year_stock(start_year, first_stock) if first_stock else None

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
        year = current_pointer.get_value(PointerField.YEAR)
        stock_code = current_pointer.get_value(PointerField.STOCK_CODE)

        from Ingredient.DataNest import UnifiedDataManager as dm

        # 获取下一个股票
        next_stock = dm.next_fixed_stock(self.db_conn, stock_code)
        if next_stock:
            return BlockPointerFactory.create_year_stock(year, next_stock)

        # 切换到下一年
        next_year = year + 1
        if next_year >= end_year:
            return None

        # 获取新年份的第一个股票
        first_stock = dm.next_fixed_stock(self.db_conn, None)
        return BlockPointerFactory.create_year_stock(next_year, first_stock) if first_stock else None

    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return (PointerField.YEAR, PointerField.STOCK_CODE)

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

        year = pointer.get_value(PointerField.YEAR)
        stock_code = pointer.get_value(PointerField.STOCK_CODE)

        if not isinstance(year, int) or year < start_year or year >= end_year:
            return False

        if not stock_code:
            return False

        # 检查股票代码是否在固定顺序表中存在
        try:
            from Ingredient.DataNest import UnifiedDataManager as dm
            if not dm.is_stock_in_fixed_seq(self.db_conn, stock_code):
                return False
        except Exception:
            # 异常时返回 False，确保安全性
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

        current_year = current_pointer.get_value(PointerField.YEAR)
        current_stock = current_pointer.get_value(PointerField.STOCK_CODE)

        try:
            from Ingredient.DataNest import UnifiedDataManager as dm

            # 计算已完成的年份数
            completed_years = current_year - start_year

            # 获取股票总数
            stock_count = dm.count_stocks_in_fixed_seq(self.db_conn)
            if stock_count == 0:
                return 0

            # 获取当前股票的位置
            stock_position = dm.get_stock_position(self.db_conn, current_stock)
            if stock_position is None:
                return 0

            return completed_years * stock_count + stock_position
        except Exception as e:
            print(f"[YearStockStrategy] 计算已完成区块数失败: {e}")
            return 0