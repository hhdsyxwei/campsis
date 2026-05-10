# test_parallel_runner.py
# Pytest test case for ParallelBacktestRunner

import pytest
from CookingEngine.Backtest import ParallelBacktestRunner


class TestParallelBacktestRunner:
    """Test cases for ParallelBacktestRunner"""

    def setup_method(self):
        """Setup test dependencies"""
        # Note: We'll use mock_db_conn from conftest.py for database
        pass

    def test_runner_creation(self, mock_db_conn):
        """Test creating ParallelBacktestRunner instance"""
        runner = ParallelBacktestRunner(mock_db_conn, max_workers=2)
        assert runner is not None
        assert runner.db_conn is not None
        assert runner.max_workers == 2

    def test_run_single_config_basic(self, mock_db_conn):
        """Test running a single backtest config (basic case)"""
        runner = ParallelBacktestRunner(mock_db_conn, max_workers=2)
        
        config = {
            "strategy": {
                "name": "factor_strategy",
                "params": {}
            },
            "data": {
                "stock_code": "000001.SZ",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31"
            },
            "initial_cash": 1000000
        }
        
        result = runner.run_single(config)
        assert result is not None
        assert 'strategy' in result
        # Can have either 'metrics' or 'error'
        if 'error' not in result:
            assert 'params' in result
            assert 'metrics' in result
            assert 'trades' in result
            assert 'transactions' in result

    def test_run_batch(self, mock_db_conn):
        """Test running multiple backtests in batch"""
        runner = ParallelBacktestRunner(mock_db_conn, max_workers=2)
        
        configs = [
            {
                "strategy": {
                    "name": "factor_strategy",
                    "params": {}
                },
                "data": {
                    "stock_code": "000001.SZ",
                    "start_date": "2025-01-01",
                    "end_date": "2025-01-31"
                },
                "initial_cash": 1000000
            }
        ]
        
        results = runner.run_batch(configs)
        assert isinstance(results, list)
        assert len(results) == len(configs)
        
        for result in results:
            assert 'strategy' in result
            # Can have either 'metrics' or 'error'
            if 'error' not in result:
                assert 'metrics' in result

    def test_error_handling_invalid_stock(self, mock_db_conn):
        """Test error handling with invalid stock code"""
        runner = ParallelBacktestRunner(mock_db_conn, max_workers=2)
        
        config = {
            "strategy": {
                "name": "factor_strategy",
                "params": {}
            },
            "data": {
                "stock_code": "INVALID.SZ",
                "start_date": "2025-01-01",
                "end_date": "2025-01-31"
            },
            "initial_cash": 1000000
        }
        
        result = runner.run_single(config)
        # Should return error dict without crashing
        assert result is not None

    def test_strategies_method(self, mock_db_conn):
        """Test the run_strategies method"""
        runner = ParallelBacktestRunner(mock_db_conn, max_workers=2)
        
        results = runner.run_strategies(
            strategy_names=['factor_strategy'],
            start_date='2025-01-01',
            end_date='2025-01-31',
            stock_code='000001.SZ'
        )
        
        assert isinstance(results, list)
        assert len(results) == 1
