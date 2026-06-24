# Trailing Bearish Grid Strategy Design Document

## 1. Strategy Overview and Use Cases

### 1.1 Strategy Name
**Trailing Bearish Grid** (空头追踪网格策略)

### 1.2 Core Mechanism
In a downtrend channel, a dynamically moving base price (P_base) is established. When the price rebounds by a certain percentage above the base price, selling is triggered; when the price falls back by a certain percentage below the sell price, buying back is triggered. The strategy locks in volatile gains through a "sell-buy" closed loop.

### 1.3 Core Features
- ✅ **Dynamic Base Price**: The base price automatically shifts down along with the downtrend channel
- ✅ **Continuous Grid Trading**: Multiple grids can be sold consecutively during rebounds
- ✅ **Position Protection**: Always retains 50% of the base position without selling
- ✅ **Profit Locking**: Each round of trading locks in deterministic profits through a closed loop

### 1.4 Suitable Scenarios
| Suitable | Unsuitable |
|----------|------------|
| ✅ Stock in a clear downtrend channel | ❌ One-sided decline with no rebound |
| ✅ Sufficient volatility (daily volatility > 2%) | ❌ Sideways consolidation |
| ✅ Long-term holding, reducing cost through volatility | ❌ Sharp V-shaped reversal |
| ✅ Defensive investment in bear markets | ❌ Chasing gains in bull markets |

### 1.5 Trading Principles
1. Initial state: 50% base position (anchored shares N) + 50% cash
2. The base price always follows the downtrend channel and never stays elevated
3. Every trade must have a buy-back to form a closed loop
4. The base position never falls below the initial 50%

---

## 2. Core Parameter Definitions

### 2.1 Basic Parameters

| Parameter | Symbol | Type | Default | Description |
|-----------|--------|------|---------|-------------|
| Initial Position Ratio | `initial_position_ratio` | float | 0.5 | 50% of capital as base position |
| Grid Sell Spacing | `grid_up_ratio` | float | 0.03 (3%) | Upward grid spacing U% |
| Grid Buy Spacing | `grid_down_ratio` | float | 0.05 (5%) | Downward grid spacing D% |
| Per-Grid Sell Ratio | `grid_sell_ratio` | float | 0.1 (10%) | Q% of base position sold each time |
| Base Price Shift Threshold | `base_shift_threshold` | float | 0.02 (2%) | Threshold for 2% base price downward shift |
| Position Protection Line | `min_position_ratio` | float | 0.5 | Remaining position not less than 50% of initial |
| **Mandatory Buyback Days** | `mandatory_buyback_days` | int | **20** | **Maximum consecutive trading days after a sell before forced market buy-back; if not triggered within N days, execute a market buy-back regardless of price to avoid "incomplete buy-back trap"** |

### 2.2 Extended Parameters

| Parameter | Symbol | Type | Default | Description |
|-----------|--------|------|---------|-------------|
| Max Grid Count | `max_grid_count` | int | 5 | Maximum number of grids supported |
| Max Daily Volatility | `max_daily_volatility` | float | 0.08 (8%) | Abnormal market filter |
| Volume Filter Toggle | `volume_filter` | bool | False | Enable volume confirmation |
| Stop Loss Line | `stop_loss_line` | float | 0.20 (20%) | Extreme stop loss threshold |

### 2.3 Order Type and Execution Mechanism Constraints (MANDATORY)

Grid strategy MUST use **Limit Order** (限价单) combined with **Slippage** for backtesting and live trading. Market Order (市价单) is strictly prohibited.

#### 2.3.1 Why Limit Order is Mandatory

Grid strategy generates trading signals at **precise price levels** (e.g., `p_base × (1 + grid_up_ratio)` for sell, `sell_price × (1 - grid_down_ratio)` for buy). Using Limit Order ensures:

1. **Price Certainty**: Orders are only filled when the market price crosses the trigger level, which is the core premise of grid trading.
2. **Grid Integrity**: Each grid level corresponds to an exact price band. Market orders would cause fills at unpredictable prices, breaking the grid's "sell-high, buy-low" closed-loop logic.
3. **Backtest Fidelity**: Backtrader's `bt.Order.Limit` fills orders only when the bar's price range touches the limit price, faithfully reproducing the real market scenario where a grid level is "touched and filled."

#### 2.3.2 Why Slippage is Mandatory

The grid strategy's single-round profit is typically small (`grid_up_ratio` + `grid_down_ratio`, roughly 3%+5% = 8% in the default config). Without slippage, backtesting will **overestimate profits** and produce unrealistic win rates. Slippage must be introduced to simulate real market friction:

- **Buy side**: Executed price = `limit_price × (1 + slippage_perc)` (成交略高于限价)
- **Sell side**: Executed price = `limit_price × (1 - slippage_perc)` (成交略低于限价)

#### 2.3.3 Backtrader Recommended Configuration

```python
# 1. Strategy side: always pass an explicit price when calling buy()/sell()
self.order = self.buy(size=size, price=buy_price)   # Limit Buy
self.order = self.sell(size=size, price=sell_price)  # Limit Sell

# 2. Broker side: enable broker-level slippage (recommended)
cerebro.broker.set_slippage_perc(
    perc=0.001,       # 0.1% slippage, adjustable per asset volatility
    abslimit=0.0      # optional absolute price cap
)
# Or use a custom slippage class for volatility-aware models:
cerebro.broker.set_slippage(GridSlippage)
```

#### 2.3.4 Forbidden Practices

❌ **Market Order** (`self.buy(size)` / `self.sell(size)` without a price) — will execute at the current bar's close, bypassing grid price levels entirely.

