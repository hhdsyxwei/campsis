# stock_year_block_manager.py
# 股票-年份区块管理器，适用于按股票和年份划分区块的下载器

from KitchenBase.download_enums import DlTaskType
from .generic_block_manager import GenericBlockManager

class YearStockBlkMgr(GenericBlockManager):
    """
    股票-年份区块管理器，适用于按股票和年份划分区块的下载器
    """
    
    def __init__(self, db_conn, task_type: DlTaskType, collection_manager=None):
        """
        初始化股票-年份区块管理器
        
        Args:
            db_conn: 数据库连接对象
            collection_manager: 股票集合管理器，可选
        """
        super().__init__(db_conn, task_type, collection_manager=collection_manager)
    
    def get_total_block_count(self, params, **kwargs) -> int:
        """
        计算总区块数：(结束年份 - 开始年份) * 股票总数
        
        Args:
            params: 下载参数（包含 start_year 和 end_year）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数
        """
        # 从 params 中提取年份范围
        start_year = params.start_year
        end_year = params.end_year
        
        # 如果有股票集合管理器，使用它获取股票数量
        if self.collection_manager:
            stock_count = self.collection_manager.get_stock_count()
        else:
            from Ingredient.DataNest import UnifiedDataManager as dm
            stock_count = dm.count_stocks_in_fixed_seq(self.db_conn)
        year_count = end_year - start_year
        return stock_count * year_count