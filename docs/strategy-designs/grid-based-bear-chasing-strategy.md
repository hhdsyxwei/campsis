# Grid-Based Bear-Chasing Strategy Design Document

## Summary & Table of Contents

### Executive Summary

| Dimension                   | Description                                                                                                                                                                                                                                                                                                              |
| :-------------------------- | :----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **🎯 Strategy Positioning** | An active grid strategy that captures **rebound opportunities** in a **downtrend (bearish market)**.                                                                                                                                                                                                                     |
| **💡 Core Logic**           | At the daily open, based on a dynamically adjusted base price, it **places multiple limit sell orders at different prices in one batch** (Static Multi-Order Parallel Model). It captures intraday rebound highs to sell holdings, then buys back at lower prices to add positions.                                      |
| **⚙️ Workflow**             | **Place Orders** → **Rebound Triggered** (Reduce Position) → **Price Pullback** (Buy Back to Add Position)                                                                                                                                                                                                               |
| **🛡️ Risk Control**        | - **Mandatory Buyback Mechanism**: Any sell position can be held for a maximum of 30 days.  - **Dynamic Base Price Downshift**: Only shifts down, following the bearish trend.  - **Consecutive Downshift Risk Control**: Pauses opening new sell orders if the base price shifts down for more than 3 consecutive days. |
| **📊 Applicable Scenarios** | ✅ Oscillating downtrend channels, pulsed rebounds, large-cap blue-chip stocks (sufficient liquidity).  ❌ Unilateral uptrends, unilateral decline without rebound, high-level oscillation.                                                                                                                                |

***

### Table of Contents

1. **Strategy Core Elements**
   - 1.1. Strategy Name
   - 1.2. Core Mechanism
   - 1.3. Core Features
   - 1.4. Strategy Goals
   - 1.5. Applicable Scenarios
   - 1.6. Market Structural Fit & Adaptability
2. **Strategy Design Philosophy**
3. **Prerequisites**
4. **Core Design Concept**
5. **Generation and Update Mechanism of the Base Price**
   - 5.1. Core Design Principles
   - 5.2. Generation Mechanism
6. **Global Data Structures**
7. **Core Trading Process (in the** **`next()`** **Function)**
   - Step 0: Preparation and Refreshment
   - Step 1: Mandatory Buyback Check
   - Step 2: Normal Buyback Logic
   - Step 3: Selling Logic
   - Step 4: Data Management and Cleanup
   - Step 5: Base Price Dynamic Update (Downshift)
8. **Order Lifecycle Management (`notify_order`** **Function)**
9. **Core Process Sequence Diagram**
10. **Exception Handling and Boundary Cases**
    - 10.1. Risk Control Strategy for Consecutive Base Price Downshifts
    - 10.2. Handling of Other Boundary Cases
11. **Core Parameters and Risk Control**
    - 11.1. Core Parameter Definition
    - 11.2. Order Type Specification
    - 11.3. Risk Control Mechanism Summary
12. **Strategy Potential Risks and Mechanism Vulnerabilities**
    - 12.1. Intraday Dynamic Order Placement Missing Risk
    - 12.2. Logic Conflict Between Base Price Update and Current Day's Sell Orders

***

This document details the core logic of the **Grid-Based Bear-Chasing Strategy (网格追空策略)**. The strategy is based on a "Static Multi-Order Parallel Model", aiming to capture rebound opportunities in a downtrend and maximize the efficiency of capturing intraday volatility through multiple pre-placed limit sell orders. The term "Bear-Chasing" refers to actively tracking the structural profit opportunities within a bear market, rather than engaging in high-risk short-selling.

***

## 1. Strategy Core Elements

### 1.1 Strategy Name

**Grid-Based Bear-Chasing Strategy** (网格追空策略)

- **Name Definition**: "Bear-Chasing" refers to the strategy's active pursuit of profit opportunities in a **bear market (空头市场)**. It is **not** a high-risk short-selling strategy, but rather a tactical operation based on existing long positions.

### 1.2 Core Mechanism

In a downtrend (bearish market), the strategy first establishes an initial base position by allocating a portion of its total capital. It then operates under the "Static Multi-Order Parallel" model: at the start of each trading day, it batches multiple limit sell orders at staggered prices based on the reference price P\_base. When a price rebound triggers a sell order, the strategy passively reduces its position by selling a portion of its holdings. Subsequently, as the price declines, it re-adds the position via pre-calculated limit buy orders. This "sell-to-reduce, buy-to-add" cycle locks in profits from price oscillations while preserving a core long exposure over the long term.

### 1.3 Core Features

- **Efficient Volatility Capture**: By placing N sell orders daily, it maximizes the opportunity to capture consecutive intraday rises, compensating for the inefficiency of the "single-order model".
- **Bidirectional Base Price Anchoring Mechanism**: The base price `P_base` dynamically adjusts in both directions: it shifts down following market declines, and shifts up to yesterday's closing price when a mandatory buyback is triggered (indicating a potential trend reversal). This ensures the strategy's adaptability in both bear and bull markets.
- **Spot Base Position Hedging**: The strategy maintains a core long position (base position) from the outset. This acts as a natural hedge against extreme uptrends (squeezing), ensuring that if the market rises sharply, the portfolio's overall value is not negatively impacted by the short-term "sell-then-buy" trading loop.
- **One-to-One Hedging**: Every sell order (reduce position) is bound to a buy order (add position), forming an independent trading loop.
- **Mandatory Risk Hedging**: The `mandatory_buyback_days` mechanism ensures that any sell position's holding period has an upper limit, preventing losses in extreme market conditions.

