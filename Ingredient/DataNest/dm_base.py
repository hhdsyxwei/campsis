# dm_base.py
from KitchenBase.download_enums import DlTaskType
from abc import ABC, abstractmethod
from typing import Optional, Tuple
from .dm_generic_block_status import GenericBlockStatusDM



class BaseDataManager(ABC):
    """数据管理器基类，定义统一接口"""
    
    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.block_status_manager = GenericBlockStatusDM(db_conn)
    
    @abstractmethod
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型
        :return: 任务类型（DlTaskType枚举）
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
    

