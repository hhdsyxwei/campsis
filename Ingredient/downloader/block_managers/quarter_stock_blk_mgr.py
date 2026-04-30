# custom_total_block_manager.py
# 自定义总区块数计算的区块管理器

from KitchenBase.download_enums import DlTaskType
from .generic_block_manager import GenericBlockManager
from Ingredient.DataNest import UnifiedDataManager as udm
from ..core.abs_collection_manager import StockCollectionManager

class QuarterStockBlkMgr(GenericBlockManager):
    """
    自定义总区块数计算的区块管理器
    
    只重写get_total_block_count方法，其他方法使用父类实现
    """
    
    def __init__(self, db_conn, task_type: DlTaskType, collection_manager: StockCollectionManager):
        """
        初始化自定义区块管理器
        
        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型枚举值
            pointer_fields: 指针字段枚举元组
            collection_manager: 股票集合管理器，必须提供
        """
        super().__init__(db_conn, task_type, collection_manager=collection_manager)

    def get_total_block_count(self, params, **kwargs) -> int:
        """
        获取总区块数量
        
        计算方法：(end_year - start_year) * 4 * 股票数量
        股票数量从 stock_fixed_seq 表中获取
        
        Args:
            params: 下载参数（包含 start_year 和 end_year）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数量
        """
        try:
            # 从 params 中提取年份范围
            start_year = params.start_year
            end_year = params.end_year
            
            # 获取股票数量
            stock_count = self.get_stock_count()
            
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

    def get_stock_count(self) -> int:
        """
        获取股票数量
        
        Returns:
            int: 股票数量
        """
        try:
            # 如果有股票集合管理器，使用它获取股票数量
            if self.collection_manager:
                return self.collection_manager.get_stock_count()
            # 否则从数据库获取
            return udm.count_stocks_in_fixed_seq(self.db_conn)
        except Exception as e:
            self.logger.error(f"获取股票数量异常：{e}", exc_info=True)
            return 5000