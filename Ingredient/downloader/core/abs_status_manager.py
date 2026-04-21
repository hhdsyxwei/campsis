# abs_status_manager.py
# 状态管理器抽象基类

from abc import ABC, abstractmethod
from KitchenBase.download_enums import DlTaskStatus

class TaskStatusManager(ABC):
    """
    任务状态管理器抽象基类，定义任务状态管理的统一接口
    """
    
    @abstractmethod
    def get_task_status(self, taskType) -> DlTaskStatus:
        """
        获取任务状态

        Args:
            taskType: 任务类型

        Returns:
            DlTaskStatus: 任务状态枚举值
        """
        pass
    
    @abstractmethod
    def set_task_status(self, taskType, status: DlTaskStatus):
        """
        设置任务状态

        Args:
            taskType: 任务类型
            status: 任务状态枚举值
        """
        pass