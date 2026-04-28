# stock_year_ptr_mgr.py
# 按股票和年份划分的指针管理器

from Ingredient.config import DownloadBlockConfig
from KitchenBase.download_enums import DlTaskType
from .generic_pointer_manager import GenericPointerManager
from ..core.download_parameters import DownloadParameters
from KitchenBase.block_pointer import BlockPointer, BlockPointerFactory
from KitchenBase.download_enums import PointerField
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from Ingredient.downloader.core.abs_collection_manager import StockCollectionManager

class StockYearPtrMgr(GenericPointerManager):
    """
    按股票和年份划分的指针管理器
    
    区块结构：(STOCK_CODE, YEAR)
    迭代顺序：先按股票顺序，同股票内按年份升序
    
    职责：
    1. 管理按股票和年份划分的下载指针
    2. 实现股票和年份的迭代逻辑
    3. 提供指针验证和转换功能
    """
    
    def __init__(self, db_conn, task_type: DlTaskType, 
                 collection_manager: StockCollectionManager, 
                 global_manager=None,
                 time_frame=None):
        """
        初始化股票年份指针管理器
        
        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型（可选）
            collection_manager: 股票集合管理器
            global_manager: GlobalDlCtrlBlockManager 实例（可选，用于依赖注入）
            time_frame: 时间周期（可选）
        """
        super().__init__(db_conn, task_type, collection_manager, global_manager, time_frame)
        self.logger = get_logger(__name__)
    
    def get_next_blk_pointer(self, params: DownloadParameters, current_block: Optional[BlockPointer] = None, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个待下载区块的指针
        
        实现思路：
        1. 区块按照股票和年份顺序排序
        2. 当current_block为None时，返回第一个区块（第一只股票的起始年份）
        3. 同一只股票内，获取下一个年份
        4. 如果是股票的最后一个年份，则获取下一只股票的起始年份
        5. 超出股票或年份范围时，返回None
        6. 处理异常情况，确保函数在各种情况下都能正常返回
        
        特殊参数：
        - params: 下载参数，包含start_year、end_year、stock_codes
        - current_block: 当前区块指针，为None时返回第一个区块
        - **kwargs: 额外参数，当前实现未使用
        
        异常情况：
        1. 股票数量为0时，返回None
        2. 超出股票范围时，返回None
        3. 超出年份范围时，返回None
        4. 解析区块指针失败时，返回None
        5. 所有其他异常，返回None
        
        注意：
        - 年份范围是前闭后开区间 [params.start_year, params.end_year)
        - 区块顺序：先按股票顺序，同股票内按年份升序
        
        Args:
            params: 下载参数
            current_block: 当前区块指针
            **kwargs: 额外参数
        
        Returns:
            Optional[BlockPointer]: 下一个区块的指针
        """
        pointer_fields = DownloadBlockConfig.get_pointer_fields(self.task_type)
        
        if current_block is None:
            try:
                stock_count = self.get_stock_total_count(params)
                if stock_count == 0:
                    self.logger.warning("股票数量为0，无法获取区块指针")
                    return None
                
                first_stock = self.get_first_stock(params)
                if not first_stock:
                    self.logger.warning("无法获取第一只股票，无法创建区块指针")
                    return None
                
                pointer_values = (first_stock, params.start_year)
                return BlockPointerFactory.create_pointer(pointer_fields, pointer_values)
            except Exception as e:
                self.logger.error(f"获取第一个区块指针失败: {str(e)}")
                return None
        
        try:
            current_stock = current_block.get_value(PointerField.STOCK_CODE)
            current_year = current_block.get_value(PointerField.YEAR)
            
            if not self.stock_exists(current_stock, params):
                self.logger.warning(f"当前股票 {current_stock} 不在有效范围内")
                return None
            
            if current_year < params.start_year or current_year >= params.end_year:
                self.logger.warning(f"当前年份 {current_year} 超出范围 [{params.start_year}, {params.end_year})")
                return None
            
            next_year = current_year + 1
            if next_year < params.end_year:
                pointer_values = (current_stock, next_year)
                return BlockPointerFactory.create_pointer(pointer_fields, pointer_values)
            else:
                next_stock = self.get_next_stock(current_stock, params)
                if next_stock:
                    pointer_values = (next_stock, params.start_year)
                    return BlockPointerFactory.create_pointer(pointer_fields, pointer_values)
                else:
                    return None
        except Exception as e:
            self.logger.error(f"获取下一个区块指针失败: {str(e)}")
            return None
    
    def is_dl_pointer_valid(self, dl_pointer: Optional[BlockPointer], params: DownloadParameters) -> bool:
        """
        判断下载指针是否合法有效
        
        Args:
            dl_pointer: 下载指针
            params: 下载参数
        
        Returns:
            bool: 指针是否有效
        """
        if not dl_pointer or not super().is_dl_pointer_valid(dl_pointer, params):
            return False
        
        try:
            stock = dl_pointer.get_value(PointerField.STOCK_CODE)
            year = dl_pointer.get_value(PointerField.YEAR)
            
            if not self.stock_exists(stock, params):
                return False
            
            return params.start_year <= year < params.end_year
        except Exception as e:
            self.logger.error(f"验证指针有效性失败: {str(e)}")
            return False
    
    def get_completed_block_count(self, params: DownloadParameters, current_pointer: BlockPointer) -> int:
        """
        计算已完成的区块数量
        
        计算公式：
        已完成区块数 = (已完成股票数 × 年份总数) + 当前股票的已完成年数
        
        Args:
            params: 下载参数
            current_pointer: 当前区块指针
        
        Returns:
            int: 已完成的区块数量
        """
        if not current_pointer:
            return 0
        
        try:
            current_stock = current_pointer.get_value(PointerField.STOCK_CODE)
            current_year = current_pointer.get_value(PointerField.YEAR)
            
            stock_list = self.collection_manager.get_stock_list()
            if not stock_list:
                return 0
            
            try:
                stock_position = stock_list.index(current_stock)
            except ValueError:
                return 0
            
            year_count = params.end_year - params.start_year
            completed_years_in_current = current_year - params.start_year
            
            return stock_position * year_count + completed_years_in_current
        except Exception as e:
            self.logger.error(f"计算已完成区块数失败: {e}")
            return 0