❌ **Manually embedding slippage into the limit price** (e.g., `price * (1 + 0.001)` passed as the limit price) — this shifts the nominal grid level and may cause the order to never get filled on a weak signal. Prefer **Broker-level slippage** via `cerebro.broker.set_slippage_perc()` or a custom `bt.Slippage_x` subclass.

---

## 3. Detailed Trading Logic

### 3.1 Base Price (P_base) Management

#### 3.1.1 Initialization
```python
# Strategy start day
p_base = closing_price  # Closing price as initial base price
initial_shares = int(total_capital * initial_position_ratio / closing_price)
```

#### 3.1.2 Dynamic Downward Shift Rule (After Daily Close)
```python
# Check whether the base price needs to shift down each day
if today_low < p_base * (1 - base_shift_threshold):
    # When price falls below base price by 2%, update to today's low
    p_base = today_low
    logger.info(f"Base price shifted down: {p_base:.2f}")
```

#### 3.1.3 Base Price Characteristics
- Only shifts down, never shifts up
- Always follows the center of the downtrend channel
- Ensures grids do not become invalid at elevated levels

---

### 3.2 Sell Logic (Sell on High Rebound)

#### 3.2.1 Sell Trigger Price Calculation (Consecutive Multiple Grids)
```python
# 1st sell
sell_price_1 = p_base * (1 + grid_up_ratio)

# 2nd sell (based on the previous sell price)
sell_price_2 = sell_price_1 * (1 + grid_up_ratio)

# Nth sell
sell_price_N = sell_price_N-1 * (1 + grid_up_ratio)
```

#### 3.2.2 Sell Execution Conditions
```python
# Sell trigger condition
current_price >= calculated_sell_price  # Price reaches sell price

# Quantity calculation
sell_shares = int(initial_shares * grid_sell_ratio)  # Fixed quantity

# Position protection check
remaining_position = current_position - total_sold_shares
min_allowed = int(initial_shares * min_position_ratio)
if remaining_position - sell_shares < min_allowed:
    # Insufficient remaining position, pause selling
    return False, 0
```

#### 3.2.3 Sell Process
```
Step 1: Calculate the sell price for the next grid
Step 2: Check whether current price has reached the sell price
Step 3: Check position protection conditions
Step 4: Calculate the sell quantity
Step 5: Execute the sell and record sell information
Step 6: Wait for further selling or buy-back
```

---

### 3.3 Buy Logic (Buy Low for Recovery)

#### 3.3.1 Buy Trigger Price Calculation
```python
# Independently calculate the buy price for each sell
buy_price_1 = sell_price_1 * (1 - grid_down_ratio)
buy_price_2 = sell_price_2 * (1 - grid_down_ratio)
...
buy_price_N = sell_price_N * (1 - grid_down_ratio)
```

#### 3.3.2 Buy Execution Conditions
```python
# Check from highest sell price to lowest
for sell_record in sold_grids_sorted_by_price_desc:
    if not sell_record.filled and current_price <= sell_record.buy_price:
        # Price reaches buy price
        # Check whether cash is sufficient
        required_cash = sell_record.shares * current_price
        if cash >= required_cash:
            # Execute buy
            buy_shares = sell_record.shares
            execute_buy(buy_shares)
            sell_record.filled = True
            # Calculate single-round profit
            profit = (sell_record.sell_price - current_price) * buy_shares
            total_profit += profit
            return True, buy_shares, profit
```

#### 3.3.3 Buy Principles
1. Priority Buy-back: Buy back sequentially from highest sell price to lowest
2. Fixed Quantity: Exactly equal to the corresponding sell quantity
3. Cash Check: Ensure sufficient cash for buying
4. Closed Loop Completion: Each sell-buy round forms a closed loop
5. **Mandatory Timeout**: Any grid not bought back within `mandatory_buyback_days` (default 20) of trading days **must be force-completed by a market buy-back regardless of current price** (see section 3.3.4).

#### 3.3.4 Forced Market Buy-back (Timeout Rescue)

**Trigger Condition**
For each `sold_grid_record` where `filled == False`:
```python
holding_days = (current_trade_date - sell_record.sell_date).days
if holding_days >= mandatory_buyback_days:
    # === Forced Market Buy-back Triggered ===
    execute_force_buyback(sell_record, reason='timeout')
```

**Execution Logic**
```python
def execute_force_buyback(grid, reason='timeout'):
    current_price = market_price_best_ask  # Use best ask / market price
    buy_shares = grid['sell_shares']
    
    # Always attempt execution regardless of price
    execute_buy_market_order(buy_shares)
    
    # Record force buyback
    grid['filled'] = True
    grid['force_completed'] = True
    grid['force_reason'] = reason
    grid['buy_price_actual'] = current_price
    grid['force_loss'] = current_price - grid['buy_price']
    
    # Update global tracking
    force_completed_count += 1
    force_loss_total += grid['force_loss']
    total_profit += (grid['sell_price'] - current_price) * buy_shares
    
    # === Critical Warnings ===
    logger.critical(
        f"[FORCED BUYBACK] Grid round={grid['round_id']} level={grid['grid_level']} "
        f"has timed out after {mandatory_buyback_days} days. "
        f"Intended buy price={grid['buy_price']:.2f}, "
        f"Actual buy price={current_price:.2f}, "
        f"Extra loss={grid['force_loss']:.2f}. "
        f"Reason: {reason}. "
        f"Please review market conditions and consider adjusting strategy parameters."
    )
    
    # Backtest warning (issued once per backtest run)
    if not force_buyback_warned:
        logger.warning(
            "[BACKTEST WARNING] Forced buyback events detected. "
            "This indicates the strategy may face 'incomplete buy-back trap' risk in real trading. "
            "Check whether the following conditions exist: "
            "(1) Prolonged market rally without pullbacks (bull market); "
            "(2) Tight grid spacing causing frequent forced buybacks; "
            "(3) Insufficient cash buffer for forced buys. "
            "Consider: increasing grid_down_ratio, reducing grid_sell_ratio, "
            "or adjusting mandatory_buyback_days. "
            "Total force-completed grids: {}, Total forced loss: {:.2f}".format(
                force_completed_count, force_loss_total
            )
        )
        force_buyback_warned = True
```