### 1.4 Strategy Goals

| Goal Type                     | Specific Objective                     | Description                                                                                                                                                                                                                                                                                                                                                      |
| :---------------------------- | :------------------------------------- | :--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Core Profit Goal**          | Long-term Cash Flow Generation         | Based on the structural characteristic of "short bull, long bear" markets, the strategy focuses on generating consistent long-term cash profits. It does **not** deliberately pursue short-term increases in total assets; instead, it strategically captures the "sell high, buy low" cycles in prolonged bear markets to continuously accumulate cash returns. |
| **Risk Control Goal**         | Limit Maximum Holding Period           | Use the `mandatory_buyback_days` mechanism to ensure that any sell-to-reduce trade is forcibly closed within a predefined period (e.g., 30 days), preventing the risk of unlimited losses caused by a single trade being trapped in a continued uptrend.                                                                                                         |
| **Risk Control Goal**         | Adapt to Market Downtrend              | Dynamically adjust the base price downward following the market's downtrend, ensuring that the strategy's sell orders are always placed at higher relative prices, maintaining the strategy's "follow the trend" ability.                                                                                                                                        |
| **Position Management Goal**  | Maintain Core Long Exposure            | While capturing short-term trading opportunities, always ensure a core long position is maintained. The trading of reducing and adding positions is a tactical overlay on the strategic long-term holding.                                                                                                                                                       |
| **Execution Efficiency Goal** | Maximize Volatility Capture Efficiency | Use the "Static Multi-Order Parallel" model to place multiple sell orders at different prices at one time, improving the probability of capturing intraday rebounds and maximizing the utilization of volatile opportunities.                                                                                                                                    |

### 1.5 Applicable Scenarios

| Suitable                                                                 | Unsuitable                                          |
| :----------------------------------------------------------------------- | :-------------------------------------------------- |
| ✅ The target is in a clear **oscillating downtrend channel**             | ❌ **Continued unilateral uptrend** market           |
| ✅ **Pulsed rebounds** exist in the downtrend                             | ❌ Market with unilateral decline but **no rebound** |
| ✅ Target has **sufficient liquidity** (e.g., large-cap blue-chip stocks) | ❌ **High-level oscillation with unclear direction** |

### 1.6 Market Structural Fit & Adaptability

This strategy's performance is highly dependent on the structural characteristics of the target market. It thrives in specific market environments and struggles in others. The following table summarizes its adaptability across different markets:

| Market                           | Structural Fit                        | Adaptability | Rationale                                                                                                                                                                                                                                                                                                     |
| :------------------------------- | :------------------------------------ | :----------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **A-Share Market (中国A股)**        | ✅ **Highly Suitable**                 | ⭐⭐⭐⭐⭐        | The classic structure of "short bull, long bear" (牛短熊长) is the ideal environment: 1. **Long Bear**: Provides continuous "sell high — buy low" cycles as the base price shifts down. 2. **Sharp Rallies**: Offers frequent and explosive rebound opportunities for the batch of sell orders to be triggered.   |
| **Hong Kong Stock Market (港股)**  | ⚠️ **Partially Suitable**             | ⭐⭐⭐          | Similar to A-shares, it can exhibit a volatile, range-bound nature. However, the lower liquidity compared to A-shares (especially for small caps) and greater influence by overseas capital flows may cause slippage during mandatory buybacks. The strategy works better for large-cap stocks.               |
| **U.S. Stock Market (美股)**       | ❌ **Unsuitable**                      | ⭐            | The dominant "slow bull" (慢牛) structure, where prices tend to drift upward over the long term without significant pullbacks, is hostile. The **"buyback" phase is permanently missing**, causing the profit loop to break and resulting in potential unlimited losses on sell positions.                      |
| **European Markets**             | ❌ **Unsuitable**                      | ⭐            | Similar to the U.S., European markets often exhibit a secular upward trend with lower volatility. The lack of sustained bear markets and sharp, frequent rebounds makes the strategy's long-term profit accumulation highly challenging.                                                                      |
| **Cryptocurrency Market (加密货币)** | ⚠️ **High Risk / Partially Suitable** | ⭐⭐           | While crypto markets offer extreme volatility (which is good for rebound selling), their unpredictable nature, potential for infinite squeezes, and often shallow liquidity make the risk of unlimited losses and slippage during mandatory buybacks extremely high. It requires very strict risk management. |

***

## 2. Strategy Design Philosophy

The core philosophy of this strategy is **"Follow the trend to sell high, earn from volatility"**. It is not an ordinary grid that passively earns low prices in an oscillating market, but an **active strategy that uses rebounds in a downtrend (bearish) as trading opportunities**.

- **Follow the trend**: Being in an **oscillating downward channel** is the premise and safety net of the strategy. Market inertia will continuously push the price down, making the high sell-then-low buy (add position) have higher win rates and certainty.
- **Profit from volatility**: In a downtrend, price inevitably comes with rebounds. The strategy aims to capture these "pulsed rebounds", reducing positions (selling) at high points and cashing in profits (buying back) using market inertia.
- **Risk hedging**: Every sell (reduce position) immediately locks in its corresponding target buyback price, forming a trading loop. This allows the strategy to automatically realize profits via price pullbacks without judging the market's end point.

