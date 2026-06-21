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

### 2.2 Extended Parameters

| Parameter | Symbol | Type | Default | Description |
|-----------|--------|------|---------|-------------|
| Max Grid Count | `max_grid_count` | int | 5 | Maximum number of grids supported |
| Max Daily Volatility | `max_daily_volatility` | float | 0.08 (8%) | Abnormal market filter |
| Volume Filter Toggle | `volume_filter` | bool | False | Enable volume confirmation |
| Stop Loss Line | `stop_loss_line` | float | 0.20 (20%) | Extreme stop loss threshold |

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

### 4.2 Grid Record Structure

```python
sold_grid_record = {
    'round_id': int,           # Grid round ID
    'grid_level': int,         # Grid level (which sell)
    'sell_price': float,       # Sell price
    'sell_shares': int,        # Sell quantity
    'buy_price': float,        # Corresponding buy price
    'filled': bool,            # Whether bought back
    'buy_price_actual': float  # Actual buy price (filled after buy-back)
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

#### 6.2.5 Closed Loop Completion Method
```python
def close_grid_round(self, grid):
    """Complete a round of grid trading"""
    # Mark as bought back
    grid['filled'] = True
    grid['buy_price_actual'] = self.data.close[0]
    
    # Calculate profit
    profit = (grid['sell_price'] - grid['buy_price_actual']) * grid['sell_shares']
    self.total_profit += profit
    
    # ===== Update Dual Profit Tracking Variables =====
    self.cash_profit = self.total_profit  # Cash profit is realized profit
    current_total_asset = self.broker.get_cash() + self.current_position * self.data.close[0]
    self.total_asset_profit = current_total_asset - self.initial_total_asset
    
    # Check whether all grids have been bought back
    if all(g['filled'] for g in self.sold_grids):
        self.round_count += 1
        logger.info(f"[ROUND] Round {self.round_count} completed, this round's profit {profit:.2f} USD")
        # Reset grid
        self.sold_grids = []
```

### 6.3 Main Loop Implementation

```python
def next(self):
    """Main trading loop"""
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
    """Record grid status (including dual-dimension profit tracking)"""
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
    """)
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

### 9.3 Usage Recommendations
- Test on simulated trading first
- Choose stocks with high volatility
- Periodically review strategy performance
- Adjust parameters based on market conditions

---

**Document Version**: v1.1  
**Created Date**: 2026-06-21  
**Applicable Framework**: backtrader