# adjustment_factor_downloader.py
from KitchenBase.download_enums import DlBlockStatus, DlTaskType, PointerField
from KitchenBase import DownloadParameters
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from KitchenBase.baostock_wrapper import query_adjust_factor
from Ingredient.DataNest import AdjustmentFactorManager, BasicStockDataManager
from KitchenBase.block_pointer import BlockPointer
from .core.abstract_downloader import BlockDownloader
from .core.abs_block_manager import BlockManager
from .core.abs_status_manager import TaskStatusManager
from .core.abs_pointer_manager import PointerManager
from .core.abs_progress_manager import ProgressManager

# ===================== 全局配置 =====================
logger = get_logger(__name__)

# ===================== 下载器核心类 =====================
class AdjFactorDownloader(BlockDownloader):
    """
    复权因子数据下载器，基于 BlockDownloader 实现
    通过区块管理和断点续传机制，解决 API 限流问题
    """
    
    def __init__(self, db_conn, params: DownloadParameters):
        """
        初始化复权因子数据下载器
        
        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn, params)
        self.adj_factor_manager = AdjustmentFactorManager(db_conn)
        self.stock_manager = BasicStockDataManager(db_conn)
        self.support_block_status = True

    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识

        Returns:
            DlTaskType: 任务类型枚举值，用于数据库存储和识别
        """
        return DlTaskType.ADJ_FACTOR

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
        return YearStockBlkMgr(self.db_conn, self.get_task_type(), collection_manager=self.collection_manager)

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
        下载原始数据

        Args:
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            Any: 原始数据
        """
        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error("缺少区块指针")
            return None
        
        year = block_pointer.get_value(PointerField.YEAR)
        stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
        
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        rs = query_adjust_factor(
            code=stock_code,
            start_date=start_date,
            end_date=end_date
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
        清洗数据

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
            "dividOperateDate": "adjust_date",
            "foreAdjustFactor": "fore_adjust_factor",
            "backAdjustFactor": "back_adjust_factor",
            "adjustFactor": "adjust_factor"
        }, inplace=True)

        if "adjust_date" in df.columns:
            df["adjust_date"] = df["adjust_date"].replace('', pd.NA)
            df["adjust_date"] = pd.to_datetime(df["adjust_date"], errors='coerce')
            df["adjust_date"] = df["adjust_date"].where(df["adjust_date"].notna(), None)

        numeric_cols = [
            "fore_adjust_factor", "back_adjust_factor", "adjust_factor"
        ]

        for col in numeric_cols:
            if col in df.columns:
                df[col] = df[col].replace('', pd.NA)
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df[col] = df[col].where(df[col].notna(), None)

        return df

    def save_data(self, data: pd.DataFrame, params: DownloadParameters, **kwargs) -> bool:
        """
        保存数据到数据库

        Args:
            data: 清洗后的数据
            params: 下载参数
            **kwargs: 额外参数

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
        
        data["std_stock_code"] = stock_code
        
        ok = self.adj_factor_manager.save_adjustment_factor_data(data)
        if not ok:
            self.logger.error(f"数据保存失败: {stock_code}")
            return False
        
        return True

# ===================== 全局唯一对外接口函数 =====================
def continue_adj_factor_download(db_conn, params: DownloadParameters, **kwargs) -> bool:
    """
    【全局唯一对外接口】继续下载复权因子数据（支持断点续传）
    
    功能说明：
    - 从上次中断的位置继续下载复权因子数据
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
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（不包含，默认当前年份+1）
    :param stock_codes: 股票代码列表，可选
    :return: True 表示全部下载完成，False 表示未完成
    """
    # start_year: int, end_year: Optional[int] = None, stock_codes: Optional[list] = None
    start_year = params.start_year
    end_year = params.end_year

    if end_year is None:
        end_year = datetime.now().year + 1
    
    if start_year >= end_year:
        raise RuntimeError(f"Invalid year range: start_year ({start_year}) must be less than end_year ({end_year})")
    
    downloader = AdjFactorDownloader(db_conn, params)
    return downloader.continue_download(params)

def start_new_adj_factor_download(db_conn, params: DownloadParameters) -> bool:
    """
    【全局唯一对外接口】开始新的复权因子数据下载任务（清空之前的下载进度）
    
    功能说明：
    - 清空之前的下载进度记录
    - 从头开始下载指定年份范围的复权因子数据
    - 按照年份和股票代码的顺序下载数据
    - 自动处理下载过程中的异常
    
    下载流程：
    1. 删除之前的任务记录
    2. 调用继续下载方法开始新的下载任务
    3. 按照年份和股票代码的顺序下载所有区块
    4. 完成后清空下载指针
    
    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（不包含，默认当前年份+1）
    :param stock_codes: 股票代码列表，可选
    :return: True 表示全部下载完成，False 表示未完成
    """
    # start_year: int, end_year: Optional[int] = None, stock_codes: Optional[list] = None
    start_year = params.start_year
    end_year = params.end_year
    
    if end_year is None:
        end_year = datetime.now().year + 1
    
    if start_year >= end_year:
        raise RuntimeError(f"Invalid year range: start_year ({start_year}) must be less than end_year ({end_year})")
    
    downloader = AdjFactorDownloader(db_conn, params)
    return downloader.start_new_download(params)
