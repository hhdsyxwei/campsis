# quarter_stock_time_frame_blk_mgr.py
# 支持多时间周期的区块管理器

from KitchenBase.download_enums import DlTaskType
from .generic_block_manager import GenericBlockManager
from KitchenBase.download_enums import PointerField
from typing import Tuple
from Ingredient.config import KLineConfig
from KitchenBase.logger_config import get_logger

class StockTmQtrBlkMgr(GenericBlockManager):
    """
    支持多时间周期的区块管理器

    计算总区块数：股票数 × 季度数 × 时间周期数
    """

    def __init__(self, db_conn, task_type: DlTaskType):
        """
        初始化区块管理器
        """
        super().__init__(db_conn, task_type)
        self.time_frame_list = KLineConfig.DEFAULT_TIME_FRAMES
        self.logger = get_logger(__name__)

    def get_total_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取总区块数量

        计算方法：股票数 × 季度数 × 时间周期数
        股票数量从 stock_fixed_seq 表中获取

        Args:
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 额外参数

        Returns:
            int: 总区块数量
        """
        try:
            stock_count = self.get_stock_count()
            year_range = end_year - start_year
            quarterly_count = year_range * 4
            time_frame_count = len(self.time_frame_list)
            total_count = stock_count * quarterly_count * time_frame_count

            self.logger.info(
                f"总区块数量计算：{start_year}-{end_year-1} 年，"
                f"{stock_count} 只股票，{time_frame_count} 个周期，共 {total_count} 个区块"
            )
            return total_count
        except Exception as e:
            self.logger.error(f"计算总区块数量异常：{e}", exc_info=True)
            return 0