**Key Rules for Forced Buy-back**
1. **No price limit**: Forced buy-back executes at market price (or best ask) regardless of how high the price has risen
2. **No size limit**: Force-buy the exact sell_shares that were sold
3. **No cash check**: Execute regardless of cash balance; if cash is insufficient, the strategy must enter emergency mode (see section 7.5)
4. **Immediate lock**: Once force-completed, the grid is marked as filled and cannot be reversed
5. **Logging mandatory**: Every force buy-back event must be logged at `CRITICAL` level with full details

---

### 3.4 Closed Loop and Reset

#### 3.4.1 Single-Round Closed Loop Completion
```python
# When a sell-buy pair is completed in a round
if all_grids_filled:
    # Calculate cumulative profit
    round_profit = sum(sell_amount - buy_amount for each grid)
    total_profit += round_profit
    
    # Log completion
    logger.info(f"Grid completed #{round_count}: Profit {round_profit:.2f} USD")
    
    # Reset grid state
    sold_grids.clear()
    round_count += 1
```

#### 3.4.2 State Reset
- Clear all sold grid records
- Reset grid counter
- **Reset force tracking flags for the new round** (force_buyback_warned can be reset per round if desired)
- Wait for the next sell signal

---

## 4. State Variable Design

### 4.1 Core State Variables

| Variable Name | Type | Initial Value | Description |
|---------------|------|---------------|-------------|
| `initial_shares` | int | Calculated | Initial base position shares |
| `current_position` | int | initial_shares | Current position shares |
| `p_base` | float | Closing price | Dynamic base price |
| `sold_grids` | List[Dict] | [] | Sold grid records |
| `round_count` | int | 0 | Completed grid rounds |
| `total_profit` | float | 0 | Cumulative profit (realized) |
| `last_price` | float | 0 | Previous price (used for base price shift calculation) |
| `initial_total_asset` | float | Calculated | Initial total asset at strategy start |
| `cash_profit` | float | 0 | **Cash profit** (realized profit, cumulative sell revenue - cumulative buy expenditure) |
| `total_asset_profit` | float | 0 | **Total asset profit** (current total asset - initial total asset, including floating P&L) |
| `start_date` | datetime | Current date | Strategy start date, used for annualized return calculation |
| `force_completed_count` | int | 0 | Number of grids force-completed (for monitoring abnormal markets) |
| `force_loss_total` | float | 0 | Cumulative extra loss caused by forced buy-back across all grids |
| `force_buyback_warned` | bool | False | Whether a backtest warning has already been issued for forced buyback events |

### 4.2 Grid Record Structure (Detailed)

Each grid element in `sold_grids` is a dictionary with the following fields. The fields are grouped by **lifecycle phase**: Planned → Submitted → Filled → Closed.

#### 4.2.1 Full Field Definition

| Field | Type | Required | Lifecycle Phase | Write Location (Function) | Description |
|-------|------|----------|-----------------|---------------------------|-------------|
| `round_id` | int | ✅ | Planned | `_issue_sold_grid_record` | Grid round identifier (inherited from current `round_count`) |
| `grid_level` | int | ✅ | Planned | `_issue_sold_grid_record` | Sequence number within the current round (`len(sold_grids) + 1`) |
| `sell_price` | float | ✅ | Planned | `_issue_sold_grid_record` | **Intended** sell price (nominal grid level price, `p_base × (1+U%)` or `prev_sell × (1+U%)`) |
| `sell_shares` | int | ✅ | Planned | `_issue_sold_grid_record` | Number of shares sold at this grid level |
| `buy_price` | float | ✅ | Planned (updated post-fill) | `_issue_sold_grid_record` / `notify_order` | Intended buy price (`sell_price × (1-D%)`), **recalculated using `sell_price_actual` after the sell order is filled** |
| `sell_date` | date | ✅ | Submitted | `_issue_sold_grid_record` | Trading date of the sell order submission (used for timeout counter) |
| `sell_price_actual` | float | ⚠️ | Filled | `notify_order` (sell branch) | Actual sell execution price (filled by backtrader broker) |
| `sell_commission` | float | ⚠️ | Filled | `notify_order` (sell branch) | Commission for the sell execution |
| `buy_price_actual` | float | ⚠️ | Filled | `notify_order` (buy branch) / `close_grid_round` fallback | Actual buy execution price |
| `buy_commission` | float | ⚠️ | Filled | `notify_order` (buy branch) | Commission for the buy execution |
| `buy_date` | date | ⚠️ | Filled | `notify_order` (buy branch) / `close_grid_round` fallback | Trading date of the buy-back fill |
| `filled` | bool | ✅ | Closed | `close_grid_round` | Whether the grid has been fully bought back and settled |
| `force_completed` | bool | ✅ | Closed | `execute_force_buyback` / `_enter_emergency_mode` | Whether the grid was force-completed (non-normal path) |
| `force_reason` | str\|None | ✅ | Closed | `execute_force_buyback` / `_enter_emergency_mode` | Force reason: `'timeout'` / `'emergency'` / `None` |
| `force_loss` | float | ✅ | Closed | `execute_force_buyback` | Extra loss (or reduced profit) from force buy-back = `actual_buy_price - intended_buy_price` |
| `_round_closed` | bool | ✅ | Closed | `close_grid_round` | Internal guard to prevent double-settlement of the same grid |