***

## 3. Prerequisites

To ensure the strategy functions as designed, the following prerequisites must be met:

### 3.1 Target Market & Liquidity

- **Trading Targets**: The strategy is designed for **A-share large-cap blue-chip stocks** (e.g., SSE 50, CSI 300 constituents).
- **Liquidity Assumption**: High market liquidity is assumed. The strategy does **not** account for slippage, order placement failures, or market impact caused by illiquidity.

### 3.2 Trading Rules & Mechanisms

- **Lot Size**: All buy and sell orders must be multiples of **100 shares (1 lot)**.
- **Initial Position Establishment**: The strategy requires the establishment of an **initial base position** at the start. A predetermined proportion of the total capital (e.g., 40%) must be allocated to purchase the target stock to enable subsequent sell operations.
- **Sufficient Capital**: Adequate capital must be available in the trading account to support the strategy's buyback (position adding) operations.

### 3.3 Technical Framework Requirements

- **State-Driven Execution**: The strategy requires a **state-driven trading framework** (e.g., Backtrader, Zipline) that supports event-driven, bar-by-bar execution.
- **Dynamic Order Management**: The framework must support dynamically placing, canceling, and updating orders *within* the main strategy logic (e.g., the `next()` method).
- **Order Lifecycle Tracking**: The framework must provide an order lifecycle callback (e.g., `notify_order`) to allow the strategy to react to order status changes (filled, canceled, rejected).
- **Path Dependency**: The framework must support maintaining internal state across trading sessions to handle path-dependent logic (e.g., counting consecutive days, tracking grid status).

***

## 4. Core Design Concept

- **Goal**: Solve the problem of "missing consecutive intraday rises due to only placing orders on a single day".
- **Model**: **Static Multi-Order Parallel Model**. At the beginning of each trading day (when the `next()` function executes), based on the latest base price `P_base`, it calculates and places `N` future limit sell orders at once. Simultaneously, it uniformly checks and places limit buy orders for all grids pending buyback.
- **Mechanism**: Utilize Backtrader's daily matching engine. When the `High` price of a single K-line touches the sell order limit, it is automatically determined as a transaction; when the `Low` price touches the buy order limit, it is automatically determined as a transaction.

***

## 5. Generation and Update Mechanism of the Base Price

The base price is the only anchor point for the grid strategy to calculate all order prices. Drawing on the design philosophy of **Grid-Based Bear-Chasing Strategy**, this strategy adopts a **dynamic bidirectional update mechanism** (downshift by threshold, upshift by trigger), ensuring the base price always follows the market's trend, whether it is a downtrend or a potential reversal, thereby improving the strategy's adaptability.

### 5.1 Core Design Principles

- **Down by Threshold, Up by Trigger**:
  - **Down**: The base price shifts down *only when* the price drops below a certain threshold (`base_shift_threshold`). This ensures the strategy's "follow the trend" in a bearish market, avoiding frequent adjustments.
  - **Up**: The base price shifts up *only when* a mandatory buyback is triggered. This acts as a signal for potential trend reversal (from bear to bull), allowing the strategy to adapt.
- **Dynamic Following**: The base price is not a fixed value, but a "dynamic anchor" that follows the market's trend, shifting down in a downtrend and being re-anchored upward when a reversal is signaled.
- **Event-Driven**: The base price update is strictly event-driven: downshifts are triggered by daily closing price evaluations, while upshifts are triggered by the specific event of a mandatory buyback.

### 5.2 Generation Mechanism

- **Initialization**:
  - **Timing**: On the first day of strategy start-up.
  - **Price**: Get the **previous closing price** of the current target as the initial base price.
    - `self.base_price = self.data.close[-1]`
