# stock_year_block_manager.py
# 股票-年份区块管理器，适用于按股票和年份划分区块的下载器

from .general_block_manager import GeneralBlockManager

class StockYearBlockManager(GeneralBlockManager):
    """
    股票-年份区块管理器，适用于按股票和年份划分区块的下载器
    """
    
    def __init__(self, db_conn, data_manager):
        """
        初始化股票-年份区块管理器
        
        Args:
            db_conn: 数据库连接对象
            data_manager: 数据管理器
        """
        super().__init__(db_conn)
        self.data_manager = data_manager
    
    def get_total_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        计算总区块数：(结束年份 - 开始年份) * 股票总数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数
        """
        from Ingredient.DataNest import UnifiedDataManager as dm
        stock_count = dm.count_stocks_in_fixed_seq(self.db_conn)
        year_count = end_year - start_year
        return stock_count * year_count
    
    def get_completed_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已完成的区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            int: 已完成区块数
        """
        return self.data_manager.get_completed_block_count(start_year, end_year)
    
    def get_skipped_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已跳过的区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            int: 已跳过区块数
        """
        return self.data_manager.get_skipped_block_count(start_year, end_year)
    
    def get_block_status(self, year: int, stock_code: str) -> int:
        """
        获取指定区块的状态
        
        Args:
            year: 年份
            stock_code: 股票代码
            
        Returns:
            int: 区块状态
        """
        return self.data_manager.get_block_status(year, stock_code)
    
    def update_block_status(self, year: int, stock_code: str, status: int, **kwargs):
        """
        更新指定区块的状态
        
        Args:
            year: 年份
            stock_code: 股票代码
            status: 区块状态
            **kwargs: 额外参数
        """
        self.data_manager.update_block_status(year, stock_code, status, **kwargs)
