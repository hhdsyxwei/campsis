import backtrader as bt
from CookingEngine.Strategies.base import BaseStrategy
from CookingEngine.Strategies import register_strategy
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

@register_strategy("multi_indicator_resonance")
class MultiIndicatorResonanceStrategy(BaseStrategy):
    """
    多指标共振策略

    适用范围：
    - 适合长期上涨趋势（牛市）中的股票，不适合下降通道或震荡市
    - 需要股价处于 MA60 均线上方，且 MA60 持续上升

    标的走势阶段要求：
    - 主要捕捉上涨趋势的初期或中期
    - 趋势惯性需要足够大，避免在下降通道中接飞刀

    信号条件：5 个技术指标中至少 4 个同时发出看涨信号
    - 均线多头排列：价格 > MA5 > MA10，且均线上升
    - MACD 金叉：DIF 上穿 DEA，直方图放大
    - RSI 强势区间：RSI ∈ [50, 70]
    - KDJ 金叉：K 线上穿 D 线
    - 布林带中轨支撑：价格在中轨上方

    风险控制：
    - 止损 5%，止盈 10%，最大持有 5 天

    回测数据（000001.SZ，2020-01 至 2026-05）：
    - 总交易次数：22 次
    - 盈利交易：12 次，亏损交易：10 次
    - 胜率：54.55%
    - 总收益：-257,045.85 元（亏损）
    - 问题：胜率虽然超过 50%，但亏损幅度大于盈利幅度
    - 原因：下降通道中频繁止损，亏损累积

    改进建议：
    - 添加长期趋势过滤（MA60 或 MA250）
    - 选择长期上涨趋势的股票进行回测
    - 调整止损止盈比例为对称设置
    - 延长最大持有期

    注意：在使用前建议检查标的长期趋势，避免在下跌趋势中频繁止损
    """
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
        
        # 均线多头排列：价格在5日均线上方，5日均线在10日均线上方
        # 且5日和10日均线均呈上升趋势
        ma_signal = (latest >= self.ma5[0]) and \
                    (self.ma5[0] >= self.ma10[0]) and \
                    (self.ma5[0] > self.ma5[-1]) and \
                    (self.ma10[0] > self.ma10[-1])

        # MACD金叉信号：MACD 金叉确认，配合直方图放大。
        # ✅ 昨日：MACD 线 < 信号线（金叉前状态）
        # ✅ 今日：MACD 线 > 信号线（金叉发生）
        # ✅ 直方图今日 > 昨日（上涨动能增强）
        macd_signal = (self.macd.l.macd[-1] < self.macd.l.signal[-1]) and (self.macd.l.macd[0] > self.macd.l.signal[0]) and \
                      (self.macd.l.histo[0] > self.macd.l.histo[-1])  # pyright: ignore

        # RSI 强势区间信号 (RSI Signal)
        # ✅ 今日RSI在50-70之间（强势区间）
        # ✅ RSI ∈ [50, 70]（默认参数）
        resonance_rsi_upper = self.params.resonance_rsi_upper # pyright: ignore
        resonance_rsi_lower = self.params.resonance_rsi_lower # pyright: ignore
        rsi_signal = (self.rsi[0] >= resonance_rsi_lower)\
            and (self.rsi[0] <= resonance_rsi_upper)  # pyright: ignore

        # KDJ 金叉信号 (KDJ Signal)
        # 条件：✅ 昨日：K 线 < D 线（金叉前状态）
        # ✅ 今日：K 线 > D 线（金叉发生）
        # ✅ J 值 ≥ 20（非极端超卖）
        # 含义 ：KDJ 金叉确认，且不是从极端超卖位置反弹。
        kdj_k = self.stoch.l.percK
        kdj_d = self.stoch.l.percD
        kdj_j = 3 * kdj_k[0] - 2 * kdj_d[0]  # pyright: ignore
        kdj_signal = (kdj_k[-1] < kdj_d[-1]) and (kdj_k[0] > kdj_d[0]) and (kdj_j >= 20)
        
        # 布林带中轨支撑信号 (Bollinger Bands Signal)
        # ✅ 今日价 >= 中轨（支撑）
        # ✅ 今日价 > 昨日价（上涨动能增强）
        # 含义 ：当前价在布林带中轨以上，且上涨动能增强，可能表示趋势继续向上。
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