import pytest
import pandas as pd
from CookingEngine.Picker.data_provider import HarvestDataProvider


def test_harvest_data_provider_initialization(mock_db_conn):
    """测试 HarvestDataProvider 初始化"""
    provider = HarvestDataProvider(mock_db_conn)
    assert provider is not None
    assert provider.db_conn == mock_db_conn
    assert provider.daily_manager is not None
    assert provider.kline_manager is not None


def test_get_price_data(mock_db_conn):
    """测试获取价格数据"""
    provider = HarvestDataProvider(mock_db_conn)
    result = provider.get_price_data("000001.SZ", "2025-01-01", "2025-12-31")
    assert isinstance(result, pd.DataFrame)


def test_get_index_data(mock_db_conn):
    """测试获取指数数据"""
    provider = HarvestDataProvider(mock_db_conn)
    result = provider.get_index_data("000300.SH", "2025-01-01", "2025-12-31")
    assert isinstance(result, pd.DataFrame)


def test_get_financial_data(mock_db_conn):
    """测试获取财务数据"""
    provider = HarvestDataProvider(mock_db_conn)
    result = provider.get_financial_data("000001.SZ", "2025-01-01", "2025-12-31")
    assert isinstance(result, pd.DataFrame)
