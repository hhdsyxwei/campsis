# general_pointer_manager.py
# 通用指针管理器实现，集成策略模式

from Ingredient.downloader.core.abs_collection_manager import StockCollectionManager
from KitchenBase.download_enums import DlTaskType
from Ingredient.DataNest.dm_unified import UnifiedDataManager
from ..core.abs_pointer_manager import PointerManager
from ..core.download_parameters import DownloadParameters
from KitchenBase.block_pointer import BlockPointer, BlockPointerFactory
from typing import Optional, Tuple, Dict, Any
from KitchenBase.download_enums import PointerField
from Ingredient.DataNest import StockFixedSeqManager
from Ingredient.DataNest import UnifiedDataManager as udm
from KitchenBase.logger_config import get_logger

class GenericPointerManager(PointerManager):
    """
    不支持直接实例化，必须通过派生类创建实例。
    通用指针管理器依然是抽象类。只实现通用的指针管理功能，不通用的由派生类实现。

    在本类中实现以下职责：
    1. 管理指针的存储和获取
    2. 使用策略模式处理指针迭代逻辑
    3. 提供指针验证和转换功能
    4. 获取第一个区块指针(注意其它指针迭代逻辑无法在本类实现，需要在派生类实现)
    5. 其它通用的算法，比如下一个季度，下一只股票等

    本类无法实现以下职责：
    1. 指针迭代功能()，指针的迭代基于字段的不同而不同，注意获取第一个区块指针可以在本类实现)
    2. 指针验证功能，指针的验证基于字段的不同而不同
    """

    def __init__(self, db_conn, task_type: DlTaskType, collection_manager: StockCollectionManager,
                  global_manager=None, time_frame=None, ):
        """
        初始化通用指针管理器

        Args:
            db_conn: 数据库连接对象
            task_type: 任务类型（可选）
            global_manager: GlobalDlCtrlBlockManager 实例（可选，用于依赖注入）
            time_frame: 时间周期（可选，仅 QuarterStockPeriodStrategy 需要）
            collection_manager: 股票集合管理器（可选，用于依赖注入）
        """
        self.db_conn = db_conn
        self.task_type = task_type
        self.time_frame = time_frame
        self.dl_pointer = None
        self.logger = get_logger(__name__)

        if global_manager is None:
            from Ingredient.DataNest import GlobalDlCtrlBlockManager
            self.global_manager = GlobalDlCtrlBlockManager(db_conn)
        else:
            self.global_manager = global_manager

        self.db_conn = db_conn
        self.stock_manager = StockFixedSeqManager(db_conn) if db_conn else None
        # 如果没有提供collection_manager，创建默认的GenericStockCollectionManager
        from ..collection_managers import GenericStockCollectionManager
        self.collection_manager = collection_manager or GenericStockCollectionManager(db_conn)


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

    def is_dl_pointer_valid(self, pointer: Optional[BlockPointer], params: DownloadParameters) -> bool:
        """
        验证指针是否有效

        Args:
            pointer: 要验证的指针
            params: 下载参数

        Returns:
            bool: 指针是否有效
        """
        if not pointer:
            return False

        year = pointer.get_value(PointerField.YEAR)
        if not isinstance(year, int) or year < params.start_year or year >= params.end_year:
            return False

        return True

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

    def get_first_blk_pointer(self, params: DownloadParameters, **kwargs) -> Optional[BlockPointer]:
        """
        获取第一个待下载区块的指针

        Args:
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            Optional[BlockPointer]: 第一个区块指针
        """
        return self.get_next_blk_pointer(params, None, **kwargs)

    def get_skipped_block_count(self, params: DownloadParameters, dl_pointer: BlockPointer) -> int:
        """
        基于指针获取已跳过区块数

        Args:
            params: 下载参数
            dl_pointer: 当前下载指针，包含当前处理的区块信息

        Returns:
            int: 已跳过区块数
        """
        # 无区块状态表时无法统计跳过的区块数，返回0
        return 0

    def pointer_to_dict(self, pointer: BlockPointer) -> Dict[PointerField, Any]:
        """
        将指针转换为字段枚举到值的映射字典

        Args:
            pointer: 区块指针

        Returns:
            Dict[PointerField, Any]: 字段枚举到值的映射字典
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
    
    def get_next_quarter(self, quarter_str: str, year_range: Tuple[int, int]) -> Optional[str]:
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

    def get_first_stock(self, params: Optional[DownloadParameters] = None) -> Optional[str]:
        """
        获取第一只股票代码
        
        Args:
            params: 下载参数，可选
            
        Returns:
            Optional[str]: 第一只股票代码
        """
        try:
            return self.collection_manager.get_first_stock()
        except Exception as e:
            self.logger.error(f"获取第一只股票失败: {str(e)}")
            return None
    
    def get_next_stock(self, current_stock: str, params: Optional[DownloadParameters] = None) -> Optional[str]:
        """
        获取下一只股票代码
        
        Args:
            current_stock: 当前股票代码
            params: 下载参数，可选
            
        Returns:
            Optional[str]: 下一只股票代码
        """
        try:
            return self.collection_manager.get_next_stock(current_stock)
        except Exception as e:
            self.logger.error(f"获取下一只股票失败: {str(e)}")
            return None

    def get_stock_total_count(self, params: Optional[DownloadParameters] = None) -> int:
        """
        获取股票总数
        
        Args:
            params: 下载参数，可选
            
        Returns:
            int: 股票总数
        """
        try:
            return self.collection_manager.get_stock_count()
        except Exception as e:
            self.logger.error(f"获取股票总数失败: {str(e)}")
            return 0
    
    def stock_exists(self, stock_code: str, params: Optional[DownloadParameters] = None) -> bool:
        """
        检查股票代码是否在股票列表中
        
        Args:
            stock_code: 股票代码
            params: 下载参数，可选
            
        Returns:
            bool: 股票是否存在
        """
        try:
            # 从collection_manager获取股票列表并检查
            stock_list = self.collection_manager.get_stock_list()
            if stock_list:
                return stock_code in stock_list
            # 如果没有自定义股票列表，检查数据库
            if not self.stock_manager:
                self.logger.error("stock_manager 未初始化")
                return False
            return self.stock_manager.stock_exists(stock_code)
        except Exception as e:
            self.logger.error(f"检查股票是否存在失败: {str(e)}")
            return False

    def get_completed_block_count(self, params: DownloadParameters, dl_pointer: BlockPointer) -> int:
        """
        基于指针获取已完成区块数

        Args:
            params: 下载参数
            dl_pointer: 当前下载指针，包含当前处理的区块信息

        Returns:
            int: 已完成区块数
        """
        # 无区块状态表时无法统计已完成区块数，返回0
        return 0