#### 4.2.2 State Lifecycle

```
         _issue_sold_grid_record         notify_order(sell)        notify_order(buy)        close_grid_round
   ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
   │   Planned (入栈)     │ → │   Submitted (挂单)   │ → │   Filled (成交)      │ → │   Closed (结算)      │
   └─────────────────────┘    └─────────────────────┘    └─────────────────────┘    └─────────────────────┘
   - round_id                 - sell_price_actual          - buy_price_actual         - filled=True
   - grid_level              - sell_commission             - buy_commission            - force_completed flag
   - sell_price (nominal)     - buy_price (recalc)         - buy_date                  - _round_closed=True
   - sell_shares              - (status: Submitted)        - (status: Partially Filled)- (status: Settled)
   - buy_price (nominal)
   - sell_date
   - filled=False
```

#### 4.2.3 Field Read by Which Functions

| Function | Fields Read | Purpose |
|----------|-------------|---------|
| `check_sell_signals` | `sell_price` (last grid), `sell_shares` (sum for total_sold) | Compute next sell price and remaining position |
| `check_buy_signals` | `filled`, `sell_price_actual`, `sell_price`, `buy_price`, `sell_shares`, `sell_date` | Find eligible grid to buy back; compute buy trigger price with actual sell price |
| `check_force_buyback_signals` | `filled`, `sell_date` | Identify grids held longer than `mandatory_buyback_days` |
| `execute_force_buyback` | `sell_shares`, `grid_level`, `buy_price` | Build force-buy order and record force-loss metadata |
| `_enter_emergency_mode` | `filled` | Mark all unfilled grids as emergency-closed |
| `close_grid_round` | `_round_closed`, `filled`, `sell_price_actual`, `sell_price`, `buy_price_actual`, `buy_price`, `sell_shares`, `sell_commission`, `buy_commission`, `round_id`, `grid_level`, `sell_date`, `buy_date`, `force_loss` | Settle PnL, append to `self.trades`, and clear `sold_grids` when all grids are closed |
| `notify_order` (sell) | — (writes) | Match `_pending_grid`; fallback LIFO match by `sell_shares` |
| `notify_order` (buy) | `filled`, `sell_shares`, `buy_price_actual`, `sell_date`, `sell_price_actual` | LIFO match and trigger settlement |
| `_issue_sold_grid_record` | `round_count` (reads) | Set `round_id` and `grid_level` for the new grid |

#### 4.2.4 Snapshot Example

```python
# A grid after sell filled but not yet bought back
{
    'round_id': 0,
    'grid_level': 1,
    'sell_price': 10.30,           # nominal
    'sell_price_actual': 10.34,    # filled by broker (includes slippage)
    'sell_shares': 500,
    'sell_commission': 5.17,
    'buy_price': 9.82,             # = sell_price_actual * (1 - grid_down_ratio), recalc after fill
    'buy_price_actual': None,
    'buy_commission': 0.0,
    'sell_date': date(2025, 2, 5),
    'buy_date': None,
    'filled': False,
    'force_completed': False,
    'force_reason': None,
    'force_loss': 0.0,
    '_round_closed': False
}
```

### 4.3 Derived Variables

```python
# Total sold shares
total_sold_shares = sum(grid['sell_shares'] for grid in sold_grids)

# Remaining base position
remaining_position = current_position - total_sold_shares

# Next grid sell price
next_sell_price = calculate_next_sell_price(sold_grids, p_base)

# Next grid buy price (corresponding to the lowest unfilled grid)
next_buy_price = calculate_next_buy_price(sold_grids)

# ===== Profit Tracking Derived Variables =====
# Current total asset = Cash + Position market value
current_total_asset = broker.get_cash() + current_position * current_price

# Total asset profit (absolute)
total_asset_profit = current_total_asset - initial_total_asset

# Cash profit (absolute, realized)
cash_profit = total_profit

# Holding days
holding_days = (current_date - start_date).days

# Cash return rate
cash_return_rate = cash_profit / initial_total_asset if initial_total_asset > 0 else 0

# Total asset return rate
total_asset_return_rate = total_asset_profit / initial_total_asset if initial_total_asset > 0 else 0

# Cash annualized return rate
cash_annualized_return = cash_return_rate * (365 / holding_days) if holding_days > 0 else 0

# Total asset annualized return rate
total_asset_annualized_return = total_asset_return_rate * (365 / holding_days) if holding_days > 0 else 0
```

---

## 5. Example Trading Flow

### 5.1 Basic Parameter Setup
```
Initial Capital: 100,000 USD
Initial Stock Price: 10.00 USD
Initial Base Position: 50,000 USD = 5,000 shares
U = 3%, D = 5%, Q = 10%
```

### 5.2 Complete Trading Flow Example

#### Phase 1: Startup Initialization (Day 1)
```
Stock Price: 10.00 USD
P_base: 10.00 USD (closing price)
Base Position: 5,000 shares
Cash: 50,000 USD
Status: Waiting for sell signal
```

