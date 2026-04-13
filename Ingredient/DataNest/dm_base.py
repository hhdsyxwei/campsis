# dm_base.py
from KitchenBase.download_enums import DlTaskType
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from .dm_generic_block_status import GenericBlockStatusManager



class BaseDataManager(ABC):
    """数据管理器基类，定义统一接口"""
    
    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.block_status_manager = GenericBlockStatusManager(db_conn)
    
    @abstractmethod
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型
        :return: 任务类型（DlTaskType枚举）
        """
        pass

    @abstractmethod
    def get_completed_block_count(self, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        获取已完成区块总数（仅统计completed状态）
        :param start_year: 起始年份
        :param end_year: 结束年份
        :return: 已完成区块总数
        """
        pass

    @abstractmethod
    def get_skipped_block_count(self, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        获取跳过区块总数（仅统计skipped状态）
        :param start_year: 起始年份
        :param end_year: 结束年份
        :return: 跳过区块总数
        """
        pass

    @abstractmethod
    def get_total_block_count(self, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        获取区块总数
        :param start_year: 起始年份
        :param end_year: 结束年份
        :return: 区块总数
        """
        pass

    @abstractmethod
    def get_block_status(self, *args, **kwargs):
        """
        获取区块状态
        """
        pass
    
    @abstractmethod
    def update_block_status(self, *args, **kwargs):
        """
        更新区块状态
        """
        pass
    
    @abstractmethod
    def is_dl_pointer_valid(self, pointer: Optional[Tuple], start_year: int, end_year: int) -> bool:
        """
        判断下载指针是否合法
        
        :param pointer: 下载指针，通常为 (year, stock_code) 元组
        :param start_year: 起始年份
        :param end_year: 结束年份
        :return: 指针是否合法
        """
        pass


    def get_attempted_block_count(self, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        获取已尝试下载的区块总数（统计completed、skipped、error状态）
        :param start_year: 起始年份
        :param end_year: 结束年份
        :return: 已尝试下载的区块总数
        """
        from KitchenBase.download_enums import DlBlockStatus
        from KitchenBase.logger_config import get_logger
        
        logger = get_logger(__name__)
        func_name = "get_attempted_block_count"
        
        try:
            # 获取任务类型
            task_type = self.get_task_type()
            
            # 调用 GenericBlockStatusManager 的 get_block_count 方法
            attempted_count = self.block_status_manager.get_block_count(
                task_type=task_type,
                start_year=start_year,
                end_year=end_year,
                status=[DlBlockStatus.COMPLETED, DlBlockStatus.SKIPPED, DlBlockStatus.ERROR]
            )
            logger.debug(f"[{__name__}.{func_name}] 已尝试下载的区块数: {attempted_count}")
            return attempted_count
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败: {str(e)}")
            return 0

