# quarter_stock_ptr_mgr.py
# 按季度和股票划分的指针管理器

from .generic_pointer_manager import GenericPointerManager
from KitchenBase.block_pointer import BlockPointer, BlockPointerFactory
from KitchenBase.download_enums import PointerField
from typing import Optional, Tuple, Dict, Any
from Ingredient.DataNest import UnifiedDataManager as dm
from KitchenBase.logger_config import get_logger


class QuarterStockPtrMgr(GenericPointerManager):
    """
    按季度和股票划分的指针管理器
    
    职责：
    1. 管理按季度和股票划分的下载指针
    2. 实现季度和股票的迭代逻辑
    3. 提供指针验证和转换功能
    """
    
    def __init__(self, db_conn, task_type=None, global_manager=None, time_frame=None):
        """
        初始化季度股票指针管理器
        
        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型（可选）
            pointer_fields: 指针字段枚举元组（可选）
            global_manager: GlobalDlCtrlBlockManager 实例（可选，用于依赖注入）
            time_frame: 时间周期（可选，仅 QuarterStockPeriodStrategy 需要）
        """
        super().__init__(db_conn, task_type, global_manager, time_frame)
        self.logger = get_logger(__name__)

    def get_next_blk_pointer(self, start_year: int, end_year: int, current_pointer: BlockPointer, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个区块指针
        
        Args:
            current_pointer: 当前区块指针
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 额外参数
            
        Returns:
            BlockPointer: 下一个区块指针，无更多区块时返回 None
        """
        # 1. 初始化检查
        if not self.stock_manager:
            self.logger.error("未初始化 StockFixedSeqManager")
            return None
        
        # 2. 首次获取
        if current_pointer is None:
            first_stock = self.get_first_stock()
            if not first_stock:
                return None
            first_quarter = f"{start_year}-Q1"
            return BlockPointer((PointerField.QUARTER, PointerField.STOCK_CODE), (first_quarter, first_stock))
        
        # 3. 非首次获取
        try:
            current_quarter = current_pointer.get_value(PointerField.QUARTER)
            current_stock = current_pointer.get_value(PointerField.STOCK_CODE)
            
            # 4. 尝试获取下一只股票
            next_stock = self.get_next_stock(current_stock)
            if next_stock:
                # 当前季度内有下一只股票
                return BlockPointer((PointerField.QUARTER, PointerField.STOCK_CODE), (current_quarter, next_stock))
            
            # 5. 切换到下一个季度
            next_quarter = self.get_next_quarter(current_quarter, (start_year, end_year))
            if next_quarter:
                # 有下一个季度
                first_stock = self.get_first_stock()
                if not first_stock:
                    return None
                return BlockPointer((PointerField.QUARTER, PointerField.STOCK_CODE), (next_quarter, first_stock))
            
            # 6. 没有更多季度
            return None
            
        except Exception as e:
            return None
    
    def get_completed_block_count(self, start_year: int, end_year: int, dl_pointer: BlockPointer) -> int:
        return 0
