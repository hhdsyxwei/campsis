# Bottom Reverse Strategy Comparison

## Overview

This document compares the `check_bottom_reverse` function in `next_day_bullish_strategy.py` with the `BottomReverseStrategy` class in `bottom_reverse_strategy.py`.

## Core Conclusion

The `BottomReverseStrategy` class is a **Backtrader strategy implementation** of the `check_bottom_reverse` function. Both share **identical buy signal logic**, but `BottomReverseStrategy` adds complete **trade execution and risk management mechanisms**.

---

## Comparison Table

| Dimension | `check_bottom_reverse` (Filter) | `BottomReverseStrategy` (Strategy) |
|-----------|---------------------------------|------------------------------------|
| **Type** | Pure function, returns True/False | Backtrader strategy class |
| **Input** | DataFrame + stock code | Real-time price feed |
| **Output** | Boolean (meets criteria or not) | Generates trading orders |
| **Signal Detection** | 6 identical conditions | 6 identical conditions |
| **Buy Execution** | None | Automatic position sizing and ordering |
| **Sell Mechanism** | None | Triple exit: holding period / stop loss / take profit |
| **Position Management** | None | Tracks entry price, date, and position size |
| **Execution Environment** | Batch stock screening | Real-time backtesting/live trading |

---

## Signal Detection Conditions (Identical)

Both implementations use exactly the same 6 conditions:

1. **Cumulative Decline >= 50%**: Stock must have fallen at least 50% from recent high
2. **Base Building Fluctuation <= 20%**: Consolidation period with limited volatility
3. **Daily Rise >= 3%**: Strong upward movement on reversal day
4. **Volume >= 2x MA5**: Volume surge confirming reversal strength
5. **RSI Recovery**: RSI was <= 20 (oversold) 5 days ago and >= 50 now
6. **MACD & KDJ Golden Cross**: Both indicators showing bullish crossover

---

## Workflow Comparison

### check_bottom_reverse (Screening Mode)

```
Input DataFrame
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Check 6 conditions (return False if any fails)  │
└──────────────────────────────────────────────────┘
    │
    ▼
Return True/False (for stock pool screening only)
```

### BottomReverseStrategy (Trading Mode)

```
Real-time price feed (Backtrader Cerebro)
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Pre-check: Pending order + data sufficiency     │
└──────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Check 6 conditions (identical logic)            │
└──────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Decision Branch:                                │
│   - No position → Calculate size → Buy order    │
│   - Has position → Check exit conditions        │
└──────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────┐
│ Exit Conditions:                                │
│   - Holding period >= 5 days → Sell            │
│   - Loss >= 5% → Stop loss                      │
│   - Profit >= 10% → Take profit                │
└──────────────────────────────────────────────────┘
    │
    ▼
Execute order → Update position → Record trade
```

---

## Parameter Comparison

| Parameter | `check_bottom_reverse` (Global) | `BottomReverseStrategy` (Class) |
|-----------|---------------------------------|----------------------------------|
| Fall days | `REVERSE_FALL_DAYS = 60` | `reverse_fall_days = 60` |
| Max fall rate | `REVERSE_MAX_FALL_RATE = 0.5` | `reverse_max_fall_rate = 0.5` |
| Build days | `REVERSE_BUILD_DAYS = 20` | `reverse_build_days = 20` |
| Rise threshold | `REVERSE_RISE_THRESHOLD = 0.03` | `reverse_rise_threshold = 0.03` |
| Volume multiple | `REVERSE_VOLUME_MULTIPLE = 2` | `reverse_volume_multiple = 2.0` |
| RSI oversold | `REVERSE_RSI_OVERSOLD = 20` | `reverse_rsi_oversold = 20` |
| **Holding days** | **N/A** | `holding_days = 5` |
| **Stop loss ratio** | **N/A** | `stop_loss_ratio = 0.05` |
| **Take profit ratio** | **N/A** | `take_profit_ratio = 0.10` |

---

## Application Scenarios

| Scenario | Recommended Module | Reason |
|----------|-------------------|--------|
| **Stock Pool Screening** | `check_bottom_reverse` | Batch screening, fast filtering |
| **Historical Backtesting** | `BottomReverseStrategy` | Complete trading logic |
| **Live Trading** | `BottomReverseStrategy` | Real-time decision making |
| **Parameter Optimization** | `BottomReverseStrategy` | Configurable parameters |

---

## Key Differences Summary

| Aspect | `check_bottom_reverse` | `BottomReverseStrategy` |
|--------|-----------------------|------------------------|
| **Purpose** | Stock screening | Trade execution |
| **Functionality** | Signal detection only | Signal + execution + risk management |
| **Output** | True/False | Trading orders |
| **Extensibility** | Fixed parameters | Configurable parameters |
| **Use Case** | Batch screening | Backtesting / Live trading |

---

## File References

- `next_day_bullish_strategy.py`: [check_bottom_reverse function](file:///c:/Users/Vulcan/Documents/c/trae-camp3/CookingEngine/next_day_bullish_strategy.py#L178-L228)
- `bottom_reverse_strategy.py`: [BottomReverseStrategy class](file:///c:/Users/Vulcan/Documents/c/trae-camp3/CookingEngine/Strategies/obs/bottom_reverse_strategy.py)

---

## Conclusion

The `BottomReverseStrategy` class builds upon the `check_bottom_reverse` function by adding:

1. **Order Management**: Buy/sell order creation and tracking
2. **Position Sizing**: Risk-based position calculation
3. **Triple Exit Mechanism**: Holding period, stop loss, and take profit
4. **State Tracking**: Entry price, entry date, and current position