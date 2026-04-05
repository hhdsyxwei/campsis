# dm_unified.py
from KitchenBase.download_enums import DlBlockStatus
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import KLinePeriod
from .dm_kline import KLineUnifiedQuarterlyExtendedManager
from .dm_stock_basic import BasicStockDataManager
from .dm_stock_seq import StockFixedSeqManager

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
            状态枚举值，BlockStatus.COMPLETED 或 BlockStatus.NOT_COMPLETED
        """
        func_name = "get_kline_block_status"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.get_kline_block_status(quarter, std_stock_code, time_frame)
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
            status: 状态，BlockStatus.COMPLETED 或 BlockStatus.NOT_COMPLETED
        """
        func_name = "update_kline_block_status"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.update_kline_block_status(quarter, std_stock_code, time_frame, status)
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
    def get_completed_block_total_count(db_conn, start_year: int, end_year: int, time_frame: KLinePeriod) -> int:
        """查询kline_block_status表中状态为completed的区块总数
        支持按年份范围过滤（仅匹配quarter字段中的年份部分）
        Args:
            db_conn: 数据库连接
            start_year: 可选，起始年份（如2024），不传则不限制起始年份
            end_year: 可选，结束年份（如2025），不传则不限制结束年份
            time_frame: 可选，时间周期，不传则不限制
        Returns:
            状态为completed的区块总数
        """
        func_name = "get_completed_block_total_count"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.get_completed_block_total_count(start_year, end_year, time_frame)
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
    def set_downloading_block(db_conn, stock_id: str, time_frame: KLinePeriod, quarter: str) -> bool:
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
        func_name = "set_downloading_block"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            result = manager.set_downloading_block(stock_id, time_frame, quarter)
            logger.debug(f"[{__name__}.{func_name}] 对外接口调用完成，返回结果: {result}")
            return result
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 对外接口调用失败: {str(e)}")
            return False

    @staticmethod
    def get_downloading_block(db_conn) -> Optional[Tuple[str, str, KLinePeriod]]:
        """
        【对外标准接口】获取当前下载的区块信息（股票代码、时间周期、季度）
        :param db_conn: 数据库连接
        :return: 元组(downloading_quarter, downloading_stock_code, downloading_time_frame) | None
        """
        func_name = "get_downloading_block"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            result = manager.get_downloading_block()
            logger.debug(f"[{__name__}.{func_name}] 对外接口调用完成，返回结果: {result}")
            return result
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
