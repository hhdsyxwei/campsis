# trailing_bearish_grid_strategy.py
# Trailing Bearish Grid Strategy (空头追踪网格策略)
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
       If a grid cannot be bought back within N trading days (default 30),
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
        ('mandatory_buyback_days', 30),
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
                self.order = self.buy(size=self.initial_shares, price=initial_price, info={'grid': None, 'reason': 'INITIAL BUY'})
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
        except Exception:
            logger.exception("update_base_price failed")

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
        except Exception:
            logger.exception("check_force_buyback_signals failed")
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

            # 记录强制买回日志
            estimated_loss = (current_price - grid.get('sell_price', current_price)) * buy_shares
            logger.info(f"[FORCE BUY] Grid level={grid.get('grid_level')}, holding_days={holding_days}, "
                        f"sell_price_plan={grid.get('sell_price')}, current_price={current_price}, "
                        f"shares={buy_shares}, estimated_loss={estimated_loss:.2f}")

            force_buy_price = current_price * (1.0 + self.slippage_perc)
            
            # 异步提交订单，通过 info 传递上下文
            self.order = self.buy(size=buy_shares, price=force_buy_price, info={'grid': grid, 'reason': 'FORCE BUY'})

            return True
        except Exception:
            logger.exception("execute_force_buyback failed")
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
        except Exception:
            logger.exception("_enter_emergency_mode failed")

    def _notify_emergency(self, reason):
        try:
            logger.warning(f"[EMERGENCY] Entered emergency mode: {reason}")
        except Exception:
            logger.exception("_notify_emergency failed")

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
        except Exception:
            logger.exception("check_sell_signals failed")
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

                # 检查1: 当前价格达到买回价
                if current_price > buy_price:
                    continue

                # 检查2: 买回价在当日K线范围内（必须能当天成交）
                # 2.1 买回价不能高于当日最高价（否则当日未触底，无法成交）
                if buy_price > day_high:
                    continue
                # 2.2 买回价不能低于当日最低价（否则订单会低于限价被拒）
                if buy_price < day_low:
                    continue

                # 检查3: 资金是否充足（使用含滑点的预估成交价计算）
                estimated_buy_price = buy_price * (1.0 + self.slippage_perc)
                required_cash = grid['sell_shares'] * estimated_buy_price
                if self.broker.get_cash() < required_cash:
                    continue

                return True, grid

            return False, None
        except Exception:
            logger.exception("check_buy_signals failed")
            return False, None

    # ------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------
    def execute_sell(self, sell_info):
        try:
            size = sell_info['sell_shares']
            price = sell_info['sell_price']
            sell_price_with_slippage = price * (1.0 - self.slippage_perc)
            
            logger.info(f"[NORMAL SELL] Grid level={sell_info.get('grid_level')}, sell_price={price}, size={size}")
            
            # 异步提交订单，通过 info 传递上下文
            self.order = self.sell(size=size, price=sell_price_with_slippage, info={'grid': sell_info, 'reason': 'NORMAL SELL'})
        except Exception:
            logger.exception("execute_sell failed")

    def execute_buy(self, grid, reason="NORMAL BUY"):
        try:
            size = grid['sell_shares']
            grid_down_ratio = self.params.grid_down_ratio  # pyright: ignore
            # 基于实际卖出价动态计算买回价（优先使用实际成交价）
            if grid.get('sell_price_actual') is not None:
                actual_sell_price = grid['sell_price_actual']
            else:
                actual_sell_price = grid.get('sell_price', float(self.data.close[0]))
            buy_price = actual_sell_price * (1.0 - grid_down_ratio)
            
            # 统一的买入执行日志
            logger.info(f"[NORMAL BUY] Grid level={grid.get('grid_level')}, sell_price={grid.get('sell_price')}, "
                        f"buy_price={buy_price:.3f}, size={size}, reason={reason}")
            
            # 异步提交订单，通过 info 传递上下文
            self.order = self.buy(size=size, price=buy_price * (1.0 + self.slippage_perc), info={'grid': grid, 'reason': reason})
        except Exception:
            logger.exception("execute_buy failed")

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
        except Exception:
            logger.exception("close_grid_round failed")

    def _compute_current_total_asset(self):
        try:
            price = float(self.data.close[0])
            return self.broker.get_cash() + self.current_position * price
        except Exception:
            logger.exception("_compute_current_total_asset failed")
            return self.broker.get_cash()

    def _update_profit_status(self):
        try:
            current_total_asset = self._compute_current_total_asset()
            self.total_asset_profit = current_total_asset - self.initial_total_asset
            self.cash_profit = self.total_profit
        except Exception:
            logger.exception("_update_profit_status failed")

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
            return new_grid
        except Exception:
            logger.exception("_issue_sold_grid_record failed")
            return None

    # ------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------
    def next(self):
        try:
            # 防止在订单挂起期间重复下单
            if self.order:
                return

            if not self._initialized:
                self._do_first_bar_init()
                self._initialized = True
                return

            if self.order is not None:
                return

            # Step 0: Force buyback check (HIGHEST PRIORITY)
            force_candidates = self.check_force_buyback_signals()
            if force_candidates:
                # 单订单模型：每次只处理一个强制买回
                grid, holding_days = force_candidates[0]
                self.execute_force_buyback(grid, holding_days)
                self._update_profit_status()
                return

            # Step 1: Base price update
            self.update_base_price()

            # Step 2: Normal buy check
            buy_signal, buy_grid = self.check_buy_signals()
            if buy_signal and buy_grid is not None:
                self.execute_buy(buy_grid, reason="NORMAL BUY")
                self._update_profit_status()
                return

            # Step 3: Normal sell check
            sell_signal, sell_info = self.check_sell_signals()
            if sell_signal and sell_info is not None:
                # 创建新的网格记录对象
                new_grid = self._issue_sold_grid_record(sell_info)
                if new_grid:
                    # 立即加入 sold_grids，防止下一K线重复挂单
                    self.sold_grids.append(new_grid)
                    self.execute_sell(new_grid)
                self._update_profit_status()
                return

            # Step 4: Status log
            self._update_profit_status()
        except Exception:
            logger.exception("next() failed")

    def notify_order(self, order):
        """订单状态变化回调函数"""
        try:
            # 过滤挂单状态
            if order.status in [order.Submitted, order.Accepted]:
                return

            # 获取上下文
            context = order.info
            grid = context.get('grid') if context else None
            reason = context.get('reason', 'UNKNOWN') if context else 'UNKNOWN'
            action = 'BUY' if order.isbuy() else 'SELL'

            # 订单已完成
            if order.status == order.Completed:
                executed_price = order.executed.price
                executed_size = int(order.executed.size)

                # 处理初始建仓等非网格订单
                if grid is None:
                    if order.isbuy():
                        self.current_position += executed_size
                    elif order.issell():
                        self.current_position -= abs(executed_size)
                    self.order = None
                    return

                # 处理买入订单
                if order.isbuy():
                    self.current_position += executed_size
                    
                    # 更新网格状态
                    grid['buy_price_actual'] = executed_price
                    grid['buy_commission'] = float(order.executed.comm)
                    grid['buy_date'] = self.data.datetime.date(0)
                    grid['filled'] = True
                    
                    # 根据原因结算
                    if reason == 'FORCE BUY':
                        # 强制买回结算逻辑
                        grid['force_completed'] = True
                        grid['force_reason'] = 'timeout'
                        # 计算强制买回的实际亏损：实际成交价 - 原本计划的买回价
                        planned_buy_price = grid.get('buy_price', executed_price)
                        if planned_buy_price is None or planned_buy_price <= 0:
                            planned_buy_price = executed_price
                        grid['force_loss'] = (executed_price - planned_buy_price) * executed_size
                        self.force_completed_count += 1
                        self.force_loss_total += grid['force_loss']
                        if not self.force_buyback_warned:
                            self.force_buyback_warned = True
                        logger.warning(f"[FORCE BUY COMPLETED] Grid level={grid.get('grid_level')}, "
                                       f"executed_price={executed_price}, planned={planned_buy_price}, "
                                       f"force_loss={grid['force_loss']:.2f}")
                            
                    # 统一调用结算函数
                    self.close_grid_round(grid)

                # 处理卖出订单
                elif order.issell():
                    self.current_position -= abs(executed_size)
                    
                    # 更新网格状态
                    grid['sell_price_actual'] = executed_price
                    grid['sell_commission'] = float(order.executed.comm)
                    grid['buy_price'] = executed_price * (1.0 - self.params.grid_down_ratio)  # pyright: ignore
                    
                    # 确保网格已在 sold_grids 中
                    if grid not in self.sold_grids:
                        self.sold_grids.append(grid)

            # 非 Completed 状态：Canceled / Margin / Rejected
            else:
                if grid is not None:
                    # 将失败/撤销的网格标记为已处理，防止强制买回误触发
                    if not grid.get('filled', False):
                        grid['filled'] = True
                        grid['force_completed'] = True
                        grid['force_reason'] = 'order_failed'
                        grid['buy_date'] = self.data.datetime.date(0)
                        grid['buy_price_actual'] = float(self.data.close[0])
                        logger.warning(f"[ORDER FAILED] action={action}, reason={reason}, "
                                       f"grid_level={grid.get('grid_level')}, status={order.status}")
                        # 调用结算函数将此轮标记结束
                        self.close_grid_round(grid)

            # 重置订单引用
            self.order = None

        except Exception:
            # 异常处理：重置订单引用
            self.order = None
            logger.exception("notify_order failed")

    def notify_trade(self, trade):
        try:
            pass
        except Exception:
            logger.exception("notify_trade failed")

    def stop(self):
        try:
            final_value = self.get_current_value()
            total_return = self.get_total_return()
            logger.info(f"[STRATEGY STOP] final_value={final_value:.2f}, total_return={total_return:.4%}, "
                        f"force_completed_count={self.force_completed_count}, force_loss_total={self.force_loss_total:.2f}")
            super().stop()
        except Exception:
            logger.exception("stop() failed")
