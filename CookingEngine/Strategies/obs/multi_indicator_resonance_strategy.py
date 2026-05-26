import backtrader as bt
from CookingEngine.Strategies.base import BaseStrategy
from CookingEngine.Strategies import register_strategy
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

@register_strategy("multi_indicator_resonance")
class MultiIndicatorResonanceStrategy(BaseStrategy):
    params = (
        ("resonance_rsi_lower", 50),
        ("resonance_rsi_upper", 70),
        ("min_signal_count", 4),
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
        self.rsi = bt.indicators.RSI(self.data, period=14)  # pyright: ignore[reportCallIssue]
        self.macd = bt.indicators.MACDHisto(
            self.data, period_me1=12, period_me2=26, period_signal=9  # pyright: ignore[reportCallIssue]
        )
        self.stoch = bt.indicators.Stochastic(
            self.data, period=9, period_dfast=3, period_dslow=3  # pyright: ignore[reportCallIssue]
        )

        self.bbands = bt.indicators.BBands( # pyright: ignore
            self.data, period=20, devfactor=2.0  
        )
        
        logger.info(f"MultiIndicatorResonanceStrategy initialized with params: {self.params}")

    def next(self):
        if self.order:
            return
        
        current_date = self.data.datetime.date(0)
        stock_code = self.data._name
        
        if len(self.data) < 30:
            return
        
        latest = self.data.close[0]
        prev_1_close = self.data.close[-1]
        
        ma_signal = (latest >= self.ma5[0]) and (latest >= self.ma10[0]) and (self.ma5[0] > self.ma5[-1])
        
        macd_signal = (self.macd.l.macd[-1] < self.macd.l.signal[-1]) and (self.macd.l.macd[0] > self.macd.l.signal[0]) and \
                      (self.macd.l.histo[0] > self.macd.l.histo[-1])  # pyright: ignore
        
        resonance_rsi_upper = self.params.resonance_rsi_upper # pyright: ignore
        resonance_rsi_lower = self.params.resonance_rsi_lower # pyright: ignore
        rsi_signal = (self.rsi[0] >= resonance_rsi_lower)\
            and (self.rsi[0] <= resonance_rsi_upper)  # pyright: ignore
        
        kdj_k = self.stoch.l.percK
        kdj_d = self.stoch.l.percD
        kdj_j = 3 * kdj_k[0] - 2 * kdj_d[0]  # pyright: ignore
        kdj_signal = (kdj_k[-1] < kdj_d[-1]) and (kdj_k[0] > kdj_d[0]) and (kdj_j >= 20)
        
        boll_mid = self.bbands.l.mid
        boll_signal = (latest >= boll_mid[0]) and (latest > prev_1_close)
        
        signal_count = sum([ma_signal, macd_signal, rsi_signal, kdj_signal, boll_signal])
        
        if signal_count < self.params.min_signal_count:  # pyright: ignore
            return
        
        if self.getposition(self.data).size == 0:
            size = self.get_position_size(latest)
            self.order = self.buy(size=size)
            self.entry_price = latest
            self.buy_date = current_date
            self.log(f"BUY SIGNAL: Multi-Indicator Resonance ({signal_count}/5) - {stock_code} at {latest:.2f}")
        
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