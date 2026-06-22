# trailing_bearish_grid_strategy.py
# Trailing Bearish Grid Strategy (空头追踪网格策略)
import traceback

import backtrader as bt

from CookingEngine.Strategies.Base import BaseStrategy
from CookingEngine.Strategies import register_strategy
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


@register_strategy("trailing_bearish_grid")
class TrailingBearishGridStrategy(BaseStrategy):
    """
    Trailing Bearish Grid Strategy (空头追踪网格策略)

    Usage:
        python main.py backtest --kind bearish_grid --stock-code 300760.SZ --start-date 2025-01-01 --end-date 2026-06-18

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
                self.order = self.buy(size=self.initial_shares)
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
            force_candidates.sort(key=lambda x: x[0].get('sell_date'))
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

            self.order = self.buy(size=buy_shares)

            grid['sell_price_actual'] = grid.get('sell_price')
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

            # 检查 1: 是否允许新卖出
            if not self.allow_new_sells:
                return False, None

            # 计算下一个网格的卖出价
            if len(self.sold_grids) == 0:
                next_sell_price = self.p_base * (1.0 + grid_up_ratio)
            else:
                last_grid = self.sold_grids[-1]
                next_sell_price = last_grid['sell_price'] * (1.0 + grid_up_ratio)

            # 检查 2: 当前价格是否达到卖出价
            if current_price < next_sell_price:
                return False, None

            # 计算剩余仓位
            total_sold = sum(g['sell_shares'] for g in self.sold_grids)
            remaining = self.current_position - total_sold
            min_allowed = int(self.initial_shares * min_position_ratio)

            # 检查 3: 剩余仓位是否充足
            if remaining <= min_allowed:
                return False, None

            # 检查 4: 网格数量是否超限
            if len(self.sold_grids) >= max_grid_count:
                return False, None

            # 计算卖出数量
            sell_shares = int(self.initial_shares * grid_sell_ratio)
            actual_shares = min(sell_shares, max(0, remaining - min_allowed))

            # 检查 5: 实际卖出数量是否为 0
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
            unsold_grids = [g for g in self.sold_grids if not g.get('filled', False)]
            unsold_grids.sort(key=lambda x: x.get('sell_price', 0), reverse=True)

            for grid in unsold_grids:
                buy_price = grid.get('buy_price', current_price)
                if current_price <= buy_price:
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
            self.order = self.sell(size=size, price=price)
        except Exception as e:
            pass

    def execute_buy(self, grid):
        try:
            size = grid['sell_shares']
            price = grid.get('buy_price', float(self.data.close[0]))
            self.order = self.buy(size=size, price=price)
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

            self._log_grid_stack(f"BUY @{buy_price:.2f}")

            if all(g.get('filled', False) for g in self.sold_grids):
                self.round_count += 1
                self.sold_grids = []
                self._log_grid_stack("ROUND COMPLETE (STACK CLEARED)")
        except Exception as e:
            pass

    def _compute_current_total_asset(self):
        try:
            price = float(self.data.close[0])
            return self.broker.get_cash() + self.current_position * price
        except Exception as e:
            return self.broker.get_cash()

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
            self._log_grid_stack(f"SELL @{new_grid['sell_price']:.2f}")
        except Exception as e:
            pass

    def _log_grid_stack(self, action_desc=""):
        try:
            grids = self.sold_grids
            if not grids:
                self.log(f"[GRID STACK{action_desc}] EMPTY")
                return
            sorted_grids = sorted(grids, key=lambda g: g.get('sell_price', 0))
            price_list = []
            for g in sorted_grids:
                sell_p = g.get('sell_price_actual') or g.get('sell_price', 0)
                buy_p = g.get('buy_price_actual') or g.get('buy_price', 0)
                status = "✓" if g.get('filled') else "○"
                sell_target = g.get('sell_price', 0)
                if sell_p != sell_target:
                    price_list.append(f"{status}{sell_target}→{sell_p:.2f}→{buy_p:.2f}")
                else:
                    price_list.append(f"{status}{sell_p:.2f}→{buy_p:.2f}")
            self.log(f"[GRID STACK{action_desc}] [{', '.join(price_list)}]")
        except Exception as e:
            pass

    def _log_grid_stack_after_update(self, updated_grid):
        try:
            target = updated_grid.get('sell_price', 0)
            actual = updated_grid.get('sell_price_actual', 0)
            if target != actual and actual is not None:
                self.log(f"[GRID PRICE UPDATED] target={target:.2f}, actual={actual:.2f}")
                self._log_grid_stack("AFTER PRICE UPDATE")
        except Exception as e:
            pass

    # ------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------
    def log_grid_status(self):
        try:
            current_total_asset = self._compute_current_total_asset()
            self.total_asset_profit = current_total_asset - self.initial_total_asset
            self.cash_profit = self.total_profit
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

            if self.order is not None:
                return

            # Step 0: Force buyback check (HIGHEST PRIORITY)
            force_candidates = self.check_force_buyback_signals()
            if force_candidates:
                for grid, holding_days in force_candidates:
                    self.execute_force_buyback(grid, holding_days)
                    self.close_grid_round(grid)
                self.log_grid_status()
                return

            # Step 1: Base price update
            self.update_base_price()

            # Step 2: Normal buy check
            buy_signal, buy_grid = self.check_buy_signals()
            if buy_signal and buy_grid is not None:
                self.execute_buy(buy_grid)
                self.close_grid_round(buy_grid)
                self.log_grid_status()
                return

            # Step 3: Normal sell check
            sell_signal, sell_info = self.check_sell_signals()
            if sell_signal and sell_info is not None:
                self.execute_sell(sell_info)
                self._issue_sold_grid_record(sell_info)
                self.log_grid_status()
                return

            # Step 4: Status log
            self.log_grid_status()
        except Exception as e:
            pass

    def notify_order(self, order):
        try:
            status_map = {
                order.Submitted: "Submitted",
                order.Accepted: "Accepted",
                order.Completed: "Completed",
                order.Canceled: "Canceled",
                order.Margin: "Margin",
                order.Rejected: "Rejected",
            }
            status_name = status_map.get(order.status, f"Unknown({order.status})")
            target_val = getattr(order, 'target', None) or 'N/A'

            if order.status in [order.Submitted, order.Accepted]:
                return

            if order.status in [order.Completed]:
                executed_price = order.executed.price
                executed_size = int(order.executed.size)
                action = 'BUY' if order.isbuy() else 'SELL'

                self.log(
                    f"{action} EXECUTED, Price: {executed_price:.2f}, "
                    f"Cost: {order.executed.value:.2f}, Commission: {order.executed.comm:.2f}"
                )

                if order.isbuy():
                    self.current_position = self.current_position + executed_size

                    for grid in self.sold_grids:
                        if (not grid.get('filled', False)
                                and grid.get('sell_shares') == executed_size
                                and grid.get('buy_price_actual') is None
                                and grid.get('sell_date') is not None):
                            grid['buy_price_actual'] = executed_price
                            grid['buy_commission'] = float(order.executed.comm)
                            grid['buy_date'] = self.data.datetime.date(0)
                            if grid.get('sell_price_actual') is not None:
                                self.close_grid_round(grid)
                            break
                else:
                    self.current_position = self.current_position - abs(executed_size)

                    matched = False
                    for grid in self.sold_grids:
                        if (not grid.get('filled', False)
                                and grid.get('sell_shares') == abs(executed_size)
                                and grid.get('sell_price_actual') is None):
                            grid['sell_price_actual'] = executed_price
                            grid['sell_commission'] = float(order.executed.comm)
                            grid['buy_price'] = executed_price * (1.0 - self.params.grid_down_ratio)  # pyright: ignore
                            self._log_grid_stack_after_update(grid)
                            matched = True
                            break
                    if not matched:
                        pass

            elif order.status in [order.Canceled, order.Margin, order.Rejected]:
                self.log(
                    f"Order Canceled/Margin/Rejected. "
                    f"Status={order.status}"
                )

            self.order = None
        except Exception as e:
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
