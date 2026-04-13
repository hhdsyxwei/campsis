# dm_unified.py
from .dm_global_dl_ctrl import GlobalDlCtrlBlockManager
from KitchenBase.download_enums import DlBlockStatus, DlTaskType
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import KLinePeriod
from .dm_kline import KLineUnifiedQuarterlyExtendedManager
from .dm_stock_basic import BasicStockDataManager
from .dm_stock_seq import StockFixedSeqManager
from .dm_xrxd import XrxdManager
from .dm_adjustment_factor import AdjustmentFactorManager
from .dm_global_dl_ctrl import GlobalDlCtrlBlockManager as dl_ctrl_manager

logger = get_logger(__name__)

class UnifiedDataManager:
    @staticmethod
    def save_stock_fixed_seq(db_conn, records: list) -> bool:
        """
        向stock_fixed_seq表中插入股票代码记录

        Args:
            db_conn: 数据库连接
            records: 股票代码记录列表，例如 [('000001',), ('000002',), ...]

        Returns:
            操作是否成功
        """
        func_name = "save_stock_fixed_seq"
        try:
            manager = StockFixedSeqManager(db_conn)
            return manager.save_stock_codes(records)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return False

    @staticmethod
    def truncate_table_stock_fixed_seq(db_conn) -> bool:
        """
        清空stock_fixed_seq表

        Args:
            db_conn: 数据库连接

        Returns:
            操作是否成功
        """
        func_name = "truncate_table_stock_fixed_seq"
        try:
            manager = StockFixedSeqManager(db_conn)
            return manager.truncate_table()
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return False

    @staticmethod
    def count_stocks_in_fixed_seq(db_conn) -> int:
        """
        统计stock_fixed_seq表中的股票总数

        Args:
            db_conn: 数据库连接

        Returns:
            股票总数
        """
        func_name = "count_stocks_in_fixed_seq"
        try:
            manager = StockFixedSeqManager(db_conn)
            return manager.count_stocks()
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return 0

    @staticmethod
    def save_kline_data_unified(db_conn, std_stock_code: str, df) -> bool:
        """
        保存统一格式的K线数据
        
        Args:
            db_conn: 数据库连接
            std_stock_code: 股票代码
            df: K线数据，包含time_frame, timestamp等字段
        
        Returns:
            保存是否成功
        """
        func_name = "save_kline_data_unified"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.save_kline_data_unified(std_stock_code, df)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return False

    @staticmethod
    def get_kline_block_status(db_conn, quarter: str, std_stock_code: str, time_frame: KLinePeriod) -> DlBlockStatus:
        """
        获取K线下载状态
        
        Args:
            db_conn: 数据库连接
            std_stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            状态枚举值，BlockStatus.COMPLETED 或 BlockStatus.NOT_COMPLETED 或 BlockStatus.SKIPPED
        """
        func_name = "get_kline_block_status"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.get_block_status(quarter, std_stock_code, time_frame)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            raise

    @staticmethod
    def update_kline_block_status(db_conn, quarter: str, std_stock_code: str, time_frame: KLinePeriod, status: DlBlockStatus):
        """
        更新K线下载进度（统一格式）
        
        Args:
            db_conn: 数据库连接
            std_stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
            status: 状态，BlockStatus.COMPLETED 或 BlockStatus.NOT_COMPLETED 或 BlockStatus.SKIPPED
        """
        func_name = "update_kline_block_status"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.update_block_status(quarter, std_stock_code, time_frame, status)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return None

    @staticmethod
    def get_quarter_data_count(db_conn, std_stock_code: str, time_frame: KLinePeriod, quarter: str) -> int:
        """
        获取指定股票、时间周期和季度的数据条数
        
        Args:
            db_conn: 数据库连接
            std_stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            数据条数
        """
        func_name = "get_quarter_data_count"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.get_quarter_data_count(std_stock_code, time_frame, quarter)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return 0

    @staticmethod
    def get_data_manager(db_conn, task_type: DlTaskType):
        """
        工厂方法：根据任务类型返回对应的数据管理器实例
        """
        if task_type == DlTaskType.KLINE:
            return KLineUnifiedQuarterlyExtendedManager(db_conn)
        elif task_type == DlTaskType.XRXD:
            return XrxdManager(db_conn)
        elif task_type == DlTaskType.ADJUSTMENT_FACTOR:
            return AdjustmentFactorManager(db_conn)
        else:
            raise ValueError(f"不支持的任务类型: {task_type}")

    @staticmethod
    def get_completed_block_count(db_conn, task_type: DlTaskType, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        统一获取已完成区块总数的接口
        """
        func_name = "get_completed_block_count"
        try:
            manager = UnifiedDataManager.get_data_manager(db_conn, task_type)
            return manager.get_completed_block_count(start_year, end_year, *args, **kwargs)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return 0

    @staticmethod
    def get_skipped_block_count(db_conn, task_type: DlTaskType, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        统一获取跳过区块总数的接口
        """
        func_name = "get_skipped_block_count"
        try:
            manager = UnifiedDataManager.get_data_manager(db_conn, task_type)
            return manager.get_skipped_block_count(start_year, end_year, *args, **kwargs)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return 0

    @staticmethod
    def get_attempted_block_count(db_conn, task_type: DlTaskType, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        统一获取已尝试下载的区块总数的接口
        """
        func_name = "get_attempted_block_count"
        try:
            manager = UnifiedDataManager.get_data_manager(db_conn, task_type)
            return manager.get_attempted_block_count(start_year, end_year, *args, **kwargs)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return 0

    @staticmethod
    def get_skipped_block_total_count(db_conn, task_type: DlTaskType, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        统一获取跳过区块总数的接口（兼容旧接口）
        """
        return UnifiedDataManager.get_skipped_block_count(db_conn, task_type, start_year, end_year, *args, **kwargs)

    @staticmethod
    def get_total_block_count(db_conn, task_type: DlTaskType, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        统一获取区块总数的接口
        """
        func_name = "get_total_block_count"
        try:
            manager = UnifiedDataManager.get_data_manager(db_conn, task_type)
            return manager.get_total_block_count(start_year, end_year, *args, **kwargs)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return 0

    @staticmethod
    def next_fixed_stock(db_conn, current_stock: Optional[str] = None) -> Optional[str]:
        """
        【对外标准接口】获取固定序列中的下一只股票
        :param current_stock: 当前股票代码，不传/传None → 返回序列第一只
        :return: 下一只股票代码 | None
        """

        try:
            manager = StockFixedSeqManager(db_conn)
            return manager.get_next_stock(current_stock)
        except Exception as e:
            logger.error(f"[{__name__}.next_fixed_stock] 调用失败: {str(e)}")
            return None

    @staticmethod
    def set_dl_pointer(db_conn, stock_id: str, time_frame: KLinePeriod, quarter: str) -> bool:
        """
        【对外标准接口】设置当前下载的区块信息（股票代码、时间周期、季度）
        Args:
            db_conn: 数据库连接
            stock_id: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            设置是否成功
        """
        func_name = "set_dl_pointer"
        try:
            dl_ctrl_manager = GlobalDlCtrlBlockManager(db_conn)
            result = dl_ctrl_manager.set_kline_dl_pointer(stock_id, quarter, time_frame)
            logger.debug(f"[{__name__}.{func_name}] 对外接口调用完成，返回结果: {result}")
            return result
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 对外接口调用失败: {str(e)}")
            return False

    @staticmethod
    def get_dl_pointer(db_conn) -> Optional[Tuple[str, str, KLinePeriod]]:
        """
        【对外标准接口】获取当前下载的区块信息（股票代码、时间周期、季度）
        :param db_conn: 数据库连接
        :return: 元组(downloading_quarter, downloading_stock_code, downloading_time_frame) | None
        """
        func_name = "get_dl_pointer"
        try:
            dl_ctrl_manager = GlobalDlCtrlBlockManager(db_conn)
            result = dl_ctrl_manager.get_kline_dl_pointer()
            logger.debug(f"[{__name__}.{func_name}] 对外接口调用完成，返回结果: {result}")
            if result:
                return result[0], result[1], result[2]
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 对外接口调用失败: {str(e)}")
            return None

    @staticmethod
    def get_all_active_stock_codes(db_conn) -> list:
        """
        通过stock_basic表获取所有活跃股票代码
        
        Args:
            db_conn: 数据库连接
        
        Returns:
            list: 所有活跃股票代码列表
        """
        func_name = "get_all_active_stock_codes"
        try:
            manager = BasicStockDataManager(db_conn)
            return manager.get_all_active_stock_codes()
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return []

    @staticmethod
    def get_stock_listing_date(db_conn, std_stock_code: str):
        """
        便捷调用BasicStockDataManager的get_stock_listing_date方法
        返回：(上市日期，退市日期)
        """
        return BasicStockDataManager(db_conn).get_stock_listing_date(std_stock_code)

    @staticmethod
    def get_stock_position(db_conn, stock_code: str) -> Optional[int]:
        """
        查询指定股票的顺序位置
        首只股票顺序位置为0，后面依次增加
        
        Args:
            db_conn: 数据库连接
            stock_code: 股票代码
            
        Returns:
            股票的顺序位置 | None（股票不存在）
        """
        func_name = "get_stock_position"
        try:
            manager = StockFixedSeqManager(db_conn)
            return manager.get_stock_position(stock_code)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return None
    
    @staticmethod
    def is_stock_in_fixed_seq(db_conn, stock_code: str) -> bool:
        """
        检查股票代码是否在固定顺序表中
        
        Args:
            db_conn: 数据库连接
            stock_code: 股票代码
            
        Returns:
            股票是否在固定顺序表中
        """
        func_name = "is_stock_in_fixed_seq"
        try:
            manager = StockFixedSeqManager(db_conn)
            return manager.stock_exists(stock_code)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return False
