# quarter_stock_period_strategy.py
# 季度-股票-周期指针策略，适用于按季度、股票和时间周期迭代的下载器

from ...core.abs_block_pointer_strategy import BlockPointerStrategy
from typing import Optional, Tuple
from KitchenBase.block_pointer import BlockPointer, BlockPointerFactory
from KitchenBase.download_enums import PointerField

class QuarterStockPeriodStrategy(BlockPointerStrategy):
    """
    季度-股票-周期指针策略，适用于按季度、股票和时间周期迭代的下载器

    迭代规则：
    1. 同季度内，按股票代码固定顺序迭代
    2. 季度内所有股票迭代完毕后，切换到下一季度
    3. 达到结束年份时返回 None
    """

    def __init__(self, db_conn, time_frame='5'):
        """
        初始化策略

        Args:
            db_conn: 数据库连接对象
            time_frame: 时间周期
        """
        self.db_conn = db_conn
        self.time_frame = time_frame

    def get_first_blk_pointer(self, start_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个季度、第一个股票和指定时间周期的指针

        Args:
            start_year: 开始年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 季度-股票-周期指针
        """
        from Ingredient.DataNest import UnifiedDataManager as dm
        first_stock = dm.next_fixed_stock(self.db_conn, None)
        return BlockPointerFactory.create_quarter_stock_period(f"{start_year}-Q1", first_stock, self.time_frame) if first_stock else None

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
        quarter = current_pointer.get_value(PointerField.QUARTER)
        stock_code = current_pointer.get_value(PointerField.STOCK_CODE)
        time_frame = current_pointer.get_value(PointerField.TIME_FRAME)

        from Ingredient.DataNest import UnifiedDataManager as dm

        # 获取下一个股票
        next_stock = dm.next_fixed_stock(self.db_conn, stock_code)
        if next_stock:
            return BlockPointerFactory.create_quarter_stock_period(quarter, next_stock, time_frame)

        # 切换到下一季度
        next_quarter = self._get_next_quarter(quarter)
        if not next_quarter:
            return None

        # 解析下一季度的年份
        year_str = next_quarter.split('-Q')[0]
        year = int(year_str)
        if year >= end_year:
            return None

        # 获取新季度的第一个股票
        first_stock = dm.next_fixed_stock(self.db_conn, None)
        return BlockPointerFactory.create_quarter_stock_period(next_quarter, first_stock, time_frame) if first_stock else None

    def _get_next_quarter(self, quarter: str) -> Optional[str]:
        """
        获取下一个季度

        Args:
            quarter: 当前季度，格式如 "2024-Q1"

        Returns:
            Optional[str]: 下一个季度，格式如 "2024-Q2"
        """
        try:
            year_str, q_str = quarter.split('-Q')
            current_year = int(year_str)
            current_q = int(q_str)

            next_q = current_q + 1
            next_year = current_year
            if next_q > 4:
                next_year += 1
                next_q = 1

            return f"{next_year}-Q{next_q}"
        except (ValueError, AttributeError):
            return None

    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return (PointerField.QUARTER, PointerField.STOCK_CODE, PointerField.TIME_FRAME)

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

        quarter = pointer.get_value(PointerField.QUARTER)
        stock_code = pointer.get_value(PointerField.STOCK_CODE)
        time_frame = pointer.get_value(PointerField.TIME_FRAME)

        # 验证季度格式
        try:
            year_str, q_str = quarter.split('-Q')
            year = int(year_str)
            q = int(q_str)

            if year < start_year or year >= end_year:
                return False

            if q < 1 or q > 4:
                return False
        except (ValueError, AttributeError):
            return False

        if not stock_code or not time_frame:
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

        quarter = current_pointer.get_value(PointerField.QUARTER)
        current_stock = current_pointer.get_value(PointerField.STOCK_CODE)

        try:
            from Ingredient.DataNest import UnifiedDataManager as dm

            # 解析当前季度
            year_str, q_str = quarter.split('-Q')
            current_year = int(year_str)
            current_q = int(q_str)

            # 计算从开始年份到当前季度的完整季度数
            completed_quarters = (current_year - start_year) * 4 + (current_q - 1)

            # 获取股票总数
            stock_count = dm.count_stocks_in_fixed_seq(self.db_conn)
            if stock_count == 0:
                return 0

            # 获取当前股票的位置
            stock_position = dm.get_stock_position(self.db_conn, current_stock)
            if stock_position is None:
                return 0

            return completed_quarters * stock_count + stock_position
        except Exception as e:
            print(f"[QuarterStockPeriodStrategy] 计算已完成区块数失败: {e}")
            return 0