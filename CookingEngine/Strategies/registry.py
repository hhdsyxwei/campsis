# registry.py
# Strategy registry for Backtrader strategies

from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


class StrategyRegistry:
    def __init__(self):
        self._strategies = {}
        logger.info("StrategyRegistry initialized")

    def register(self, name, strategy_class):
        self._strategies[name] = strategy_class
        logger.info(f"Registered strategy: {name}")

    def get(self, name):
        return self._strategies.get(name)

    def list_strategies(self):
        return list(self._strategies.keys())

    def clear(self):
        self._strategies.clear()
        logger.info("Strategy registry cleared")


strategy_registry = StrategyRegistry()


def register_strategy(name):
    def decorator(cls):
        strategy_registry.register(name, cls)
        return cls
    return decorator
