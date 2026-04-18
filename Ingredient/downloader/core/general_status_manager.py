# general_status_manager.py
# 通用状态管理器实现

from .abs_status_manager import StatusManager
from KitchenBase.download_enums import DlTaskStatus

class GeneralStatusManager(StatusManager):
    """
    通用状态管理器实现，提供基础状态管理功能
    """
    
    def __init__(self, db_conn):
        """
        初始化通用状态管理器
        
        Args:
            db_conn: 数据库连接对象
        """
        self.db_conn = db_conn
        self.status = DlTaskStatus.NOT_STARTED
    
    def get_download_status(self) -> DlTaskStatus:
        """
        获取下载状态

        Returns:
            DlTaskStatus: 下载状态枚举值
        """
        # 通用实现，子类需要根据具体情况重写
        return self.status
    
    def set_download_status(self, status: DlTaskStatus):
        """
        设置下载状态

        Args:
            status: 下载状态枚举值
        """
        # 通用实现，子类需要根据具体情况重写
        self.status = status