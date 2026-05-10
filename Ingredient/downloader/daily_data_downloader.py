# daily_data_downloader.py
# 日线数据下载器，基于 BlockDownloader 实现

from datetime import datetime
import pandas as pd
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from KitchenBase.baostock_wrapper import query_history_k_data_plus
from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
from KitchenBase import DownloadParameters
from Ingredient.DataNest import DailyDataManager
from Ingredient.downloader.core.abstract_downloader import BlockDownloader
from Ingredient.downloader.core.abs_block_manager import BlockManager
from Ingredient.downloader.core.abs_status_manager import TaskStatusManager
from Ingredient.downloader.core.abs_pointer_manager import PointerManager
from Ingredient.downloader.core.abs_progress_manager import ProgressManager
from Ingredient.DataNest.dm_standard_columns import StockDailyStandardColumns

logger = get_logger(__name__)


class BaoStockApiColumns:
    """baostock API 原始列名（下载器内部使用）"""
    DATE = "date"
    CODE = "code"
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    VOLUME = "volume"
    AMOUNT = "amount"
    ADJUSTFLAG = "adjustflag"
    TURN = "turn"
    TRADESTATUS = "tradestatus"
    PCTCHG = "pctChg"
    PE_TTM = "peTTM"
    PB_MRQ = "pbMRQ"
    PS_TTM = "psTTM"
    PCF_NCF_TTM = "pcfNcfTtm"
    IS_ST = "isST"
    
    # API 查询字段字符串
    FIELDS = ",".join([
        DATE, CODE, OPEN, HIGH, LOW, CLOSE, VOLUME, AMOUNT,
        ADJUSTFLAG, TURN, TRADESTATUS, PCTCHG, PE_TTM, PB_MRQ,
        PS_TTM, PCF_NCF_TTM, IS_ST
    ])


# API → 内部标准的映射（只在下载器内部使用）
BAOSTOCK_TO_STANDARD = {
    BaoStockApiColumns.DATE: StockDailyStandardColumns.TRADE_DATE,
    BaoStockApiColumns.OPEN: StockDailyStandardColumns.OPEN,
    BaoStockApiColumns.HIGH: StockDailyStandardColumns.HIGH,
    BaoStockApiColumns.LOW: StockDailyStandardColumns.LOW,
    BaoStockApiColumns.CLOSE: StockDailyStandardColumns.CLOSE,
    BaoStockApiColumns.VOLUME: StockDailyStandardColumns.VOLUME,
    BaoStockApiColumns.AMOUNT: StockDailyStandardColumns.AMOUNT,
    BaoStockApiColumns.TURN: StockDailyStandardColumns.TURNOVER_RATE,
    BaoStockApiColumns.PCTCHG: StockDailyStandardColumns.CHANGE_RATE,
    BaoStockApiColumns.PE_TTM: StockDailyStandardColumns.PE,
    BaoStockApiColumns.PB_MRQ: StockDailyStandardColumns.PB,
    BaoStockApiColumns.PS_TTM: StockDailyStandardColumns.PS,
    BaoStockApiColumns.PCF_NCF_TTM: StockDailyStandardColumns.PCF,
    BaoStockApiColumns.ADJUSTFLAG: StockDailyStandardColumns.ADJUST_FLAG,
    BaoStockApiColumns.TRADESTATUS: StockDailyStandardColumns.TRADE_STATUS,
    BaoStockApiColumns.IS_ST: StockDailyStandardColumns.IS_ST,
}


