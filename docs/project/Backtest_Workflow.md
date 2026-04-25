# Backtest Workflow Documentation

## Overview

This document describes the complete backtesting workflow in the Campsis quantitative trading system, from data preparation to performance analysis.

## Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Backtest Workflow                              │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐
  │ 1. Data Prep │
  └──────┬───────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  Data Layer (DataNest)                                                      │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────┐                   │
│  │ stock_daily │───▶│ DailyDataMgr │───▶│ Backtrader  │                   │
│  │ (MySQL)     │    │              │    │ DataAdapter │                   │
│  └─────────────┘    └──────────────┘    └──────┬──────┘                   │
└────────────────────────────────────────────────┼───────────────────────────┘
                                                 │
                                                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  2. Strategy Configuration                                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ StrategyRegistry                                                     │  │
│  │ - factor_strategy (registered)                                       │  │
│  │ - Other strategies...                                                │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ ParallelBacktestRunner                                               │  │
│  │ - Multi-strategy parallel execution                                  │  │
│  │ - Performance metrics collection                                     │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────┬────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  3. Backtrader Engine                                                       │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│  │ Cerebro      │───▶│ Strategy     │───▶│ Broker       │                │
│  │ (Backtest    │    │ (Strategy    │    │ (Simulated   │                │
│  │  Brain)      │    │  Instance)   │    │  Broker)     │                │
│  └──────────────┘    └──────────────┘    └──────────────┘                │
│         │                    │                    │                        │
│         ▼                    ▼                    ▼                        │
│  ┌──────────────────────────────────────────────────────────────────────┐ │
│  │ Backtest Loop (execute next() for each bar)                          │ │
│  │ 1. Calculate factor scores                                           │ │
│  │ 2. Generate buy/sell signals                                          │ │
│  │ 3. Execute trading orders                                            │ │
│  │ 4. Update positions and cash                                          │ │
│  └──────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────┬────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  4. Performance Analysis                                                     │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ PerformanceAnalyzer                                                  │  │
│  │                                                                     │  │
│  │ Core Metrics:                                                        │  │
│  │ - Annual Return (annual_return)                                      │  │
│  │ - Sharpe Ratio (sharpe_ratio)                                        │  │
│  │ - Maximum Drawdown (max_drawdown)                                   │  │
│  │ - Calmar Ratio (calmar_ratio)                                       │  │
│  │ - Win Rate (win_rate)                                               │  │
│  │ - Profit Factor (profit_factor)                                     │  │
│  │                                                                     │  │
│  │ Functions:                                                           │  │
│  │ - Single strategy analysis                                           │  │
│  │ - Multi-strategy comparison                                          │  │
│  │ - Ranking evaluation                                                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────┬────────────────────────────────────┘
                                        │
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  5. Result Output                                                           │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ - Performance metrics report                                         │  │
│  │ - Strategy comparison matrix                                         │  │
│  │ - Trading record details                                             │  │
│  │ - Best strategy recommendation                                      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Detailed Steps

### Step 1: Data Preparation

1. Load historical price data from MySQL database
2. Convert to Backtrader format via `BacktraderDataAdapter`
3. Cache data to avoid repeated loading

**Key Components:**
- `DailyDataManager`: Manages daily data access
- `BacktraderDataAdapter`: Converts DataNest format to Backtrader format
- `DataCache`: Caches data for reuse

### Step 2: Strategy Configuration

1. Strategy registry manages all available strategies
2. Configure strategy parameters (weights, thresholds, etc.)
3. Create strategy instances and inject data providers

**Key Components:**
- `StrategyRegistry`: Manages strategy registration with decorator pattern
- `@register_strategy`: Decorator for automatic strategy registration
- Strategy parameters: `trend_weight`, `momentum_weight`, `quality_weight`, `timing_weight`

### Step 3: Backtest Execution

1. **Initialization**: Set initial cash, commissions, etc.
2. **Backtest Loop**: Execute `next()` method for each bar
3. **Signal Generation**: Determine buy/sell based on factor scores
4. **Order Execution**: Simulated broker executes trades
5. **State Update**: Update positions, cash, trading records

**Backtrader Core Components:**
- `Cerebro`: Main backtest engine coordinator
- `Strategy`: Strategy instance with `next()` method
- `Broker`: Simulated broker for order execution
- `Data Feed`: Historical price data

### Step 4: Performance Analysis

1. Collect trading records from backtest
2. Calculate performance metrics
3. Perform multi-strategy comparison analysis
4. Generate comprehensive report

