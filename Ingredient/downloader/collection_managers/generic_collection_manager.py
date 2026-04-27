from typing import Optional, List
from Ingredient.downloader.core.abs_collection_manager import StockCollectionManager
from Ingredient.DataNest import UnifiedDataManager as udm
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


class GenericStockCollectionManager(StockCollectionManager):
    """
    通用股票集合管理器，实现 StockCollectionManager 接口
    支持参数指定的股票列表和数据库 stock_fixed_seq 表
    """
    
    def __init__(self, db_conn, stock_codes: Optional[List[str]] = None):
        """
        初始化通用股票集合管理器
        
        Args:
            db_conn: 数据库连接
            stock_codes: 股票代码列表，可选，None表示使用 stock_fixed_seq 表
        """
        self.db_conn = db_conn
        self.stock_codes = stock_codes
        self._stock_index = 0
        
    def get_stock_list(self) -> Optional[List[str]]:
        """
        获取股票代码列表
        
        Returns:
            Optional[List[str]]: 股票代码列表，None表示使用默认股票集合
        """
        return self.stock_codes
    
    def has_custom_stock_list(self) -> bool:
        """
        检查是否使用自定义股票列表
        
        Returns:
            bool: 是否使用自定义股票列表
        """
        return self.stock_codes is not None
    
    def get_stock_count(self) -> int:
        """
        获取股票数量
        
        Returns:
            int: 股票数量
        """
        if self.stock_codes:
            return len(self.stock_codes)
        else:
            # 从 stock_fixed_seq 表获取股票数量
            try:
                count = udm.count_stocks_in_fixed_seq(self.db_conn)
                return count
            except Exception as e:
                logger.error(f"获取股票数量失败: {str(e)}")
                return 0
    
    def get_next_stock(self, current_stock: Optional[str]) -> Optional[str]:
        """
        获取下一个股票代码
        
        Args:
            current_stock: 当前股票代码，None表示获取第一个
            
        Returns:
            Optional[str]: 下一个股票代码，None表示没有更多
        """
        if self.stock_codes:
            # 使用参数指定的股票列表
            if current_stock is None:
                # 获取第一个股票
                return self.stock_codes[0] if self.stock_codes else None
            
            try:
                current_index = self.stock_codes.index(current_stock)
                if current_index + 1 < len(self.stock_codes):
                    return self.stock_codes[current_index + 1]
                else:
                    return None
            except ValueError:
                # 当前股票不在列表中，返回第一个
                return self.stock_codes[0] if self.stock_codes else None
        else:
            # 使用数据库中的 stock_fixed_seq 表
            try:
                return udm.next_fixed_stock(self.db_conn, current_stock)
            except Exception as e:
                logger.error(f"获取下一个股票失败: {str(e)}")
                return None
    
    def get_first_stock(self) -> Optional[str]:
        """
        获取第一个股票代码
        
        Returns:
            Optional[str]: 第一个股票代码，None表示没有股票
        """
        if self.stock_codes:
            # 使用参数指定的股票列表
            return self.stock_codes[0] if self.stock_codes else None
        else:
            # 使用数据库中的 stock_fixed_seq 表
            try:
                return udm.next_fixed_stock(self.db_conn, None)
            except Exception as e:
                logger.error(f"获取第一个股票失败: {str(e)}")
                return None