#### Phase 2: Consecutive Selling (Day 5-6)
```
Day 5: Stock price rebounds to 10.35 USD
├── Calculate 1st grid sell price: 10.00 × 1.03 = 10.30 USD
├── Check conditions:
│   ✅ 10.35 ≥ 10.30 (price met)
│   ✅ 5000 - 500 = 4500 ≥ 2500 (position protection)
├── Execute: Sell 500 shares @ 10.35 USD
├── Position: 5000 → 4500 shares
├── Cash: 50,000 + 5,175 = 55,175 USD
└── Record 1st grid: sell=10.35, buy=9.83, shares=500

Day 6: Stock price continues to rebound to 10.68 USD
├── Calculate 2nd grid sell price: 10.35 × 1.03 = 10.66 USD
├── Check conditions:
│   ✅ 10.68 ≥ 10.66 (price met)
│   ✅ 4500 - 500 = 4000 ≥ 2500 (position protection)
├── Execute: Sell 500 shares @ 10.68 USD
├── Position: 4500 → 4000 shares
├── Cash: 55,175 + 5,340 = 60,515 USD
└── Record 2nd grid: sell=10.68, buy=10.15, shares=500
```

#### Phase 3: Consecutive Buy-back (Day 8-10)
```
Day 8: Stock price falls back to 10.10 USD
├── Check 2nd grid buy: 10.10 ≤ 10.15 ✅
├── Execute: Buy 500 shares @ 10.10 USD
├── Position: 4000 → 4500 shares
├── Cash: 60,515 - 5,050 = 55,465 USD
├── 2nd grid profit: (10.68 - 10.10) × 500 = 290 USD
└── Record 2nd grid: filled=True, profit=290

Day 10: Stock price continues to fall to 9.80 USD
├── Check 1st grid buy: 9.80 ≤ 9.83 ✅
├── Execute: Buy 500 shares @ 9.80 USD
├── Position: 4500 → 5000 shares (fully bought back!)
├── Cash: 55,465 - 4,900 = 50,565 USD
├── 1st grid profit: (10.35 - 9.80) × 500 = 275 USD
└── 1st round completed, total profit: 290 + 275 = 565 USD
```

#### Phase 4: Base Price Update (Day 11)
```
Day 11: Intraday low 9.75 USD
├── Check base price downward shift: 9.75 < 10.00 × 0.98 = 9.80 ✅
├── Update P_base = 9.75 USD
├── New sell price: 9.75 × 1.03 = 10.04 USD
└── Grid repositioned to downtrend channel
```

### 5.3 Trading Record Detail Table

| Date | Action | Price | Shares | Cash Change | Position | Cumulative Profit | Cumulative Cash Profit | Total Asset | Total Asset Profit |
|------|--------|-------|--------|-------------|----------|-------------------|----------------------|-------------|--------------------|
| Day 1 | - | 10.00 | 5,000 | 50,000 | 5,000 | 0 | 0 | 100,000 | 0 |
| Day 5 | **Sell** | 10.35 | 500 | +5,175 | 4,500 | 0 | 0 | 99,675 | -325 |
| Day 6 | **Sell** | 10.68 | 500 | +5,340 | 4,000 | 0 | 0 | 99,095 | -905 |
| Day 8 | **Buy** | 10.10 | 500 | -5,050 | 4,500 | 290 | 290 | 99,950 | -50 |
| Day 10 | **Buy** | 9.80 | 500 | -4,900 | 5,000 | 565 | 565 | 100,565 | 565 |
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

---

## 6. Code Implementation Highlights

### 6.1 Class Structure Design

```python
class TrailingBearishGrid(BaseStrategy):
    """
    Trailing Bearish Grid Strategy
    
    Core Mechanism:
    1. Base price dynamically shifts down, following the downtrend channel
    2. Continuous grid selling, calculated based on the previous sell price
    3. Position protection, remaining position not less than initial 50%
    4. Closed loop buy-back, locking in each round's profit
    5. Dual-dimension profit tracking: tracks both cash profit (realized) and total asset profit (including floating)
    6. Forced market buy-back: if a grid cannot be bought back within N trading days (default 20),
       a market buy-back is force-executed regardless of price to avoid the "incomplete buy-back trap".
       WARNING: This mechanism introduces bull-market risk. See Section 7.5 for risk disclosure.
    """
    
    # Parameter definitions
    params = (
        ('initial_position_ratio', 0.5),    # Initial position ratio
        ('grid_up_ratio', 0.03),            # Grid sell spacing U%
        ('grid_down_ratio', 0.05),          # Grid buy spacing D%
        ('grid_sell_ratio', 0.1),           # Per-grid sell ratio Q%
        ('base_shift_threshold', 0.02),     # Base price shift threshold
        ('min_position_ratio', 0.5),        # Position protection line
        ('max_grid_count', 5),              # Maximum grid count
        ('mandatory_buyback_days', 20),     # Days before force market buy-back
    )
```

### 6.2 Core Method Implementation

#### 6.2.1 Initialization Method
```python
def __init__(self, data_provider, factor_calculator, **kwargs):
    super().__init__(data_provider, factor_calculator, **kwargs)
    
    # Calculate initial base position
    initial_value = self.broker.getvalue()
    initial_capital = initial_value * self.params.initial_position_ratio
    self.initial_shares = int(initial_capital / self.data.close[0])
    
    # Initialize state
    self.current_position = self.initial_shares
    self.p_base = self.data.close[0]
    self.sold_grids = []
    self.round_count = 0
    self.total_profit = 0
    
    # ===== Dual Profit Tracking Variable Initialization =====
    self.initial_total_asset = initial_value  # Record initial total asset
    self.cash_profit = 0                      # Cash profit (realized)
    self.total_asset_profit = 0               # Total asset profit
    self.start_date = self.data.datetime.date(0)  # Strategy start date
    
    # ===== Force Buyback Tracking Initialization =====
    self.force_completed_count = 0            # Number of force-completed grids
    self.force_loss_total = 0                # Cumulative extra loss from forced buybacks
    self.force_buyback_warned = False         # Backtest warning flag (one-shot per run)
    self.allow_new_sells = True               # Master switch for new sells (HALTED in Emergency)
```

