import pytest
import pandas as pd
from Ingredient.DataNest.dm_daily import DailyDataManager


class TestDailyDataManager:
    """DailyDataManager 单元测试"""

    def test_save_daily_data(self, mock_db_conn):
        """测试保存日线数据"""
        manager = DailyDataManager(mock_db_conn)

        df = pd.DataFrame({
            'date': pd.to_datetime(['2025-01-07', '2025-01-08']),
            'open': [11.50, 11.60],
            'high': [11.70, 11.80],
            'low': [11.40, 11.50],
            'close': [11.55, 11.65],
            'volume': [100000000, 110000000],
            'amount': [1150000000.00, 1265000000.00],
            'turn': [0.50, 0.55],
            'pctChg': [1.05, 0.87],
            'peTTM': [8.5, 8.6],
            'pbMRQ': [0.95, 0.96],
            'psTTM': [2.10, 2.15],
            'pcfNcfTtm': [8.20, 8.30]
        })

        result = manager.save_daily_data('000001.SZ', df)
        assert result is True

    def test_save_daily_data_empty(self, mock_db_conn):
        """测试保存空数据"""
        manager = DailyDataManager(mock_db_conn)

        df = pd.DataFrame()
        result = manager.save_daily_data('000001.SZ', df)
        assert result is True

    def test_get_price_data(self, mock_db_conn):
        """测试获取价格数据"""
        manager = DailyDataManager(mock_db_conn)

        df = manager.get_price_data('000001.SZ', '2025-01-01', '2025-12-31')

        assert not df.empty
        assert len(df) >= 3  # 至少有3条初始测试数据（可能包含之前测试保存的数据）
        assert 'date' in df.columns
        assert 'open' in df.columns
        assert 'high' in df.columns
        assert 'low' in df.columns
        assert 'close' in df.columns
        assert 'volume' in df.columns
        assert 'amount' in df.columns

    def test_get_price_data_date_range(self, mock_db_conn):
        """测试日期范围查询"""
        manager = DailyDataManager(mock_db_conn)

        df = manager.get_price_data('000001.SZ', '2025-01-02', '2025-01-03')

        assert not df.empty
        assert len(df) == 2

    def test_get_price_data_no_data(self, mock_db_conn):
        """测试查询不存在的股票"""
        manager = DailyDataManager(mock_db_conn)

        df = manager.get_price_data('999999.SZ', '2025-01-01', '2025-12-31')

        assert df.empty

    def test_get_price_data_out_of_range(self, mock_db_conn):
        """测试查询日期范围外的数据"""
        manager = DailyDataManager(mock_db_conn)

        df = manager.get_price_data('000001.SZ', '2020-01-01', '2020-12-31')

        assert df.empty

    def test_check_date_range_exists(self, mock_db_conn):
        """测试检查股票是否存在"""
        manager = DailyDataManager(mock_db_conn)

        exists = manager.check_date_range_exists('000001.SZ')
        assert exists is True

        not_exists = manager.check_date_range_exists('999999.SZ')
        assert not_exists is False

    def test_get_active_stocks(self, mock_db_conn):
        """测试获取活跃股票列表"""
        manager = DailyDataManager(mock_db_conn)

        stocks = manager.get_active_stocks()

        assert isinstance(stocks, list)