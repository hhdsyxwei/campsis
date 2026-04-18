# download_strategy.py
# 下载策略接口

from abc import ABC, abstractmethod

class DownloadStrategy(ABC):
    """
    下载策略接口，定义下载策略的统一接口
    """
    
    @abstractmethod
    def execute(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        执行下载策略
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数
            
        Returns:
            bool: 下载是否成功
        """
        pass
    
    @abstractmethod
    def can_handle(self, download_type: str) -> bool:
        """
        判断是否能处理指定类型的下载
        
        Args:
            download_type: 下载类型
            
        Returns:
            bool: 是否能处理
        """
        pass