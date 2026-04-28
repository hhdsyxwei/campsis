# xrxd_downloader.py
# 分红送配数据下载器，继承 BlockDownloader

import pandas as pd
from datetime import datetime
from typing import Optional, Tuple
from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
from KitchenBase.logger_config import get_logger
from KitchenBase.baostock_wrapper import query_dividend_data
from KitchenBase.block_pointer import BlockPointer
from Ingredient.DataNest import XrxdManager, BasicStockDataManager
from .core.abstract_downloader import BlockDownloader
from .core.download_parameters import DownloadParameters
from .core.abs_block_manager import BlockManager
from .core.abs_status_manager import TaskStatusManager
from .core.abs_pointer_manager import PointerManager
from .core.abs_progress_manager import ProgressManager

logger = get_logger(__name__)


class XrxdDownloader(BlockDownloader):
    """
    分红送配数据下载器，基于 BlockDownloader 实现
    通过区块管理和断点续传机制，解决 API 限流问题

    区块概念：
    - 一个区块代表一个股票在一个年份的数据
    - 区块排序规则：先按年份升序，同一年内按 stock_fixed_seq 表顺序
    """

    def __init__(self, db_conn, params: DownloadParameters):
        """
        初始化分红送配数据下载器

        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn, params)
        self.xrxd_manager = XrxdManager(db_conn)
        self.stock_manager = BasicStockDataManager(db_conn)
        self.support_block_status = True

    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识

        Returns:
            DlTaskType: 任务类型枚举值，用于数据库存储和识别
        """
        return DlTaskType.XRXD

    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return (PointerField.YEAR, PointerField.STOCK_CODE)

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
        from .pointer_managers import YearStockPtrMgr
        return YearStockPtrMgr(self.db_conn, self.get_task_type(), self.collection_manager)

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
            year = block_pointer.get_value(PointerField.YEAR)
            stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
            if not year or not stock_code:
                self.logger.error(f"无效的区块指针: {block_pointer}")
                return False

        return True

    def download_raw_data(self, params: DownloadParameters, **kwargs) -> Optional[pd.DataFrame]:
        """
        下载原始分红送配数据

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

        rs = query_dividend_data(
            code=stock_code,
            year=str(year),
            yearType="report"
        )

        if rs.error_code != "0":
            self.logger.warning(f"Baostock API错误: {rs.error_msg}")
            return None

        df = rs.get_data()
        if df.empty:
            self.logger.debug(f"无数据: {stock_code} {year}")
            return None

        return df

    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗分红送配数据

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
            "dividPreNoticeDate": "xrxd_pre_notice_date",
            "dividAgmPumDate": "xrxd_agm_pum_date",
            "dividPlanAnnounceDate": "xrxd_plan_announce_date",
            "dividPlanDate": "xrxd_plan_date",
            "dividRegistDate": "xrxd_regist_date",
            "dividOperateDate": "xrxd_operate_date",
            "dividPayDate": "xrxd_pay_date",
            "dividStockMarketDate": "xrxd_stock_market_date",
            "dividCashPsBeforeTax": "xrxd_cash_ps_before_tax",
            "dividCashPsAfterTax": "xrxd_cash_ps_after_tax",
            "dividStocksPs": "xrxd_stocks_ps",
            "dividCashStock": "xrxd_cash_stock",
            "dividReserveToStockPs": "xrxd_reserve_to_stock_ps"
        }, inplace=True)

        date_cols = [
            "xrxd_pre_notice_date", "xrxd_agm_pum_date", "xrxd_plan_announce_date",
            "xrxd_plan_date", "xrxd_regist_date", "xrxd_operate_date",
            "xrxd_pay_date", "xrxd_stock_market_date"
        ]

        for col in date_cols:
            if col in df.columns:
                df[col] = df[col].replace('', pd.NA)
                df[col] = pd.to_datetime(df[col], errors='coerce')
                df[col] = df[col].where(df[col].notna(), None)

        numeric_cols = [
            "xrxd_cash_ps_before_tax", "xrxd_cash_ps_after_tax",
            "xrxd_stocks_ps", "xrxd_reserve_to_stock_ps"
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].replace('', pd.NA)
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df[col] = df[col].where(df[col].notna(), None)

        string_cols = [("xrxd_cash_stock", 200)]
        for col, max_len in string_cols:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: None if pd.isna(x) or str(x).strip() == '' else str(x)[:max_len]
                )

        return df

    def save_data(self, data: pd.DataFrame, params: DownloadParameters, **kwargs) -> bool:
        """
        保存分红送配数据到数据库

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
        year = block_pointer.get_value(PointerField.YEAR)

        data["std_stock_code"] = stock_code
        data["xrxd_year"] = year

        ok = self.xrxd_manager.save_xrxd_data(data)
        if not ok:
            self.logger.error(f"数据保存失败: {stock_code} {year}")
            return False

        return True


def continue_download_xrxd(db_conn, params: DownloadParameters) -> bool:
    """
    【全局唯一对外接口】继续下载分红送配数据（支持断点续传）

    功能说明：
    - 从上次中断的位置继续下载分红送配数据
    - 支持断点续传，自动恢复下载进度
    - 按照年份和股票代码的顺序下载数据
    - 自动处理下载过程中的异常

    下载流程：
    1. 检查下载状态（未开始、进行中、已完成）
    2. 计算总区块数
    3. 优先恢复中断的下载区块
    4. 按顺序下载所有区块
    5. 完成后清空下载指针

    :param db_conn: 使用者创建的数据库连接
    :param params: 下载参数
    """
    downloader = XrxdDownloader(db_conn, params)
    return downloader.continue_download(params)

def start_new_xrxd_download(db_conn, params: DownloadParameters) -> bool:
    """
    【全局唯一对外接口】开始新的分红送配数据下载任务（清空之前的下载进度）

    功能说明：
    - 清空之前的下载进度记录
    - 从头开始下载指定年份范围的分红送配数据
    - 按照年份和股票代码的顺序下载数据
    - 自动处理下载过程中的异常

    下载流程：
    1. 删除之前的任务记录
    2. 调用继续下载方法开始新的下载任务
    3. 按照年份和股票代码的顺序下载所有区块
    4. 完成后清空下载指针

    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（包含，默认当前年份）
    :param stock_codes: 股票代码列表，可选
    :return: True 表示全部下载完成， False 表示未完成
    """

    downloader = XrxdDownloader(db_conn, params)
    return downloader.start_new_download(params)