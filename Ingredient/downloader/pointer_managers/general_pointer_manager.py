# general_pointer_manager.py
# 通用指针管理器实现，集成策略模式

from ..core.abs_pointer_manager import PointerManager
from .pointer_strategies.block_pointer_strategy_factory import BlockPointerStrategyFactory
from KitchenBase.block_pointer import BlockPointer, BlockPointerFactory
from typing import Optional, Tuple, Dict, Any

class GeneralPointerManager(PointerManager):
    """
    通用指针管理器实现，使用策略模式管理指针迭代

    职责：
    1. 管理指针的存储和获取
    2. 使用策略模式处理指针迭代逻辑
    3. 提供指针验证和转换功能
    """

    def __init__(self, db_conn, task_type=None, pointer_fields=(), global_manager=None, time_frame=None):
        """
        初始化通用指针管理器

        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型（可选）
            pointer_fields: 指针字段元组（可选）
            global_manager: GlobalDlCtrlBlockManager 实例（可选，用于依赖注入）
            time_frame: 时间周期（可选，仅 QuarterStockPeriodStrategy 需要）
        """
        self.db_conn = db_conn
        self.task_type = task_type
        self.pointer_fields = pointer_fields
        self.time_frame = time_frame
        self.dl_pointer = None

        if global_manager is None:
            from Ingredient.DataNest import GlobalDlCtrlBlockManager
            self.global_manager = GlobalDlCtrlBlockManager(db_conn)
        else:
            self.global_manager = global_manager

        # 创建策略实例
        self.strategy = BlockPointerStrategyFactory.create_strategy(
            pointer_fields, db_conn=db_conn, time_frame=time_frame
        )

    def get_dl_pointer(self) -> Optional[BlockPointer]:
        """
        获取当前下载指针

        Returns:
            Optional[BlockPointer]: 当前下载区块的指针
        """
        try:
            if not self.task_type:
                return self.dl_pointer

            pointer = self.global_manager.read_task_pointer(self.task_type)

            if not pointer:
                return None

            if not pointer.is_valid():
                return None

            return pointer
        except Exception as e:
            print(f"[{self.__class__.__name__}] 获取指针失败: {e}")
            return self.dl_pointer

    def set_dl_pointer(self, pointer: BlockPointer):
        """
        设置当前下载指针

        Args:
            pointer: 区块指针
        """
        try:
            self.dl_pointer = pointer

            if self.task_type:
                self.global_manager.write_task_pointer(self.task_type, pointer)
        except Exception as e:
            print(f"[{self.__class__.__name__}] 设置指针失败: {e}")

    def is_dl_pointer_valid(self, dl_pointer: Optional[BlockPointer], start_year: int, end_year: int) -> bool:
        """
        判断下载指针是否合法有效

        Args:
            dl_pointer: 下载指针
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）

        Returns:
            bool: 指针是否有效
        """
        if not dl_pointer:
            return False

        # 验证指针元组长度是否匹配
        if len(dl_pointer) != len(self.pointer_fields):
            return False

        # 调用策略的验证方法
        return self.strategy.is_valid_pointer(dl_pointer, start_year, end_year)

    def clear_dl_pointer(self):
        """
        清空下载指针
        """
        try:
            self.dl_pointer = None

            if self.task_type:
                self.global_manager.clear_dl_pointer(self.task_type)
        except Exception as e:
            print(f"[{self.__class__.__name__}] 清空指针失败: {e}")

    def get_first_blk_pointer(self, start_year: int, end_year: int, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个待下载区块的指针

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 第一个区块的指针
        """
        return self.strategy.get_first_blk_pointer(start_year, **kwargs)

    def get_next_blk_pointer(self, start_year: int, end_year: int, current_block: Optional[BlockPointer] = None, **kwargs) -> Optional[BlockPointer]:
        """
        获取下一个待下载区块的指针

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            current_block: 当前区块指针（首次调用传None，返回第一个区块）
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 下一个区块的指针
        """
        if current_block is None:
            return self.get_first_blk_pointer(start_year, end_year, **kwargs)

        return self.strategy.get_next_blk_pointer(current_block, start_year, end_year, **kwargs)

    def get_completed_block_count(self, start_year: int, end_year: int, dl_pointer: BlockPointer) -> int:
        """
        基于指针获取已完成区块数

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            dl_pointer: 当前下载指针，包含当前处理的区块信息

        Returns:
            int: 已完成区块数
        """
        if not dl_pointer:
            return 0

        return self.strategy.get_completed_block_count(start_year, end_year, dl_pointer)

    def get_skipped_block_count(self, start_year: int, end_year: int, dl_pointer: BlockPointer) -> int:
        """
        基于指针获取已跳过区块数

        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            dl_pointer: 当前下载指针，包含当前处理的区块信息

        Returns:
            int: 已跳过区块数
        """
        # 无区块状态表时无法统计跳过的区块数，返回0
        return 0

    def pointer_to_dict(self, pointer: BlockPointer) -> Dict[str, Any]:
        """
        将指针转换为字段到值的映射字典

        Args:
            pointer: 区块指针

        Returns:
            Dict[str, Any]: 字段到值的映射字典
        """
        if not pointer:
            return {}
        return pointer.to_dict()

    def log_pointer_info(self, pointer: BlockPointer, message: str = "当前下载指针"):
        """
        输出指针信息到日志

        Args:
            pointer: 区块指针
            message: 日志消息前缀
        """
        if not pointer:
            return
        return f"{message}: {pointer}"

    def to_tuple(self, pointer: BlockPointer) -> Tuple:
        """
        将指针转换为元组

        Args:
            pointer: 区块指针

        Returns:
            Tuple: 指针值元组
        """
        if not pointer:
            return ()
        return pointer.to_tuple()