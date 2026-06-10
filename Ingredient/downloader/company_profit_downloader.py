# stock_profit_downloader.py
# 股票利润数据下载器


import pandas as pd
import time
import os
from datetime import date
from typing import Tuple, Optional
from KitchenBase import DownloadParameters
from KitchenBase.logger_config import get_logger
from KitchenBase.download_utils import convert_to_baostock_code,convert_baostock_code
from Ingredient.downloader.progress_managers.generic_progress_manager import GenericProgressManager
from .core.abstract_downloader import BlockDownloader
from .block_managers.generic_block_manager import GenericBlockManager
from .status_managers.generic_status_manager import GenericStatusManager
from .pointer_managers.generic_pointer_manager import GenericPointerManager
from Ingredient.DataNest import CompanyProfitManager, BasicStockDataManager
from Ingredient.DataNest.dm_standard_columns import CompanyProfitStandardColumns
from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
from KitchenBase.baostock_wrapper import query_profit_data
from Ingredient.downloader.pointer_managers import QuarterStockPtrMgr
from Ingredient.downloader.block_managers.quarter_stock_blk_mgr import QuarterStockBlkMgr

# ===================== 全局日志记录器 =====================
logger = get_logger(__name__)


QUARTER_ENDS = {
    1: (3, 31),
    2: (6, 30),
    3: (9, 30),
    4: (12, 31),
}

class BaoStockProfitApiColumns:
    """baostock API 利润数据原始列名（下载器内部使用）"""
    CODE = "code"
    PUB_DATE = "pubDate"
    STAT_DATE = "statDate"
    ROE_AVG = "roeAvg"
    NP_MARGIN = "npMargin"
    GP_MARGIN = "gpMargin"
    NET_PROFIT = "netProfit"
    EPS_TTM = "epsTTM"
    MB_REVENUE = "MBRevenue"
    TOTAL_SHARE = "totalShare"
    LIQA_SHARE = "liqaShare"

# API → 内部标准的映射（只在下载器内部使用）
BAOSTOCK_PROFIT_TO_STANDARD = {
    BaoStockProfitApiColumns.CODE: CompanyProfitStandardColumns.STD_STOCK_CODE,
    BaoStockProfitApiColumns.PUB_DATE: CompanyProfitStandardColumns.PUB_DATE,
    BaoStockProfitApiColumns.STAT_DATE: CompanyProfitStandardColumns.STAT_DATE,
    BaoStockProfitApiColumns.ROE_AVG: CompanyProfitStandardColumns.ROE_AVG,
    BaoStockProfitApiColumns.NP_MARGIN: CompanyProfitStandardColumns.NP_MARGIN,
    BaoStockProfitApiColumns.GP_MARGIN: CompanyProfitStandardColumns.GP_MARGIN,
    BaoStockProfitApiColumns.NET_PROFIT: CompanyProfitStandardColumns.NET_PROFIT,
    BaoStockProfitApiColumns.EPS_TTM: CompanyProfitStandardColumns.EPS_TTM,
    BaoStockProfitApiColumns.MB_REVENUE: CompanyProfitStandardColumns.MB_REVENUE,
    BaoStockProfitApiColumns.TOTAL_SHARE: CompanyProfitStandardColumns.TOTAL_SHARE,
    BaoStockProfitApiColumns.LIQA_SHARE: CompanyProfitStandardColumns.LIQA_SHARE,
}


