from abc import ABC, abstractmethod
from typing import Optional, List


class StockCollectionManager(ABC):
    """
    股票集合管理器接口，定义股票集合管理的统一接口
    """
    
    @abstractmethod
    def get_stock_list(self) -> Optional[List[str]]:
        """
        获取股票代码列表
        
        Returns:
            Optional[List[str]]: 股票代码列表，None表示使用默认股票集合
        """
        pass
    
    @abstractmethod
    def has_custom_stock_list(self) -> bool:
        """
        检查是否使用自定义股票列表
        
        Returns:
            bool: 是否使用自定义股票列表
        """
        pass
    
    @abstractmethod
    def get_stock_count(self) -> int:
        """
        获取股票数量
        
        Returns:
            int: 股票数量
        """
        pass
    
    @abstractmethod
    def get_next_stock(self, current_stock: Optional[str]) -> Optional[str]:
        """
        获取下一个股票代码
        
        Args:
            current_stock: 当前股票代码，None表示获取第一个
            
        Returns:
            Optional[str]: 下一个股票代码，None表示没有更多
        """
        pass
    
    @abstractmethod
    def get_first_stock(self) -> Optional[str]:
        """
        获取第一个股票代码
        
        Returns:
            Optional[str]: 第一个股票代码，None表示没有股票
        """
        pass