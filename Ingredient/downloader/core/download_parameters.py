# download_parameters.py
# 下载参数容器类

from typing import Optional, List


class DownloadParameters:
    """
    下载参数容器类，统一管理下载相关参数
    
    职责：
    1. 统一管理下载参数，避免参数分散传递
    2. 提供参数验证和访问方法
    """
    
    def __init__(
        self,
        start_year: int,
        end_year: int,
        stock_codes: Optional[List[str]] = None
    ):
        """
        初始化下载参数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            stock_codes: 股票代码列表，可选，None表示使用stock_fixed_seq表中的股票
        """
        self._start_year = start_year
        self._end_year = end_year
        self._stock_codes = stock_codes if stock_codes is not None else None
    
    @property
    def start_year(self) -> int:
        """获取开始年份"""
        return self._start_year
    
    @property
    def end_year(self) -> int:
        """获取结束年份"""
        return self._end_year
    
    @property
    def stock_codes(self) -> Optional[List[str]]:
        """获取股票代码列表，None表示使用stock_fixed_seq表中的股票"""
        return self._stock_codes
    
    @property
    def year_range(self) -> tuple:
        """获取年份范围元组"""
        return (self._start_year, self._end_year)
    
    def has_custom_stock_list(self) -> bool:
        """检查是否有自定义股票列表"""
        return self._stock_codes is not None and len(self._stock_codes) > 0
    
    def __repr__(self) -> str:
        return (
            f"DownloadParameters("
            f"start_year={self._start_year}, "
            f"end_year={self._end_year}, "
            f"stock_codes={'...' if self._stock_codes else 'None'})"
        )
