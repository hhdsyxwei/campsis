# base_strategy.py
# Base strategy class for Backtrader integration
import backtrader as bt
from CookingEngine.Picker.factor_calculator import FactorCalculator
from CookingEngine.Picker.data_provider import DataProvider
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


class BaseStrategy(bt.Strategy):
    def __init__(self, data_provider: DataProvider, factor_calculator: FactorCalculator,
                 initial_cash=1000000.0, max_positions=10, risk_per_trade=0.02):
        self.order = None
        self.data_provider = data_provider
        self.factor_calculator = factor_calculator
        self.stock_position_map = {}  # 以股票代码为键的持仓字典
        self.initial_cash = initial_cash
        self.max_positions = max_positions
        self.risk_per_trade = risk_per_trade
        self.trades = []
        self.starting_value = self.broker.getvalue()
        logger.info(f"BaseStrategy initialized with starting cash: {self.starting_value:.2f}")

    def log(self, txt, dt=None):
        dt = dt or self.datas[0].datetime.date(0)
        logger.info(f"[{dt.isoformat()}] {txt}")

    def notify_order(self, order):
        if order.status in [order.Submitted, order.Accepted]:
            return

        if order.status in [order.Completed]:
            if order.isbuy():
                self.log(f"BUY EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Commission: {order.executed.comm:.2f}")
                self.stock_position_map[order.data._name] = {
                        "price": order.executed.price,
                        "size": order.executed.size,
                        "cost": order.executed.value
                    }
            else:
                self.log(f"SELL EXECUTED, Price: {order.executed.price:.2f}, Cost: {order.executed.value:.2f}, Commission: {order.executed.comm:.2f}")
                if order.data._name in self.stock_position_map:
                    del self.stock_position_map[order.data._name]

        elif order.status in [order.Canceled, order.Margin, order.Rejected]:
            self.log("Order Canceled/Margin/Rejected")

        self.order = None

    def notify_trade(self, trade):
        if not trade.isclosed:
            return
        self.log(f"TRADE CLOSED, Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}")
        self.trades.append({
            "date": self.datas[0].datetime.date(0),
            "gross": trade.pnl,
            "net": trade.pnlcomm,
            "size": trade.size
        })

    def next(self):
        raise NotImplementedError("Subclasses must implement next()")

    def get_position_size(self, price):
        risk_amount = self.broker.getvalue() * self.risk_per_trade
        size = int(risk_amount / price)
        return max(1, size)

    def get_current_value(self):
        return self.broker.getvalue()

    def get_total_return(self):
        current = self.get_current_value()
        return (current - self.starting_value) / self.starting_value

    def stop(self):
        final_value = self.get_current_value()
        total_return = self.get_total_return()
        self.log(f"Final Portfolio Value: {final_value:.2f}")
        self.log(f"Total Return: {total_return:.2%}")
        self.log(f"Trades: {len(self.trades)}")
