# data_provider.py
# 数据提供者接口

import pandas as pd
from abc import ABC, abstractmethod
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest.dm_daily import DailyDataManager
from Ingredient.DataNest.dm_kline import KLineUnifiedQuarterlyExtendedManager
from KitchenBase.stock_enums import KLinePeriod

logger = get_logger(__name__)

class DataProvider(ABC):
    """数据提供者抽象基类"""
    
    @abstractmethod
    def get_price_data(self, stock_code, start_date, end_date):
        """
        获取股票价格数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 包含日期、开盘价、最高价、最低价、收盘价、成交量等数据的DataFrame
        """
        pass
    
    @abstractmethod
    def get_index_data(self, index_code, start_date, end_date):
        """
        获取指数数据
        
        Args:
            index_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 包含日期、开盘价、最高价、最低价、收盘价、成交量等数据的DataFrame
        """
        pass
    
    @abstractmethod
    def get_financial_data(self, stock_code, start_date, end_date):
        """
        获取财务数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 包含财务指标的DataFrame
        """
        pass

class HarvestDataProvider(DataProvider):
    """数据提供者，从MySQL数据库获取数据"""
    
    def __init__(self, db_conn):
        """
        初始化HarvestDataProvider
        
        Args:
            db_conn: MySQL数据库连接
        """
        self.db_conn = db_conn
        self.daily_manager = DailyDataManager(db_conn)
        self.kline_manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
    
    def get_price_data(self, stock_code, start_date, end_date):
        """
        从数据库获取股票价格数据
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 包含日期、开盘价、最高价、最低价、收盘价、成交量等数据的DataFrame
        """

        try:
            # 调用DailyDataManager的get_price_data方法
            df = self.daily_manager.get_price_data(stock_code, start_date, end_date)
            logger.info(f"从数据库获取价格数据 {stock_code}: {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取价格数据失败 {stock_code}: {str(e)}")
            return pd.DataFrame()
    
    def get_index_data(self, index_code, start_date, end_date):
        """
        从数据库获取指数数据
        
        Args:
            index_code: 指数代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 包含日期、开盘价、最高价、最低价、收盘价、成交量等数据的DataFrame
        """
        try:
            # 调用DailyDataManager的get_price_data方法
            df = self.daily_manager.get_price_data(index_code, start_date, end_date)
            logger.info(f"从数据库获取指数数据 {index_code}: {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取指数数据失败 {index_code}: {str(e)}")
            return pd.DataFrame()
    
    def get_financial_data(self, stock_code, start_date, end_date):
        """
        获取财务数据（暂时置空）
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 空的DataFrame
        """
        logger.debug(f"获取财务数据 {stock_code}: 暂时返回空数据")
        return pd.DataFrame()