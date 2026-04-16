import pytest
from CookingEngine.Picker.factor_calculator import FactorCalculator
from CookingEngine.Picker.data_provider import HarvestDataProvider


def test_factor_calculator_initialization(mock_db_conn):
    """测试 FactorCalculator 初始化"""
    data_provider = HarvestDataProvider(mock_db_conn)
    calculator = FactorCalculator(data_provider)
    assert calculator is not None
    assert calculator.data_provider == data_provider


def test_calculate_trend_score(mock_db_conn):
    """测试计算趋势因子分数"""
    data_provider = HarvestDataProvider(mock_db_conn)
    calculator = FactorCalculator(data_provider)
    score = calculator.calculate_trend_score("000001.SZ", "2025-01-01", "2025-12-31")
    assert isinstance(score, (int, float))


def test_calculate_momentum_score(mock_db_conn):
    """测试计算动量因子分数"""
    data_provider = HarvestDataProvider(mock_db_conn)
    calculator = FactorCalculator(data_provider)
    score = calculator.calculate_momentum_score("000001.SZ", "2025-01-01", "2025-12-31")
    assert isinstance(score, (int, float))


def test_calculate_quality_score(mock_db_conn):
    """测试计算质量因子分数"""
    data_provider = HarvestDataProvider(mock_db_conn)
    calculator = FactorCalculator(data_provider)
    score = calculator.calculate_quality_score("000001.SZ", "2025-01-01", "2025-12-31")
    assert isinstance(score, (int, float))


def test_calculate_timing_score(mock_db_conn):
    """测试计算时机因子分数"""
    data_provider = HarvestDataProvider(mock_db_conn)
    calculator = FactorCalculator(data_provider)
    score = calculator.calculate_timing_score("000001.SZ", "2025-01-01", "2025-12-31")
    assert isinstance(score, (int, float))
