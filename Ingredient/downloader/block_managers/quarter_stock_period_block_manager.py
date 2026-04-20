# quarter_stock_period_block_manager.py
# 季度-股票-周期区块管理器，适用于按季度、股票和K线周期划分区块的下载器

from .general_block_manager import GeneralBlockManager

class QuarterStockPeriodBlockManager(GeneralBlockManager):
    """
    季度-股票-周期区块管理器，适用于按季度、股票和K线周期划分区块的下载器
    """
    
    def __init__(self, db_conn, data_manager):
        """
        初始化季度-股票-周期区块管理器
        
        Args:
            db_conn: 数据库连接对象
            data_manager: 数据管理器
        """
        super().__init__(db_conn)
        self.data_manager = data_manager
    
    def get_total_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        计算总区块数：(结束年份 - 开始年份) * 4 * 股票总数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数
        """
        from Ingredient.DataNest import UnifiedDataManager as dm
        stock_count = dm.count_stocks_in_fixed_seq(self.db_conn)
        quarter_count = (end_year - start_year) * 4
        return stock_count * quarter_count
    
    def get_completed_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取已完成的区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            int: 已完成区块数
        """
        # 从kwargs中获取time_frame参数
        time_frame = kwargs.get('time_frame') if 'kwargs' in locals() else None
        return self.data_manager.get_completed_block_count(start_year, end_year, time_frame)
    
    def get_skipped_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取已跳过的区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            int: 已跳过区块数
        """
        # 从kwargs中获取time_frame参数
        time_frame = kwargs.get('time_frame') if 'kwargs' in locals() else None
        return self.data_manager.get_skipped_block_count(start_year, end_year, time_frame)
    
    def get_block_status(self, quarter: str, stock_code: str, time_frame) -> int:
        """
        获取指定区块的状态
        
        Args:
            quarter: 季度，格式为"YYYY-QN"
            stock_code: 股票代码
            time_frame: K线周期
            
        Returns:
            int: 区块状态
        """
        return self.data_manager.get_kline_block_status(quarter, stock_code, time_frame)
    
    def update_block_status(self, quarter: str, stock_code: str, time_frame, status: int, **kwargs):
        """
        更新指定区块的状态
        
        Args:
            quarter: 季度，格式为"YYYY-QN"
            stock_code: 股票代码
            time_frame: K线周期
            status: 区块状态
            **kwargs: 额外参数
        """
        self.data_manager.update_kline_block_status(quarter, stock_code, time_frame, status, **kwargs)
