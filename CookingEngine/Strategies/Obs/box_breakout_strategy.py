import backtrader as bt
from CookingEngine.Strategies.Base import BaseStrategy
from CookingEngine.Strategies import register_strategy
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

@register_strategy("box_breakout")
class BoxBreakoutStrategy(BaseStrategy):
    params = (
        ("box_range_days", 20),
        ("box_fluctuation_rate", 0.15),
        ("box_break_threshold", 1.03),
        ("box_volume_multiple", 2.0),
        ("holding_days", 5),
        ("stop_loss_ratio", 0.05),
        ("take_profit_ratio", 0.10),
    )

    def __init__(self, data_provider, factor_calculator, **kwargs):
        super().__init__(data_provider, factor_calculator, **kwargs)
        self.order = None
        self.entry_price = 0
        self.buy_date = None
        
        self.ma5 = bt.indicators.SMA(self.data, period=5)  # pyright: ignore[reportCallIssue]
        self.ma10 = bt.indicators.SMA(self.data, period=10)  # pyright: ignore[reportCallIssue]
        self.volume_ma5 = bt.indicators.SMA(self.data.volume, period=5)  # pyright: ignore[reportCallIssue]
        
        logger.info(f"BoxBreakoutStrategy initialized with params: {self.params}")

    def next(self):
        if self.order:
            return
        
        current_date = self.data.datetime.date(0)
        stock_code = self.data._name
        box_range_days = self.params.box_range_days # pyright: ignore
        
        if len(self.data) < box_range_days + 5:
            return
        
        latest = self.data.close[0]
        box_high = max(self.data.high.get(size=box_range_days))
        box_low = min(self.data.low.get(size=box_range_days))
    
        box_fluctuation = (box_high / box_low) - 1

        if box_fluctuation > self.params.box_fluctuation_rate:  # pyright: ignore
            return
        
        if latest < box_high * self.params.box_break_threshold:  # pyright: ignore
            return
        
        if self.data.volume[0] < self.volume_ma5[0] * self.params.box_volume_multiple:  # pyright: ignore
            return
        
        if latest < self.ma5[0] or latest < self.ma10[0]:
            return
        
        if self.getposition(self.data).size == 0:
            size = self.get_position_size(latest)
            self.order = self.buy(size=size)
            self.entry_price = latest
            self.buy_date = current_date
            self.log(f"BUY SIGNAL: Box Breakout - {stock_code} at {latest:.2f}")
        
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