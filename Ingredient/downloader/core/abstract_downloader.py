# abstract_downloader.py
# 下载器抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Any, Dict, Tuple
import pandas as pd
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest import GlobalDlCtrlBlockManager
from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
from KitchenBase.block_pointer import BlockPointer
from .abs_block_manager import BlockManager
from .abs_status_manager import TaskStatusManager
from .abs_pointer_manager import PointerManager
from .abs_progress_manager import ProgressManager
from .abs_collection_manager import StockCollectionManager
from .download_parameters import DownloadParameters
from ..block_managers.generic_block_manager import GenericBlockManager
from ..pointer_managers.generic_pointer_manager import GenericPointerManager

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
    def validate_parameters(self, params: DownloadParameters, **kwargs) -> bool:
        """
        验证参数有效性

        Args:
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            bool: 参数是否有效
        """
        pass

    @abstractmethod
    def download_raw_data(self, params: DownloadParameters, **kwargs) -> Any:
        """
        下载原始数据

        Args:
            params: 下载参数
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
        pass

    def on_download_completed(self, params: DownloadParameters, cleaned_data: pd.DataFrame, success: bool, **kwargs) -> None:
        """
        下载完成后的钩子方法，默认空实现

        Args:
            params: 下载参数
            cleaned_data: 清洗后的数据
            success: 下载（保存）是否成功
            **kwargs: 额外参数
        """
        pass

    def download(self, params: DownloadParameters, **kwargs) -> bool:
        """
        执行一次性下载

        Args:
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            bool: 下载是否成功
        """
        from ..strategies.simple_download_strategy import SimpleDownloadStrategy
        strategy = SimpleDownloadStrategy(self)
        return strategy.execute(params, **kwargs)


class BlockDownloader(SimpleDownloader):
    """
    区块下载器抽象基类，定义区块下载的通用接口和方法
    继承自 SimpleDownloader，添加区块管理相关功能
    """

    def __init__(self, db_conn, params: DownloadParameters):
        """
        初始化区块下载器

        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn)
        self.support_block_status = False
        
        # 初始化股票集合管理器
        from ..collection_managers import GenericStockCollectionManager
        self.collection_manager = GenericStockCollectionManager(self.db_conn, params.stock_codes)

        # 创建其他管理器
        self.block_manager = self.create_block_manager()
        self.status_manager = self.create_status_manager()
        self.pointer_manager = self.create_pointer_manager()
        self.progress_calculator = self.create_progress_manager()

    @abstractmethod
    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
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
    def create_status_manager(self) -> TaskStatusManager:
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

    def download_block(self, block_pointer: BlockPointer, params: DownloadParameters) -> bool:
        """
        下载单个区块（模板方法）

        统一的下载流程：
        1. 验证参数
        2. 下载原始数据（直接传递 block_pointer）
        3. 清洗数据
        4. 保存数据
        5. 更新区块状态

        Args:
            block_pointer: 区块指针
            params: 下载参数

        Returns:
            bool: 是否下载成功
        """
        # 1. 验证参数（传递 block_pointer 作为 kwargs）
        if not self.validate_parameters(params, block_pointer=block_pointer):
            self._update_block_status(block_pointer, DlBlockStatus.ERROR, "参数验证失败")
            return False

        try:
            # 2. 下载原始数据（直接传递 block_pointer）
            raw_data = self.download_raw_data(params, block_pointer=block_pointer)

            # 处理无数据情况
            if raw_data is None or (isinstance(raw_data, pd.DataFrame) and raw_data.empty):
                self._update_block_status(block_pointer, DlBlockStatus.SKIPPED, "无数据")
                return True

            # 3. 清洗数据
            cleaned_data = self.clean_data(raw_data)

            if cleaned_data.empty:
                self._update_block_status(block_pointer, DlBlockStatus.SKIPPED, "无有效数据")
                return True

            # 4. 保存数据（传递 block_pointer）
            save_result = self.save_data(cleaned_data, params, block_pointer=block_pointer)

            # 调用区块下载完成钩子
            self.on_block_download_completed(block_pointer, params, cleaned_data, save_result)

            if save_result:
                self._update_block_status(block_pointer, DlBlockStatus.COMPLETED)
                return True
            else:
                self._update_block_status(block_pointer, DlBlockStatus.ERROR, "数据保存失败")
                return False

        except Exception as e:
            self._update_block_status(block_pointer, DlBlockStatus.ERROR, str(e))
            self.logger.error(f"下载区块异常：{block_pointer} - {str(e)}", exc_info=True)
            return False

    def on_block_download_completed(self, block_pointer, params: DownloadParameters, cleaned_data: pd.DataFrame, success: bool) -> None:
        """
        单个区块下载完成后的钩子方法，默认空实现

        Args:
            block_pointer: 区块指针
            params: 下载参数
            cleaned_data: 清洗后的数据
            success: 是否下载成功
        """
        pass

    def _update_block_status(self, block_pointer: BlockPointer, status: DlBlockStatus, error_message: str = ""):
        """
        更新区块状态

        Args:
            block_pointer: 区块指针
            status: 区块状态
            error_message: 错误信息
        """
        try:
            # 调用 block_manager 的 update_block_status 方法
            # 传递 block_pointer 作为第一个参数
            self.block_manager.update_block_status(block_pointer, status=status, error_message=error_message)
        except Exception as e:
            self.logger.error(f"更新区块状态失败：{e}", exc_info=True)

    def continue_download(self, params: DownloadParameters, **kwargs) -> bool:
        """
        执行区块恢复下载

        Args:
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            bool: 下载是否成功
        """
        from ..strategies.block_download_strategy import BlockDownloadStrategy
        strategy = BlockDownloadStrategy(self)
        kwargs["download_type"] = "block_resume"
        return strategy.execute(params, **kwargs)

    def start_new_download(self, params: DownloadParameters, **kwargs) -> bool:
        """
        执行区块全新下载

        Args:
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            bool: 下载是否成功
        """
        if not self.save_startup_parameters(params.start_year, params.end_year, stock_codes=params.stock_codes, **kwargs):
            self.logger.error(f"[{self.get_task_type().value}] 保存启动参数失败")
            return False

        from ..strategies.block_download_strategy import BlockDownloadStrategy
        strategy = BlockDownloadStrategy(self)
        kwargs["download_type"] = "block_new"
        return strategy.execute(params, **kwargs)

    def load_startup_parameters(self) -> Optional[Tuple[int, int, Optional[list], Dict]]:
        """
        从数据库加载启动参数

        Returns:
            Optional[Tuple[int, int, Optional[list], Dict]]: (start_year, end_year, stock_codes, extra_params)，如果没有则返回 None
        """
        startup_params = self.progress_manager.read_startup_params(self.get_task_type())

        if startup_params and "start_year" in startup_params and "end_year" in startup_params:
            start_year = startup_params["start_year"]
            end_year = startup_params["end_year"]
            stock_codes = startup_params.get("stock_codes")
            extra_params = {k: v for k, v in startup_params.items() if k not in ["start_year", "end_year", "stock_codes"]}
            return (start_year, end_year, stock_codes, extra_params)

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
