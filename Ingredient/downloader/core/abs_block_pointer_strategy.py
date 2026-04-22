# abs_block_pointer_strategy.py
# 区块指针策略抽象基类

from abc import ABC, abstractmethod
from typing import Optional, Tuple
from KitchenBase.block_pointer import BlockPointer
from KitchenBase.download_enums import PointerField

class BlockPointerStrategy(ABC):
    """
    区块指针策略抽象基类，定义获取下一个区块指针的算法

    职责：
    1. 定义获取第一个区块指针的接口
    2. 定义获取下一个区块指针的接口
    3. 提供指针字段信息
    4. 提供指针验证功能

    注意：
    - db_conn 不是所有子类的依赖，因此不在基类中定义
    - 需要 db_conn 的子类应在自己的 __init__ 中接收
    """

    @abstractmethod
    def get_first_blk_pointer(self, start_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个区块指针

        Args:
            start_year: 开始年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 第一个区块的指针
        """
        pass

    @abstractmethod
    def get_next_blk_pointer(self, current_pointer: BlockPointer, start_year: int, end_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个区块指针

        Args:
            current_pointer: 当前区块指针
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 下一个区块的指针
        """
        pass

    @abstractmethod
    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        pass

    @abstractmethod
    def get_completed_block_count(self, start_year: int, end_year: int, current_pointer: BlockPointer) -> int:
        """
        计算已完成的区块数量

        Args:
            start_year: 开始年份
            end_year: 结束年份
            current_pointer: 当前区块指针

        Returns:
            int: 已完成的区块数量
        """
        pass

    def is_valid_pointer(self, pointer: BlockPointer, start_year: int, end_year: int) -> bool:
        """
        验证指针是否有效

        Args:
            pointer: 要验证的指针
            start_year: 开始年份
            end_year: 结束年份

        Returns:
            bool: 指针是否有效
        """
        return True
    
    @staticmethod
    def get_next_quarter(quarter_str: str, year_range: Tuple[int, int]) -> Optional[str]:
        """
        计算指定季度的下一个季度
        
        Args:
            quarter_str: 季度字符串，格式如 "2026-Q1"
            year_range: 年份区间元组 (start_year, end_year)，前闭后开 [start_year, end_year)
                        如果为 None，则不进行校验
        
        Returns:
            str: 下一个季度字符串，格式如 "2026-Q2"
            None: 如果输入季度不合法或返回季度超出范围
        """
        # 解析季度
        try:
            year_str, quarter_part = quarter_str.split('-Q')
            year = int(year_str)
            quarter = int(quarter_part)
        except ValueError:
            return None  # 格式错误
        
        # 校验输入季度
        if year_range:
            start_year, end_year = year_range
            # 检查年份是否在范围内
            if year < start_year or year >= end_year:
                return None  # 输入年份超出范围
            # 检查季度值是否合法
            if quarter < 1 or quarter > 4:
                return None  # 季度值不合法
        
        # 计算下一个季度
        if quarter < 4:
            next_year = year
            next_quarter = quarter + 1
        else:
            next_year = year + 1
            next_quarter = 1
        
        # 校验返回季度是否在范围内
        if year_range:
            start_year, end_year = year_range
            if next_year < start_year or next_year >= end_year:
                return None  # 返回季度超出范围
        
        return f"{next_year}-Q{next_quarter}"
