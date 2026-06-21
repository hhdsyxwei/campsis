import backtrader as bt
from CookingEngine.Strategies.Base import BaseStrategy
from CookingEngine.Strategies import register_strategy
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

@register_strategy("trend_pullback")
class TrendPullbackStrategy(BaseStrategy):
    params = (
        ("trend_pullback_volume_ratio", 0.8),
        ("trend_rebound_volume_multiple", 1.5),
        ("holding_days", 5),
        ("stop_loss_ratio", 0.05),
        ("take_profit_ratio", 0.10),
    )

    def __init__(self, data_provider, factor_calculator, **kwargs):
        super().__init__(data_provider, factor_calculator, **kwargs)
        self.order = None
        self.entry_price = 0
        self.buy_date = None
        
        self.ma5 = bt.indicators.SMA(self.data, period=5)  # pyright: ignore
        self.ma10 = bt.indicators.SMA(self.data, period=10)  # pyright: ignore
        self.ma20 = bt.indicators.SMA(self.data, period=20)  # pyright: ignore
        self.ma60 = bt.indicators.SMA(self.data, period=60)  # pyright: ignore
        self.rsi = bt.indicators.RSI(self.data, period=14)  # pyright: ignore
        self.macd = bt.indicators.MACD(
            self.data, period_me1=12, period_me2=26, period_signal=9  # pyright: ignore[reportCallIssue]
        )
        self.volume_ma5 = bt.indicators.SMA(self.data.volume, period=5)  # pyright: ignore[reportCallIssue]
        
        logger.info(f"TrendPullbackStrategy initialized with params: {self.params}")

    def next(self):
        if self.order:
            return
        
        current_date = self.data.datetime.date(0)
        stock_code = self.data._name
        
        if len(self.data) < 60:
            return
        
        latest = self.data.close[0]
        prev_1_close = self.data.close[-1]
        prev_2_close = self.data.close[-2]
        
        if not (self.ma5[0] > self.ma10[0] > self.ma20[0] > self.ma60[0]):
            return
        
        pullback_ma5 = (self.data.low[-2] <= self.ma5[-2]) and (self.data.low[-1] <= self.ma5[-1]) and (latest >= self.ma5[0])
        pullback_ma10 = (self.data.low[-2] <= self.ma10[-2]) and (self.data.low[-1] <= self.ma10[-1]) and (latest >= self.ma10[0])
        pullback_ma20 = (self.data.low[-2] <= self.ma20[-2]) and (self.data.low[-1] <= self.ma20[-1]) and (latest >= self.ma20[0])

        if not (pullback_ma5 or pullback_ma10 or pullback_ma20):
            return
        
        trend_pullback_volume_ratio = self.params.trend_pullback_volume_ratio  # pyright: ignore
        trend_rebound_volume_multiple = self.params.trend_rebound_volume_multiple  # pyright: ignore

        callback_volume = (self.data.volume[-2] <= self.volume_ma5[-2] * trend_pullback_volume_ratio) and \
                         (self.data.volume[-1] <= self.volume_ma5[-1] * trend_pullback_volume_ratio)
        rebound_volume = self.data.volume[0] >= self.volume_ma5[0] * trend_rebound_volume_multiple
        
        if not (callback_volume and rebound_volume):
            return
        
        if self.macd.lines[0][0] < self.macd.lines[1][0] or self.rsi[0] < 50:
            return
        
        if self.getposition(self.data).size == 0:
            size = self.get_position_size(latest)
            self.order = self.buy(size=size)
            self.entry_price = latest
            self.buy_date = current_date
            self.log(f"BUY SIGNAL: Trend Pullback - {stock_code} at {latest:.2f}")
        
        else:
            self._check_exit_conditions(current_date, latest)

    def _check_exit_conditions(self, current_date, current_price):
        days_held = (current_date - self.buy_date).days
        
        if days_held >= self.params.holding_days:  # pyright: ignore
            self.order = self.sell(size=self.getposition(self.data).size)
            self.log(f"SELL SIGNAL: Holding period exceeded - sold at {current_price:.2f}")
            return
        
        if self.entry_price > 0:
            loss_ratio = (self.entry_price - current_price) / self.entry_price
            if loss_ratio >= self.params.stop_loss_ratio:  # pyright: ignore
                self.order = self.sell(size=self.getposition(self.data).size)
                self.log(f"SELL SIGNAL: Stop loss triggered - sold at {current_price:.2f}")
                return
            
            profit_ratio = (current_price - self.entry_price) / self.entry_price
            if profit_ratio >= self.params.take_profit_ratio:  # pyright: ignore
                self.order = self.sell(size=self.getposition(self.data).size)
                self.log(f"SELL SIGNAL: Take profit triggered - sold at {current_price:.2f}")
                return