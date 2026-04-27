# stock_industry_downloader.py
# 行业分类数据下载器

from typing import Tuple, Optional
import pandas as pd
import datetime
from Ingredient.downloader.core.abstract_downloader import BlockDownloader
from Ingredient.downloader.core.download_parameters import DownloadParameters
from Ingredient.downloader.core.abs_block_manager import BlockManager
from Ingredient.downloader.core.abs_status_manager import TaskStatusManager
from Ingredient.downloader.core.abs_pointer_manager import PointerManager
from Ingredient.downloader.core.abs_progress_manager import ProgressManager
from Ingredient.downloader.status_managers.generic_status_manager import GenericStatusManager
from Ingredient.downloader.pointer_managers.year_ptr_mgr import YearPtrMgr
from Ingredient.downloader.progress_managers.generic_progress_manager import GenericProgressManager
from Ingredient.DataNest import StockIndustryDataManager, BasicStockDataManager
from KitchenBase.baostock_wrapper import query_stock_industry
from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
from KitchenBase.block_pointer import BlockPointer
from Ingredient.downloader.block_managers import YearBlkMgr



class StockIndustryDownloader(BlockDownloader):
    """
    行业分类数据下载器，基于 BlockDownloader 实现
    通过区块管理和断点续传机制，解决 API 限流问题
    支持批量获取全市场行业数据
    """
    
    def __init__(self, db_conn):
        """
        初始化行业分类数据下载器
        
        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn)
        self.industry_manager = StockIndustryDataManager(db_conn)
        self.stock_manager = BasicStockDataManager(db_conn)
        self.support_block_status = True
        
        # 默认起始年份
        self.default_start_year = 2000
        # 默认结束年份（当前年份）
        self.default_end_year = datetime.datetime.now().year
    
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识

        Returns:
            DlTaskType: 任务类型枚举值，用于数据库存储和识别
        """
        return DlTaskType.INDUSTRY

    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段

        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return (PointerField.YEAR,)

    def create_block_manager(self) -> BlockManager:
        """
        创建区块管理器

        Returns:
            BlockManager: 区块管理器实例
        """
        return YearBlkMgr(self.db_conn, self.get_task_type())



    def create_status_manager(self) -> TaskStatusManager:
        """
        创建状态管理器

        Returns:
            TaskStatusManager: 状态管理器实例
        """
        return GenericStatusManager(self.db_conn)

    def create_pointer_manager(self) -> PointerManager:
        """
        创建指针管理器

        Returns:
            PointerManager: 指针管理器实例
        """
        return YearPtrMgr(self.db_conn, self.get_task_type())

    def create_progress_manager(self) -> ProgressManager:
        """
        创建进度管理器

        Returns:
            ProgressManager: 进度管理器实例
        """
        return GenericProgressManager(self.db_conn)

    def validate_parameters(self, params: DownloadParameters, **kwargs) -> bool:
        """
        验证参数有效性

        Args:
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            bool: 参数是否有效
        """
        if params.start_year >= params.end_year:
            self.logger.error(f"无效年份范围: start_year ({params.start_year}) 必须小于 end_year ({params.end_year})")
            return False
        
        block_pointer = kwargs.get('block_pointer')
        if block_pointer:
            year = block_pointer.get_value(PointerField.YEAR)
            if not year:
                self.logger.error(f"无效的区块指针: {block_pointer}")
                return False
        
        return True

    def download_raw_data(self, params: DownloadParameters, **kwargs) -> Optional[pd.DataFrame]:
        """
        下载原始行业数据

        批量获取全市场行业数据，不传股票代码参数

        Args:
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            Optional[pd.DataFrame]: 原始数据
        """
        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error("缺少区块指针")
            return None
        
        year = block_pointer.get_value(PointerField.YEAR)
        
        # 构建查询日期
        current_year = datetime.datetime.now().year
        if year == current_year:
            # 如果是当前年份，使用今天的日期
            query_date = datetime.datetime.now().strftime("%Y-%m-%d")
        else:
            # 否则使用该年的最后一天
            query_date = f"{year}-12-31"
        
        # 直接调用 query_stock_industry() 获取全市场行业数据
        # 不传 code 参数，返回所有股票的行业分类
        self.logger.debug(f"调用 API 获取 {year} 年行业数据，查询日期: {query_date}")
        rs = query_stock_industry(date=query_date)

        # 检查API返回状态
        if rs.error_code != "0":
            self.logger.warning(f"Baostock API错误: {rs.error_msg}")
            return None
        
        df = rs.get_data()
        if not df.empty:
            self.logger.info(f"获取到 {len(df)} 条原始数据")
        
        return df

    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗行业数据

        Args:
            raw_data: 原始数据

        Returns:
            pd.DataFrame: 清洗后的数据
        """
        if raw_data is None or raw_data.empty:
            self.logger.warning("原始数据为空")
            return pd.DataFrame()

        try:
            # 重命名字段
            column_mapping = {
                'code': 'std_stock_code',
                'code_name': 'stock_name',
                'industry': 'industry',
                'industryClassification': 'industry_classification',
                'updateDate': 'update_date'
            }
            
            # 只重命名存在的字段
            rename_dict = {k: v for k, v in column_mapping.items() if k in raw_data.columns}
            df = raw_data.rename(columns=rename_dict)
            
            # 确保必要字段存在
            required_columns = ['std_stock_code', 'stock_name', 'industry', 'industry_classification', 'update_date']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # 填充空值
            df = df.fillna({
                'industry': '未知',
                'industry_classification': '未知',
                'stock_name': ''
            })
            
            # 添加数据源字段
            df['industry_source'] = 'baostock'
            
            self.logger.debug(f"数据清洗完成，共 {len(df)} 条记录")
            return df
            
        except Exception as e:
            self.logger.error(f"数据清洗失败: {str(e)}")
            return pd.DataFrame()

    def save_data(self, data: pd.DataFrame, params: DownloadParameters, **kwargs) -> bool:
        """
        保存行业数据到数据库

        Args:
            data: 清洗后的数据
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            bool: 保存是否成功
        """
        if data.empty:
            self.logger.warning("无数据可保存")
            return True
        
        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error("缺少区块指针")
            return False
        
        try:
            success = self.industry_manager.save_industry_data(data)
            if success:
                self.logger.debug(f"数据保存成功，共 {len(data)} 条记录")
            return success
        except Exception as e:
            self.logger.error(f"数据保存失败: {str(e)}")
            return False


def start_new_industry_download(db_conn, start_year: Optional[int] = None, end_year: Optional[int] = None, stock_codes: Optional[list] = None) -> bool:
    """
    从头开始下载行业分类数据
    
    Args:
        db_conn: 数据库连接
        start_year: 起始年份（默认使用 2000）
        end_year: 结束年份（默认使用当前年份）
        stock_codes: 股票代码列表，可选
        **kwargs: 额外参数
        
    Returns:
        bool: 是否下载成功
    """
    if start_year is None:
        start_year = 2000
    if end_year is None:
        end_year = datetime.datetime.now().year + 1
    
    downloader = StockIndustryDownloader(db_conn)
    params = DownloadParameters(start_year, end_year, stock_codes)
    return downloader.start_new_download(params)

def continue_industry_download(db_conn, start_year: Optional[int] = None, end_year: Optional[int] = None, stock_codes: Optional[list] = None) -> bool:
    """
    继续下载行业分类数据
    
    Args:
        db_conn: 数据库连接
        start_year: 起始年份（默认使用 2000）
        end_year: 结束年份（默认使用当前年份）
        stock_codes: 股票代码列表，可选
        
    Returns:
        bool: 是否下载成功
    """
    if start_year is None:
        start_year = 2000
    if end_year is None:
        end_year = datetime.datetime.now().year + 1
    
    downloader = StockIndustryDownloader(db_conn)
    params = DownloadParameters(start_year, end_year, stock_codes)
    return downloader.continue_download(params)