**Key Metrics:**
| Metric | Description |
|--------|-------------|
| Annual Return | Annualized return rate |
| Sharpe Ratio | Risk-adjusted return |
| Max Drawdown | Maximum peak-to-trough decline |
| Calmar Ratio | Annual return / Max drawdown |
| Win Rate | Percentage of profitable trades |
| Profit Factor | Gross profit / Gross loss |

### Step 5: Result Output

1. Output performance metrics
2. Output strategy rankings
3. Provide decision recommendations

## Key Code Calls

```python
# 1. Create backtest runner
runner = ParallelBacktestRunner(db_conn)

# 2. Configure backtest tasks
configs = [
    {
        "strategy": {
            "name": "factor_strategy",
            "params": {
                "trend_weight": 0.25,
                "momentum_weight": 0.25,
                "quality_weight": 0.25,
                "timing_weight": 0.25,
                "buy_threshold": 0.6,
                "sell_threshold": 0.4
            }
        },
        "data": {
            "stock_code": "000001.SZ",
            "start_date": "2020-01-01",
            "end_date": "2025-12-31"
        },
        "initial_cash": 1000000
    }
]

# 3. Execute backtest
results = runner.run_batch(configs)

# 4. Analyze results
analyzer = PerformanceAnalyzer()
analysis = analyzer.compare(results)
```

## Strategy Decision Core

The core decision logic is implemented in `FactorStrategy.next()`:

```python
def next(self):
    # 1. Get current date and stock code
    current_date = self.datas[0].datetime.date(0).isoformat()
    stock_code = self.datas[0]._name

    # 2. Get price data
    price_data = self.data_provider.get_price_data(
        stock_code,
        start_date=self.datas[0].datetime.date(-60).isoformat(),
        end_date=current_date
    )

    # 3. Calculate four factor scores
    trend_score = self.factor_calculator.calculate_trend_score(stock_code, price_data)
    momentum_score = self.factor_calculator.calculate_momentum_score(stock_code, price_data)
    quality_score = self.factor_calculator.calculate_quality_score(stock_code, "2020-01-01", current_date)
    timing_score = self.factor_calculator.calculate_timing_score(stock_code, price_data)

    # 4. Calculate weighted total score
    total_score = (
        trend_score * self.trend_weight +
        momentum_score * self.momentum_weight +
        quality_score * self.quality_weight +
        timing_score * self.timing_weight
    )

    # 5. Make decisions based on score and position
    current_position = self.getposition(self.datas[0]).size

    if total_score >= self.buy_threshold and current_position == 0:
        # Buy signal
        size = self.get_position_size(self.datas[0].close[0])
        self.buy(size=size)
        self.log(f"BUY SIGNAL: Score={total_score:.2f}")

    elif total_score <= self.sell_threshold and current_position > 0:
        # Sell signal
        self.sell(size=abs(current_position))
        self.log(f"SELL SIGNAL: Score={total_score:.2f}")
```

## Multi-Strategy Parallel Backtest Advantages

| Advantage | Description |
|-----------|-------------|
| Efficiency | Test multiple strategies simultaneously, saving time |
| Comparison | Unified performance framework for strategy comparison |
| Optimization | Intelligent task scheduling, full hardware utilization |
| Comprehensive | Multi-dimensional metrics, comprehensive strategy evaluation |

## Architecture Summary

| Layer | Components | Responsibility |
|-------|------------|----------------|
| Data Layer | `DailyDataManager`, `BacktraderDataAdapter`, `DataCache` | Data access and format conversion |
| Strategy Layer | `StrategyRegistry`, `@register_strategy`, `BaseStrategy` | Strategy management and framework |
| Strategy Impl | `FactorStrategy` | Specific trading decision logic |
| Execution Layer | `ParallelBacktestRunner`, `Cerebro` | Backtest execution and coordination |
| Analysis Layer | `PerformanceAnalyzer` | Performance calculation and comparison |

## File Structure

```
CookingEngine/
├── Backtest/
│   ├── data_adapter.py       # Data format conversion
│   └── parallel_runner.py     # Parallel backtest execution
├── Strategies/
│   ├── registry.py           # Strategy registration
│   ├── base/
│   │   └── base_strategy.py   # Strategy base class
│   └── factors/
│       └── factor_strategy.py # Factor strategy implementation
└── Analysis/
    └── performance_analyzer.py # Performance analysis
```

## Conclusion

The backtest workflow is a complete pipeline from data preparation to result output. Through standardized module design, it achieves rapid strategy validation and optimization. The core advantages are:

1. **Separation of Concerns**: Strategy framework and business logic are separated
2. **Code Reuse**: Different strategies share supporting functions
3. **Easy Extension**: New strategy variants can be easily created
4. **Easy Testing**: Core logic can be tested independently