class DailyDataDownloader(BlockDownloader):
    """
    日线数据下载器，基于 BlockDownloader 实现
    
    区块定义：
    - 每个区块 = 一只股票 + 一个年份的数据
    - 指针字段：STOCK_CODE, YEAR
    """

    def __init__(self, db_conn, params: DownloadParameters):
        """
        初始化日线数据下载器

        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn, params)
        self.support_block_status = True

    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识

        Returns:
            DlTaskType: 任务类型枚举值，用于数据库存储和识别
        """
        return DlTaskType.DAILY

    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return (PointerField.STOCK_CODE, PointerField.YEAR)

    def create_block_manager(self) -> BlockManager:
        """
        创建区块管理器

        Returns:
            BlockManager: 区块管理器实例
        """
        from .block_managers.year_stock_blk_mgr import YearStockBlkMgr
        return YearStockBlkMgr(self.db_conn, self.get_task_type(), self.collection_manager)

    def create_status_manager(self) -> TaskStatusManager:
        """
        创建状态管理器

        Returns:
            TaskStatusManager: 状态管理器实例
        """
        from .status_managers.generic_status_manager import GenericStatusManager
        return GenericStatusManager(self.db_conn)

    def create_pointer_manager(self) -> PointerManager:
        """
        创建指针管理器

        Returns:
            PointerManager: 指针管理器实例
        """
        from .pointer_managers.stock_year_ptr_mgr import StockYearPtrMgr
        return StockYearPtrMgr(self.db_conn, self.get_task_type(), self.collection_manager)

    def create_progress_manager(self) -> ProgressManager:
        """
        创建进度管理器

        Returns:
            ProgressManager: 进度管理器实例
        """
        from .progress_managers.generic_progress_manager import GenericProgressManager
        return GenericProgressManager(self.db_conn)

    def validate_parameters(self, params: DownloadParameters, **kwargs) -> bool:
        """
        验证参数有效性

        Args:
            params: 下载参数
            **kwargs: 额外参数，包含 block_pointer

        Returns:
            bool: 参数是否有效
        """
        if params.start_year >= params.end_year:
            self.logger.error(f"无效年份范围: start_year ({params.start_year}) 必须小于 end_year ({params.end_year})")
            return False

        block_pointer = kwargs.get('block_pointer')
        if block_pointer:
            stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
            year = block_pointer.get_value(PointerField.YEAR)
            if not stock_code or year is None:
                self.logger.error(f"无效的区块指针: {block_pointer}")
                return False

        return True

    def download_raw_data(self, params: DownloadParameters, **kwargs) -> Optional[pd.DataFrame]:
        """
        下载原始日线数据

        Args:
            params: 下载参数
            **kwargs: 额外参数，包含 block_pointer

        Returns:
            Optional[pd.DataFrame]: 原始数据
        """
        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error("缺少区块指针")
            return None

        stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
        year = block_pointer.get_value(PointerField.YEAR)

        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"

        parts = stock_code.split('.')
        if len(parts) != 2:
            self.logger.warning(f"股票代码格式错误: {stock_code}")
            return pd.DataFrame()

        symbol, market = parts
        market_map = {'SH': 'sh', 'SZ': 'sz'}
        bs_code = f"{market_map.get(market.upper(), market)}.{symbol}"

        self.logger.debug(f"下载日线数据: {stock_code} ({bs_code}) {start_date} ~ {end_date}")

        rs = query_history_k_data_plus(
            bs_code,
            BaoStockApiColumns.FIELDS,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="3"
        )

        if rs is None:
            self.logger.warning(f"获取 {bs_code} 数据超时或发生错误，返回结果为 None。")
            return pd.DataFrame()

        self.logger.debug(f"查询 {bs_code} 日线数据结果: {rs.error_code} - {rs.error_msg}")
        if rs.error_code != '0':
            self.logger.warning(f"获取 {bs_code} 数据失败: {rs.error_msg}")
            return pd.DataFrame()

        data_list = []
        while rs.next():
            data_list.append(rs.get_row_data())

        if not data_list:
            self.logger.info(f"股票 {stock_code} 在 {year} 年无数据")
            return pd.DataFrame()

        return pd.DataFrame(data_list, columns=rs.fields)

    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗日线数据

        Args:
            raw_data: 原始数据

        Returns:
            pd.DataFrame: 清洗后的数据
        """
        if raw_data is None or raw_data.empty:
            self.logger.warning("原始数据为空")
            return pd.DataFrame()

        df = raw_data.copy()

        # 1. 使用下载器内部 API 列名进行处理
        df[BaoStockApiColumns.DATE] = pd.to_datetime(df[BaoStockApiColumns.DATE])
        numeric_columns = [
            BaoStockApiColumns.OPEN, BaoStockApiColumns.HIGH, BaoStockApiColumns.LOW,
            BaoStockApiColumns.CLOSE, BaoStockApiColumns.VOLUME, BaoStockApiColumns.AMOUNT,
            BaoStockApiColumns.TURN, BaoStockApiColumns.PCTCHG,
            BaoStockApiColumns.PE_TTM, BaoStockApiColumns.PB_MRQ,
            BaoStockApiColumns.PS_TTM, BaoStockApiColumns.PCF_NCF_TTM
        ]
        for col in numeric_columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 2. 关键步骤：转换为内部标准列名
        df = df.rename(columns=BAOSTOCK_TO_STANDARD)

        # 3. 后续处理使用内部标准列名
        df[StockDailyStandardColumns.PRE_CLOSE] = df[StockDailyStandardColumns.CLOSE].shift(1)

        # 处理 NaN 值
        for col in [
            StockDailyStandardColumns.OPEN, StockDailyStandardColumns.HIGH, StockDailyStandardColumns.LOW,
            StockDailyStandardColumns.CLOSE, StockDailyStandardColumns.VOLUME, StockDailyStandardColumns.AMOUNT,
            StockDailyStandardColumns.TURNOVER_RATE, StockDailyStandardColumns.CHANGE_RATE,
            StockDailyStandardColumns.PE, StockDailyStandardColumns.PB, StockDailyStandardColumns.PS, StockDailyStandardColumns.PCF,
            StockDailyStandardColumns.PRE_CLOSE
        ]:
            if col in df.columns:
                df[col] = df[col].where(pd.notna(df[col]), None)

        # 4. 只保留内部标准列
        final_columns = [
            StockDailyStandardColumns.TRADE_DATE,
            StockDailyStandardColumns.OPEN,
            StockDailyStandardColumns.HIGH,
            StockDailyStandardColumns.LOW,
            StockDailyStandardColumns.CLOSE,
            StockDailyStandardColumns.VOLUME,
            StockDailyStandardColumns.AMOUNT,
            StockDailyStandardColumns.TURNOVER_RATE,
            StockDailyStandardColumns.CHANGE_RATE,
            StockDailyStandardColumns.PE,
            StockDailyStandardColumns.PB,
            StockDailyStandardColumns.PS,
            StockDailyStandardColumns.PCF,
            StockDailyStandardColumns.ADJUST_FLAG,
            StockDailyStandardColumns.TRADE_STATUS,
            StockDailyStandardColumns.IS_ST,
            StockDailyStandardColumns.PRE_CLOSE
        ]
        df = df[final_columns]

        return df

    def save_data(self, data: pd.DataFrame, params: DownloadParameters, **kwargs) -> bool:
        """
        保存日线数据到数据库

        Args:
            data: 清洗后的数据
            params: 下载参数
            **kwargs: 额外参数，包含 block_pointer

        Returns:
            bool: 保存是否成功
        """
        if data.empty:
            self.logger.warning("无数据可保存")
            return True

        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error("缺少区块指针")
            return False

        stock_code = block_pointer.get_value(PointerField.STOCK_CODE)

        manager = DailyDataManager(self.db_conn)
        success = manager.save_daily_data(stock_code, data)
        if not success:
            self.logger.warning(f"保存 {stock_code} 的数据到数据库失败。")

        return success


def continue_download_daily(db_conn, params: DownloadParameters) -> bool:
    """
    继续下载日线数据（支持断点续传）

    Args:
        db_conn: 数据库连接对象
        params: 下载参数

    Returns:
        bool: 是否下载完成
    """
    downloader = DailyDataDownloader(db_conn, params)
    return downloader.continue_download(params)


def start_new_daily_download(db_conn, params: DownloadParameters) -> bool:
    """
    开始新的日线数据下载任务（清空之前的下载进度）

    Args:
        db_conn: 数据库连接对象
        params: 下载参数

    Returns:
        bool: 是否下载完成
    """
    downloader = DailyDataDownloader(db_conn, params)
    return downloader.start_new_download(params)