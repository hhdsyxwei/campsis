# year_stock_ptr_mrg.py
# 按年份和股票划分的指针管理器

from Ingredient.config import DownloadBlockConfig
from KitchenBase.download_enums import DlTaskType
from .generic_pointer_manager import GenericPointerManager
from ..core.download_parameters import DownloadParameters
from KitchenBase.block_pointer import BlockPointer, BlockPointerFactory
from KitchenBase.download_enums import PointerField
from typing import Optional, Tuple
from Ingredient.DataNest import UnifiedDataManager as dm
from KitchenBase.logger_config import get_logger


class YearStockPtrMgr(GenericPointerManager):
    """
    按年份和股票划分的指针管理器
    
    职责：
    1. 管理按年份和股票划分的下载指针
    2. 实现年份和股票的迭代逻辑
    3. 提供指针验证和转换功能
    """
    
    def __init__(self, db_conn, task_type: DlTaskType, global_manager=None, time_frame=None, collection_manager=None):
        """
        初始化年份股票指针管理器
        
        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型（可选）
            pointer_fields: 指针字段枚举元组（可选）
            global_manager: GlobalDlCtrlBlockManager 实例（可选，用于依赖注入）
            time_frame: 时间周期（可选）
            collection_manager: 股票集合管理器（可选）
        """
        super().__init__(db_conn, task_type, global_manager, time_frame, collection_manager=collection_manager)
        self.logger = get_logger(__name__)

    def get_next_blk_pointer(self, params: DownloadParameters, current_block: Optional[BlockPointer] = None, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个待下载区块的指针
        
        实现思路：
        1. 区块按照年份和股票顺序排序
        2. 当current_block为None时，返回第一个区块（起始年份的第一只股票）
        3. 同一年份内，获取下一只股票
        4. 如果是年份内的最后一只股票，则获取下一年份的第一只股票
        5. 超出年份范围时，返回None
        6. 处理异常情况，确保函数在各种情况下都能正常返回
        
        特殊参数：
        - params: 下载参数，包含start_year、end_year、stock_codes
        - current_block: 当前区块指针，为None时返回第一个区块
        - **kwargs: 额外参数，当前实现未使用
        
        异常情况：
        1. 股票数量为0时，返回None
        2. 超出年份范围时，返回None
        3. 解析区块指针失败时，返回None
        4. 获取下一只股票失败时，继续处理下一年份
        5. 所有其他异常，返回None
        
        注意：
        - 年份范围是前闭后开区间 [params.start_year, params.end_year)
        - 区块顺序：先按年份升序，同一年份内按股票顺序
        
        Args:
            params: 下载参数
            current_block: 当前区块指针
            **kwargs: 额外参数
        
        Returns:
            Optional[BlockPointer]: 下一个区块的指针
        """
        # 当current_block为None时，返回第一个区块（起始年份的第一只股票）
        pointer_fields = DownloadBlockConfig.get_pointer_fields(self.task_type)
        if current_block is None:
            try:
                # 检查股票数量
                stock_count = self.get_stock_total_count(params)
                if stock_count == 0:
                    self.logger.warning("股票数量为0，无法获取区块指针")
                    return None
                
                # 获取第一只股票
                first_stock = self.get_first_stock(params)
                if not first_stock:
                    self.logger.warning("无法获取第一只股票，无法创建区块指针")
                    return None
                
                # 构建第一个年份的指针
                pointer_values = (params.start_year, first_stock)
                return BlockPointerFactory.create_pointer(pointer_fields, pointer_values)
            except Exception as e:
                self.logger.error(f"获取第一个区块指针失败: {str(e)}")
                return None
        
        try:
            # 解析当前区块指针
            current_year = current_block.get_value(PointerField.YEAR)
            current_stock = current_block.get_value(PointerField.STOCK_CODE)
            
            # 检查当前年份是否在有效范围内
            if current_year < params.start_year or current_year >= params.end_year:
                self.logger.warning(f"当前年份 {current_year} 超出范围 [{params.start_year}, {params.end_year})")
                return None
            
            # 获取下一只股票
            next_stock = self.get_next_stock(current_stock, params)
            if next_stock:
                # 同一年份内的下一只股票
                pointer_values = (current_year, next_stock)
                return BlockPointerFactory.create_pointer(pointer_fields, pointer_values)
            else:
                # 当前年份的股票已遍历完毕，获取下一个年份
                next_year = current_year + 1
                if next_year < params.end_year:
                    # 检查股票数量
                    stock_count = self.get_stock_total_count(params)
                    if stock_count == 0:
                        self.logger.warning("股票数量为0，无法获取下一年份的区块指针")
                        return None
                    
                    # 下一年份的第一只股票
                    first_stock = self.get_first_stock(params)
                    if first_stock:
                        pointer_values = (next_year, first_stock)
                        return BlockPointerFactory.create_pointer(pointer_fields, pointer_values)
                    else:
                        self.logger.warning("无法获取第一只股票，无法创建下一年份的区块指针")
                        return None
            
            # 没有下一个区块（超出年份范围）
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
            # 验证年份是否在年份范围内
            year = dl_pointer.get_value(PointerField.YEAR)
            return params.start_year <= year < params.end_year
        except Exception as e:
            self.logger.error(f"验证指针有效性失败: {str(e)}")
            return False

    def get_completed_block_count(self, params: DownloadParameters, current_pointer: BlockPointer) -> int:
        """
        计算已完成的区块数量

        Args:
            params: 下载参数
            current_pointer: 当前区块指针

        Returns:
            int: 已完成的区块数量
        """
        if not current_pointer:
            return 0

        current_year = current_pointer.get_value(PointerField.YEAR)
        current_stock = current_pointer.get_value(PointerField.STOCK_CODE)

        try:
            from Ingredient.DataNest import UnifiedDataManager as dm

            # 计算已完成的年份数
            completed_years = current_year - params.start_year

            # 获取股票总数
            stock_count = self.get_stock_total_count(params)
            if stock_count == 0:
                return 0

            # 获取当前股票的位置
            stock_list = self.collection_manager.get_stock_list()
            if stock_list:
                # 使用自定义股票列表的位置
                try:
                    stock_position = stock_list.index(current_stock)
                except ValueError:
                    return 0
            else:
                # 使用数据库的位置
                stock_position = dm.get_stock_position(self.db_conn, current_stock)
                if stock_position is None:
                    return 0

            return completed_years * stock_count + stock_position
        except Exception as e:
            print(f"[YearStockStrategy] 计算已完成区块数失败: {e}")
            return 0
