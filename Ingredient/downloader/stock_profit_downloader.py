# stock_profit_downloader.py
# 股票利润数据下载器

import pandas as pd
import time
from typing import Tuple
from Ingredient.downloader.progress_managers.general_progress_manager import GeneralProgressManager
from .core.abstract_downloader import BlockDownloader
from .block_managers.general_block_manager import GeneralBlockManager
from .status_managers.general_status_manager import GeneralStatusManager
from .pointer_managers.general_pointer_manager import GeneralPointerManager
from Ingredient.DataNest import StockProfitManager, BasicStockDataManager
from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
from KitchenBase.baostock_wrapper import query_profit_data



class StockProfitDownloader(BlockDownloader):
    """
    股票利润数据下载器，基于 BlockDownloader 实现
    通过区块管理和断点续传机制，解决 API 限流问题
    """
    
    def __init__(self, db_conn):
        """
        初始化股票利润数据下载器
        
        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn)
        self.profit_manager = StockProfitManager(db_conn)
        self.stock_manager = BasicStockDataManager(db_conn)
        self.support_block_status = True
    
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识
        """
        return DlTaskType.STOCK_PROFIT
    
    def get_pointer_fields(self) -> Tuple[PointerField, ...]:
        """
        获取指针字段
        
        Returns:
            Tuple[PointerField, ...]: 指针字段枚举元组
        """
        return (PointerField.QUARTER, PointerField.STOCK_CODE)
    
    def validate_parameters(self, start_year: int, end_year: int, **kwargs) -> bool:
        """
        验证参数有效性
        """
        # 年份合法性校验
        if not isinstance(start_year, int) or not isinstance(end_year, int):
            self.logger.error("年份必须为整数类型")
            return False
        if start_year <= 0 or end_year <= 0:
            self.logger.error("年份必须为正整数")
            return False
        if start_year >= end_year:
            self.logger.error(f"年份范围异常：start_year({start_year}) >= end_year({end_year})")
            return False
        return True
    
    def create_block_manager(self) -> GeneralBlockManager:
        """
        创建区块管理器
        """
        return GeneralBlockManager(self.db_conn, self.get_task_type(), self.get_pointer_fields())
    
    def create_status_manager(self) -> GeneralStatusManager:
        """
        创建状态管理器
        """
        return GeneralStatusManager(self.db_conn)
    
    def create_pointer_manager(self) -> GeneralPointerManager:
        """
        创建指针管理器
        """
        # 这里可以使用通用的指针管理器实现
        return GeneralPointerManager(self.db_conn, self.get_task_type(), self.get_pointer_fields())
    
    def create_progress_manager(self) -> GeneralProgressManager:
        """
        创建进度管理器
        """
        return GeneralProgressManager(self.db_conn)
    
    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗数据
        """
        if raw_data is None or raw_data.empty:
            self.logger.warning("原始数据为空")
            return pd.DataFrame()
        
        try:
            # 复制数据避免修改原数据
            df = raw_data.copy()
            
            # 1. 格式转换
            # 转换日期格式
            if 'pubDate' in df.columns:
                df['pubDate'] = pd.to_datetime(df['pubDate'], errors='coerce').dt.strftime('%Y-%m-%d')
            if 'statDate' in df.columns:
                df['statDate'] = pd.to_datetime(df['statDate'], errors='coerce').dt.strftime('%Y-%m-%d')
            
            # 转换数值类型
            numeric_fields = ['roeAvg', 'npMargin', 'gpMargin', 'netProfit', 'epsTTM', 'MBRevenue']
            for field in numeric_fields:
                if field in df.columns:
                    df[field] = pd.to_numeric(df[field], errors='coerce')
            
            # 2. 空值处理
            df = df.dropna(subset=['code', 'statDate'])
            
            # 3. 去重
            df = df.drop_duplicates(subset=['code', 'statDate'], keep='last')
            
            self.logger.info(f"数据清洗完成，有效数据 {len(df)} 条")
            return df
        except Exception as e:
            self.logger.error(f"清洗利润数据异常：{e}", exc_info=True)
            return pd.DataFrame()
    
    def download_raw_data(self, start_year: int, end_year: int, **kwargs) -> pd.DataFrame:
        """
        下载原始数据
        
        Args:
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 包含 block_pointer 等参数
            
        Returns:
            pd.DataFrame: 原始数据
        """
        # 从 kwargs 中获取 block_pointer
        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error("缺少 block_pointer 参数")
            return pd.DataFrame()
        
        # 解包 block_pointer
        stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
        quarter_str = block_pointer.get_value(PointerField.QUARTER)
        
        if not stock_code or not quarter_str:
            self.logger.error("block_pointer 缺少必要字段")
            return pd.DataFrame()
        
        # 从 quarter 字段中提取年份和季度
        try:
            year_str, quarter_str = quarter_str.split('-Q')
            year = int(year_str)
            quarter = int(quarter_str)
        except ValueError:
            self.logger.error(f"quarter 字段格式错误：{quarter_str}，应为 'YYYY-QN' 格式")
            return pd.DataFrame()
        
        try:
            # 调用接口获取数据
            rs = query_profit_data(
                code=stock_code,
                year=year,
                quarter=quarter
            )
            
            # 处理返回结果
            if rs.error_code == '0':
                data_list = []
                while rs.next():
                    data_list.append(rs.get_row_data())
                
                if data_list:
                    # 转换为 DataFrame
                    df = pd.DataFrame(data_list, columns=rs.fields)
                    self.logger.info(f"利润数据下载完成：{stock_code} {year}年Q{quarter}，共 {len(df)} 条数据")
                    return df
                else:
                    self.logger.warning(f"无利润数据：{stock_code} {year}年Q{quarter}")
                    return pd.DataFrame()
            else:
                # API 调用失败
                self.logger.error(f"API 调用失败：{stock_code} {year}年Q{quarter} - {rs.error_msg}")
                return pd.DataFrame()
        except Exception as e:
            # 异常处理
            self.logger.error(f"下载异常：{stock_code} {year}年Q{quarter} - {str(e)}", exc_info=True)
            return pd.DataFrame()
        finally:
            # 避免 API 限流
            time.sleep(0.1)
    
    def save_data(self, data: pd.DataFrame, start_year: int, end_year: int, **kwargs) -> bool:
        """
        保存数据
        
        Args:
            data: 清洗后的数据
            start_year: 开始年份
            end_year: 结束年份
            **kwargs: 包含 block_pointer 等参数
            
        Returns:
            bool: 是否保存成功
        """
        # 从 kwargs 中获取 block_pointer
        block_pointer = kwargs.get('block_pointer')
        if not block_pointer:
            self.logger.error("缺少 block_pointer 参数")
            return False
        
        # 解包 block_pointer
        stock_code = block_pointer.get_value(PointerField.STOCK_CODE)
        
        if not stock_code:
            self.logger.error("block_pointer 缺少 stock_code 字段")
            return False
        
        # 保存数据
        try:
            save_result = self.profit_manager.save_profit_data(stock_code, data)
            if save_result:
                self.logger.info(f"保存成功：{stock_code}")
                return True
            else:
                self.logger.error(f"保存失败：{stock_code}")
                return False
        except Exception as e:
            self.logger.error(f"保存数据异常：{stock_code} - {str(e)}", exc_info=True)
            return False

def start_new_profit_download(conn, start_year: int, end_year: int, **kwargs) -> bool:
    """
    从头开始下载股票利润数据
    
    Args:
        start_year: 开始年份
        end_year: 结束年份
        **kwargs: 包含 block_pointer 等参数
        
    Returns:
        bool: 是否下载成功
    """
    downloader = StockProfitDownloader(conn)
    return downloader.start_new_download(start_year, end_year, **kwargs)

def continue_profit_download(conn,start_year: int, end_year: int) -> bool:
    """
    继续下载股票利润数据
    
    Args:
        start_year: 开始年份
        end_year: 结束年份
        **kwargs: 包含 block_pointer 等参数
        
    Returns:
        bool: 是否下载成功
    """
    downloader = StockProfitDownloader(conn)
    return downloader.continue_download(start_year, end_year)