class StockProfitDownloader(BlockDownloader):
    """
    股票利润数据下载器，基于 BlockDownloader 实现
    通过区块管理和断点续传机制，解决 API 限流问题
    """

    def __init__(self, db_conn, params: DownloadParameters):
        """
        初始化股票利润数据下载器
        
        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn, params)
        self.profit_manager = CompanyProfitManager(db_conn)
        self.stock_manager = BasicStockDataManager(db_conn)
        self.support_block_status = True
        self.logger = logger
    
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识
        """
        return DlTaskType.COMPANY_PROFIT
    
    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段
        
        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return (PointerField.QUARTER, PointerField.STOCK_CODE)
    
    def validate_parameters(self, params: DownloadParameters, **kwargs) -> bool:
        """
        验证参数有效性
        """
        # 年份合法性校验
        if not isinstance(params.start_year, int) or not isinstance(params.end_year, int):
            self.logger.error("年份必须为整数类型")
            return False
        if params.start_year <= 0 or params.end_year <= 0:
            self.logger.error("年份必须为正整数")
            return False
        if params.start_year >= params.end_year:
            self.logger.error(f"年份范围异常：start_year({params.start_year}) >= end_year({params.end_year})")
            return False
        return True
    
    def create_block_manager(self) -> GenericBlockManager:
        """
        创建区块管理器
        """
        return QuarterStockBlkMgr(self.db_conn, self.get_task_type(), self.collection_manager)
    
    def create_status_manager(self) -> GenericStatusManager:
        """
        创建状态管理器
        """
        return GenericStatusManager(self.db_conn)
    
    def create_pointer_manager(self) -> GenericPointerManager:
        """
        创建指针管理器
        """
        # 这里可以使用通用的指针管理器实现
        return QuarterStockPtrMgr(self.db_conn, self.get_task_type(), self.collection_manager)
    
    def create_progress_manager(self) -> GenericProgressManager:
        """
        创建进度管理器
        """
        return GenericProgressManager(self.db_conn)
    
    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗数据
        """
        if raw_data is None or raw_data.empty:
            self.logger.warning("原始数据为空")
            return pd.DataFrame()
        
        try:
            # 复制数据避免修改原数据
            df = raw_data.copy()
            
            # 1. 格式转换 - 使用 API 列名
            # 转换日期格式
            if BaoStockProfitApiColumns.PUB_DATE in df.columns:
                df[BaoStockProfitApiColumns.PUB_DATE] = pd.to_datetime(df[BaoStockProfitApiColumns.PUB_DATE], errors='coerce')
                df[BaoStockProfitApiColumns.PUB_DATE] = df[BaoStockProfitApiColumns.PUB_DATE].dt.strftime('%Y-%m-%d') if not df[BaoStockProfitApiColumns.PUB_DATE].isna().all() else df[BaoStockProfitApiColumns.PUB_DATE]
            if BaoStockProfitApiColumns.STAT_DATE in df.columns:
                df[BaoStockProfitApiColumns.STAT_DATE] = pd.to_datetime(df[BaoStockProfitApiColumns.STAT_DATE], errors='coerce')
                df[BaoStockProfitApiColumns.STAT_DATE] = df[BaoStockProfitApiColumns.STAT_DATE].dt.strftime('%Y-%m-%d') if not df[BaoStockProfitApiColumns.STAT_DATE].isna().all() else df[BaoStockProfitApiColumns.STAT_DATE]
            
            # 转换数值类型
            numeric_fields = [
                BaoStockProfitApiColumns.ROE_AVG,
                BaoStockProfitApiColumns.NP_MARGIN,
                BaoStockProfitApiColumns.GP_MARGIN,
                BaoStockProfitApiColumns.NET_PROFIT,
                BaoStockProfitApiColumns.EPS_TTM,
                BaoStockProfitApiColumns.MB_REVENUE,
                BaoStockProfitApiColumns.TOTAL_SHARE,
                BaoStockProfitApiColumns.LIQA_SHARE
            ]
            for field in numeric_fields:
                if field in df.columns:
                    df[field] = pd.to_numeric(df[field], errors='coerce')

            # 2. 关键步骤：转换为内部标准列名
            df = df.rename(columns=BAOSTOCK_PROFIT_TO_STANDARD)

            # 2.1 转换股票代码格式（baostock -> 标准）
            df[CompanyProfitStandardColumns.STD_STOCK_CODE] = df[CompanyProfitStandardColumns.STD_STOCK_CODE].apply(
                lambda x: convert_baostock_code(x) if pd.notna(x) else x
            )

            # 3. 空值处理 - 使用标准列名
            df = df.dropna(subset=[CompanyProfitStandardColumns.STD_STOCK_CODE, CompanyProfitStandardColumns.STAT_DATE])

            # 4. 去重 - 使用标准列名
            df = df.drop_duplicates(subset=[CompanyProfitStandardColumns.STD_STOCK_CODE, CompanyProfitStandardColumns.STAT_DATE], keep='last')

            # 5. 只保留标准列（包含 std_stock_code 方便调试）
            final_columns = [
                CompanyProfitStandardColumns.STD_STOCK_CODE,
                CompanyProfitStandardColumns.PUB_DATE,
                CompanyProfitStandardColumns.STAT_DATE,
                CompanyProfitStandardColumns.ROE_AVG,
                CompanyProfitStandardColumns.NP_MARGIN,
                CompanyProfitStandardColumns.GP_MARGIN,
                CompanyProfitStandardColumns.NET_PROFIT,
                CompanyProfitStandardColumns.EPS_TTM,
                CompanyProfitStandardColumns.MB_REVENUE,
                CompanyProfitStandardColumns.TOTAL_SHARE,
                CompanyProfitStandardColumns.LIQA_SHARE
            ]
            df = df[final_columns]
            
            self.logger.info(f"数据清洗完成，有效数据 {len(df)} 条")
            return df
        except Exception as e:
            self.logger.error(f"清洗利润数据异常：{e}", exc_info=True)
            return pd.DataFrame()

    def _is_future_quarter(self, year: int, quarter: int) -> bool:
        month, day = QUARTER_ENDS[quarter]
        return date(year, month, day) > date.today()
    
    def download_raw_data(self, params: DownloadParameters, **kwargs) -> pd.DataFrame:
        """
        下载原始数据
        
        Args:
            params: 下载参数
            **kwargs: 包含 block_pointer 等参数
            
        Returns:
            pd.DataFrame: 原始数据
        """
        # 从 kwargs 中获取 block_pointer
        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error("缺少 block_pointer 参数")
            return pd.DataFrame()
        
        # 解包 block_pointer
        stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
        quarter_str = block_pointer.get_value(PointerField.QUARTER)
        
        if not stock_code or not quarter_str:
            self.logger.error("block_pointer 缺少必要字段")
            return pd.DataFrame()

        bs_stock_code = convert_to_baostock_code(stock_code)
        if not bs_stock_code:
            self.logger.error(f"转换股票代码失败：{stock_code}")
            return pd.DataFrame()

        # 从 quarter 字段中提取年份和季度
        try:
            year_str, quarter_str = quarter_str.split('-Q')
            year = int(year_str)
            quarter = int(quarter_str)
        except ValueError:
            self.logger.error(f"quarter 字段格式错误：{quarter_str}，应为 'YYYY-QN' 格式")
            return pd.DataFrame()
        
        if quarter not in QUARTER_ENDS:
            raise ValueError(f"季度值非法：{quarter}")

        if self._is_future_quarter(year, quarter):
            self.logger.info(f"跳过未来季度：{stock_code} {year}年Q{quarter}")
            return pd.DataFrame()

        api_timeout = int(os.getenv("CAMPSIS_BAOSTOCK_FINANCE_TIMEOUT", "60"))
        api_max_retry = int(os.getenv("CAMPSIS_BAOSTOCK_FINANCE_RETRY", "3"))
        request_interval = float(os.getenv("CAMPSIS_BAOSTOCK_FINANCE_SLEEP", "0.35"))

        try:
            rs = query_profit_data(
                code=bs_stock_code,
                year=year,
                quarter=quarter,
                timeout=api_timeout,
                max_retry=api_max_retry,
            )

            # 处理返回结果
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    # 转换为 DataFrame
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    self.logger.info(f"利润数据下载完成：{stock_code} {year}年Q{quarter}，共 {len(df)} 条数据")
                    return df
                else:
                    self.logger.warning(f"无利润数据：{stock_code} {year}年Q{quarter}")
                    return pd.DataFrame()
            else:
                raise RuntimeError(
                    f"API 调用失败：{stock_code} {year}年Q{quarter} - "
                    f"{rs.error_code}=={rs.error_msg}"
                )
        except Exception as e:
            self.logger.error(f"下载异常：{stock_code} {year}年Q{quarter} - {str(e)}", exc_info=True)
            raise
        finally:
            time.sleep(request_interval)
    
    def save_data(self, data: pd.DataFrame, params: DownloadParameters, **kwargs) -> bool:
        """
        保存数据
        
        Args:
            data: 清洗后的数据
            params: 下载参数
            **kwargs: 包含 block_pointer 等参数
            
        Returns:
            bool: 是否保存成功
        """
        func_name = "save_data"
        self.logger.debug(f"[{__name__}.{func_name}] 方法开始执行 | data行数: {len(data) if data is not None else 0}")
        
        # 从 kwargs 中获取 block_pointer
        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error(f"[{__name__}.{func_name}] 缺少 block_pointer 参数")
            return False
        
        # 解包 block_pointer
        stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
        quarter_str = block_pointer.get_value(PointerField.QUARTER)
        
        self.logger.debug(f"[{__name__}.{func_name}] block_pointer: stock_code={stock_code}, quarter={quarter_str}")
        
        if not stock_code:
            self.logger.error(f"[{__name__}.{func_name}] block_pointer 缺少 stock_code 字段")
            return False
        
        # 数据验证
        if data is None or data.empty:
            self.logger.warning(f"[{__name__}.{func_name}] 数据为空，无可保存的内容 | stock_code={stock_code}")
            return True
        
        self.logger.debug(f"[{__name__}.{func_name}] 待保存数据: {stock_code}, 行数: {len(data)}, 列: {list(data.columns)}")
        self.logger.debug(f"[{__name__}.{func_name}] 数据前3行:\n{data.head(3)}")
        
        # 保存数据
        try:
            self.logger.debug(f"[{__name__}.{func_name}] 开始保存数据 | stock_code={stock_code}")
            self.logger.debug(f"[{__name__}.{func_name}] self.profit_manager={self.profit_manager}")
            self.logger.debug(f"[{__name__}.{func_name}] data类型: {type(data)}, data行数: {len(data)}")
            
            save_result = self.profit_manager.save_profit_data(stock_code, data)
            
            self.logger.debug(f"[{__name__}.{func_name}] save_result={save_result}")
            
            if save_result:
                self.logger.info(f"[{__name__}.{func_name}] 保存成功 | stock_code={stock_code}, 数据行数={len(data)}")
                return True
            else:
                self.logger.error(f"[{__name__}.{func_name}] 保存失败，返回 False | stock_code={stock_code}")
                import traceback
                self.logger.error(f"[{__name__}.{func_name}] 异常堆栈: {traceback.format_exc()}")
                return False
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 保存数据异常 | stock_code={stock_code}, 错误: {str(e)}")
            import traceback
            self.logger.error(f"[{__name__}.{func_name}] 异常堆栈: {traceback.format_exc()}")
            return False

def start_new_profit_download(conn, params: DownloadParameters, **kwargs) -> bool:
    """
    从头开始下载股票利润数据
    
    Args:
        conn: 数据库连接对象
        params: 下载参数对象
        **kwargs: 包含 block_pointer 等参数
        
    Returns:
        bool: 是否下载成功
    """
    downloader = StockProfitDownloader(conn, params)
    return downloader.start_new_download(params, **kwargs)

def continue_profit_download(conn, params: DownloadParameters) -> bool:
    """
    继续下载股票利润数据
    
    Args:
        params: 下载参数对象
        
    Returns:
        bool: 是否下载成功
    """
    downloader = StockProfitDownloader(conn, params)
    return downloader.continue_download(params)