#### 6.2.2 Base Price Update Method
```python
def update_base_price(self):
    """Update base price after daily close"""
    today_low = self.data.low[0]
    threshold = self.p_base * (1 - self.params.base_shift_threshold)
    
    if today_low < threshold:
        self.p_base = today_low
        logger.info(f"[P_BASE] Base price shifted down to {self.p_base:.2f}")
```

#### 6.2.3 Sell Check Method
```python
def check_sell_signals(self):
    """Check continuous sell conditions"""
    current_price = self.data.close[0]
    
    # Calculate the next grid sell price
    if len(self.sold_grids) == 0:
        next_sell_price = self.p_base * (1 + self.params.grid_up_ratio)
    else:
        last_grid = self.sold_grids[-1]
        next_sell_price = last_grid['sell_price'] * (1 + self.params.grid_up_ratio)
    
    # Check sell trigger
    if current_price < next_sell_price:
        return False, None
    
    # Check position protection
    total_sold = sum(g['sell_shares'] for g in self.sold_grids)
    remaining = self.current_position - total_sold
    min_allowed = int(self.initial_shares * self.params.min_position_ratio)
    
    if remaining <= min_allowed:
        logger.warning("[SELL] Insufficient position, suspend selling")
        return False, None
    
    # Check max grid count
    if len(self.sold_grids) >= self.params.max_grid_count:
        logger.warning("[SELL] Max grid count reached")
        return False, None
    
    # Calculate sell quantity
    sell_shares = int(self.initial_shares * self.params.grid_sell_ratio)
    actual_shares = min(sell_shares, remaining - min_allowed)
    
    if actual_shares <= 0:
        return False, None
    
    return True, {
        'sell_price': next_sell_price,
        'sell_shares': actual_shares,
        'buy_price': next_sell_price * (1 - self.params.grid_down_ratio)
    }
```

#### 6.2.4 Buy Check Method
```python
def check_buy_signals(self):
    """Check continuous buy conditions"""
    current_price = self.data.close[0]
    
    # Check from highest sell price to lowest
    unsold_grids = [g for g in self.sold_grids if not g['filled']]
    unsold_grids.sort(key=lambda x: x['sell_price'], reverse=True)
    
    for grid in unsold_grids:
        if current_price <= grid['buy_price']:
            # Check cash sufficiency
            required_cash = grid['sell_shares'] * current_price
            if self.broker.get_cash() < required_cash:
                logger.warning(f"[BUY] Insufficient cash, need {required_cash:.2f}")
                continue
            
            return True, grid
    
    return False, None
```

#### 6.2.5 Forced Buy-back Check Method
```python
def check_force_buyback_signals(self):
    """Check whether any grid has timed out and requires forced market buy-back"""
    current_date = self.data.datetime.date(0)
    force_candidates = []
    
    for grid in self.sold_grids:
        if grid['filled']:
            continue
        holding_days = (current_date - grid['sell_date']).days
        if holding_days >= self.params.mandatory_buyback_days:
            force_candidates.append((grid, holding_days))
    
    # Sort by oldest sell first (most urgent)
    force_candidates.sort(key=lambda x: x[0]['sell_date'])
    return force_candidates
```

#### 6.2.6 Execute Forced Market Buy-back
```python
def execute_force_buyback(self, grid, holding_days):
    """Execute forced market buy-back to avoid incomplete buy-back trap"""
    current_price = self.data.close[0]  # Use close price as market price
    buy_shares = grid['sell_shares']
    
    # Force buy at market price regardless of cash sufficiency
    required_cash = buy_shares * current_price
    available_cash = self.broker.get_cash()
    
    if available_cash < required_cash:
        # Insufficient cash for forced buy-back -> Enter Emergency Mode
        logger.critical(
            f"[FORCED BUYBACK EMERGENCY] Insufficient cash for forced buy-back. "
            f"Required: {required_cash:.2f}, Available: {available_cash:.2f}. "
            f"Grid round={grid['round_id']} level={grid['grid_level']}. "
            f"Entering Emergency Mode."
        )
        self.enter_emergency_mode(f"insufficient_cash_for_force_buyback")
        return False
    
    # Execute the market buy
    self.execute_buy_order(buy_shares, current_price)
    
    # Update grid record
    grid['filled'] = True
    grid['force_completed'] = True
    grid['force_reason'] = 'timeout'
    grid['buy_price_actual'] = current_price
    grid['force_loss'] = (current_price - grid['buy_price']) * buy_shares
    
    # Update global tracking
    self.force_completed_count += 1
    self.force_loss_total += grid['force_loss']
    
    # Update profit
    profit = (grid['sell_price'] - current_price) * buy_shares
    self.total_profit += profit
    
    # === Critical Logging ===
    logger.critical(
        f"[FORCED BUYBACK] Grid round={grid['round_id']} level={grid['grid_level']} "
        f"has timed out after {holding_days} days (threshold={self.params.mandatory_buyback_days}). "
        f"Sell price={grid['sell_price']:.2f}, Intended buy price={grid['buy_price']:.2f}, "
        f"Actual buy price={current_price:.2f}, Shares={buy_shares}, "
        f"Forced loss={grid['force_loss']:.2f}, Grid profit={profit:.2f}. "
        f"Total force-completed grids: {self.force_completed_count}, "
        f"Total forced loss: {self.force_loss_total:.2f}. "
        f"Please review market conditions and strategy parameters immediately."
    )
    
    # Backtest warning (issued once)
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
```

