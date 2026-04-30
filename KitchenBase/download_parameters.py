# download_parameters.py
# 下载参数容器类

from typing import Optional, List
from .stock_enums import KLinePeriod


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
        stock_codes: Optional[List[str]] = None,
        stock_table: str = "stock_fixed_seq",
        kline_period_list: Optional[List[KLinePeriod]] = None
    ):
        """
        初始化下载参数
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            stock_codes: 股票代码列表，可选，None表示使用stock_fixed_seq表中的股票
            stock_table: 股票列表表名，默认使用stock_fixed_seq
            kline_period_list: K线周期列表，默认下载日线数据
        """
        self._start_year = start_year
        self._end_year = end_year
        self._stock_codes = stock_codes if stock_codes is not None else None
        self._stock_table = stock_table
        self._kline_period_list = kline_period_list if kline_period_list else [KLinePeriod.DAILY]
    
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
    def stock_table(self) -> str:
        """获取股票列表表名"""
        return self._stock_table
    
    @property
    def kline_period_list(self) -> List[KLinePeriod]:
        """获取K线周期列表"""
        return self._kline_period_list
    
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
            f"stock_codes={'...' if self._stock_codes else 'None'}, "
            f"stock_table='{self._stock_table}', "
            f"kline_period_list={self._kline_period_list})"
        )