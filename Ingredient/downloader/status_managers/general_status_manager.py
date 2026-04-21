# general_status_manager.py
# 通用状态管理器实现

from ..core.abs_status_manager import TaskStatusManager
from KitchenBase.download_enums import DlTaskStatus, DlTaskType
from Ingredient.DataNest import GlobalDlCtrlBlockManager

class GeneralStatusManager(TaskStatusManager):
    """
    通用状态管理器实现，作为 GlobalDlCtrlBlockManager 的适配器

    该类实现了 StatusManager 接口，并将调用委托给底层的 GlobalDlCtrlBlockManager。
    支持依赖注入，便于单元测试。
    """

    def __init__(self, db_conn, global_manager=None):
        """
        初始化通用状态管理器

        Args:
            db_conn: 数据库连接对象
            global_manager: GlobalDlCtrlBlockManager 实例（可选，用于依赖注入）
        """
        self.db_conn = db_conn
        if global_manager is None:
            self.global_manager = GlobalDlCtrlBlockManager(db_conn)
        else:
            self.global_manager = global_manager

    def get_task_status(self, taskType: DlTaskType) -> DlTaskStatus:
        """
        获取任务状态

        Args:
            taskType: 任务类型

        Returns:
            DlTaskStatus: 任务状态枚举值
        """
        try:
            return self.global_manager.get_task_status(taskType)
        except Exception as e:
            print(f"[{self.__class__.__name__}] 获取状态失败: {e}")
            return DlTaskStatus.NOT_STARTED

    def set_task_status(self, taskType: DlTaskType, status: DlTaskStatus):
        """
        设置任务状态

        Args:
            taskType: 任务类型
            status: 任务状态枚举值
        """
        try:
            self.global_manager.set_task_status(taskType, status)
        except Exception as e:
            print(f"[{self.__class__.__name__}] 设置状态失败: {e}")