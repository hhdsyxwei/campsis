# quarter_stock_period_block_manager.py
# 季度-股票-周期区块管理器，适用于按季度、股票和K线周期划分区块的下载器

from KitchenBase.download_enums import DlTaskType
from .generic_block_manager import GenericBlockManager

class QuarterStockPeriodBlockManager(GenericBlockManager):
    """
    季度-股票-周期区块管理器，适用于按季度、股票和K线周期划分区块的下载器
    """
    
    def __init__(self, db_conn,task_type: DlTaskType):
        """
        初始化季度-股票-周期区块管理器
        
        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn, task_type)
        
    def get_total_block_count(self, params, **kwargs) -> int:
        """
        计算总区块数：(结束年份 - 开始年份) * 4 * 股票总数
        
        Args:
            params: 下载参数（包含 start_year 和 end_year）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数
        """
        from Ingredient.DataNest import UnifiedDataManager as dm
        stock_count = dm.count_stocks_in_fixed_seq(self.db_conn)
        quarter_count = (params.end_year - params.start_year) * 4
        return stock_count * quarter_count

    