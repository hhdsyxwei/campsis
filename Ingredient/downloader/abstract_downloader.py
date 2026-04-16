# abstract_downloader.py
# 下载器抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Any, List, Dict, Tuple
import pandas as pd
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest import GlobalDlCtrlBlockManager
from KitchenBase.download_enums import DlTaskStatus

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
    
    @abstractmethod
    def validate_parameters(self, *args, **kwargs) -> bool:
        """
        验证参数有效性
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 参数是否有效
        """
        pass
    
    @abstractmethod
    def download_raw_data(self, *args, **kwargs) -> Any:
        """
        下载原始数据
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
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
    def save_data(self, data: pd.DataFrame, *args, **kwargs) -> bool:
        """
        保存数据到数据库
        
        Args:
            data: 清洗后的数据
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 保存是否成功
        """
        pass
    
    @abstractmethod
    def get_next_block(self, *args, **kwargs) -> Optional[Tuple]:
        """
        获取下一个待下载区块
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            Optional[Tuple]: 下一个区块的标识，如 (year, stock_code) 或 (quarter, stock_code)
        """
        pass
    
    @abstractmethod
    def get_dl_pointer(self) -> Optional[Tuple]:
        """
        获取当前下载指针
        
        Returns:
            Optional[Tuple]: 当前下载区块的标识
        """
        pass
    
    @abstractmethod
    def set_dl_pointer(self, *args, **kwargs):
        """
        设置当前下载指针
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
        """
        pass
    
    @abstractmethod
    def get_download_status(self) -> DlTaskStatus:
        """
        获取下载状态
        
        Returns:
            DlTaskStatus: 下载状态枚举值
        """
        pass
    
    @abstractmethod
    def set_download_status(self, status: DlTaskStatus):
        """
        设置下载状态
        
        Args:
            status: 下载状态枚举值
        """
        pass
    
    @abstractmethod
    def get_total_block_count(self, *args, **kwargs) -> int:
        """
        获取总区块数
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            int: 总区块数
        """
        pass
    
    @abstractmethod
    def get_completed_block_count(self, *args, **kwargs) -> int:
        """
        获取已完成区块数
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            int: 已完成区块数
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
    
    def download(self, *args, **kwargs) -> bool:
        """
        完整下载流程
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 下载是否成功
        """
        # 1. 验证参数
        if not self.validate_parameters(*args, **kwargs):
            return False
        
        # 2. 下载原始数据
        raw_data = self.download_raw_data(*args, **kwargs)
        if raw_data is None:
            return False
        
        # 3. 清洗数据
        cleaned_data = self.clean_data(raw_data)
        if cleaned_data.empty:
            return False
        
        # 4. 保存数据
        return self.save_data(cleaned_data, *args, **kwargs)
    
    def continue_download(self, *args, **kwargs) -> bool:
        """
        继续下载（支持断点续传）
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 下载是否成功
        """
        # 1. 检查下载状态
        status = self.get_download_status()
        if status == DlTaskStatus.COMPLETED:
            self.logger.info("下载已完成，无需重复执行")
            return True
        elif status == DlTaskStatus.IN_PROGRESS:
            self.logger.info("下载正在进行，将从断点恢复")
        else:
            self.logger.info("下载未开始，将从头开始")
            self.set_download_status(DlTaskStatus.IN_PROGRESS)
        
        # 2. 计算总区块数
        total_blocks = self.get_total_block_count(*args, **kwargs)
        
        # 3. 获取下一个下载区块
        next_block = self.get_dl_pointer()
        if not next_block:
            next_block = self.get_next_block(*args, **kwargs)
        
        # 4. 核心下载循环
        while next_block:
            try:
                # 设置下载指针
                self.set_dl_pointer(*next_block)
                
                # 下载区块
                self.download_block(*next_block)
                
                # 记录进度
                completed_blocks = self.get_completed_block_count(*args, **kwargs)
                if total_blocks > 0:
                    progress = self.calculate_progress(completed_blocks, total_blocks)
                    self.logger.info(f"下载进度: {progress:.2f}% ({completed_blocks}/{total_blocks})")
                
                # 获取下一个区块
                next_block = self.get_next_block(*args, **kwargs, current_block=next_block)
            except Exception as e:
                self.logger.error(f"下载失败: {str(e)}")
                return False
        
        # 5. 下载完成
        self.set_download_status(DlTaskStatus.COMPLETED)
        self.clear_dl_pointer()
        self.logger.info("全部下载完成，已清空下载指针")
        return True
    
    def start_new_download(self, *args, **kwargs) -> bool:
        """
        开始新的下载任务（清空之前的下载进度）
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
            
        Returns:
            bool: 下载是否成功
        """
        # 1. 清空之前的下载进度
        self.set_download_status(DlTaskStatus.NOT_STARTED)
        self.clear_dl_pointer()
        
        # 2. 调用继续下载方法
        return self.continue_download(*args, **kwargs)
    
    def clear_dl_pointer(self):
        """
        清空下载指针
        """
        pass
    
    def calculate_progress(self, completed: int, total: int) -> float:
        """
        计算下载进度百分比
        
        Args:
            completed: 已完成的区块数
            total: 总区块数
            
        Returns:
            float: 进度百分比
        """
        if total == 0:
            return 0.0
        return (completed / total) * 100
