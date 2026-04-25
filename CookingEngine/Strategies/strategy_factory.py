# factory.py
# Strategy factory for creating configured strategy instances

from CookingEngine.Strategies.registry import strategy_registry
from CookingEngine.Picker.data_provider import HarvestDataProvider
from CookingEngine.Picker.factor_calculator import FactorCalculator
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


class StrategyFactory:
    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.data_provider = HarvestDataProvider(db_conn)
        self.factor_calculator = FactorCalculator(self.data_provider)
        logger.info("StrategyFactory initialized")

    def create(self, strategy_name, **params):
        strategy_class = strategy_registry.get(strategy_name)
        if not strategy_class:
            raise ValueError(f"Strategy '{strategy_name}' not found")

        logger.info(f"Creating strategy: {strategy_name} with params: {params}")

        strategy = strategy_class(
            data_provider=self.data_provider,
            factor_calculator=self.factor_calculator,
            **params
        )

        logger.info(f"Created strategy instance: {strategy_name}")
        return strategy

    def list_available_strategies(self):
        strategies = strategy_registry.list_strategies()
        logger.info(f"Available strategies: {strategies}")
        return strategies
