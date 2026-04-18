# general_progress_manager.py
# 通用进度管理器实现

from .abs_progress_manager import ProgressManager

class GeneralProgressManager(ProgressManager):
    """
    通用进度管理器实现，提供基础进度管理功能
    """
    
    def __init__(self, db_conn):
        """
        初始化通用进度管理器
        
        Args:
            db_conn: 数据库连接对象
        """
        self.db_conn = db_conn
    
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