#### 6.2.7 Emergency Mode Entry
```python
def enter_emergency_mode(self, reason):
    """Enter emergency mode and halt strategy"""
    logger.critical(
        f"[EMERGENCY MODE] Strategy halted. Reason: {reason}. "
        f"Force-completed grids: {self.force_completed_count}, "
        f"Total forced loss: {self.force_loss_total:.2f}. "
        f"Total profit: {self.total_profit:.2f}."
    )
    # Halt new sells
    self.allow_new_sells = False
    # Force close all unfilled grids at market
    # (implementation depends on broker API; mark all as force_completed)
    self._force_close_remaining_grids()
    # Send external notification
    self.notify_emergency()
```

### 6.3 Main Loop Implementation

```python
def next(self):
    """Main trading loop"""
    # 0. Force buyback check (HIGHEST PRIORITY - must run first to avoid trap)
    force_candidates = self.check_force_buyback_signals()
    if force_candidates:
        for grid, holding_days in force_candidates:
            self.execute_force_buyback(grid, holding_days)
            self.close_grid_round(grid)
        return
    
    # 1. Base price update (after daily close)
    self.update_base_price()
    
    # 2. Check buy conditions (priority on buy-back)
    buy_signal, buy_grid = self.check_buy_signals()
    if buy_signal:
        self.execute_buy(buy_grid)
        self.close_grid_round(buy_grid)
        return
    
    # 3. Check sell conditions
    sell_signal, sell_info = self.check_sell_signals()
    if sell_signal:
        self.execute_sell(sell_info)
        return
    
    # 4. Record status
    self.log_grid_status()
```

### 6.4 Logging Implementation

```python
def log_grid_status(self):
    """Record grid status (including dual-dimension profit tracking and force-buyback monitoring)"""
    # Calculate current total asset
    current_total_asset = self.broker.get_cash() + self.current_position * self.data.close[0]
    self.total_asset_profit = current_total_asset - self.initial_total_asset
    self.cash_profit = self.total_profit
    
    # Calculate holding days and annualized return rates
    holding_days = (self.data.datetime.date(0) - self.start_date).days
    cash_return_rate = self.cash_profit / self.initial_total_asset if self.initial_total_asset > 0 else 0
    total_asset_return_rate = self.total_asset_profit / self.initial_total_asset if self.initial_total_asset > 0 else 0
    cash_annualized = cash_return_rate * (365 / holding_days) if holding_days > 0 else 0
    total_asset_annualized = total_asset_return_rate * (365 / holding_days) if holding_days > 0 else 0
    
    # Calculate force-buyback stress indicators
    force_loss_ratio = self.force_loss_total / self.initial_total_asset if self.initial_total_asset > 0 else 0
    force_stress_level = (
        "CRITICAL" if force_loss_ratio > 0.1 or self.force_completed_count >= self.params.max_grid_count
        else "HIGH" if self.force_completed_count > 0
        else "NORMAL"
    )
    
    logger.info(f"""
    [GRID STATUS]
    P_base: {self.p_base:.2f}
    Position: {self.current_position} shares
    Sold Grids: {len(self.sold_grids)}
    Round Count: {self.round_count}
    ----- Profit Tracking -----
    Initial Total Asset: {self.initial_total_asset:.2f}
    Current Total Asset: {current_total_asset:.2f}
    Cash Profit:      {self.cash_profit:.2f} (Return: {cash_return_rate:.2%}, Annualized: {cash_annualized:.2%})
    Total Asset Profit: {self.total_asset_profit:.2f} (Return: {total_asset_return_rate:.2%}, Annualized: {total_asset_annualized:.2%})
    Holding Days:     {holding_days}
    ----- Forced Buyback Monitoring -----
    Force-Completed Grids: {self.force_completed_count}
    Total Forced Loss:     {self.force_loss_total:.2f} ({force_loss_ratio:.2%} of initial capital)
    Stress Level:          {force_stress_level}
    """)
    
    # Backtest stress warning
    if force_stress_level in ('CRITICAL', 'HIGH') and not self.force_buyback_warned:
        logger.warning(
            f"[BACKTEST STRESS WARNING] Forced buyback stress level: {force_stress_level}. "
            f"Force-completed grids: {self.force_completed_count}, "
            f"Total forced loss: {self.force_loss_total:.2f} ({force_loss_ratio:.2%} of initial capital). "
            "Please review strategy parameters before deploying to live trading."
        )
        self.force_buyback_warned = True
```

---

## 7. Risk Control Explanation

### 7.1 Position Protection Mechanism
- Remaining position always no less than 50% of initial base position
- Prevent excessive selling leading to "selling out"
- Ensure long-term holding foundation

### 7.2 Cash Protection Mechanism
- Check whether cash is sufficient before buying
- Avoid buy-back failure due to insufficient funds
- Prevent forced liquidation

### 7.3 Abnormal Market Protection
- Suspend trading during single-day large fluctuations
- Force liquidation when extreme stop loss line is triggered
- Prevent loss expansion in abnormal markets

### 7.4 Grid Count Limit
- Set maximum grid count (e.g., 5 grids)
- Prevent over-exposure in one-sided markets
- Control maximum loss exposure

### 7.5 Forced Buy-back Risk & Emergency Mode

