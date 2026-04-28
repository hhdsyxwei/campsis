# kline_unified_downloader.py
# K线数据下载器，继承 BlockDownloader

from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from KitchenBase.baostock_wrapper import query_history_k_data_plus
from KitchenBase.baostock_wrapper import BaostockWrapper as bsw
from Ingredient.DataNest import UnifiedDataManager as dm
from Ingredient.downloader.core.abstract_downloader import BlockDownloader
from Ingredient.downloader.core.download_parameters import DownloadParameters
from Ingredient.downloader.core.abs_block_manager import BlockManager
from Ingredient.downloader.core.abs_status_manager import TaskStatusManager
from Ingredient.downloader.core.abs_pointer_manager import PointerManager
from Ingredient.downloader.core.abs_progress_manager import ProgressManager
from KitchenBase.stock_enums import KLinePeriod

logger = get_logger(__name__)
BLOCK_COMPLETED = DlBlockStatus.COMPLETED

class KLineDownloader(BlockDownloader):
    """
    K线数据下载器，基于 BlockDownloader 实现
    通过区块管理和断点续传机制，解决 API 限流问题

    区块概念：
    - 一个区块代表一个股票在一个时间周期下一个季度的数据
    - 区块排序规则：先按股票代码升序，再按时间周期，最后按季度升序
    """

    def __init__(self, db_conn, params: DownloadParameters):
        """
        初始化K线数据下载器

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
        return DlTaskType.KLINE

    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return (PointerField.STOCK_CODE, PointerField.TIME_FRAME, PointerField.QUARTER)

    def create_block_manager(self) -> BlockManager:
        """
        创建区块管理器

        Returns:
            BlockManager: 区块管理器实例
        """
        from .block_managers.stock_tm_qtr_blk_mgr import StockTmQtrBlkMgr
        return StockTmQtrBlkMgr(self.db_conn, self.get_task_type())

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
        from .pointer_managers.stock_tm_qtr_ptr_mgr import StockTimeFrameQuarterPtrMgr
        return StockTimeFrameQuarterPtrMgr(self.db_conn, self.get_task_type())

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
            **kwargs: 额外参数

        Returns:
            bool: 参数是否有效
        """
        if params.start_year >= params.end_year:
            self.logger.error(f"无效年份范围: start_year ({params.start_year}) 必须小于 end_year ({params.end_year})")
            return False

        block_pointer = kwargs.get('block_pointer')
        if block_pointer:
            stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
            time_frame = block_pointer.get_value(PointerField.TIME_FRAME)
            quarter = block_pointer.get_value(PointerField.QUARTER)
            if not stock_code or not time_frame or not quarter:
                self.logger.error(f"无效的区块指针: {block_pointer}")
                return False

        return True

    def download_raw_data(self, params: DownloadParameters, **kwargs) -> Optional[pd.DataFrame]:
        """
        下载原始K线数据

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
        time_frame_str = block_pointer.get_value(PointerField.TIME_FRAME)
        quarter = block_pointer.get_value(PointerField.QUARTER)

        s_date, e_date = self._quarter_to_date_range(quarter)

        is_ok, real_s, real_e = self._is_time_range_overlap_with_listing_period(stock_code, s_date, e_date)
        if not is_ok or not real_s or not real_e:
            self.logger.debug(f"无有效数据，标记跳过: {stock_code} {quarter}")
            return pd.DataFrame()

        time_frame = next((tf for tf in KLinePeriod if tf.value == time_frame_str), None)
        if not time_frame:
            self.logger.error(f"无效的时间周期: {time_frame_str}")
            return None

        self.logger.debug(f"下载: {stock_code} {real_s} ~ {real_e} {time_frame.value}")
        freq = bsw.convert_kline_period_to_baostock_freq(time_frame)
        res = query_history_k_data_plus(
            code=stock_code,
            fields="date,open,high,low,close,volume,amount",
            start_date=real_s,
            end_date=real_e,
            frequency=freq,
            adjustflag="3"
        )

        if res.error_code != "0":
            raise Exception(f"baostock下载失败 {stock_code} {quarter}: {res.error_msg}")

        return res.get_data()

    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗K线数据

        Args:
            raw_data: 原始数据

        Returns:
            pd.DataFrame: 清洗后的数据
        """
        if raw_data is None or raw_data.empty:
            self.logger.warning("原始数据为空")
            return pd.DataFrame()

        df = raw_data.copy()
        df.rename(columns={
            "date": "timestamp",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price",
            "volume": "volume",
            "amount": "turnover"
        }, inplace=True)

        df["timestamp"] = pd.to_datetime(df["timestamp"])

        numeric_cols = ["open_price", "high_price", "low_price", "close_price", "volume", "turnover"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        price_cols = ["open_price", "high_price", "low_price", "close_price", "turnover"]
        for col in price_cols:
            df[col] = df[col].astype("Float64")

        df["volume"] = df["volume"].fillna(0).astype("Int64")

        df = df.dropna(subset=["timestamp"])
        return df

    def save_data(self, data: pd.DataFrame, params: DownloadParameters, **kwargs) -> bool:
        """
        保存K线数据到数据库

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
        time_frame = block_pointer.get_value(PointerField.TIME_FRAME)  # 提取时间周期

        # 添加 time_frame 列到 DataFrame
        data = data.copy()
        data['time_frame'] = time_frame  # 添加时间周期列

        ok = dm.save_kline_data_unified(self.db_conn, stock_code, data)
        if not ok:
            raise Exception(f"数据保存失败: {stock_code}")

        return True

    def _quarter_to_date_range(self, quarter: str) -> Tuple[str, str]:
        """
        季度转起止日期

        Args:
            quarter: 季度字符串，格式如 '2024-Q1'

        Returns:
            Tuple[str, str]: (开始日期, 结束日期)
        """
        year, q = quarter.split("-Q")
        q = int(q)
        mapping = {
            1: (f"{year}-01-01", f"{year}-03-31"),
            2: (f"{year}-04-01", f"{year}-06-30"),
            3: (f"{year}-07-01", f"{year}-09-30"),
            4: (f"{year}-10-01", f"{year}-12-31"),
        }
        if q not in mapping:
            raise ValueError(f"无效季度: {quarter}")
        return mapping[q]

    def _is_time_range_overlap_with_listing_period(
        self, std_stock_code: str, start_date: str, end_date: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        上市时间校验

        Args:
            std_stock_code: 股票代码
            start_date: 请求开始日期
            end_date: 请求结束日期

        Returns:
            Tuple[bool, Optional[str], Optional[str]]: (是否有效, 实际开始日期, 实际结束日期)
        """
        listing_date, delist_date = dm.get_stock_listing_date(self.db_conn, std_stock_code)

        if not listing_date:
            self.logger.debug(f"{std_stock_code} 无上市日期，跳过")
            return False, None, None

        req_s = datetime.strptime(start_date, "%Y-%m-%d")
        req_e = datetime.strptime(end_date, "%Y-%m-%d")
        list_dt = datetime.strptime(listing_date, "%Y-%m-%d")
        delist_dt = datetime.strptime(delist_date, "%Y-%m-%d") if delist_date else None

        if delist_dt and delist_dt < req_s:
            return False, None, None
        if list_dt > req_e:
            return False, None, None

        real_s = max(list_dt, req_s).strftime("%Y-%m-%d")
        real_e = min(delist_dt, req_e).strftime("%Y-%m-%d") if delist_dt else req_e.strftime("%Y-%m-%d")
        return True, real_s, real_e


def continue_download_kline(db_conn, params: DownloadParameters, **kwargs) -> bool:
    """
    【全局唯一对外接口】继续下载K线数据（支持断点续传）

    功能说明：
    - 从上次中断的位置继续下载K线数据
    - 支持断点续传，自动恢复下载进度
    - 按照股票代码、时间周期、季度的顺序下载数据
    - 自动处理下载过程中的异常

    下载流程：
    1. 检查下载状态（未开始、进行中、已完成）
    2. 计算总区块数
    3. 优先恢复中断的下载区块
    4. 按顺序下载所有区块
    5. 完成后清空下载指针

    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（不包含）
    :param stock_codes: 股票代码列表，可选
    :return: True 表示全部下载完成，False 表示未完成
    """
    downloader = KLineDownloader(db_conn, params)
    return downloader.continue_download(params, **kwargs)


def start_new_kline_download(db_conn, params: DownloadParameters, **kwargs) -> bool:
    """
    【全局唯一对外接口】开始新的K线数据下载任务（清空之前的下载进度）

    功能说明：
    - 清空之前的下载进度记录
    - 从头开始下载指定年份范围的K线数据
    - 按照股票代码、时间周期、季度的顺序下载数据
    - 自动处理下载过程中的异常

    下载流程：
    1. 删除之前的任务记录
    2. 调用继续下载方法开始新的下载任务
    3. 按照股票代码、时间周期、季度的顺序下载所有区块
    4. 完成后清空下载指针

    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（不包含）
    :param stock_codes: 股票代码列表，可选
    :return: True 表示全部下载完成，False 表示未完成
    """
    downloader = KLineDownloader(db_conn, params)
    return downloader.start_new_download(params, **kwargs)
