# abstract_downloader.py
# 下载器抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Any, List, Dict, Tuple
import pandas as pd
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest import GlobalDlCtrlBlockManager
from KitchenBase.download_enums import DlTaskStatus, DlTaskType

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
    def get_next_block(self, start_year: int, end_year: int, **kwargs) -> Optional[Tuple]:
        """
        获取下一个待下载区块
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数，可包含current_block等
            
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
    def is_dl_pointer_valid(self, dl_pointer: Optional[Tuple], start_year: int, end_year: int) -> bool:
        """
        判断下载指针是否合法有效
        
        Args:
            dl_pointer: 下载指针
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            bool: 指针是否有效
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
    def get_total_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取总区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            int: 总区块数
        """
        pass

    @abstractmethod
    def get_completed_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取已完成区块数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            int: 已完成区块数
        """
        pass

    @abstractmethod
    def get_skipped_block_count(self, start_year: int, end_year: int, **kwargs) -> int:
        """
        获取已跳过区块数

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数

        Returns:
            int: 已跳过区块数
        """
        pass

    @abstractmethod
    def get_completed_block_count_with_status(self, start_year: int, end_year: int) -> int:
        """
        获取已完成区块数（有区块状态表的情况）

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）

        Returns:
            int: 已完成区块数
        """
        pass

    @abstractmethod
    def get_skipped_block_count_with_status(self, start_year: int, end_year: int) -> int:
        """
        获取已跳过区块数（有区块状态表的情况）

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）

        Returns:
            int: 已跳过区块数
        """
        pass

    @abstractmethod
    def get_completed_block_count_with_pointer(self, start_year: int, end_year: int, dl_pointer: Tuple) -> int:
        """
        获取已完成区块数（无区块状态表的情况）

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            dl_pointer: 当前下载指针，包含当前处理的区块信息

        Returns:
            int: 已完成区块数
        """
        pass

    def get_skipped_block_count_with_pointer(self, start_year: int, end_year: int, dl_pointer: Tuple) -> int:
        """
        获取已跳过区块数（无区块状态表的情况）
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            dl_pointer: 当前下载指针，包含当前处理的区块信息
            
        Returns:
            int: 已跳过区块数（固定返回0，因为无法统计）
        """
        # 无区块状态表时无法统计跳过的区块数，返回0
        return 0

    @abstractmethod
    def download_block(self, *args, **kwargs):
        """
        下载单个区块
        
        Args:
            *args: 位置参数
            **kwargs: 关键字参数
        """
        pass
    
    def download(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        完整下载流程
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            bool: 下载是否成功
        """
        # 1. 验证参数
        if not self.validate_parameters(start_year, end_year, **kwargs):
            return False
        
        # 2. 下载原始数据
        raw_data = self.download_raw_data(start_year, end_year, **kwargs)
        if raw_data is None:
            return False
        
        # 3. 清洗数据
        cleaned_data = self.clean_data(raw_data)
        if cleaned_data.empty:
            return False
        
        # 4. 保存数据
        return self.save_data(cleaned_data, start_year, end_year, **kwargs)
    
    def continue_download(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        继续下载（支持断点续传）
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            bool: 下载是否成功
        """
        # 获取任务类型标识
        task_type = self.get_task_type()
        task_identifier = f"[{task_type.value}]"
        
        # 1. 检查下载状态
        status = self.get_download_status()
        if status == DlTaskStatus.COMPLETED:
            self.logger.info(f"{task_identifier} 下载已完成，无需重复执行")
            return True
        elif status == DlTaskStatus.IN_PROGRESS:
            self.logger.info(f"{task_identifier} 下载正在进行，将从断点恢复")
        else:
            self.logger.info(f"{task_identifier} 下载未开始，将从头开始")
            self.set_download_status(DlTaskStatus.IN_PROGRESS)

        # 2. 计算总区块数
        total_blocks = self.get_total_block_count(start_year, end_year, **kwargs)
        self.logger.info(f"{task_identifier} 总区块数: {total_blocks} (年份范围: {start_year}-{end_year-1})")

        # 3. 获取下一个下载区块
        next_block = self.get_dl_pointer()
        if not next_block or not self.is_dl_pointer_valid(next_block, start_year, end_year):
            next_block = self.get_next_block(start_year, end_year, **kwargs)
            self.logger.info(f"{task_identifier} 下载指针无效或不存在，使用第一个区块: {next_block}")
        else:
            self.logger.info(f"{task_identifier} 启动后：第一个下载区块: {next_block}")

        # 4. 核心下载循环
        while next_block:
            try:
                # 设置下载指针
                self.set_dl_pointer(*next_block)
                
                # 下载区块
                self.download_block(*next_block)
                
                # 记录进度
                dl_pointer = self.get_dl_pointer()
                if self.support_block_status:
                    completed_blocks = self.get_completed_block_count_with_status(start_year, end_year)
                    skipped_blocks = self.get_skipped_block_count_with_status(start_year, end_year)
                else:
                    completed_blocks = self.get_completed_block_count_with_pointer(start_year, end_year, dl_pointer)
                    skipped_blocks = self.get_skipped_block_count_with_pointer(start_year, end_year, dl_pointer)
                if total_blocks > 0:
                    progress = self.calculate_progress(completed_blocks, skipped_blocks, total_blocks)
                    self.logger.info(f"{task_identifier} 下载进度: {progress:.2f}% ({completed_blocks + skipped_blocks}/{total_blocks}) | 当前区块: {next_block}")
                
                # 获取下一个区块
                next_block = self.get_next_block(start_year, end_year, **kwargs, current_block=next_block)
            except Exception as e:
                self.logger.error(f"{task_identifier} 下载失败: {str(e)} | 当前区块: {next_block}")
                return False
        
        # 5. 下载完成
        self.set_download_status(DlTaskStatus.COMPLETED)
        self.clear_dl_pointer()
        self.logger.info(f"{task_identifier} 全部下载完成，已清空下载指针")
        return True
    
    def start_new_download(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        开始新的下载任务（清空之前的下载进度）
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外的启动参数
            
        Returns:
            bool: 下载是否成功
        """
        # 获取任务类型标识
        task_type = self.get_task_type()
        task_identifier = f"[{task_type.value}]"
        
        self.logger.info(f"{task_identifier} 开始新的下载任务: {start_year}-{end_year}")
        
        # 1. 保存启动参数
        if not self.save_startup_parameters(start_year, end_year, **kwargs):
            self.logger.error(f"{task_identifier} 保存启动参数失败")
            return False
        
        # 2. 清空之前的下载进度
        self.set_download_status(DlTaskStatus.NOT_STARTED)
        self.clear_dl_pointer()
        self.logger.info(f"{task_identifier} 已清空之前的下载进度")
        
        # 3. 调用继续下载方法
        return self.continue_download(start_year, end_year, **kwargs)
    
    def clear_dl_pointer(self):
        """
        清空下载指针
        """
        pass
    
    def calculate_progress(self, completed: int, skipped: int, total: int) -> float:
        """
        计算下载进度百分比
        
        Args:
            completed: 已完成的区块数
            skipped: 已跳过的区块数
            total: 总区块数
            
        Returns:
            float: 进度百分比
        """
        if total == 0:
            return 0.0
        processed = completed + skipped
        return (processed / total) * 100
    
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
