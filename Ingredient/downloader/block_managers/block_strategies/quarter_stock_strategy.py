# quarter_stock_strategy.py
# 按季度和股票划分的区块策略

from KitchenBase.download_enums import DlTaskType
from KitchenBase.download_enums import DlBlockStatus
from Ingredient.DataNest.dm_generic_block_status import GenericBlockStatusDM
from ...core.abs_block_strategy import BlockStrategy
from Ingredient.DataNest import UnifiedDataManager as dm
from KitchenBase.logger_config import get_logger


class QuarterStockStrategy(BlockStrategy):
    """
    按季度和股票划分的区块策略
    
    计算按 (year, stock_code, quarter) 组合划分的区块数量
    """
    
    def __init__(self, db_conn, **kwargs):
        """
        初始化季度股票策略
        
        Args:
            db_conn: 数据库连接对象
            **kwargs: 额外参数
        """
        self.db_conn = db_conn
        self.logger = get_logger(__name__)
    
    def get_total_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取总区块数量
        
        计算方法：(end_year - start_year) * 4 * 股票数量
        股票数量从 stock_fixed_seq 表中获取
        
        Args:
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数量
        """
        try:
            # 获取股票数量
            stock_count = self._get_stock_count()
            
            # 计算年份范围
            year_range = end_year - start_year
            
            # 每个年份有 4 个季度
            quarterly_count = year_range * 4
            
            # 总区块数量 = 季度数量 * 股票数量
            total_count = quarterly_count * stock_count
            
            self.logger.info(f"总区块数量计算：{start_year}-{end_year-1} 年，{stock_count} 只股票，共 {total_count} 个区块")
            return total_count
        except Exception as e:
            self.logger.error(f"计算总区块数量异常：{e}", exc_info=True)
            return 0
    
    def get_completed_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取已完成区块数
        
        计算方法：(end_year - start_year) * 4 * 股票数量
        股票数量从 stock_fixed_seq 表中获取
        
        Args:
            start_year: 开始年份
            end_year: 结束年份
            
        Returns:
            int: 已完成区块数
        """
        #利用get_block_count获得已完成区块数
        gbsm = GenericBlockStatusDM(self.db_conn)
        completed_count = gbsm.get_block_count(DlTaskType.STOCK_PROFIT,start_year, end_year, [DlBlockStatus.COMPLETED])
        return completed_count

    def _get_stock_count(self) -> int:
        """
        获取股票数量
        
        从 stock_fixed_seq 表中获取股票数量
        
        Returns:
            int: 股票数量
        """        
        try:
            # 使用 UnifiedDataManager.count_stocks_in_fixed_seq() 方法获取股票数量  
            return dm.count_stocks_in_fixed_seq(self.db_conn)
        except Exception as e:
            self.logger.error(f"获取股票数量异常：{e}", exc_info=True)
            return 5000
