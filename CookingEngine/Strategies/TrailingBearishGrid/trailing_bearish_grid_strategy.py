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

            initial_value = self.broker.getvalue()
            initial_capital = initial_value * self.params.initial_position_ratio  # pyright: ignore
            self.initial_shares = int(initial_capital / self.data.close[0])

            self.current_position = self.initial_shares
            self.p_base = float(self.data.close[0])
            self.sold_grids = []
            self.round_count = 0
            self.total_profit = 0.0

            self.initial_total_asset = initial_value
            self.cash_profit = 0.0
            self.total_asset_profit = 0.0
            self.start_date = self.data.datetime.date(0)

            self.force_completed_count = 0
            self.force_loss_total = 0.0
            self.force_buyback_warned = False
            self.allow_new_sells = True

            self.order = None
            try:
                logger.info(
                    f"TrailingBearishGridStrategy initialized. Params: {self.params}"  # pyright: ignore
                )
            except Exception:
                logger.info("TrailingBearishGridStrategy initialized.")
        except Exception as e:
            logger.error(f"[INIT FAILED] {e}\n{traceback.format_exc()}")
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
                logger.info(f"[P_BASE] Base price shifted down to {self.p_base:.2f}")
        except Exception as e:
            logger.error(f"[P_BASE ERROR] {e}\n{traceback.format_exc()}")

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
            logger.error(f"[FORCE CHECK ERROR] {e}\n{traceback.format_exc()}")
            return []

    def execute_force_buyback(self, grid, holding_days):
        try:
            current_price = float(self.data.close[0])
            buy_shares = grid.get('sell_shares', 0)
            required_cash = buy_shares * current_price
            available_cash = self.broker.get_cash()

            if available_cash < required_cash:
                logger.critical(
                    f"[FORCED BUYBACK EMERGENCY] Insufficient cash for forced buy-back. "
                    f"Required: {required_cash:.2f}, Available: {available_cash:.2f}. "
                    f"Grid round={grid.get('round_id')} level={grid.get('grid_level')}. "
                    f"Entering Emergency Mode."
                )
                self._enter_emergency_mode('insufficient_cash_for_force_buyback')
                return False

            self.order = self.buy(size=buy_shares)

            grid['filled'] = True
            grid['force_completed'] = True
            grid['force_reason'] = 'timeout'
            grid['buy_price_actual'] = current_price
            grid['force_loss'] = (current_price - grid.get('buy_price', current_price)) * buy_shares

            self.force_completed_count += 1
            self.force_loss_total += grid['force_loss']
            profit = (grid.get('sell_price', current_price) - current_price) * buy_shares
            self.total_profit += profit

            mandatory_buyback_days = self.params.mandatory_buyback_days # pyright: ignore
            logger.critical(
                f"[FORCED BUYBACK] Grid round={grid.get('round_id')} level={grid.get('grid_level')} "
                f"has timed out after {holding_days} days (threshold={mandatory_buyback_days}). "
                f"Sell price={grid.get('sell_price'):.2f}, Intended buy price={grid.get('buy_price'):.2f}, "
                f"Actual buy price={current_price:.2f}, Shares={buy_shares}, "
                f"Forced loss={grid['force_loss']:.2f}, Grid profit={profit:.2f}. "
                f"Total force-completed grids: {self.force_completed_count}, "
                f"Total forced loss: {self.force_loss_total:.2f}. "
                f"Please review market conditions and strategy parameters immediately."
            )

            if not self.force_buyback_warned:
                logger.warning(
                    "[BACKTEST WARNING] Forced buyback events detected during backtest. "
                    f"Number of force-completed grids: {self.force_completed_count}, "
                    f"Total forced loss: {self.force_loss_total:.2f}. "
                    "This indicates the strategy faces 'incomplete buy-back trap' risk. "
                    "Check: (1) Market may be in bull phase without pullbacks; "
                    "(2) Grid spacing may be too tight; (3) Consider increasing grid_down_ratio or mandatory_buyback_days. "
                    "Affected grids must be reviewed for strategy optimization."
                )
                self.force_buyback_warned = True

            return True
        except Exception as e:
            logger.critical(
                f"[FORCED BUYBACK ERROR] {e}\n{traceback.format_exc()}"
            )
            return False

    def _enter_emergency_mode(self, reason):
        try:
            logger.critical(
                f"[EMERGENCY MODE] Strategy halted. Reason: {reason}. "
                f"Force-completed grids: {self.force_completed_count}, "
                f"Total forced loss: {self.force_loss_total:.2f}, "
                f"Total profit: {self.total_profit:.2f}."
            )
            self.allow_new_sells = False
            for grid in self.sold_grids:
                if not grid.get('filled', False):
                    grid['force_completed'] = True
                    grid['force_reason'] = 'emergency'
                    grid['filled'] = True
            self._notify_emergency(reason)
        except Exception as e:
            logger.critical(
                f"[EMERGENCY MODE ERROR] {e}\n{traceback.format_exc()}"
            )

    def _notify_emergency(self, reason):
        try:
            logger.critical(
                f"[EMERGENCY NOTIFY] Sending emergency notification. "
                f"Reason: {reason}, Force loss total: {self.force_loss_total:.2f}"
            )
        except Exception as e:
            logger.critical(
                f"[EMERGENCY NOTIFY ERROR] {e}\n{traceback.format_exc()}"
            )

    # ------------------------------------------------------------
    # Sell / Buy signal checks
    # ------------------------------------------------------------
    def check_sell_signals(self):
        try:
            if not self.allow_new_sells:
                return False, None

            min_position_ratio = self.params.min_position_ratio # pyright: ignore
            grid_up_ratio = self.params.grid_up_ratio # pyright: ignore
            current_price = float(self.data.close[0])

            if len(self.sold_grids) == 0:
                next_sell_price = self.p_base * (1.0 + grid_up_ratio)
            else:
                last_grid = self.sold_grids[-1]
                next_sell_price = last_grid['sell_price'] * (1.0 + grid_up_ratio)

            if current_price < next_sell_price:
                return False, None

            total_sold = sum(g['sell_shares'] for g in self.sold_grids)
            remaining = self.current_position - total_sold
            min_allowed = int(self.initial_shares * min_position_ratio)

            if remaining <= min_allowed:
                logger.warning("[SELL] Insufficient position, suspend selling")
                return False, None

            max_grid_count = self.params.max_grid_count # pyright: ignore
            if len(self.sold_grids) >= max_grid_count:
                logger.warning("[SELL] Max grid count reached")
                return False, None

            grid_sell_ratio = self.params.grid_sell_ratio # pyright: ignore
            sell_shares = int(self.initial_shares * grid_sell_ratio)
            actual_shares = min(sell_shares, max(0, remaining - min_allowed))

            if actual_shares <= 0:
                return False, None

            grid_down_ratio = self.params.grid_down_ratio # pyright: ignore
            return True, {
                'sell_price': next_sell_price,
                'sell_shares': actual_shares,
                'buy_price': next_sell_price * (1.0 - grid_down_ratio),
            }
        except Exception as e:
            logger.error(f"[SELL SIGNAL ERROR] {e}\n{traceback.format_exc()}")
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
                        logger.warning(
                            f"[BUY] Insufficient cash, need {required_cash:.2f}, have {self.broker.get_cash():.2f}"
                        )
                        continue
                    return True, grid

            return False, None
        except Exception as e:
            logger.error(f"[BUY SIGNAL ERROR] {e}\n{traceback.format_exc()}")
            return False, None

    # ------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------
    def execute_sell(self, sell_info):
        try:
            size = sell_info['sell_shares']
            self.order = self.sell(size=size)
            logger.info(
                f"[SELL] Submitted sell order for {size} shares at target {sell_info['sell_price']:.2f}"
            )
        except Exception as e:
            logger.error(f"[SELL EXECUTE ERROR] {e}\n{traceback.format_exc()}")

    def execute_buy(self, grid):
        try:
            size = grid['sell_shares']
            self.order = self.buy(size=size)
            logger.info(
                f"[BUY] Submitted buy order for {size} shares (grid round={grid.get('round_id')} level={grid.get('grid_level')})"
            )
        except Exception as e:
            logger.error(f"[BUY EXECUTE ERROR] {e}\n{traceback.format_exc()}")

    def close_grid_round(self, grid):
        try:
            if not grid.get('filled', False):
                grid['filled'] = True
                grid['buy_price_actual'] = float(self.data.close[0])

            profit = (grid.get('sell_price', 0) - grid.get('buy_price_actual', 0)) * grid.get('sell_shares', 0)
            self.total_profit += profit

            self.cash_profit = self.total_profit
            current_total_asset = self._compute_current_total_asset()
            self.total_asset_profit = current_total_asset - self.initial_total_asset

            if all(g.get('filled', False) for g in self.sold_grids):
                self.round_count += 1
                logger.info(
                    f"[ROUND] Round {self.round_count} completed, this round's profit {profit:.2f} USD"
                )
                self.sold_grids = []
        except Exception as e:
            logger.error(f"[CLOSE ROUND ERROR] {e}\n{traceback.format_exc()}")

    def _compute_current_total_asset(self):
        try:
            price = float(self.data.close[0])
            return self.broker.get_cash() + self.current_position * price
        except Exception as e:
            logger.error(f"[ASSET COMPUTE ERROR] {e}\n{traceback.format_exc()}")
            return self.broker.get_cash()

    def _issue_sold_grid_record(self, sell_info):
        try:
            current_date = self.data.datetime.date(0)
            new_grid = {
                'round_id': self.round_count,
                'grid_level': len(self.sold_grids) + 1,
                'sell_price': sell_info['sell_price'],
                'sell_shares': sell_info['sell_shares'],
                'buy_price': sell_info['buy_price'],
                'filled': False,
                'buy_price_actual': None,
                'sell_date': current_date,
                'force_completed': False,
                'force_reason': None,
                'force_loss': 0.0,
            }
            self.sold_grids.append(new_grid)
            logger.info(
                f"[GRID] New grid added: round={new_grid['round_id']} level={new_grid['grid_level']} "
                f"sell={new_grid['sell_price']:.2f} buy={new_grid['buy_price']:.2f} shares={new_grid['sell_shares']}"
            )
        except Exception as e:
            logger.error(f"[GRID RECORD ERROR] {e}\n{traceback.format_exc()}")

    # ------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------
    def log_grid_status(self):
        try:
            current_total_asset = self._compute_current_total_asset()
            self.total_asset_profit = current_total_asset - self.initial_total_asset
            self.cash_profit = self.total_profit

            holding_days = (self.data.datetime.date(0) - self.start_date).days
            cash_return_rate = (self.cash_profit / self.initial_total_asset) if self.initial_total_asset > 0 else 0.0
            total_asset_return_rate = (self.total_asset_profit / self.initial_total_asset) if self.initial_total_asset > 0 else 0.0
            cash_annualized = (cash_return_rate * (365.0 / holding_days)) if holding_days > 0 else 0.0
            total_asset_annualized = (total_asset_return_rate * (365.0 / holding_days)) if holding_days > 0 else 0.0

            max_grid_count = self.params.max_grid_count # pyright: ignore
            force_loss_ratio = (self.force_loss_total / self.initial_total_asset) if self.initial_total_asset > 0 else 0.0
            if force_loss_ratio > 0.1 or self.force_completed_count >= max_grid_count:
                force_stress_level = 'CRITICAL'
            elif self.force_completed_count > 0:
                force_stress_level = 'HIGH'
            else:
                force_stress_level = 'NORMAL'

            unsold_count = sum(1 for g in self.sold_grids if not g.get('filled', False))
            grid_details = ", ".join(
                f"[round={g.get('round_id')} lvl={g.get('grid_level')} "
                f"sell={g.get('sell_price'):.2f} buy={g.get('buy_price'):.2f} "
                f"filled={g.get('filled')} force={g.get('force_completed')}]"
                for g in self.sold_grids
            )

            logger.info(
                f"[GRID STATUS] "
                f"P_base={self.p_base:.2f}, "
                f"Position={self.current_position} shares, "
                f"Cash={self.broker.get_cash():.2f}, "
                f"Sold Grids={len(self.sold_grids)} (open={unsold_count}), "
                f"Round Count={self.round_count}, "
                f"Init Asset={self.initial_total_asset:.2f}, "
                f"Current Asset={current_total_asset:.2f}, "
                f"Cash Profit={self.cash_profit:.2f} (Ret={cash_return_rate:.2%}, Ann={cash_annualized:.2%}), "
                f"Asset Profit={self.total_asset_profit:.2f} (Ret={total_asset_return_rate:.2%}, Ann={total_asset_annualized:.2%}), "
                f"Holding Days={holding_days}, "
                f"Force Completed={self.force_completed_count}, "
                f"Force Loss={self.force_loss_total:.2f} ({force_loss_ratio:.2%}), "
                f"Stress={force_stress_level}, "
                f"Grids=[{grid_details}]"
            )

            if force_stress_level in ('CRITICAL', 'HIGH') and not self.force_buyback_warned:
                logger.warning(
                    f"[BACKTEST STRESS WARNING] Forced buyback stress level: {force_stress_level}. "
                    f"Force-completed grids: {self.force_completed_count}, "
                    f"Total forced loss: {self.force_loss_total:.2f} ({force_loss_ratio:.2%} of initial capital). "
                    "Please review strategy parameters before deploying to live trading."
                )
                self.force_buyback_warned = True
        except Exception as e:
            logger.error(f"[LOG STATUS ERROR] {e}\n{traceback.format_exc()}")

    # ------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------
    def next(self):
        try:
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
            logger.error(
                f"[NEXT LOOP ERROR] {e}\n{traceback.format_exc()}"
            )

    def notify_order(self, order):
        try:
            if order.status in [order.Submitted, order.Accepted]:
                return

            if order.status in [order.Completed]:
                if order.isbuy():
                    self.log(
                        f"BUY EXECUTED, Price: {order.executed.price:.2f}, "
                        f"Cost: {order.executed.value:.2f}, Commission: {order.executed.comm:.2f}"
                    )
                    self.current_position = self.current_position + int(order.executed.size)
                else:
                    self.log(
                        f"SELL EXECUTED, Price: {order.executed.price:.2f}, "
                        f"Cost: {order.executed.value:.2f}, Commission: {order.executed.comm:.2f}"
                    )
                    self.current_position = self.current_position - int(order.executed.size)

            elif order.status in [order.Canceled, order.Margin, order.Rejected]:
                self.log(
                    f"Order Canceled/Margin/Rejected. "
                    f"Status={order.status}"
                )
                logger.critical(
                    f"[ORDER FAILED] Status={order.status}. "
                    f"This may leave grids in an incomplete state. "
                    f"Check for force buyback requirements."
                )

            self.order = None
        except Exception as e:
            logger.error(
                f"[NOTIFY ORDER ERROR] {e}\n{traceback.format_exc()}"
            )
            self.order = None

    def notify_trade(self, trade):
        try:
            if not trade.isclosed:
                return
            self.log(
                f"TRADE CLOSED, Gross: {trade.pnl:.2f}, Net: {trade.pnlcomm:.2f}"
            )
            self.trades.append({
                'date': self.datas[0].datetime.date(0),
                'gross': trade.pnl,
                'net': trade.pnlcomm,
                'size': trade.size,
            })
        except Exception as e:
            logger.error(
                f"[NOTIFY TRADE ERROR] {e}\n{traceback.format_exc()}"
            )

    def stop(self):
        try:
            final_value = self.get_current_value()
            total_return = self.get_total_return()
            logger.info(
                f"[FINAL] Portfolio Value: {final_value:.2f}, "
                f"Total Return: {total_return:.2%}, "
                f"Trades: {len(self.trades)}, "
                f"Force Completed Grids: {self.force_completed_count}, "
                f"Total Forced Loss: {self.force_loss_total:.2f}"
            )
            super().stop()
        except Exception as e:
            logger.error(
                f"[STOP ERROR] {e}\n{traceback.format_exc()}"
            )
