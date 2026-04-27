# stock_time_frame_quarter_ptr_mgr.py
# 股票-时间周期-季度 指针管理器

from .generic_pointer_manager import GenericPointerManager
from ..core.download_parameters import DownloadParameters
from KitchenBase.block_pointer import BlockPointer
from KitchenBase.download_enums import PointerField
from typing import Optional, Tuple
from Ingredient.DataNest import UnifiedDataManager as udm
from Ingredient.config import KLineConfig
from KitchenBase.logger_config import get_logger
from Ingredient.config import DlTaskType


class StockTimeFrameQuarterPtrMgr(GenericPointerManager):
    """
    股票-时间周期-季度 指针管理器
    迭代顺序：stock_code → time_frame → quarter
    """

    def __init__(self, db_conn, task_type: DlTaskType, global_manager=None):
        """
        初始化指针管理器
        """
        super().__init__(db_conn, task_type, global_manager)
        self.time_frame_list = KLineConfig.DEFAULT_TIME_FRAMES
        self.logger = get_logger(__name__)

    def get_next_blk_pointer(self, params: DownloadParameters, current_pointer: Optional[BlockPointer] = None, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个区块指针

        迭代顺序：stock_code → time_frame → quarter

        Args:
            params: 下载参数
            current_pointer: 当前区块指针（首次调用传None，返回第一个区块）

        Returns:
            BlockPointer: 下一个区块指针，无更多区块时返回 None
        """
        # 1. 首次调用，返回第一个区块
        if not current_pointer:
            first_stock = self.get_first_stock(params)
            if not first_stock:
                self.logger.error("无股票数据可用")
                return None
            if not self.time_frame_list:
                self.logger.error("时间周期列表为空")
                return None
            first_time_frame = self.time_frame_list[0].value
            first_quarter = f"{params.start_year}-Q1"
            return BlockPointer(
                (PointerField.STOCK_CODE, PointerField.TIME_FRAME, PointerField.QUARTER),
                (first_stock, first_time_frame, first_quarter)
            )

        # 2. 非首次调用
        try:
            current_stock = current_pointer.get_value(PointerField.STOCK_CODE)
            current_timeframe = current_pointer.get_value(PointerField.TIME_FRAME)
            current_quarter = current_pointer.get_value(PointerField.QUARTER)

            # 3. 同股票、同时期 → 下一个季度
            next_quarter = self.get_next_quarter(current_quarter, (params.start_year, params.end_year))
            if next_quarter:
                self.logger.debug(f"同股票同时期，下一季度: {current_stock} {current_timeframe} {next_quarter}")
                return BlockPointer(
                    (PointerField.STOCK_CODE, PointerField.TIME_FRAME, PointerField.QUARTER),
                    (current_stock, current_timeframe, next_quarter)
                )

            # 4. 同股票 → 下一个时间周期，重置季度
            current_timeframe_idx = -1
            for i, tf in enumerate(self.time_frame_list):
                if tf.value == current_timeframe:
                    current_timeframe_idx = i
                    break

            if current_timeframe_idx < len(self.time_frame_list) - 1:
                next_timeframe = self.time_frame_list[current_timeframe_idx + 1].value
                self.logger.debug(f"同股票，下一周期: {current_stock} {next_timeframe}")
                return BlockPointer(
                    (PointerField.STOCK_CODE, PointerField.TIME_FRAME, PointerField.QUARTER),
                    (current_stock, next_timeframe, f"{params.start_year}-Q1")
                )

            # 5. 下一只股票，重置周期和季度
            next_stock = self.get_next_stock(current_stock, params)
            if next_stock and self.time_frame_list:
                first_timeframe = self.time_frame_list[0].value
                self.logger.debug(f"下一只股票: {next_stock} {first_timeframe}")
                return BlockPointer(
                    (PointerField.STOCK_CODE, PointerField.TIME_FRAME, PointerField.QUARTER),
                    (next_stock, first_timeframe, f"{params.start_year}-Q1")
                )

            # 6. 没有更多区块
            self.logger.debug("无更多区块")
            return None

        except Exception as e:
            self.logger.error(f"获取下一个区块指针失败: {str(e)}")
            return None

    def is_dl_pointer_valid(self, pointer: Optional[BlockPointer], params: DownloadParameters) -> bool:
        """
        验证指针是否有效

        Args:
            pointer: 要验证的指针
            params: 下载参数

        Returns:
            bool: 指针是否有效
        """
        # 1. 检查指针是否存在
        if not pointer:
            return False

        # 2. 检查字段完整性
        stock_code = pointer.get_value(PointerField.STOCK_CODE)
        time_frame = pointer.get_value(PointerField.TIME_FRAME)
        quarter = pointer.get_value(PointerField.QUARTER)

        if not stock_code or not time_frame or not quarter:
            self.logger.error(f"指针字段不完整: stock_code={stock_code}, time_frame={time_frame}, quarter={quarter}")
            return False

        # 3. 验证季度是否在年份范围内
        try:
            year_str, quarter_part = quarter.split('-Q')
            quarter_year = int(year_str)

            if quarter_year < params.start_year or quarter_year >= params.end_year:
                self.logger.error(f"季度年份超出范围: {quarter_year} not in [{params.start_year}, {params.end_year})")
                return False

            quarter_num = int(quarter_part)
            if quarter_num < 1 or quarter_num > 4:
                self.logger.error(f"季度值不合法: {quarter_num}")
                return False

        except ValueError:
            self.logger.error(f"季度格式错误: {quarter}")
            return False

        # 4. 验证时间周期是否在配置列表中
        time_frame_valid = any(tf.value == time_frame for tf in self.time_frame_list)
        if not time_frame_valid:
            self.logger.error(f"时间周期无效: {time_frame}")
            return False

        # 5. 验证股票代码是否在股票列表中
        if not self.stock_exists(stock_code, params):
            self.logger.error(f"股票代码不存在于股票列表: {stock_code}")
            return False

        return True