# test_backtrader_integration.py
# Pytest test case for Backtrader integration

import pytest
from Ingredient.DataNest import create_database_and_tables
from CookingEngine.Strategies import strategy_registry, StrategyFactory
from CookingEngine.Backtest import BacktraderDataAdapter
from CookingEngine.Analysis import PerformanceAnalyzer
from CookingEngine.Strategies.Factors import FactorStrategy


class TestBacktraderIntegration:
    def setup_method(self):
        self.conn = create_database_and_tables()

    def teardown_method(self):
        if hasattr(self, 'conn'):
            self.conn.close()

    def test_database_connection(self):
        """Test database connection"""
        assert self.conn is not None

    def test_data_adapter_creation(self):
        """Test data adapter creation"""
        data_adapter = BacktraderDataAdapter(self.conn)
        assert data_adapter is not None

    def test_strategy_registry(self):
        """Test strategy registry"""
        strategies = strategy_registry.list_strategies()
        assert isinstance(strategies, list)
        assert 'factor_strategy' in strategies

    def test_strategy_factory_creation(self):
        """Test strategy factory creation"""
        factory = StrategyFactory(self.conn)
        assert factory is not None

    def test_performance_analyzer_creation(self):
        """Test performance analyzer creation"""
        analyzer = PerformanceAnalyzer()
        assert analyzer is not None
