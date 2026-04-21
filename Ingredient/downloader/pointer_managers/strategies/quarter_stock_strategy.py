# quarter_stock_strategy.py
# 季度股票策略，用于生成按季度和股票划分的区块指针

from ...core.abs_block_pointer_strategy import BlockPointerStrategy
from KitchenBase.block_pointer import BlockPointer
from typing import Optional, List
from Ingredient.DataNest import StockFixedSeqManager
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


class QuarterStockStrategy(BlockPointerStrategy):
    """
    季度股票策略
    
    用于生成按季度和股票划分的区块指针
    格式: (quarter, stock_code)
    """
    
    def __init__(self, db_conn):
        """
        初始化季度股票策略
        
        Args:
            db_conn: 数据库连接对象
        """
        self.db_conn = db_conn
        self.stock_manager = StockFixedSeqManager(db_conn) if db_conn else None
    
    def get_next_blk_pointer(self, current_pointer: BlockPointer, start_year: int, end_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个区块指针
        
        Args:
            current_pointer: 当前区块指针
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 额外参数
            
        Returns:
            BlockPointer: 下一个区块指针，无更多区块时返回 None
        """
        # 1. 初始化检查
        if not self.stock_manager:
            logger.error("未初始化 StockFixedSeqManager")
            return None
        
        # 2. 首次获取
        if current_pointer is None:
            first_stock = self._get_first_stock()
            if not first_stock:
                return None
            first_quarter = f"{start_year}-Q1"
            return BlockPointer('quarter', first_quarter, 'stock_code', first_stock)
        
        # 3. 非首次获取
        try:
            current_quarter = current_pointer.get_value('quarter')
            current_stock = current_pointer.get_value('stock_code')
            
            # 4. 尝试获取下一只股票
            next_stock = self._get_next_stock(current_stock)
            if next_stock:
                # 当前季度内有下一只股票
                return BlockPointer(('quarter', 'stock_code'), (current_quarter, next_stock))
            
            # 5. 切换到下一个季度
            next_quarter = BlockPointerStrategy.get_next_quarter(current_quarter, (start_year, end_year))
            if next_quarter:
                # 有下一个季度
                first_stock = self._get_first_stock()
                if not first_stock:
                    return None
                return BlockPointer(('quarter', 'stock_code'), (next_quarter, first_stock))
            
            # 6. 没有更多季度
            return None
            
        except Exception as e:
            logger.error(f"获取下一个区块指针失败: {e}")
            return None
    
    def _get_first_stock(self):
        """
        获取第一只股票
        
        Returns:
            Optional[str]: 第一只股票代码
        """
        try:
            if self.stock_manager:
                return self.stock_manager.get_first_stock()
            else:
                logger.warning("未提供数据库连接，无法获取股票代码")
                return None
        except Exception as e:
            logger.error(f"获取第一只股票失败: {e}")
            return None
    
    def _get_next_stock(self, current_stock):
        """
        获取下一只股票
        
        Args:
            current_stock: 当前股票代码
        
        Returns:
            Optional[str]: 下一只股票代码
        """
        try:
            if self.stock_manager:
                return self.stock_manager.get_next_stock(current_stock)
            else:
                logger.warning("未提供数据库连接，无法获取股票代码")
                return None
        except Exception as e:
            logger.error(f"获取下一只股票失败: {e}")
            return None
    
    def get_first_blk_pointer(self, start_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个区块指针
        
        Args:
            start_year: 开始年份
            **kwargs: 额外参数
            
        Returns:
            Optional[BlockPointer]: 第一个区块的指针
        """
        first_stock = self._get_first_stock()
        if not first_stock:
            return None
        first_quarter = f"{start_year}-Q1"
        return BlockPointer(('quarter', 'stock_code'), (first_quarter, first_stock))
    
    def get_pointer_fields(self) -> tuple:
        """
        获取指针字段
        
        Returns:
            tuple: 指针字段元组
        """
        return ('quarter', 'stock_code')
    
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
        # 简化实现，实际项目中可能需要更复杂的计算
        return 0