- **Daily Dynamic Update Mechanism**: The base price is updated through a **bidirectional mechanism** to adapt to both downtrend and potential uptrend.
  - **1. Dual-Track Downshift Mechanism (In Downtrend)**:
    - **Timing**: At the end of the daily `next()` function (Step 5).
    - **Logic**: This mechanism combines **price threshold trigger** and **time decay trigger** to handle both sharp drops (急跌) and gradual declines (阴跌).
      1. **Track 1: Price Threshold Trigger (For Sharp Drops)**
         - **Judgment**: If `today_close < self.base_price * (1 - self.params.base_shift_threshold)`.
         - **Action**: **Immediately** shift the base price down to `today_close`.
         - **Purpose**: Captures sudden, significant declines to keep sell orders competitive.
      2. **Track 2: Time Decay Trigger (For Gradual Declines)**
         - **Judgment**: If `today_close < self.base_price` (regardless of the magnitude of decline).
         - **Action**: 
             a. Increment a counter `self.below_base_days += 1`.
             b. If `self.below_base_days >= self.params.time_decay_days`, forcibly adjust the base price downward by a small fixed ratio.
             c. Reset the counter `self.below_base_days = 0` after the adjustment.
         - **Purpose**: Solves the "shock" problem during gradual declines (阴跌). Ensures the base price slowly follows the market when prices are continuously below it, even if they don't drop sharply on any single day.
    - **Formula**:
      ```python
      # Track 1: Price Threshold
      if self.data.close[0] < self.base_price * (1 - self.params.base_shift_threshold):
          self.base_price = self.data.close[0]
          self.below_base_days = 0 # reset counter on sharp drop
      else:
          # Track 2: Time Decay
          if self.data.close[0] < self.base_price:
              self.below_base_days += 1
              if self.below_base_days >= self.params.time_decay_days:
                  self.base_price *= (1 - self.params.time_decay_ratio)
                  self.below_base_days = 0
          else:
              self.below_base_days = 0 # reset counter if price recovers
      ```
  - **2. Dynamic Upshift (In Potential Uptrend)**:
    - **Timing**: At the beginning of the daily `next()` function (Step 1), **only when a mandatory buyback is triggered**.
    - **Logic**:
      1. **Trigger Condition**: A mandatory buyback is triggered (market failed to fall to the expected buyback price).
      2. **Update Action**: Immediately raise the `base_price` to the closing price of the previous complete trading day `self.data.close[-1]`.
      3. **Design Choice (Anchor Price)**: **\[Important]** This is a deliberate design choice. Using `self.data.close[-1]` (yesterday's close) as the new anchor point provides a deterministic and stable reference point for the trend reversal. It represents the final consensus price of the previous trading cycle, avoiding the potential uncertainty of the current day's opening price (`self.data.open[0]`), which may be affected by overnight gaps.
      4. **Formula**:
         ```python
         if mandatory_buyback_triggered:
             self.base_price = self.data.close[-1]
         ```
      5. **Purpose**: Recognizes a potential trend reversal (from bear to bull). By raising the base price and canceling old sell orders, the strategy avoids selling at the old, low levels and repositions itself for a rising market, closing the "loss loop" of forced buying high and forced selling low.

***

## 6. Global Data Structures

- **Active Sell Order List (`self.active_sell_orders`)**: Stores limit sell orders that have been submitted but not yet settled on the current day.
- **Active Buy Order List (`self.active_buy_orders`)**: Stores limit buyback orders that have been submitted but not yet settled on the current day.
- **Sold Grid List (`self.sold_grids`)**: Stores information about all grids that have been successfully sold but not yet completed buyback.
- **Continuous Forced Buyback Counter (`self.forced_buyback_streak`)**: Tracks the number of consecutive days the mandatory buyback rule has been triggered. Used for risk monitoring (soft warning).
  - **Grid Record Structure**:
    ```python
    {
        'grid_id': int,             # Grid unique identifier
        'sell_price': float,        # Sell execution price
        'sell_shares': int,         # Number of shares sold
        'sell_date': datetime.date, # Sell execution date
        'base_price_snapshot': float, # Base price snapshot at the time of selling (used for buyback price calculation)
        'buy_price_target': float,   # Target buyback price
        'status': 'pending_buy',    # Grid status: 'pending_buy' | 'filled' | 'force_closed'
        'buy_date': datetime.date,  # Buyback execution date
        'buy_price_actual': float,  # Actual buyback execution price
        'force_loss': float         # Loss amount from forced closing         
    }
    ```

***

## 7. Core Trading Process (in the `next()` Function)

The execution order of the `next()` function must be strictly defined to ensure logical rigor and state consistency.

### Step 0: Preparation and Refreshment

- **\[0.1] Order Queue Initialization**: Prepare to handle orders left over from yesterday. (Note: Base price update is moved to the end)

### Step 1: Mandatory Buyback Check (Independent Non-Blocking)

- **\[1.1] Status Scan**: Traverse `self.sold_grids` to find grids with `status == 'pending_buy'` that exceed `mandatory_buyback_days`.
- **\[1.2] Execution**:
  - **Share Adjustment**: Adjust `grid['sell_shares']` to an **integer multiple of 100 shares** (rounded down).
  - **Order Placement**: Submit a market order for forced liquidation.
  - **Base Price Upshift**: **\[NEW]** If a mandatory buyback is triggered, immediately raise `self.base_price` to `self.data.close[-1]` (yesterday's closing price). **\[Design Choice]** Using the previous day's close provides a stable and deterministic anchor point for the new market conditions, representing the final consensus of the previous trading cycle. This signals a potential trend reversal and repositions the strategy.
  - **Cancel All Sell Orders**: **\[NEW]** If a mandatory buyback is triggered, immediately cancel all unfilled limit sell orders in `self.active_sell_orders` to prevent selling at the old, lower base price.
- **\[1.3] Update**: Change status to `'force_closed'`.
- **\[1.4] Counter Update & Warning**:
  - If any mandatory buyback was triggered today: `self.forced_buyback_streak += 1`.
  - Otherwise: `self.forced_buyback_streak = 0`.
  - **Soft Warning**: If `self.forced_buyback_streak >= self.params.max_forced_buyback_days`, output a **warning log**: `WARNING: Continuous forced buyback count has reached {self.forced_buyback_streak} days. Please monitor market conditions closely.`
- **\[1.5] Termination**: Execution completes. This process is independent and non-blocking. It does not suspend or skip the subsequent logic of the day.

### Step 2: Intraday Buy Order Logic

**\[Independent from Forced Buyback]**

- **\[2.1] Expire Old Buy Orders**: Cancel all unfilled limit buy orders in `self.active_buy_orders`.
- **\[2.2] Generate New Buy Orders (Normal Settlement)**:
  - Traverse grids with `status == 'pending_buy'` in `self.sold_grids`.
  - **Price Calculation**: Calculate the buyback price based on its `base_price_snapshot` (locked at the time of selling to avoid interference from base price changes).
  - **Share Adjustment**: Adjust `grid['sell_shares']` to an **integer multiple of 100 shares** (rounded down).
  - **Order Placement**: Submit a new limit buy order and add it to `self.active_buy_orders`.

### Step 3: Intraday Sell Order Logic

**\[Dynamically Adapted to Forced Buyback]**

- **\[3.1] Expire Old Sell Orders**: (Already processed in Step 1.2 if forced buyback occurred, otherwise executes here)
- **\[3.2] Generate New Sell Orders (New Transaction Decision)**:
  - **Core Logic**: **Entirely based on the current** **`self.base_price`**. If Step 1 triggered, the `base_price` is now updated (higher), and new sell orders will naturally be generated at higher prices, closing the "loss loop".
  - **Price Calculation**: Calculate N new sell grid prices based on the current `self.base_price`.
  - **Share Calculation and Adjustment (Based on Holdings)**:
    - Calculate the target number of shares for each grid based on the current **available holdings** (the total shares held in spot positions). This is a "sell-first, then-buy" strategy, selling existing positions rather than opening new short positions.
      ```python
      # 'self.position.size' is the current number of shares held
      sell_shares_per_grid = min(self.position.size / num_grids, max_sell_per_grid)
      ```
    - Adjust the target number of shares to an **integer multiple of 100 shares** (rounded down). If the adjusted number of shares is 0, skip that grid.
      ```python
      sell_shares_per_grid = (sell_shares_per_grid // 100) * 100
      ```
  - **Order Placement**: Submit a new limit sell order and add it to `self.active_sell_orders`.

### Step 4: Data Management and Cleanup

- **\[4.1] Status Cleanup**: Clean up expired records in `self.sold_grids` where `status` is `'filled'` or `'force_closed'`.

### Step 5: Base Price Dynamic Update (Daily Update)

- **\[5.1] Update Base Price (Downshift for Next Day)**: Execute the base price dynamic downshift logic (see Section 5.2 for details). **Note**: The base price upshift has already been handled in Step 1 when a mandatory buyback is triggered. This step exclusively manages the downward adjustment, preparing the base price for the next trading day if the market continues to decline.

***

## 8. Order Lifecycle Management (`notify_order` Function)

The `notify_order` function only serves as a **status updater** and does not generate any new orders.

- **Sell Order Completed (`Completed`)**:
  - Remove from `self.active_sell_orders`.
  - Create a new record in `self.sold_grids`, with status marked as `'pending_buy'`.
  - Log recording.
- **Buy Order Completed (`Completed`)**:
  - Remove from `self.active_buy_orders`.
  - Find the corresponding record in `self.sold_grids` and update its status to `'filled'`.
  - Log recording.
- **Order Canceled/Rejected (`Canceled`/`Rejected`)**:
  - Remove from the active order list and record the log.

***

## 9. Core Process Sequence Diagram

```mermaid
sequenceDiagram
    participant Next as "next() Start"
    participant Refresh as "Step 0: Refresh"
    participant BuyLogic as "Step 1/2: Buyback Logic"
    participant SellLogic as "Step 3: Selling Logic"
    participant Cleanup as "Step 4: Data Cleanup"
    participant BaseUpdate as "Step 5: Base Price Update (Downshift)"

    Next->>Refresh: "Initialize order list"
    Refresh->>BuyLogic: 

    BuyLogic->>BuyLogic: "Step 1.1: Scan sold_grids for pending_buy grids"

    alt Mandatory Buyback Triggered
        BuyLogic->>BuyLogic: "**Step 1.2: Execute Mandatory Buyback Process**<br>(See 9.2 Detail)"
        BuyLogic->>BuyLogic: "Step 2: Generate new limit buy orders<br>(for all pending_buy grids)"
        BuyLogic->>SellLogic: "Continue (non-blocking)"
        
    else Normal Buyback Triggered
        BuyLogic->>BuyLogic: "**Step 1.2: Execute Normal Buyback Process**<br>(See 9.3 Detail)"
        BuyLogic->>BuyLogic: "Step 2: Generate new limit buy orders<br>(for all pending_buy grids)"
        BuyLogic->>SellLogic: "Continue (non-blocking)"

    else No Buyback
        BuyLogic->>BuyLogic: "Step 1.2: Reset forced_buyback_streak = 0"
        BuyLogic->>BuyLogic: "Step 2: Generate new limit buy orders<br>(for all pending_buy grids)"
        BuyLogic->>SellLogic: "Continue"
    end

    SellLogic->>SellLogic: "Step 3.1: Cancel any remaining old sell orders<br>(redundant safety check)"
    SellLogic->>SellLogic: "Step 3.2: Generate new limit sell orders"
    SellLogic->>Cleanup: 

    Cleanup->>Cleanup: "Step 4: Clean up expired records<br>('filled' / 'force_closed' status)"
    Cleanup->>BaseUpdate: 

    BaseUpdate->>BaseUpdate: "**5.1: Execute Base Price Bidirectional Adjustment**<br>(See 9.1 Detail)"
    BaseUpdate->>Next: "Complete"

    Note over Next,BaseUpdate: "─── Intraday Trading (async, via notify_order) ───"

    alt Sell order filled
        Next->>Next: "Remove from active_sell_orders<br>Add new 'pending_buy' record to sold_grids"
    else Buy order filled
        Next->>Next: "Remove from active_buy_orders<br>Update grid status to 'filled'"
    end
```

### 9.1 Base Price Bidirectional Adjustment Mechanism Detail

This diagram details the complex logic of how the base price is dynamically adjusted both upward and downward, which is simplified in the core flow diagram above.

```mermaid
flowchart TD
    subgraph "Base Price Upshift Mechanism (Step 1.2)"
        direction LR
        UpStart["Execute at Daily Market Open"] --> CheckForcedBuyback{"Is Forced Buyback Triggered?"}
        CheckForcedBuyback -- Yes --> UpAction["Upshift Base Price<br>Base = Close[-1]<br>(Yesterday's Close)"]
        UpAction --> CancelSells["Cancel All Unfilled Limit Sell Orders"]
        CancelSells --> UpEnd["Process Ended, Prepare New Sell Orders"]
    end

    subgraph "Base Price Downshift Mechanism (Step 5)"
        direction TB
        DownStart["Execute at Daily Market Close"] --> Calc["Calculate Deviation<br>decline = (Base - Close[0]) / Base"]
        
        Calc --> CheckCondition{"Determine Market State"}
        
        CheckCondition -- "Plunge (decline greater than 5 percent)" --> Track1_Start
        
        subgraph "Track 1: Plunge Response"
            Track1_Start["Trigger Track 1"] --> Track1_Action["Immediate Base Price Downshift<br>Base = Close[0]"]
            Track1_Action --> Track1_Reset["Reset Counter days = 0"]
            Track1_Reset --> DownEnd
        end
        
        CheckCondition -- "Gradual Decline (between 2 percent and 5 percent)" --> Track2_Start
        
        subgraph "Track 2: Time Decay Response"
            Track2_Start["Trigger Track 2"] --> Inc["Days Counter Increment<br>days += 1"]
            Inc --> CheckDays{"Check if days count reaches threshold<br>Check if days greater than or equal to 5<br>(time_decay_days)"}
            CheckDays -- "Yes" --> Decay["Forced Base Price Adjustment<br>Base = Base * (1 - 0.5 percent)<br>(time_decay_ratio)"]
            Decay --> Track2_Reset["Reset Counter days = 0"]
            Track2_Reset --> DownEnd
            CheckDays -- "No" --> Wait["Wait for Next Day Observation"]
        end

        CheckCondition -- "Rangebound/Rebound (decline less than 2 percent)" --> ResetCounter["Reset Counter days = 0"]
        ResetCounter --> NoChange["Base Price Remains Unchanged"]
    end
    
    DownEnd["Process Terminated"]
```

***


### 9.2 Mandatory Buyback Process Detail

This diagram details the handling process of the mandatory buyback signal, which is triggered when a grid fails to fill within the holding period.

```mermaid
flowchart TD
    Start["Start Mandatory Buyback"] --> SubmitOrder["Submit MARKET ORDER<br>to buy back shares"]
    
    SubmitOrder --> CancelSells["Cancel all unfilled<br>limit sell orders"]
    
    CancelSells --> Upshift["Execute Base Price UPSHIFT<br>(See 9.1 Detail)"]
    
    Upshift --> MarkGrid["Mark grid as 'force_closed'"]
    
    MarkGrid --> UpdateStreak["Update forced_buyback_streak counter<br>streak += 1"]
    
    UpdateStreak --> CheckStreak{"Check if streak >=<br>max_forced_buyback_days?"}
    
    CheckStreak -- Yes --> LogWarning["Output WARNING log<br>for consecutive force closes"]
    
    CheckStreak -- No --> End["End Process"]
    
    LogWarning --> End

```

***

### 9.3 Normal Buyback Process Detail

This diagram details the handling process of the normal buyback signal, which is triggered when a limit buy order is successfully filled by the market.

```mermaid
flowchart TD
    Start["Start Normal Buyback"] --> ConfirmFill["Confirm limit buy order is filled"]
    
    ConfirmFill --> UpdateStatus["Update grid status to 'filled'"]
    
    UpdateStatus --> RecordProfit["Record trading profit for this grid"]
    
    RecordProfit --> End["End Process"]
```

***

## 10. Exception Handling and Boundary Cases

This section focuses on describing the strategy's handling logic under extreme or abnormal market conditions, especially the risk control strategy for consecutive base price downshifts.

### 10.1 Risk Control Strategy for Consecutive Base Price Downshifts

- **Risk Description**:
  - When the target is in a unilateral downtrend, the base price will shift down daily (based on the closing price), causing the daily sell grid price to also decrease.
  - The strategy will place sell orders at increasingly lower prices. If the market continues to fall without rebounding, these sell orders will continue to be executed, causing the strategy to establish a large number of short positions at low levels.
  - Once the market rebounds at low levels, these short positions will face huge unrealized loss risks.
- **Risk Control Strategy**:
  - **Core Idea**: By monitoring the frequency and magnitude of base price downshifts, proactively intervene in extreme downtrends to control risks.
  - **Specific Measures**:
    1. **Add Consecutive Downshift Counter**:
       - In the `self.base_price` update logic, add a counter `self.consecutive_down_days`.
       - If the base price shifts down today, the counter `+1`; otherwise, reset to zero.
    2. **Set Threshold to Trigger Risk Control**:
       - **Pause Selling**: If `self.consecutive_down_days` exceeds `max_down_days_to_sell` (e.g., 3 days), pause the generation of new sell orders. At this point, the strategy only handles buyback orders and no longer opens new short positions.
       - **Accelerate Buyback**: Consider increasing the density of buyback grids during the consecutive downshift period of the base price (i.e., reduce `grid_down_ratio`) to lock in short profits faster, even if the price only fluctuates slightly, it can close the position.
    3. **Code Implementation Location**:
       - The counter update logic should be implemented in Step 5 (Base Price Dynamic Downshift) of Chapter 7.
       - The risk control check should be performed at the beginning of Step 3 (Selling Logic) of Chapter 7.

### 10.2 Handling of Other Boundary Cases

- **Limit Up / Limit Down**:
  - When the target hits the limit up, sell orders may not be filled.
  - When the target hits the limit down, buy orders (including market orders for mandatory buyback) may not be filled.
  - The strategy needs to handle order rejection or failure scenarios, for example, if mandatory buyback fails, it may need to be retried on the next trading day, or increase slippage tolerance.
- **Extreme Lack of Liquidity**:
  - In extreme market conditions, even large-cap blue-chip stocks may experience liquidity issues.
  - The strategy should consider market depth when forcibly buying back, potentially splitting a large order into multiple small orders for batch execution.
- **Holidays / Trading Suspension**:
  - Encountering holidays or trading suspensions, the strategy should be paused and reinitialize the base price and order queue upon resumption of trading.

***

## 11. Core Parameters and Risk Control

### 11.1 Core Parameter Definition

To clearly show the key parameters affecting strategy performance, the following table details them:

| Parameter Name                                  | Variable Name             | Type  | Default Value | Description and Impact                                                                                                                                                                                                                                                                                                                                                  |
| :---------------------------------------------- | :------------------------ | :---- | :------------ | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Initial Position Ratio**                      | `initial_position_ratio`  | float | 0.4 (40%)     | **Definition**: The ratio of funds used for grid trading to total funds. **Impact**: **Too high (>60%)** has high capital efficiency but weak risk resistance; **Too low (<20%)** is very safe but has no obvious returns. **Suggestion**: Conservative 30-40%, Aggressive 40-50%.                                                                                      |
| **Grid Upward Spacing**                         | `grid_up_ratio`           | float | 0.03 (3%)     | **Definition**: The price spacing between sell grids. **Impact**: The smaller the spacing, the denser the order placement, the stronger the ability to capture volatility, but the greater the risk of rapid full position on a unilateral uptrend.                                                                                                                     |
| **Grid Buyback Price Difference**               | `grid_down_ratio`         | float | 0.05 (5%)     | **Definition**: The decline amplitude of the buyback price relative to the sell price. **Impact**: The larger the amplitude, the higher the single profit, but the more difficult the buyback transaction, the longer the holding period, and the greater the risk of facing a rebound.                                                                                 |
| **Parallel Order Quantity**                     | `num_grids`               | int   | 5             | **Definition**: The number of sell orders placed simultaneously per day. **Impact**: The larger the quantity, the stronger the ability to capture the rally on a single day, but the more capital it occupies, and the higher the risk that all orders are triggered (full position reduction).                                                                         |
| **Mandatory Buyback Days**                      | `mandatory_buyback_days`  | int   | 30            | **Definition**: The maximum number of trading days that a sell grid (sell order) can hold after being executed. **Impact**: **The only safety fuse**. The shorter the days, the smaller the risk exposure, but frequent mandatory buybacks (stop loss) may be triggered in a weak oscillating market.                                                                   |
| **Continuous Forced Buyback Warning Threshold** | `max_forced_buyback_days` | int   | 3             | **Definition**: The number of consecutive days that the mandatory buyback rule is triggered before a warning log is output. **Impact**: This is a soft warning mechanism that alerts the user to a potential trend reversal (e.g., sustained uptrend) without automatically changing the strategy's behavior.                                                           |
| **Track 1: Plunge Trigger Threshold** | `base_shift_threshold` | float | 0.05 (5%) | **Definition**: The percentage drop (relative to the base price) that triggers the **Track 1 (Plunge)** mechanism, causing an immediate base price downshift. **Impact**: Sets the threshold for identifying a "sharp drop". A lower value (e.g., 3%) means more sensitive, while a higher value (e.g., 8%) means more conservative. This value must be higher than the Track 2 entry threshold to ensure the two mechanisms are completely isolated. |
| **Time Decay Trigger Days**                    | `time_decay_days`         | int   | 5             | **Definition**: The number of consecutive days that the closing price is below the base price before the time decay mechanism is activated. **Impact**: It acts as a filter for gradual declines (阴跌), ensuring the base price slowly follows the market without being triggered by normal day-to-day fluctuations. |
| **Time Decay Ratio**                           | `time_decay_ratio`        | float | 0.005 (0.5%)  | **Definition**: The percentage by which the base price is forcibly reduced each time the time decay mechanism triggers. **Impact**: Controls the speed of base price adjustment during gradual declines. A smaller value means slower adaptation, while a larger value means faster adaptation. |
| **Consecutive Downshift Day Limit**             | `max_down_days_to_sell`   | int   | 3             | **Definition**: The maximum number of consecutive days the base price has shifted down before the strategy pauses generating new sell orders. **Impact**: This is a risk control mechanism for extreme downtrends. It prevents the strategy from continuously opening new short positions (sell orders) in a free-falling market, which could lead to excessive losses. |

### 11.2 Order Type Specification

To balance profitability and risk control, the strategy adopts different order types in different scenarios:

- **Normal Trading Scenarios**
  - **Goal**: Precise pricing, cost control.
  - **Sell Orders**: **Limit Order**. Passive sell orders are placed at preset grid prices to ensure execution at the target price or higher.
  - **Buy Orders**: **Limit Order**. Passive buy orders are placed at the corresponding target buyback prices to ensure execution at the target price or lower, locking in profits.
- **Forced Trading Scenarios**
  - **Goal**: Immediate execution, risk removal.
  - **Mandatory Buyback Orders**: **Market Order**. When a timeout or risk warning is triggered, to ensure immediate position closing, the market price is unconditionally accepted to control further losses.

### 11.3 Risk Control Mechanism Summary

- **Core Risk**: The biggest risk of this strategy is a **unilateral uptrend**. After all sell orders are filled, if the price continues to not fall back, it will lead to capital exhaustion, eventually triggering forced liquidation or a liquidity crisis.
- **Control Measures**:
  1. **Initial Position Control**: Limit total risk exposure through `initial_position_ratio`.
  2. **Mandatory Buyback Mechanism**: Use `mandatory_buyback_days` as the last line of defense to lock losses within an acceptable range. Market orders are used for mandatory buybacks to ensure quick execution.
  3. **Grid Parameter Configuration**: Reasonably configure `grid_up_ratio` and `num_grids` to avoid excessive order placement leading to rapid full positions.
  4. **Liquidity Crisis Response Mechanism**:
     - **Real-time Liquidity Monitoring**: Continuously monitor the bid/ask spread and order book depth. If the spread exceeds a certain threshold (e.g., `max_spread_ratio`) or the volume is critically low, the strategy should automatically pause trading.
     - **Forced Liquidation via Market Orders**: When a liquidity crisis is triggered (e.g., limit down, extreme spread), the strategy should prioritize exiting positions. It must use market orders to ensure execution, accepting high slippage as a cost of risk control.
     - **Sliced Execution**: For large positions, split forced liquidation orders into multiple smaller market orders to minimize market impact and improve the probability of filling at a reasonable price.

***

## 12. Strategy Potential Risks and Mechanism Vulnerabilities

This section is dedicated to recording potential mechanism vulnerabilities found during the strategy design process. These vulnerabilities may affect the actual operation performance of the strategy and require focused attention during the code implementation phase.

### 12.1 Intraday Dynamic Order Placement Missing Risk

- **Risk Description**:
  - In the current design, the `next()` function is responsible for uniformly placing buy orders for all grids with `pending_buy` status daily. The `notify_order` function only updates the status to `pending_buy` when a sell order is executed.
  - **Vulnerability Point**: If a sell order is executed intraday, its status becomes `pending_buy`, but its buy order must wait until the next `next()` function runs to be generated. This means that during the remaining trading time after execution, the strategy is in a "naked" state (having reduced a position without a corresponding buy order for risk hedging).
- **Risk Assessment**:
  - **High Risk**: In extreme market conditions, violent intraday price fluctuations may lead to margin shortages, increasing the risk of being forced to liquidate.

### 12.2 Logic Conflict Between Base Price Update and Current Day's Sell Orders

- **Risk Description**:
  - There is a logical conflict between the update timing of `base_price` and the placement of sell orders on the same day. If `base_price` is updated before placing sell orders, it could lead to "sell order target price being lower than the price that has already occurred", creating a contradictory trading logic.
- **Risk Assessment**:
  - **Medium Risk**: This design conflict could lead to illogical sell order triggers, potentially locking in profits at suboptimal prices or increasing strategy complexity.

### 12.3 Base Price One-Way Trap Risk (Defect 3)

- **Status**: Resolved
- **Solution**: Introduced a bidirectional base price update mechanism (See Section 7, Step 1 and Step 5).
  - **Upshift (Step 1)**: When a mandatory buyback is triggered (indicating a failed downtrend), the `base_price` is immediately raised to the previous day's closing price (`self.data.close[-1]`), and all old sell orders are canceled. **\[Design Choice]** Using yesterday's close as the new anchor provides a stable and deterministic reference point, avoiding the uncertainty of the current day's opening price, to reposition the strategy for a potential uptrend.
  - **Downshift (Step 5)**: The original logic of dynamically shifting down the `base_price` when the market drops is preserved.
- **Vulnerability Point Mitigated**:
  - **(1) Low-Level Full Position Dump**: By canceling old sell orders and generating new ones based on the updated (higher) `base_price`, the strategy is protected from immediately selling at low prices in a reversal.
  - **(2) Guaranteed Losses from Forced Buyback**: The upward adjustment of `base_price` ensures that new sell orders are placed at higher levels, providing an opportunity to offset the forced buyback losses through subsequent higher sales.

