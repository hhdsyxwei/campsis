# Next Day Bullish Strategy Implementation Plan

## Overview

This plan aims to convert the 4 next-day bullish strategies defined in `next_day_bullish_strategy.py` into backtestable Backtrader strategies for win rate comparison analysis.

## Background

### Current Strategy Module

- **Location**: `CookingEngine/next_day_bullish_strategy.py`
- **Status**: Contains 4 screening functions for stock pool filtering only
- **Issue**: Not implemented as Backtrader strategies, cannot perform quantitative backtesting or win rate analysis

### Four Core Strategies

1. **Box Breakout Strategy** (`check_box_breakout`): Identifies stocks breaking out from consolidation with volume surge
2. **Bottom Reversal Strategy** (`check_bottom_reverse`): Identifies oversold stocks with bounce-back signals
3. **Trend Pullback Strategy** (`check_trend_pullback`): Identifies stocks pulling back to key moving averages in uptrend
4. **Multi-Indicator Resonance Strategy** (`check_multi_indicator_resonance`): Multiple technical indicators generate synchronized buy signals

### Existing Backtesting Infrastructure

- `BaseStrategy`: Backtrader base strategy class
- `PerformanceAnalyzer`: Performance analyzer with win rate calculation
- `ParallelBacktestRunner`: Parallel backtest runner
- `StrategyRegistry`: Strategy registration mechanism

## Implementation Steps

### Step 1: Create Backtrader Implementations for 4 Strategies

**Goal**: Convert screening functions into Backtrader strategies inheriting from `BaseStrategy`

**Output Files**:
- `CookingEngine/Strategies/bullish/box_breakout_strategy.py`
- `CookingEngine/Strategies/bullish/bottom_reverse_strategy.py`
- `CookingEngine/Strategies/bullish/trend_pullback_strategy.py`
- `CookingEngine/Strategies/bullish/multi_indicator_resonance_strategy.py`

**Each Strategy Must Implement**:
1. **Signal Detection**: Convert screening conditions to buy signal logic
2. **Next-Day Buy**: Execute buy at next-day open price after signal
3. **Exit Logic**: Define stop loss / take profit / holding period rules
4. **Position Management**: Single or multiple simultaneous positions

**Strategy Implementation Template**:
```python
@register_strategy("box_breakout")
class BoxBreakoutStrategy(BaseStrategy):
    def __init__(self, ...):
        super().__init__(...)
        # Initialize technical indicators

    def next(self):
        # 1. Check if buy signal is triggered
        # 2. Execute buy (next-day open price)
        # 3. Execute sell (stop loss / take profit / holding period)
```

### Step 2: Create Backtest Comparison Script

**Goal**: Run 4 strategies in batch and compare performance

**Output File**: `tools/compare_bullish_strategies.py`

**Script Features**:
1. Configure backtest parameters (stock pool, time range, initial capital)
2. Run 4 strategies in batch
3. Collect backtest results
4. Output comparison analysis report

**Recommended Backtest Configuration**:
| Parameter | Value | Description |
|-----------|-------|-------------|
| Stock Pool | CSI 300 Components | High liquidity, quality data |
| Time Range | 2020-01-01 to 2024-12-31 | 5 years of data |
| Initial Capital | 1,000,000 | 1M CNY |
| Commission | 0.03% | Per trade |
| Max Positions | 10 | Diversification |

### Step 3: Run Backtest and Analyze Results

**Goal**: Obtain win rate and other performance metrics for each strategy

**Analysis Metrics**:
| Metric | Description |
|--------|-------------|
| Win Rate | Profitable trades / Total trades |
| Annual Return | Average yearly return |
| Sharpe Ratio | Risk-adjusted return |
| Max Drawdown | Maximum account decline |
| Profit Factor | Gross profit / Gross loss |
| Trade Count | Sample size for statistics |

**Output Report**: Generate `bullish_strategy_comparison.xlsx` with detailed comparison data

## Pending Confirmation

The following parameters need confirmation before implementation:

1. **Backtest Scope**
   - [ ] Stock Pool: CSI 300 / Full Market / Custom
   - [ ] Time Range: Start and End Dates

2. **Exit Logic**
   - [ ] Fixed Holding Period (sell after N days)
   - [ ] Target Return (take profit at X%)
   - [ ] Stop Loss (cut loss at X%)
   - [ ] Trailing Stop (sell when price drops below moving average)

3. **Position Management**
   - [ ] Single Position / Multiple Positions
   - [ ] Maximum Position Count

## Risk Disclaimer

1. **Overfitting**: Strategy parameters may be over-optimized for historical data
2. **Market Regime Change**: Past performance does not guarantee future returns
3. **Slippage**: Backtest does not account for actual trading slippage
4. **Liquidity**: Large capital may cause impact costs

## Expected Deliverables

After completing this plan:

1. 4 independent Backtrader strategies
2. Win rate comparison analysis report
3. Strategy optimization recommendations

## Implementation Priority

1. **High Priority**: Create Backtrader implementations for 4 strategies
2. **Medium Priority**: Create backtest comparison script
3. **Low Priority**: Run backtest and generate analysis report
