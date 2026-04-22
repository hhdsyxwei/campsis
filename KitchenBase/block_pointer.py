# block_pointer.py
# 区块指针数据类，用于存储和管理指针的字段和值

from typing import Optional, Tuple, Dict, Any
from .download_enums import PointerField


class BlockPointer:
    """
    区块指针数据类，用于存储和管理指针的字段和值

    职责：
    1. 存储指针的字段名称和值
    2. 提供便捷的访问接口
    3. 支持数据验证和格式转换
    """

    def __init__(self, fields: Tuple[PointerField, ...], values: Tuple[Any, ...]):
        """
        初始化区块指针

        Args:
            fields: 指针字段枚举元组
            values: 指针值元组

        Raises:
            ValueError: 当字段和值长度不一致时抛出
        """
        if len(fields) != len(values):
            raise ValueError(f"字段数量({len(fields)})与值数量({len(values)})不一致")

        self._fields = fields
        self._values = values
        self._dict = dict(zip(fields, values))

    def get_value(self, field_name: PointerField) -> Any:
        """
        通过字段枚举获取值

        Args:
            field_name: 字段枚举

        Returns:
            Any: 字段对应的值，如果字段不存在返回 None
        """
        return self._dict.get(field_name)

    def get_value_by_index(self, index: int) -> Any:
        """
        通过索引获取值

        Args:
            index: 字段索引

        Returns:
            Any: 索引对应的值

        Raises:
            IndexError: 当索引超出范围时抛出
        """
        return self._values[index]

    def get_fields(self) -> Tuple[PointerField, ...]:
        """
        获取所有字段枚举

        Returns:
            Tuple[PointerField, ...]: 字段枚举元组
        """
        return self._fields

    def get_values(self) -> Tuple[Any, ...]:
        """
        获取所有值

        Returns:
            Tuple[Any, ...]: 值元组
        """
        return self._values

    def to_tuple(self) -> Tuple[Any, ...]:
        """
        转换为元组形式

        Returns:
            Tuple[Any, ...]: 指针值元组
        """
        return self._values

    def to_dict(self) -> Dict[PointerField, Any]:
        """
        转换为字典形式

        Returns:
            Dict[PointerField, Any]: 字段枚举到值的字典
        """
        return self._dict.copy()

    def is_valid(self) -> bool:
        """
        检查指针是否有效

        Returns:
            bool: 指针是否有效
        """
        return None not in self._values

    def __getitem__(self, index: int) -> Any:
        """
        支持索引访问

        Args:
            index: 字段索引

        Returns:
            Any: 索引对应的值
        """
        return self._values[index]

    def __iter__(self):
        """
        支持迭代

        Returns:
            Iterator: 值的迭代器
        """
        return iter(self._values)

    def __len__(self) -> int:
        """
        获取字段数量

        Returns:
            int: 字段数量
        """
        return len(self._fields)

    def __eq__(self, other) -> bool:
        """
        比较两个指针是否相等

        Args:
            other: 另一个指针

        Returns:
            bool: 是否相等
        """
        if not isinstance(other, BlockPointer):
            return False
        return self._fields == other._fields and self._values == other._values

    def __str__(self) -> str:
        """
        字符串表示

        Returns:
            str: 指针的字符串表示
        """
        items = [f"{k}={v}" for k, v in self._dict.items()]
        return f"BlockPointer({', '.join(items)})"


class BlockPointerFactory:
    """
    区块指针工厂，用于创建不同类型的指针
    """

    @staticmethod
    def create_pointer(fields: Tuple[PointerField, ...], values: Tuple[Any, ...]) -> BlockPointer:
        """
        创建区块指针

        Args:
            fields: 指针字段枚举元组
            values: 指针值元组

        Returns:
            BlockPointer: 区块指针实例
        """
        return BlockPointer(fields, values)

    @staticmethod
    def create_from_dict(data: Dict[PointerField, Any]) -> BlockPointer:
        """
        从字典创建区块指针

        Args:
            data: 字段枚举到值的字典

        Returns:
            BlockPointer: 区块指针实例
        """
        fields = tuple(data.keys())
        values = tuple(data.values())
        return BlockPointer(fields, values)

    @staticmethod
    def create_year_stock(year: int, stock_code: str) -> BlockPointer:
        """
        创建年份-股票指针

        Args:
            year: 年份
            stock_code: 股票代码

        Returns:
            BlockPointer: 区块指针实例
        """
        return BlockPointer((PointerField.YEAR, PointerField.STOCK_CODE), (year, stock_code))

    @staticmethod
    def create_quarter_stock_period(quarter: str, stock_code: str, time_frame: str) -> BlockPointer:
        """
        创建季度-股票-周期指针

        Args:
            quarter: 季度
            stock_code: 股票代码
            time_frame: 时间周期

        Returns:
            BlockPointer: 区块指针实例
        """
        return BlockPointer((PointerField.QUARTER, PointerField.STOCK_CODE, PointerField.TIME_FRAME), (quarter, stock_code, time_frame))

    @staticmethod
    def create_year(year: int) -> BlockPointer:
        """
        创建年份指针

        Args:
            year: 年份

        Returns:
            BlockPointer: 区块指针实例
        """
        return BlockPointer((PointerField.YEAR,), (year,))

    @staticmethod
    def create_from_db_dict(db_dict: Dict[str, Any]) -> Optional[BlockPointer]:
        """
        从数据库字典创建 BlockPointer
        数据库字典格式包含 primary_pointer_name/value, secondary_pointer_name/value, tertiary_pointer_name/value

        Args:
            db_dict: 数据库查询结果的字典

        Returns:
            Optional[BlockPointer]: 区块指针实例，如果没有任何有效指针则返回 None
        """
        if not db_dict:
            return None

        pointer_fields = []
        pointer_values = []

        primary_name = db_dict.get('primary_pointer_name')
        primary_value = db_dict.get('primary_pointer_value')
        if primary_name and primary_value:
            try:
                field = PointerField(primary_name)
                pointer_fields.append(field)
                pointer_values.append(primary_value)
            except ValueError:
                pass

        secondary_name = db_dict.get('secondary_pointer_name')
        secondary_value = db_dict.get('secondary_pointer_value')
        if secondary_name and secondary_value:
            try:
                field = PointerField(secondary_name)
                pointer_fields.append(field)
                pointer_values.append(secondary_value)
            except ValueError:
                pass

        tertiary_name = db_dict.get('tertiary_pointer_name')
        tertiary_value = db_dict.get('tertiary_pointer_value')
        if tertiary_name and tertiary_value:
            try:
                field = PointerField(tertiary_name)
                pointer_fields.append(field)
                pointer_values.append(tertiary_value)
            except ValueError:
                pass

        if not pointer_fields:
            return None

        return BlockPointer(tuple(pointer_fields), tuple(pointer_values))