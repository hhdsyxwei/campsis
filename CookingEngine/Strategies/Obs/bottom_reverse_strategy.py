import backtrader as bt
from CookingEngine.Strategies.Base import BaseStrategy
from CookingEngine.Strategies import register_strategy
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

@register_strategy("bottom_reverse")
class BottomReverseStrategy(BaseStrategy):
    """
    底部反转策略 - 识别超跌后放量反弹的股票
    
    核心逻辑：
    1. 股票经过深度下跌（累计跌幅≥50%）
    2. 进入横盘筑底阶段（20日内波动≤20%）
    3. 出现放量上涨（涨幅≥3%，量能≥2倍5日均量）
    4. RSI从超卖区回升（前5日≤20，当前≥50）
    5. MACD和KDJ同时金叉

    退出机制：
    - 持有期退出：持有5天后自动卖出
    - 止损退出：亏损≥5%时卖出
    - 止盈退出：盈利≥10%时卖出
    
    注册名称："bottom_reverse"
    """

    params = (
        # 底部反转条件参数
        ("reverse_fall_days", 60),         # 累计跌幅计算周期（交易日）
        ("reverse_max_fall_rate", 0.5),    # 最大累计跌幅阈值（50%）
        ("reverse_build_days", 20),        # 筑底周期（交易日）
        ("reverse_rise_threshold", 0.03),  # 反转当日最低涨幅（3%）
        ("reverse_volume_multiple", 2.0),   # 反转当日量能放大倍数（2倍）
        ("reverse_rsi_oversold", 20),      # RSI超卖区阈值（20以下）
        
        # 风险管理参数
        ("holding_days", 5),               # 固定持有天数
        ("stop_loss_ratio", 0.05),         # 止损比例（5%）
        ("take_profit_ratio", 0.10),       # 止盈比例（10%）
    )

    def __init__(self, data_provider, factor_calculator, **kwargs):
        """
        策略初始化方法
        
        Args:
            data_provider: 数据提供者，用于获取股票数据
            factor_calculator: 因子计算器，用于计算财务因子
            **kwargs: 额外参数（如初始资金、最大持仓数等）
        """
        # 调用父类初始化
        super().__init__(data_provider, factor_calculator, **kwargs)
        
        # 交易状态变量初始化
        self.order = None          # 当前未完成订单（避免重复下单）
        self.entry_price = 0       # 买入价格（用于计算盈亏）
        self.buy_date = None       # 买入日期（用于计算持有天数）
        
        # 技术指标初始化（Backtrader会自动维护每日更新）
        self.rsi = bt.indicators.RSI(self.data, period=14)  # pyright: ignore[reportCallIssue]  # 相对强弱指标
        self.macd = bt.indicators.MACD(
            self.data, period_me1=12, period_me2=26, period_signal=9  # MACD指标 # pyright: ignore[reportCallIssue]
        )
        self.stoch = bt.indicators.Stochastic(
            self.data, period=9, period_dfast=3, period_dslow=3  # KDJ指标 # pyright: ignore[reportCallIssue]
        )
        self.volume_ma5 = bt.indicators.SMA(self.data.volume, period=5)  # pyright: ignore[reportCallIssue]  # 5日成交量均线
        
        # 记录初始化日志
        logger.info(f"BottomReverseStrategy initialized with params: {self.params}")

    def next(self):
        """
        每日执行的核心策略逻辑
        
        执行流程：
        1. 检查是否有未完成订单（避免重复下单）
        2. 检查数据量是否足够
        3. 执行6个条件检查（全部满足才发出买入信号）
        4. 根据持仓状态执行买入或检查退出条件
        """
        # 1. 如果有未完成订单，跳过当前周期（避免重复下单）
        if self.order:
            return
        
        # 获取当前日期和股票代码
        current_date = self.data.datetime.date(0)
        stock_code = self.data._name

        # 2. 检查数据量是否足够（需要跌幅周期+筑底周期的数据）
        reverse_build_days = self.params.reverse_build_days # pyright: ignore
        reverse_fall_days = self.params.reverse_fall_days # pyright: ignore
        required_days = reverse_fall_days + reverse_build_days
        if len(self.data) < required_days:
            return

        # 获取当前和前一日收盘价
        latest = self.data.close[0]
        prev_close = self.data.close[-1]

        # 3. 条件1：检查累计跌幅是否达标（深度超跌）
        # 取跌幅周期内的最高价
        total_period = reverse_fall_days + reverse_build_days
        prev_high = max(self.data.high[-i] for i in range(1, reverse_fall_days + 1))
        # 计算累计跌幅
        current_fall_rate = (prev_high - latest) / prev_high
        # 跌幅未达参数所规定的最大累计跌幅(缺省设置50%)，不满足条件
        if current_fall_rate < self.params.reverse_max_fall_rate:  # pyright: ignore
            return

        # 4. 条件2：检查筑底阶段波动（横盘筑底）
        # 获取筑底周期的最高和最低价
        build_high = max(self.data.high[-i] for i in range(1, reverse_build_days + 1))
        build_low = min(self.data.low[-i] for i in range(1, reverse_build_days + 1))
        build_fluctuation = (build_high / build_low) - 1
        # 筑底周期内波动超过20%，不满足条件
        if build_fluctuation > 0.2:
            return

        # 5. 条件3：检查当日涨幅（放量上涨）
        latest_rise_rate = (latest - prev_close) / prev_close
        # 涨幅不足3%，不满足条件
        if latest_rise_rate < self.params.reverse_rise_threshold: # pyright: ignore
            return

        # 6. 条件4：检查量能放大（量能确认）
        if self.data.volume[0] < self.volume_ma5[0] * self.params.reverse_volume_multiple: # pyright: ignore
            return

        # 7. 条件5：检查RSI从超卖区回升（指标确认1）
        # 前5日RSI在超卖区（<=20）且当前RSI进入多头区间（>=50）
        if self.rsi[-5] > self.params.reverse_rsi_oversold or self.rsi[0] < 50: # pyright: ignore
            return
        
        # 8. 条件6：检查MACD和KDJ金叉（指标确认2）
        # MACD金叉：DIF从下向上穿越DEA
        macd_gold_cross = (self.macd.l.macd[-1] < self.macd.l.signal[-1]) and (self.macd.l.macd[0] > self.macd.l.signal[0])  # pyright: ignore
        # KDJ金叉：K线从下向上穿越D线
        kdj_gold_cross = (self.stoch.l.percK[-1] < self.stoch.l.percD[-1]) and (self.stoch.l.percK[0] > self.stoch.l.percD[0])  # pyright: ignore
        # 两个指标必须同时金叉
        if not (macd_gold_cross and kdj_gold_cross):
            return
        
        # 9. 所有条件满足，执行交易决策
        if self.getposition(self.data).size == 0:
            # 无持仓：计算仓位并发出买入订单
            size = self.get_position_size(latest)           # 按账户2%风险计算仓位
            self.order = self.buy(size=size)               # 发出买入订单
            self.entry_price = latest                       # 记录买入价格
            self.buy_date = current_date                   # 记录买入日期
            self.log(f"BUY SIGNAL: Bottom Reverse - {stock_code} at {latest:.2f}")
        
        else:
            # 有持仓：检查退出条件
            self._check_exit_conditions(current_date, latest)

    def _check_exit_conditions(self, current_date, current_price):
        """
        检查退出条件（三重退出机制）
        
        退出优先级：
        1. 持有期退出（优先）：持有天数达到设定值
        2. 止损退出：亏损达到设定比例
        3. 止盈退出：盈利达到设定比例
        
        Args:
            current_date: 当前日期
            current_price: 当前价格
        """
        # 计算持有天数
        days_held = (current_date - self.buy_date).days
        
        # 退出条件1：持有期退出（持有5天后自动卖出）
        if days_held >= self.params.holding_days: # pyright: ignore
            self.order = self.sell(size=self.getposition(self.data).size)
            self.log(f"SELL SIGNAL: Holding period exceeded - sold at {current_price:.2f}")
            return
        
        # 退出条件2和3：需要有有效的买入价格
        if self.entry_price > 0:
            # 退出条件2：止损退出（亏损≥5%时卖出）
            loss_ratio = (self.entry_price - current_price) / self.entry_price
            if loss_ratio >= self.params.stop_loss_ratio: # pyright: ignore
                self.order = self.sell(size=self.getposition(self.data).size)
                self.log(f"SELL SIGNAL: Stop loss triggered - sold at {current_price:.2f}")
                return
            
            # 退出条件3：止盈退出（盈利≥10%时卖出）
            profit_ratio = (current_price - self.entry_price) / self.entry_price
            if profit_ratio >= self.params.take_profit_ratio: # pyright: ignore
                self.order = self.sell(size=self.getposition(self.data).size)
                self.log(f"SELL SIGNAL: Take profit triggered - sold at {current_price:.2f}")
                return