# abstract_downloader.py
# 下载器抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, Tuple
import pandas as pd
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest import GlobalDlCtrlBlockManager
from KitchenBase.download_enums import DlTaskType
from .abs_block_manager import BlockManager
from .abs_status_manager import StatusManager
from .abs_pointer_manager import PointerManager
from .abs_progress_manager import ProgressManager


class SimpleDownloader(ABC):
    """
    简单下载器抽象基类，定义一次性下载的通用接口和方法
    """

    def __init__(self, db_conn):
        """
        初始化下载器

        Args:
            db_conn: 数据库连接对象
        """
        self.db_conn = db_conn
        self.logger = get_logger(__name__)
        self.progress_manager = GlobalDlCtrlBlockManager(db_conn)
        self.func_name = ""
        self.download_config = {
            "timeout": 60,
            "max_retry": 3
        }

    @abstractmethod
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识

        Returns:
            DlTaskType: 任务类型枚举值，用于数据库存储和识别
        """
        pass

    @abstractmethod
    def validate_parameters(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        验证参数有效性

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数

        Returns:
            bool: 参数是否有效
        """
        pass

    @abstractmethod
    def download_raw_data(self, start_year: int, end_year: int, **kwargs) -> Any:
        """
        下载原始数据

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数

        Returns:
            Any: 原始数据
        """
        pass

    @abstractmethod
    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗数据

        Args:
            raw_data: 原始数据

        Returns:
            pd.DataFrame: 清洗后的数据
        """
        pass

    @abstractmethod
    def save_data(self, data: pd.DataFrame, start_year: int, end_year: int, **kwargs) -> bool:
        """
        保存数据到数据库

        Args:
            data: 清洗后的数据
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数

        Returns:
            bool: 保存是否成功
        """
        pass

    def download(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        执行一次性下载

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数

        Returns:
            bool: 下载是否成功
        """
        from ..strategies.simple_download_strategy import SimpleDownloadStrategy
        strategy = SimpleDownloadStrategy(self)
        return strategy.execute(start_year, end_year, **kwargs)


class BlockDownloader(SimpleDownloader):
    """
    区块下载器抽象基类，定义区块下载的通用接口和方法
    继承自 SimpleDownloader，添加区块管理相关功能
    """

    def __init__(self, db_conn):
        """
        初始化区块下载器

        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn)
        self.support_block_status = False

        self.pointer_fields = ()

        self.block_manager = self.create_block_manager()
        self.status_manager = self.create_status_manager()
        self.pointer_manager = self.create_pointer_manager()
        self.progress_calculator = self.create_progress_manager()

        params = self.load_startup_parameters()
        if params:
            self.start_year, self.end_year, self.extra_params = params
        else:
            self.start_year = None
            self.end_year = None
            self.extra_params = {}

    @abstractmethod
    def download_block(self, *args, **kwargs):
        """
        下载单个区块

        Args:
            *args: 位置参数
            **kwargs: 关键字参数
        """
        pass

    @abstractmethod
    def create_block_manager(self) -> BlockManager:
        """
        创建区块管理器

        Returns:
            BlockManager: 区块管理器实例
        """
        pass

    @abstractmethod
    def create_status_manager(self) -> StatusManager:
        """
        创建状态管理器

        Returns:
            StatusManager: 状态管理器实例
        """
        pass

    @abstractmethod
    def create_pointer_manager(self) -> PointerManager:
        """
        创建指针管理器

        Returns:
            PointerManager: 指针管理器实例
        """
        pass

    @abstractmethod
    def create_progress_manager(self) -> ProgressManager:
        """
        创建进度管理器

        Returns:
            ProgressManager: 进度管理器实例
        """
        pass

    def continue_download(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        执行区块恢复下载

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数

        Returns:
            bool: 下载是否成功
        """
        from ..strategies.block_download_strategy import BlockDownloadStrategy
        strategy = BlockDownloadStrategy(self)
        kwargs["download_type"] = "block_resume"
        return strategy.execute(start_year, end_year, **kwargs)

    def start_new_download(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        执行区块全新下载

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数

        Returns:
            bool: 下载是否成功
        """
        if not self.save_startup_parameters(start_year, end_year, **kwargs):
            self.logger.error(f"[{self.get_task_type().value}] 保存启动参数失败")
            return False

        from ..strategies.block_download_strategy import BlockDownloadStrategy
        strategy = BlockDownloadStrategy(self)
        kwargs["download_type"] = "block_new"
        return strategy.execute(start_year, end_year, **kwargs)

    def load_startup_parameters(self) -> Optional[Tuple[int, int, Dict]]:
        """
        从数据库加载启动参数

        Returns:
            Optional[Tuple[int, int, Dict]]: (start_year, end_year, extra_params)，如果没有则返回 None
        """
        startup_params = self.progress_manager.read_startup_params(self.get_task_type())

        if startup_params and "start_year" in startup_params and "end_year" in startup_params:
            start_year = startup_params["start_year"]
            end_year = startup_params["end_year"]
            extra_params = {k: v for k, v in startup_params.items() if k not in ["start_year", "end_year"]}
            return (start_year, end_year, extra_params)

        return None

    def save_startup_parameters(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        保存启动参数到数据库

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外的启动参数

        Returns:
            bool: 保存是否成功
        """
        startup_params = {
            "start_year": start_year,
            "end_year": end_year
        }
        startup_params.update(kwargs)
        return self.progress_manager.save_startup_params(self.get_task_type(), startup_params)
