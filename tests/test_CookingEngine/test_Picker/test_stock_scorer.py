import pytest
import pandas as pd
from CookingEngine.Picker.stock_scorer import StockScorer
from CookingEngine.Picker.data_provider import HarvestDataProvider


def test_stock_scorer_initialization(mock_db_conn):
    """测试 StockScorer 初始化"""
    data_provider = HarvestDataProvider(mock_db_conn)
    scorer = StockScorer(data_provider)
    assert scorer is not None
    assert scorer.data_provider == data_provider
    assert scorer.factor_calculator is not None


def test_score_stock(mock_db_conn):
    """测试为单个股票打分"""
    data_provider = HarvestDataProvider(mock_db_conn)
    scorer = StockScorer(data_provider)
    result = scorer.score_stock("000001.SZ", "2025-01-01", "2025-12-31")
    assert isinstance(result, dict)
    assert "stock_code" in result
    assert "total_score" in result
    assert "trend_score" in result
    assert "momentum_score" in result
    assert "quality_score" in result
    assert "timing_score" in result
    assert "weights" in result


def test_score_stocks(mock_db_conn):
    """测试为多个股票打分"""
    data_provider = HarvestDataProvider(mock_db_conn)
    scorer = StockScorer(data_provider)
    result = scorer.score_stocks(["000001.SZ", "000002.SZ"], "2025-01-01", "2025-12-31")
    assert isinstance(result, pd.DataFrame)


def test_get_top_stocks(mock_db_conn):
    """测试获取打分最高的前N只股票"""
    data_provider = HarvestDataProvider(mock_db_conn)
    scorer = StockScorer(data_provider)
    result = scorer.get_top_stocks(["000001.SZ", "000002.SZ"], "2025-01-01", "2025-12-31", top_n=1)
    assert isinstance(result, pd.DataFrame)
    assert len(result) <= 1


def test_save_scores(tmp_path, mock_db_conn):
    """测试保存打分结果"""
    data_provider = HarvestDataProvider(mock_db_conn)
    scorer = StockScorer(data_provider)
    scores_df = scorer.score_stocks(["000001.SZ"], "2025-01-01", "2025-12-31")
    file_path = tmp_path / "test_scores.csv"
    result = scorer.save_scores(scores_df, str(file_path))
    assert result is True
    assert file_path.exists()
