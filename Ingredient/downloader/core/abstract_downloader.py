# abstract_downloader.py
# 下载器抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Any, List, Dict, Tuple
import pandas as pd
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest import GlobalDlCtrlBlockManager
from KitchenBase.download_enums import DlTaskStatus, DlTaskType
from .download_strategy import DownloadStrategy
from .abs_block_manager import BlockManager
from .abs_status_manager import StatusManager
from .abs_pointer_manager import PointerManager
from .abs_progress_manager import ProgressManager

class AbstractDownloader(ABC):
    """
    下载器抽象基类，定义所有下载器的通用接口和方法
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
        self.support_block_status = False  # 默认为不支持区块状态表
        
        # 指针字段元组（由子类定义）
        self.pointer_fields = ()
        
        # 初始化功能模块
        self.block_manager = self.create_block_manager()
        self.status_manager = self.create_status_manager()
        self.pointer_manager = self.create_pointer_manager()
        self.progress_calculator = self.create_progress_manager()
        
        # 初始化策略
        self.strategies = {}
        self.simple_strategy = self.create_simple_strategy()
        self.block_strategy = self.create_block_strategy()
        
        # 注册策略
        self.register_strategy(self.simple_strategy)
        self.register_strategy(self.block_strategy)
        
        # 加载启动参数（如果有）
        params = self.load_startup_parameters()
        if params:
            self.start_year, self.end_year, self.extra_params = params
        else:
            self.start_year = None
            self.end_year = None
            self.extra_params = {}
    
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
    
    def create_simple_strategy(self):
        """
        创建一次性下载策略
        
        Returns:
            DownloadStrategy: 一次性下载策略实例
        """
        from ..strategies.simple_download_strategy import SimpleDownloadStrategy
        return SimpleDownloadStrategy(self)
    
    def create_block_strategy(self):
        """
        创建区块下载策略
        
        Returns:
            DownloadStrategy: 区块下载策略实例
        """
        from ..strategies.block_download_strategy import BlockDownloadStrategy
        return BlockDownloadStrategy(self)
    
    def register_strategy(self, strategy: DownloadStrategy):
        """
        注册下载策略
        
        Args:
            strategy: 下载策略实例
        """
        for download_type in ["simple", "block_new", "block_resume"]:
            if strategy.can_handle(download_type):
                self.strategies[download_type] = strategy
    
    def get_strategy(self, download_type: str) -> Optional[DownloadStrategy]:
        """
        获取指定类型的下载策略
        
        Args:
            download_type: 下载类型
            
        Returns:
            Optional[DownloadStrategy]: 下载策略实例
        """
        return self.strategies.get(download_type)
    
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
        strategy = self.get_strategy("simple")
        if strategy:
            return strategy.execute(start_year, end_year, **kwargs)
        return False
    
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
        strategy = self.get_strategy("block_resume")
        if strategy:
            kwargs["download_type"] = "block_resume"
            return strategy.execute(start_year, end_year, **kwargs)
        return False
    
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
        # 保存启动参数
        if not self.save_startup_parameters(start_year, end_year, **kwargs):
            self.logger.error(f"[{self.get_task_type().value}] 保存启动参数失败")
            return False
        
        strategy = self.get_strategy("block_new")
        if strategy:
            kwargs["download_type"] = "block_new"
            return strategy.execute(start_year, end_year, **kwargs)
        return False
    
    def load_startup_parameters(self) -> Optional[Tuple[int, int, Dict]]:
        """
        从数据库加载启动参数
        
        Returns:
            Optional[Tuple[int, int, Dict]]: (start_year, end_year, extra_params)，如果没有则返回 None
        """
        # 调用 GlobalDlCtrlBlockManager 的 read_startup_params 方法
        startup_params = self.progress_manager.read_startup_params(self.get_task_type())
        
        if startup_params and "start_year" in startup_params and "end_year" in startup_params:
            # 提取核心参数
            start_year = startup_params["start_year"]
            end_year = startup_params["end_year"]
            
            # 提取额外参数
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
        # 构建启动参数字典
        startup_params = {
            "start_year": start_year,
            "end_year": end_year
        }
        
        # 添加额外参数
        startup_params.update(kwargs)
        
        # 调用 GlobalDlCtrlBlockManager 的 save_startup_params 方法
        return self.progress_manager.save_startup_params(self.get_task_type(), startup_params)