# abs_progress_manager.py
# 进度管理器抽象基类

from abc import ABC, abstractmethod

class ProgressManager(ABC):
    """
    进度管理器抽象基类，定义进度管理的统一接口
    """
    
    @abstractmethod
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
        pass