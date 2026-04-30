# data_provider.py
# 数据提供者接口

import pandas as pd
from abc import ABC, abstractmethod
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest.dm_daily import DailyDataManager
from Ingredient.DataNest.dm_kline import KLineUnifiedQuarterlyExtendedManager
from Ingredient.DataNest.dm_company_profit import CompanyProfitManager
from Ingredient.DataNest.dm_company_balance import CompanyBalanceManager
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
        self.profit_manager = CompanyProfitManager(db_conn)
        self.balance_manager = CompanyBalanceManager(db_conn)
    
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
            logger.info(f"从数据库获取指数数据 {index_code}{start_date}{end_date}: {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"获取指数数据失败 {index_code}: {str(e)}")
            return pd.DataFrame()
    
    def get_financial_data(self, stock_code, start_date, end_date):
        """
        获取财务数据，整合利润表和资产负债表

        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            pd.DataFrame: 包含财务指标的DataFrame，字段包括:
                - stat_date: 统计日期
                - roe: 净资产收益率 (from roe_avg)
                - debt_to_asset: 资产负债率 (from liability_to_asset)
                - net_profit: 净利润
                - revenue: 主营营业收入 (from mb_revenue)
                - gross_margin: 毛利率 (from gp_margin)
        """
        try:
            profit_df = self.profit_manager.get_profit_data(stock_code, start_date, end_date)
            balance_df = self.balance_manager.get_balance_data(stock_code, start_date, end_date)

            if profit_df.empty and balance_df.empty:
                logger.debug(f"获取财务数据 {stock_code}: 无数据")
                return pd.DataFrame()

            if profit_df.empty:
                balance_df = balance_df.rename(columns={
                    'liability_to_asset': 'debt_to_asset'
                })
                return balance_df

            if balance_df.empty:
                profit_df = profit_df.rename(columns={
                    'roe_avg': 'roe',
                    'mb_revenue': 'revenue',
                    'gp_margin': 'gross_margin'
                })
                return profit_df

            merged_df = pd.merge(
                profit_df,
                balance_df[['stat_date', 'liability_to_asset']],
                on='stat_date',
                how='outer'
            )

            merged_df = merged_df.rename(columns={
                'roe_avg': 'roe',
                'mb_revenue': 'revenue',
                'gp_margin': 'gross_margin',
                'liability_to_asset': 'debt_to_asset'
            })

            merged_df = merged_df.sort_values('stat_date')
            logger.info(f"获取财务数据 {stock_code}: {len(merged_df)} 条")
            return merged_df

        except Exception as e:
            logger.error(f"获取财务数据失败 {stock_code}: {str(e)}")
            return pd.DataFrame()