# abs_status_manager.py
# 状态管理器抽象基类

from abc import ABC, abstractmethod
from KitchenBase.download_enums import DlTaskStatus

class StatusManager(ABC):
    """
    状态管理器抽象基类，定义状态管理的统一接口
    """
    
    @abstractmethod
    def get_download_status(self, taskType) -> DlTaskStatus:
        """
        获取下载状态

        Args:
            taskType: 任务类型

        Returns:
            DlTaskStatus: 下载状态枚举值
        """
        pass
    
    @abstractmethod
    def set_download_status(self, taskType, status: DlTaskStatus):
        """
        设置下载状态

        Args:
            taskType: 任务类型
            status: 下载状态枚举值
        """
        pass