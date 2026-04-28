# factor_strategy.py
# Four-factor strategy implementation

from CookingEngine.Picker.factor_calculator import FactorCalculator
from CookingEngine.Picker.data_provider import DataProvider
import backtrader as bt
from CookingEngine.Strategies.base import BaseStrategy
from CookingEngine.Strategies import register_strategy
from KitchenBase.logger_config import get_logger
from backtrader.indicators import SMA, RSI

logger = get_logger(__name__)
logger.error(dir(bt.indicators))

@register_strategy("factor_strategy")
class FactorStrategy(BaseStrategy):
    def __init__(self, data_provider: DataProvider, factor_calculator: FactorCalculator,
                 trend_weight=0.25, momentum_weight=0.25, quality_weight=0.25,
                 timing_weight=0.25, lookback_period=20, max_positions=10,
                 buy_threshold=0.6, sell_threshold=0.4):
        super().__init__(data_provider, factor_calculator,
                        max_positions=max_positions)

        self.trend_weight = trend_weight
        self.momentum_weight = momentum_weight
        self.quality_weight = quality_weight
        self.timing_weight = timing_weight
        self.lookback_period = lookback_period
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

        self.ma20 = bt.indicators.SMA(self.datas[0], period=20) # pyright: ignore[reportCallIssue]
        self.ma60 = bt.indicators.SMA(self.datas[0], period=60) # pyright: ignore[reportCallIssue]  
        self.rsi = bt.indicators.RSI(self.datas[0], period=14) # pyright: ignore[reportCallIssue]

        logger.info(f"ma20: {self.ma20}")
        logger.info(f"ma60: {self.ma60}")
        logger.info(f"rsi: {self.rsi}")

        logger.info("FactorStrategy initialized with weights: trend=0.25, momentum=0.25, quality=0.25, timing=0.25")

    def next(self):
        current_date = self.datas[0].datetime.date(0).isoformat()
        stock_code = self.datas[0]._name

        try:
            # 获取最近60天的股票数据，用于计算因子
            start_date=self.datas[0].datetime.date(-60).isoformat()
            end_date = current_date
            price_data = self.data_provider.get_price_data(
                stock_code,
                start_date=start_date,
                end_date=end_date
            )

            # 参数检查
            if price_data is None or price_data.empty:
                logger.warning(f"No price data for {stock_code}")
                return

            # 计算因子
            trend_score = self.factor_calculator.calculate_trend_score(stock_code, start_date, end_date)
            momentum_score = self.factor_calculator.calculate_momentum_score(stock_code,  start_date, end_date)
            quality_score = self.factor_calculator.calculate_quality_score(stock_code,  start_date, end_date)
            timing_score = self.factor_calculator.calculate_timing_score(stock_code, start_date, end_date)

            logger.info(f"trend_score: {trend_score}")
            logger.info(f"momentum_score: {momentum_score}")
            logger.info(f"quality_score: {quality_score}")
            logger.info(f"timing_score: {timing_score}")

            total_score = (
                trend_score * self.trend_weight +
                momentum_score * self.momentum_weight +
                quality_score * self.quality_weight +
                timing_score * self.timing_weight
            )

            logger.debug(f"Factor scores for {stock_code} on {current_date}: "
                        f"trend={trend_score:.2f}, momentum={momentum_score:.2f}, "
                        f"quality={quality_score:.2f}, timing={timing_score:.2f}, "
                        f"total={total_score:.2f}")

            current_position = self.getposition(self.datas[0]).size

            if total_score >= self.buy_threshold and current_position == 0:
                size = self.get_position_size(self.datas[0].close[0])
                self.buy(size=size)
                self.log(f"BUY SIGNAL: Score={total_score:.2f}")

            elif total_score <= self.sell_threshold and current_position > 0:
                self.sell(size=abs(current_position))
                self.log(f"SELL SIGNAL: Score={total_score:.2f}")

        except Exception as e:
            logger.error(f"Error in factor calculation: {str(e)}")
