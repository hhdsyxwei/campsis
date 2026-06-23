# trailing_bearish_grid_strategy.py
# Trailing Bearish Grid Strategy (空头追踪网格策略)
import traceback

import backtrader as bt

from CookingEngine.Strategies.Base import BaseStrategy
from CookingEngine.Strategies import register_strategy


@register_strategy("trailing_bearish_grid")
class TrailingBearishGridStrategy(BaseStrategy):
    """
    Trailing Bearish Grid Strategy (空头追踪网格策略)

    Usage:
        python main.py backtest --kind bearish_grid --stock-code 300760.SZ --start-date 2025-01-01 --end-date 2025-02-28

    Core Mechanism:
    1. Base price dynamically shifts down, following the downtrend channel.
    2. Continuous grid selling, calculated based on the previous sell price.
    3. Position protection: remaining position not less than initial 50%.
    4. Closed loop buy-back, locking in each round's profit.
    5. Dual-dimension profit tracking:
       - Cash profit (realized)
       - Total asset profit (including floating)
       - Annualized return rates for both
    6. Mandatory forced buy-back:
       If a grid cannot be bought back within N trading days (default 20),
       a market buy-back is force-executed regardless of price to avoid
       the "incomplete buy-back trap".

    WARNING: The forced buy-back mechanism is a double-edged sword.
    In a sustained bull market, it will execute market buy-backs at
    significantly higher prices, resulting in realized losses.
    See Section 7.5 of the design doc for full risk disclosure.
    """

    params = (
        ('initial_position_ratio', 0.5),
        ('grid_up_ratio', 0.03),
        ('grid_down_ratio', 0.05),
        ('grid_sell_ratio', 0.1),
        ('base_shift_threshold', 0.02),
        ('min_position_ratio', 0.5),
        ('max_grid_count', 5),
        ('mandatory_buyback_days', 20),
    )

    def __init__(self, data_provider, factor_calculator, **kwargs):
        try:
            super().__init__(data_provider, factor_calculator, **kwargs)

            self._initialized = False

            self.current_position = 0
            self.p_base = 0.0
            self.sold_grids = []
            self.round_count = 0
            self.total_profit = 0.0

            self.initial_total_asset = 0.0
            self.initial_shares = 0
            self.cash_profit = 0.0
            self.total_asset_profit = 0.0
            self.start_date = None

            self.force_completed_count = 0
            self.force_loss_total = 0.0
            self.force_buyback_warned = False
            self.allow_new_sells = True

            self.order = None
            self.slippage_perc = 0.001  # 滑点比例 0.1%
            self._pending_grid = None
            self._last_expected_price = 0.0  # 最近一次下单的期望价格
            self._last_grid_level = '-'  # 最近一次下单的网格级别
        except Exception as e:
            raise

    def _do_first_bar_init(self):
        """在第一根 K 线上完成 P_base 初始化和初始建仓

        注意：backtrader 的 __init__ 执行时 self.data.close[0] 指向最后一根 K 线，
        因此 P_base 必须延迟到 next() 首次调用时才能正确获取第一根 K 线的价格。
        """
        try:
            initial_value = self.broker.getvalue()
            current_close = float(self.data.close[0])

            self.p_base = current_close

            initial_capital = initial_value * self.params.initial_position_ratio  # pyright: ignore
            self.initial_shares = int(initial_capital / current_close)
            self.current_position = self.initial_shares

            self.initial_total_asset = initial_value
            self.start_date = self.data.datetime.date(0)

            if self.initial_shares > 0:
                initial_price = current_close * (1.0 + self.slippage_perc)
                self._last_expected_price = current_close
                self._last_grid_level = 0
                self.order = self.buy(size=self.initial_shares, price=initial_price)
        except Exception as e:
            raise

    # ------------------------------------------------------------
    # Base price management
    # ------------------------------------------------------------
    def update_base_price(self):
        try:
            today_low = float(self.data.low[0])
            threshold = self.p_base * (1.0 - self.params.base_shift_threshold) # pyright: ignore
            if today_low < threshold:
                self.p_base = today_low
        except Exception as e:
            pass

    # ------------------------------------------------------------
    # Force buyback (HIGHEST PRIORITY)
    # ------------------------------------------------------------
    def check_force_buyback_signals(self):
        try:
            current_date = self.data.datetime.date(0)
            force_candidates = []
            for grid in self.sold_grids:
                if grid.get('filled', False):
                    continue
                sell_date = grid.get('sell_date')
                if sell_date is None:
                    continue
                holding_days = (current_date - sell_date).days
                if holding_days >= self.params.mandatory_buyback_days: # pyright: ignore
                    force_candidates.append((grid, holding_days))
            # LIFO 原则：优先买回最近卖出的格子（按 sell_date 降序排列）
            force_candidates.sort(key=lambda x: x[0].get('sell_date'), reverse=True)
            return force_candidates
        except Exception as e:
            return []

    def execute_force_buyback(self, grid, holding_days):
        try:
            current_price = float(self.data.close[0])
            buy_shares = grid.get('sell_shares', 0)
            required_cash = buy_shares * current_price
            available_cash = self.broker.get_cash()

            if available_cash < required_cash:
                self._enter_emergency_mode('insufficient_cash_for_force_buyback')
                return False

            force_buy_price = current_price * (1.0 + self.slippage_perc)
            grid_level = grid.get('grid_level', '-')
            self._last_expected_price = current_price
            self._last_grid_level = grid_level
            self.order = self.buy(size=buy_shares, price=force_buy_price)

            # 保留已有的 sell_price_actual（应该已被 notify_order 正确设置）
            grid['buy_price_actual'] = current_price
            grid['buy_date'] = self.data.datetime.date(0)
            grid['buy_commission'] = float(self.broker.getcommissioninfo(self.data).getcommission(
                buy_shares, current_price
            ))
            grid['filled'] = True
            grid['force_completed'] = True
            grid['force_reason'] = 'timeout'
            grid['force_loss'] = (current_price - grid.get('buy_price', current_price)) * buy_shares

            self.force_completed_count += 1
            self.force_loss_total += grid['force_loss']

            self.close_grid_round(grid)

            if not self.force_buyback_warned:
                self.force_buyback_warned = True

            return True
        except Exception as e:
            return False

    def _enter_emergency_mode(self, reason):
        try:
            self.allow_new_sells = False
            for grid in self.sold_grids:
                if not grid.get('filled', False):
                    grid['force_completed'] = True
                    grid['force_reason'] = 'emergency'
                    grid['filled'] = True
            self._notify_emergency(reason)
        except Exception as e:
            pass

    def _notify_emergency(self, reason):
        try:
            pass
        except Exception as e:
            pass

    # ------------------------------------------------------------
    # Sell / Buy signal checks
    # ------------------------------------------------------------
    def check_sell_signals(self):
        try:
            current_date = self.data.datetime.date(0)
            min_position_ratio = self.params.min_position_ratio # pyright: ignore
            grid_up_ratio = self.params.grid_up_ratio # pyright: ignore
            grid_sell_ratio = self.params.grid_sell_ratio # pyright: ignore
            grid_down_ratio = self.params.grid_down_ratio # pyright: ignore
            max_grid_count = self.params.max_grid_count # pyright: ignore
            current_price = float(self.data.close[0])
            day_high = float(self.data.high[0])
            day_low = float(self.data.low[0])

            # 检查 1: 是否允许新卖出
            if not self.allow_new_sells:
                return False, None

            # 计算下一个网格的卖出价
            if len(self.sold_grids) == 0:
                next_sell_price = self.p_base * (1.0 + grid_up_ratio)
            else:
                last_grid = self.sold_grids[-1]
                next_sell_price = last_grid['sell_price'] * (1.0 + grid_up_ratio)

            # 检查 2: 卖出价是否在当日K线范围内（必须能当天成交）
            if next_sell_price < day_low:
                return False, None

            # 检查 3: 当前价格是否达到卖出价
            if current_price < next_sell_price:
                return False, None

            # 计算剩余仓位
            total_sold = sum(g['sell_shares'] for g in self.sold_grids)
            remaining = self.current_position - total_sold
            min_allowed = int(self.initial_shares * min_position_ratio)

            # 检查 4: 剩余仓位是否充足
            if remaining <= min_allowed:
                return False, None

            # 检查 5: 网格数量是否超限
            if len(self.sold_grids) >= max_grid_count:
                return False, None

            # 计算卖出数量
            sell_shares = int(self.initial_shares * grid_sell_ratio)
            actual_shares = min(sell_shares, max(0, remaining - min_allowed))

            # 检查 6: 实际卖出数量是否为 0
            if actual_shares <= 0:
                return False, None

            # 所有检查通过，返回卖出信号
            buy_price = next_sell_price * (1.0 - grid_down_ratio)
            return True, {
                'sell_price': next_sell_price,
                'sell_shares': actual_shares,
                'buy_price': buy_price,
            }
        except Exception as e:
            return False, None

    def check_buy_signals(self):
        try:
            current_price = float(self.data.close[0])
            day_high = float(self.data.high[0])
            day_low = float(self.data.low[0])
            grid_down_ratio = self.params.grid_down_ratio  # pyright: ignore
            unsold_grids = [g for g in self.sold_grids if not g.get('filled', False)]
            unsold_grids.sort(key=lambda x: x.get('sell_price_actual') if x.get('sell_price_actual') is not None else x.get('sell_price', 0), reverse=True)

            for grid in unsold_grids:
                # 基于实际卖出价动态计算买回价（优先使用实际成交价）
                if grid.get('sell_price_actual') is not None:
                    actual_sell_price = grid['sell_price_actual']
                else:
                    actual_sell_price = grid.get('sell_price', current_price)
                buy_price = actual_sell_price * (1.0 - grid_down_ratio)

                # 调试日志
                self.log(f"[BUY CHECK] Grid #{grid.get('grid_level')}, sell_price_actual={grid.get('sell_price_actual')}, sell_price={grid.get('sell_price')}, buy_price={buy_price:.2f}, close={current_price:.2f}")

                # 检查1: 当前价格达到买回价
                if current_price > buy_price:
                    continue

                # 检查2: 买回价在当日K线范围内（必须能当天成交）
                if buy_price > day_high:
                    continue

                # 检查3: 资金是否充足
                required_cash = grid['sell_shares'] * current_price
                if self.broker.get_cash() < required_cash:
                    continue

                return True, grid

            return False, None
        except Exception as e:
            return False, None

    # ------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------
    def execute_sell(self, sell_info):
        try:
            size = sell_info['sell_shares']
            price = sell_info['sell_price']
            self._last_expected_price = price
            self._last_grid_level = sell_info.get('grid_level', '-')
            sell_price_with_slippage = price * (1.0 - self.slippage_perc)
            self.order = self.sell(size=size, price=sell_price_with_slippage)
        except Exception as e:
            pass

    def execute_buy(self, grid):
        try:
            size = grid['sell_shares']
            grid_down_ratio = self.params.grid_down_ratio  # pyright: ignore
            # 基于实际卖出价动态计算买回价（优先使用实际成交价）
            if grid.get('sell_price_actual') is not None:
                actual_sell_price = grid['sell_price_actual']
            else:
                actual_sell_price = grid.get('sell_price', float(self.data.close[0]))
            buy_price = actual_sell_price * (1.0 - grid_down_ratio)
            self._last_expected_price = buy_price
            self._last_grid_level = grid.get('grid_level', '-')
            buy_price_with_slippage = buy_price * (1.0 + self.slippage_perc)
            
            # 调试日志
            self.log(f"[BUY EXEC] Grid #{grid.get('grid_level')}, sell_price_actual={grid.get('sell_price_actual')}, actual_sell_price={actual_sell_price}, buy_price={buy_price:.2f}, size={size}")
            
            self.order = self.buy(size=size, price=buy_price_with_slippage)
        except Exception as e:
            pass

    def close_grid_round(self, grid):
        try:
            grid_in_stack = grid in self.sold_grids
            if not grid_in_stack:
                return

            if grid.get('_round_closed', False):
                return

            if not grid.get('filled', False):
                grid['filled'] = True
                if grid.get('buy_price_actual') is None:
                    grid['buy_price_actual'] = float(self.data.close[0])
                if grid.get('buy_date') is None:
                    grid['buy_date'] = self.data.datetime.date(0)
            else:
                if grid.get('buy_price_actual') is None:
                    grid['buy_price_actual'] = float(self.data.close[0])
                if grid.get('buy_date') is None:
                    grid['buy_date'] = self.data.datetime.date(0)

            sell_price = grid.get('sell_price_actual', grid.get('sell_price', 0))
            if sell_price is None:
                sell_price = grid.get('sell_price', 0)
            buy_price = grid.get('buy_price_actual', 0)
            if buy_price is None:
                buy_price = 0
            shares = grid.get('sell_shares', 0)
            gross_pnl = (sell_price - buy_price) * shares
            commission = grid.get('sell_commission', 0) + grid.get('buy_commission', 0)
            net_pnl = gross_pnl - commission

            self.total_profit += net_pnl

            self.cash_profit = self.total_profit
            current_total_asset = self._compute_current_total_asset()
            self.total_asset_profit = current_total_asset - self.initial_total_asset

            trade_record = {
                'round_id': grid.get('round_id', 0),
                'grid_level': grid.get('grid_level', 0),
                'sell_date': grid.get('sell_date'),
                'buy_date': grid.get('buy_date'),
                'sell_price': sell_price,
                'buy_price': buy_price,
                'shares': shares,
                'gross_pnl': gross_pnl,
                'commission': commission,
                'net_pnl': net_pnl,
                'net': net_pnl,
                'gross': gross_pnl,
                'is_win': net_pnl > 0,
            }
            self.trades.append(trade_record)

            grid['_round_closed'] = True

            if all(g.get('filled', False) for g in self.sold_grids):
                self.round_count += 1
                self.sold_grids = []
        except Exception as e:
            pass

    def _compute_current_total_asset(self):
        try:
            price = float(self.data.close[0])
            return self.broker.get_cash() + self.current_position * price
        except Exception as e:
            return self.broker.get_cash()

    def _update_profit_status(self):
        try:
            current_total_asset = self._compute_current_total_asset()
            self.total_asset_profit = current_total_asset - self.initial_total_asset
            self.cash_profit = self.total_profit
        except Exception as e:
            pass

    def _issue_sold_grid_record(self, sell_info):
        try:
            current_date = self.data.datetime.date(0)
            new_grid = {
                'round_id': self.round_count,
                'grid_level': len(self.sold_grids) + 1,
                'sell_price': sell_info['sell_price'],
                'sell_price_actual': None,
                'sell_shares': sell_info['sell_shares'],
                'buy_price': sell_info['buy_price'],
                'buy_price_actual': None,
                'filled': False,
                'sell_date': current_date,
                'force_completed': False,
                'force_reason': None,
                'force_loss': 0.0,
            }
            self.sold_grids.append(new_grid)
            self._pending_grid = new_grid
        except Exception as e:
            pass

    # ------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------
    def next(self):
        try:
            if not self._initialized:
                self._do_first_bar_init()
                self._initialized = True
                return

            # 输出当前K线数据：开盘价、最高价、最低价、收盘价
            open_price = float(self.data.open[0])
            high_price = float(self.data.high[0])
            low_price = float(self.data.low[0])
            close_price = float(self.data.close[0])
            self.log(
                f"[{self.data.datetime.date(0)}] OHLC: "
                f"O:{open_price:.2f}, H:{high_price:.2f}, L:{low_price:.2f}, C:{close_price:.2f}"
            )

            if self.order is not None:
                return

            # Step 0: Force buyback check (HIGHEST PRIORITY)
            force_candidates = self.check_force_buyback_signals()
            if force_candidates:
                for grid, holding_days in force_candidates:
                    self.log(f"[FORCE BUY] Grid #{grid.get('grid_level')}, sell_price_actual={grid.get('sell_price_actual')}, holding_days={holding_days}")
                    self.execute_force_buyback(grid, holding_days)
                self._update_profit_status()
                return

            # Step 1: Base price update
            self.update_base_price()

            # Step 2: Normal buy check
            buy_signal, buy_grid = self.check_buy_signals()
            if buy_signal and buy_grid is not None:
                self.log(f"[NORMAL BUY] Grid #{buy_grid.get('grid_level')}, sell_price_actual={buy_grid.get('sell_price_actual')}, sell_price={buy_grid.get('sell_price')}")
                self.execute_buy(buy_grid)
                self._update_profit_status()
                return

            # Step 3: Normal sell check
            sell_signal, sell_info = self.check_sell_signals()
            if sell_signal and sell_info is not None:
                sell_info['grid_level'] = len(self.sold_grids) + 1
                self.execute_sell(sell_info)
                self._issue_sold_grid_record(sell_info)
                self._update_profit_status()
                return

            # Step 4: Status log
            self._update_profit_status()
        except Exception as e:
            pass

    def notify_order(self, order):
        """订单状态变化回调函数

        处理卖出/买入订单完成后的逻辑：
        1. 更新持仓数量
        2. 匹配对应网格并更新网格状态
        3. 对于买回订单，若网格已卖出则结算该网格的盈亏
        """
        try:
            # 过滤挂单状态：只处理已完成的订单
            if order.status in [order.Submitted, order.Accepted]:
                return

            # 订单已完成
            if order.status in [order.Completed]:
                # 提取订单执行信息
                executed_price = order.executed.price  # 实际成交价
                executed_size = int(order.executed.size)  # 成交股数（正=买入，负=卖出）
                action = 'BUY' if order.isbuy() else 'SELL'

                # 从保存的最近一次下单的期望价格和网格级别获取
                expected_price = self._last_expected_price if self._last_expected_price > 0 else executed_price
                grid_level = self._last_grid_level

                # 输出交易日志：记录成交价、股数、P_base、网格级别、期望价、实际价
                self.log(
                    f"{action} EXECUTED, Level: {grid_level}, Price: {executed_price:.2f}, Size: {executed_size}, "
                    f"P_base: {self.p_base:.2f}, Expected: {expected_price:.2f}, Actual: {executed_price:.2f}"
                )

                # 处理买入订单（买回网格）
                if order.isbuy():
                    # 更新持仓：增加买入股数
                    self.current_position = self.current_position + executed_size

                    # 匹配网格：找到对应的卖出网格并标记买回（LIFO：从尾部开始遍历）
                    for grid in reversed(self.sold_grids):
                        # 匹配条件：网格未买回 + 股数匹配 + 未实际买回 + 已卖出
                        if (not grid.get('filled', False)
                                and grid.get('sell_shares') == executed_size
                                and grid.get('buy_price_actual') is None
                                and grid.get('sell_date') is not None):
                            # 更新网格的实际买回信息
                            grid['buy_price_actual'] = executed_price  # 实际买回价
                            grid['buy_commission'] = float(order.executed.comm)  # 买回佣金
                            grid['buy_date'] = self.data.datetime.date(0)  # 买回日期

                            # 若网格已完成卖出，则结算该网格的盈亏
                            if grid.get('sell_price_actual') is not None:
                                self.close_grid_round(grid)  # 调用结算函数
                            break  # 只匹配第一个符合条件的网格

                # 处理卖出订单（卖出网格）
                else:
                    # 更新持仓：减少卖出股数
                    self.current_position = self.current_position - abs(executed_size)

                    # 优先使用 _pending_grid 引用更新
                    if hasattr(self, '_pending_grid') and self._pending_grid is not None:
                        grid = self._pending_grid
                        grid['sell_price_actual'] = executed_price
                        grid['sell_commission'] = float(order.executed.comm)
                        grid['buy_price'] = executed_price * (1.0 - self.params.grid_down_ratio)  # pyright: ignore
                        self._pending_grid = None
                    else:
                        # 回退方案：从尾部开始匹配最近添加的网格
                        for grid in reversed(self.sold_grids):
                            if (not grid.get('filled', False)
                                    and grid.get('sell_shares') == abs(executed_size)):
                                grid['sell_price_actual'] = executed_price
                                grid['sell_commission'] = float(order.executed.comm)
                                grid['buy_price'] = executed_price * (1.0 - self.params.grid_down_ratio)  # pyright: ignore
                                break

            # 重置订单引用，允许下一个订单下单
            self.order = None

        except Exception as e:
            # 异常处理：重置订单引用，防止订单阻塞
            self.order = None

    def notify_trade(self, trade):
        try:
            pass
        except Exception as e:
            pass

    def stop(self):
        try:
            final_value = self.get_current_value()
            total_return = self.get_total_return()
            super().stop()
        except Exception as e:
            pass