#### 7.5.1 Risk Disclosure (Critical)
> ⚠️ **WARNING**: The mandatory forced buy-back mechanism is a **double-edged sword**. It solves the "incomplete buy-back trap" but introduces new risks that must be fully understood before deploying this strategy in live trading:

1. **Bull Market Risk (The Primary Risk)**: In a sustained bull market, prices may never fall back to the `buy_price` levels. The strategy will **execute market buy-backs at prices significantly higher than the sell prices**, resulting in **realized losses on every forced buy-back**. The longer the bull market persists, the larger the cumulative loss.

2. **Forced Buy-back Can Wipe Out All Previous Gains**: If a bull market lasts longer than `mandatory_buyback_days` (default 20 trading days) and multiple grids are triggered, forced buy-backs can consume all cash reserves and turn a previously profitable strategy into a losing one.

3. **Liquidity Risk**: Forced buy-back executes at market price. In thin/illiquid markets, the market buy order itself may drive the price even higher, causing slippage beyond expectation.

4. **Cash Reserve Risk**: When multiple grids trigger forced buy-back simultaneously, the total required capital may exceed available cash. In this case:
   - The strategy enters **Emergency Mode**: the system must alert the user immediately and pause new sells
   - The user must manually decide whether to inject capital or accept a partial position close
   - Without intervention, the account may face margin calls or forced liquidation by the broker

5. **Backtest Bias**: Historical backtests may **underestimate** forced buy-back losses because:
   - Backtest data typically uses one closing price per day, hiding intraday volatility
   - Slippage and market impact are often not modeled
   - Bull markets in the past may not reflect future conditions

#### 7.5.2 Warning Indicators
The following conditions in backtest or live trading indicate the strategy is facing abnormal stress and user attention is required:

| Warning Indicator | Severity | Action Required |
|-------------------|----------|-----------------|
| `force_completed_count > 0` | ⚠️ Medium | Review market conditions; this should not happen in normal downtrends |
| `force_completed_count >= max_grid_count/2` | 🔴 High | Stop new sells immediately; the market is in a bull phase |
| `force_loss_total > total_profit` | 🔴 Critical | All previous gains have been erased by forced buy-backs; **STOP the strategy immediately** |
| `force_loss_total > initial_total_asset * 0.1` | 💀 Emergency | Losses exceed 10% of initial capital; enter Emergency Mode |
| Cash insufficient for forced buy-back | 💀 Emergency | Immediate manual intervention required |

#### 7.5.3 Emergency Mode Protocol
When emergency conditions are detected:
```python
def enter_emergency_mode(reason):
    # 1. Log critical alert
    logger.critical(f"[EMERGENCY MODE] Reason: {reason}. Strategy halted.")
    
    # 2. Send external notification (email, SMS, webhook)
    notify_user(reason, force_loss_total, force_completed_count)
    
    # 3. Pause all new sell signals
    self.allow_new_sells = False
    
    # 4. Log all open positions and force events
    log_emergency_snapshot()
    
    # 5. Wait for user confirmation before resuming
    # DO NOT auto-resume
```

#### 7.5.4 Recommended Mitigations
1. **Parameter Tuning**: Increase `mandatory_buyback_days` to 30-60 days for bearish markets; or reduce to 10 days if you believe a bull market may be starting
2. **Cash Buffer**: Keep at least 20% of total assets as an emergency cash buffer beyond the initial 50%
3. **Market Regime Detection**: Consider adding a bull-market filter (e.g., 200-day MA) that disables sells when the market is confirmed bullish
4. **Position Sizing**: Reduce `grid_sell_ratio` during market uncertainty
5. **Regular Backtesting**: Run backtests specifically on bull-market periods to stress-test forced buy-back behavior

---

## 8. Parameter Tuning Recommendations

### 8.1 Conservative Configuration (Low Risk)
```python
grid_up_ratio = 0.04      # 4% sell spacing
grid_down_ratio = 0.06    # 6% buy spacing
grid_sell_ratio = 0.08    # 8% per grid
max_grid_count = 3        # Maximum 3 grids
```

### 8.2 Balanced Configuration (Recommended)
```python
grid_up_ratio = 0.03      # 3% sell spacing
grid_down_ratio = 0.05    # 5% buy spacing
grid_sell_ratio = 0.10    # 10% per grid
max_grid_count = 5        # Maximum 5 grids
```

### 8.3 Aggressive Configuration (High Return)
```python
grid_up_ratio = 0.02      # 2% sell spacing
grid_down_ratio = 0.04    # 4% buy spacing
grid_sell_ratio = 0.12    # 12% per grid
max_grid_count = 7        # Maximum 7 grids
```

---

## 9. Notes

### 9.1 Prerequisites for Application
- Must be used in a downtrend channel
- Requires sufficient stock price volatility
- Long-term holding to demonstrate value

### 9.2 Potential Risks
- One-sided decline may lead to stop loss
- Limited returns in sideways markets
- May miss out on strong rebounds
- **Bull market risk**: Forced buy-back at elevated prices can turn the strategy into a losing position. See Section 7.5 for full risk disclosure.
- **Liquidity risk**: Thin markets during forced buy-back may cause significant slippage

### 9.3 Usage Recommendations
- Test on simulated trading first
- Choose stocks with high volatility
- Periodically review strategy performance
- Adjust parameters based on market conditions
- **Always run backtests on bull-market periods** to stress-test the forced buy-back mechanism
- Start with conservative `mandatory_buyback_days` (20 days) and adjust based on actual market behavior

---

**Document Version**: v1.1  
**Created Date**: 2026-06-21  
**Applicable Framework**: backtrader