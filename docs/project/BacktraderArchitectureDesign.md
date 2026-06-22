# Backtrader Integration Architecture Design Summary

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     CookingEngine                                  │
├─────────────────────────────────────────────────────────────────┤
│  Data Layer (Existing)                                              │
│  ┌─────────────────┐                                              │
│  │  DataNest/MySQL │  ← Stock daily, Financial data               │
│  └────────┬────────┘                                              │
│           │                                                         │
├───────────┼─────────────────────────────────────────────────────┤
│           ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Backtest Framework Layer                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │  │
│  │  │Data Adapter  │  │Backtest Runner│  │   Optimizer  │      │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │  │
│  └─────────────────────────────────────────────────────────────┘  │
│           │                                                         │
├───────────┼─────────────────────────────────────────────────────┤
│           ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Strategy Management Layer                        │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │  │
│  │  │   Registry   │  │    Config    │  │   Factory    │      │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │  │
│  └─────────────────────────────────────────────────────────────┘  │
│           │                                                         │
├───────────┼─────────────────────────────────────────────────────┤
│           ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Strategy Implementation Layer                    │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │  │
│  │  │BaseStrategy │  │FactorStrategy│  │MomentumStrat │      │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │  │
│  └─────────────────────────────────────────────────────────────┘  │
│           │                                                         │
├───────────┼─────────────────────────────────────────────────────┤
│           ▼                                                         │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │              Performance Analysis Layer                       │  │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │  │
│  │  │  Analyzer   │  │  Comparator  │  │  ReportGen   │      │  │
│  │  └──────────────┘  └──────────────┘  └──────────────┘      │  │
│  └─────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Core Design Principles

| Principle | Description |
|-----------|-------------|
| **Strategy Isolation** | Each strategy is an independent class, inheriting from base |
| **Unified Interface** | All strategies follow the same interface contract |
| **Configuration Driven** | Strategy behavior controlled by external configuration |
| **Data Abstraction** | Data layer abstracted through adapter |
| **Parallel Execution** | Support concurrent backtesting out of the box |
| **Result Standardization** | Unified performance metrics and reporting |

---

## 3. Key Modules

### 3.1 Data Adapter Layer

```python
# CookingEngine/Backtest/data_adapter.py

class BacktraderDataAdapter:
    """Data adapter converting DataNest data to Backtrader format"""

    def __init__(self, db_conn):
        self.daily_manager = DailyDataManager(db_conn)
        self.cache = DataCache()

    def get_stock_data(self, stock_code, start_date, end_date):
        """Get single stock data in Backtrader format"""
        # Implementation...

    def get_multiple_stocks(self, stock_codes, start_date, end_date):
        """Get multiple stocks data"""
        # Implementation...
```

**Responsibilities**:
- Convert MySQL data to Backtrader PandasData format
- Handle data caching to avoid repeated queries
- Support multiple stock data retrieval

### 3.2 Strategy Registry

```python
# CookingEngine/Strategies/registry.py

class StrategyRegistry:
    """Central registry for all strategies"""

    def __init__(self):
        self._strategies = {}

    def register(self, name: str, strategy_class):
        """Register a strategy"""
        self._strategies[name] = strategy_class

    def get(self, name: str):
        """Get strategy class by name"""
        return self._strategies.get(name)

    def list_strategies(self):
        """List all registered strategies"""
        return list(self._strategies.keys())

# Global registry instance
strategy_registry = StrategyRegistry()

def register_strategy(name):
    """Decorator for strategy registration"""
    def decorator(cls):
        strategy_registry.register(name, cls)
        return cls
    return decorator
```

**Responsibilities**:
- Central management of all strategy classes
- Strategy discovery and retrieval
- Support dynamic strategy loading

### 3.3 Strategy Base Class

```python
# CookingEngine/Strategies/Base/base_strategy.py

class BaseStrategy(bt.Strategy):
    """Base class for all strategies"""

    def __init__(self):
        self.order = None
        self.data_provider = None
        self.factor_calculator = None

    def log(self, txt, dt=None):
        """Unified logging"""
        dt = dt or self.datas[0].datetime.date(0)
        print(f'[{dt.isoformat()}] {txt}')

    def notify_order(self, order):
        """Order lifecycle management"""
        # Implementation...

    def notify_trade(self, trade):
        """Trade performance tracking"""
        # Implementation...

    def next(self):
        """Strategy logic - to be implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement next()")
```

**Responsibilities**:
- Encapsulate common Backtrader logic
- Provide unified order and trade management
- Define strategy interface contract

### 3.4 Strategy Factory

```python
# CookingEngine/Strategies/factory.py

class StrategyFactory:
    """Factory for creating configured strategy instances"""

    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.data_provider = HarvestDataProvider(db_conn)
        self.factor_calculator = FactorCalculator(self.data_provider)

    def create(self, strategy_name, **params):
        """Create a configured strategy instance"""
        strategy_class = strategy_registry.get(strategy_name)
        if not strategy_class:
            raise ValueError(f"Strategy {strategy_name} not found")

        return strategy_class(
            data_provider=self.data_provider,
            factor_calculator=self.factor_calculator,
            **params
        )
```

**Responsibilities**:
- Create configured strategy instances
- Inject dependencies (data provider, factor calculator)
- Manage strategy lifecycle

### 3.5 Parallel Backtest Runner

```python
# CookingEngine/Backtest/parallel_runner.py

class ParallelBacktestRunner:
    """Parallel backtest execution engine"""

    def __init__(self, db_conn, max_workers=4):
        self.db_conn = db_conn
        self.max_workers = max_workers
        self.data_adapter = BacktraderDataAdapter(db_conn)
        self.strategy_factory = StrategyFactory(db_conn)

    def run_single(self, config):
        """Run single strategy backtest"""
        strategy = self.strategy_factory.create(**config['strategy'])
        data = self.data_adapter.get_stock_data(**config['data'])

        cerebro = bt.Cerebro()
        cerebro.addstrategy(strategy)
        cerebro.adddata(data)
        cerebro.broker.setcash(config.get('initial_cash', 1000000))

        results = cerebro.run()
        return {
            'strategy': config['strategy']['name'],
            'results': results,
            'params': config['strategy']
        }

    def run_batch(self, configs):
        """Run multiple strategies in parallel"""
        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(self.run_single, cfg) for cfg in configs]
            return [f.result() for f in futures]
```

**Responsibilities**:
- Execute backtests in parallel using multiprocessing
- Manage backtest configuration
- Aggregate results from multiple runs

### 3.6 Performance Analyzer

```python
# CookingEngine/Analysis/performance_analyzer.py

class PerformanceAnalyzer:
    """Unified performance analysis"""

    def __init__(self):
        self.broker = None  # Backtrader's built-in analyzer

    def analyze(self, backtest_results):
        """Analyze single strategy performance"""
        return {
            'annual_return': self._calc_annual_return(backtest_results),
            'sharpe_ratio': self._calc_sharpe_ratio(backtest_results),
            'max_drawdown': self._calc_max_drawdown(backtest_results),
            'win_rate': self._calc_win_rate(backtest_results),
            'profit_factor': self._calc_profit_factor(backtest_results)
        }

    def compare(self, results_list):
        """Compare multiple strategies"""
        analyses = [self.analyze(r) for r in results_list]
        return self._generate_comparison_table(analyses)
```

**Responsibilities**:
- Calculate standardized performance metrics
- Compare multiple strategies
- Generate comparison reports

---

## 4. Multi-Strategy Management

### 4.1 Strategy Hierarchy

```
Strategy Hierarchy
├── BaseStrategy (abstract)
│   ├── FactorStrategy
│   │   ├── FourFactorStrategy
│   │   └── ValueFactorStrategy
│   ├── MomentumStrategy
│   │   ├── TrendFollowingStrategy
│   │   └── MeanReversionStrategy
│   └── CompositeStrategy
│       ├── DualThrustStrategy
│       └── MultiFactorStrategy
```

### 4.2 Strategy Configuration

```yaml
# config/strategies.yaml

strategies:
  four_factor:
    class: FactorStrategy
    params:
      trend_weight: 0.25
      momentum_weight: 0.25
      quality_weight: 0.25
      timing_weight: 0.25
      lookback_period: 20
      max_positions: 10

  momentum:
    class: MomentumStrategy
    params:
      lookback_period: 60
      threshold: 0.05
      holding_period: 20

  value:
    class: ValueStrategy
    params:
      pe_max: 15
      pb_max: 1.5
      roe_min: 0.10
```

### 4.3 Strategy Group Management

```python
# CookingEngine/Strategies/group_manager.py

class StrategyGroup:
    """Manage a group of related strategies"""

    def __init__(self, name):
        self.name = name
        self.strategies = []
        self.weights = []

    def add_strategy(self, strategy_name, params, weight=1.0):
        """Add strategy to group"""
        self.strategies.append({
            'name': strategy_name,
            'params': params,
            'weight': weight
        })

    def normalize_weights(self):
        """Normalize strategy weights"""
        total = sum(s['weight'] for s in self.strategies)
        for s in self.strategies:
            s['weight'] /= total
```

---

## 5. Parallel Execution Design

### 5.1 Task Distribution

```
┌─────────────────────────────────────────────┐
│           Parallel Backtest Task             │
├─────────────────────────────────────────────┤
│                                             │
│  Task Queue                                 │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐          │
│  │ T1  │ │ T2  │ │ T3  │ │ T4  │ ...      │
│  └──┬──┘ └──┬──┘ └──┬──┘ └──┬──┘          │
│     │        │        │        │             │
│     ▼        ▼        ▼        ▼             │
│  ┌─────────────────────────────────┐        │
│  │     ProcessPoolExecutor         │        │
│  │     (max_workers: N)            │        │
│  └─────────────────────────────────┘        │
│     │        │        │        │             │
│     ▼        ▼        ▼        ▼             │
│  ┌─────┐ ┌─────┐ ┌─────┐ ┌─────┐          │
│  │ R1  │ │ R2  │ │ R3  │ │ R4  │          │
│  └─────┘ └─────┘ └─────┘ └─────┘          │
│                                             │
└─────────────────────────────────────────────┘
```

### 5.2 Shared Data Cache

```python
# CookingEngine/Backtest/shared_cache.py

class SharedDataCache:
    """Thread-safe shared data cache for parallel execution"""

    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, key):
        """Get data from cache"""
        with self._lock:
            return self._cache.get(key)

    def set(self, key, value):
        """Set data to cache"""
        with self._lock:
            self._cache[key] = value

    def clear(self):
        """Clear all cached data"""
        with self._lock:
            self._cache.clear()
```

### 5.3 Resource Management

| Resource | Management Strategy |
|----------|---------------------|
| **CPU** | ProcessPoolExecutor with max_workers limit |
| **Memory** | Data cache sharing, result streaming |
| **Database** | Connection pooling |
| **Disk** | Result serialization, cleanup |

---

## 6. Performance Analysis Framework

### 6.1 Standard Metrics

| Metric | Formula | Description |
|--------|---------|-------------|
| **Annual Return** | (1 + Total Return)^(1/years) - 1 | Annualized return |
| **Sharpe Ratio** | (Return - Risk Free) / Std Dev | Risk-adjusted return |
| **Max Drawdown** | max(Peak - Trough) / Peak | Maximum loss |
| **Win Rate** | Winning Trades / Total Trades | Trade success rate |
| **Profit Factor** | Gross Profit / Gross Loss | Profitability |
| **Calmar Ratio** | Annual Return / Max Drawdown | Return per unit drawdown |

### 6.2 Strategy Comparison Matrix

```
Strategy      │ Annual │ Sharpe │ Max DD │ Win Rate │ Profit Factor
──────────────┼────────┼────────┼────────┼──────────┼─────────────
Four Factor   │ 12.5%  │ 1.82   │ 15.2%  │ 58%      │ 1.45
Momentum     │ 18.3%  │ 1.52   │ 22.4%  │ 52%      │ 1.32
Value        │  9.7%  │ 2.15   │ 10.8%  │ 65%      │ 1.68
Composite    │ 15.1%  │ 1.95   │ 12.3%  │ 60%      │ 1.55
```

---

## 7. File Structure

```
CookingEngine/
├── Backtest/
│   ├── __init__.py
│   ├── data_adapter.py          # Backtrader data adapter
│   ├── parallel_runner.py       # Parallel backtest runner
│   ├── optimizer.py             # Parameter optimizer
│   └── cache.py                 # Shared data cache
├── Strategies/
│   ├── __init__.py
│   ├── registry.py              # Strategy registry
│   ├── factory.py               # Strategy factory
│   ├── base/
│   │   ├── __init__.py
│   │   └── base_strategy.py     # Base strategy class
│   ├── factors/
│   │   ├── __init__.py
│   │   ├── factor_strategy.py   # Four factor strategy
│   │   └── value_strategy.py    # Value strategy
│   └── momentum/
│       ├── __init__.py
│       └── momentum_strategy.py  # Momentum strategy
├── Analysis/
│   ├── __init__.py
│   ├── performance_analyzer.py  # Performance analysis
│   ├── comparator.py             # Strategy comparison
│   └── report_generator.py       # Report generation
└── Trading/
    ├── __init__.py
    └── broker_adapter.py         # Broker adapter (future)
```

---

## 8. Development Roadmap

### Phase 1: Core Framework (2-3 weeks)

| Module | Deliverable |
|--------|-------------|
| Data Adapter | BacktraderDataAdapter class |
| Strategy Base | BaseStrategy abstract class |
| Registry | StrategyRegistry with decorator |
| Basic Runner | BacktestRunner for single strategy |

### Phase 2: Multi-Strategy Support (1-2 weeks)

| Module | Deliverable |
|--------|-------------|
| Factory | StrategyFactory for instance creation |
| Parallel Runner | ParallelBacktestRunner |
| Config Manager | YAML-based strategy configuration |

### Phase 3: Performance Analysis (1-2 weeks)

| Module | Deliverable |
|--------|-------------|
| Analyzer | PerformanceAnalyzer with standard metrics |
| Comparator | Strategy comparison matrix |
| Report Gen | Tear sheet generation |

### Phase 4: Advanced Features (Optional)

| Module | Deliverable |
|--------|-------------|
| Optimizer | Grid search and walk-forward |
| Live Trading | Broker adapter |
| Risk Management | Position sizing and limits |

---

## 9. Key Design Decisions

| Decision | Rationale |
|----------|----------|
| **Strategy Registry** | Enables dynamic strategy loading and management |
| **Base Strategy Class** | Encapsulates common logic, ensures interface consistency |
| **Strategy Factory** | Decouples strategy creation from usage |
| **Parallel Runner** | Leverages multiprocessing for performance |
| **Shared Data Cache** | Reduces data loading overhead |
| **Standard Metrics** | Enables fair strategy comparison |
| **YAML Configuration** | Externalizes strategy parameters for flexibility |

---

## 10. Conclusion

The proposed architecture supports:

| Capability | Implementation |
|------------|----------------|
| **Multi-Strategy Management** | Registry + Factory + Config |
| **Parallel Execution** | ProcessPoolExecutor + Shared Cache |
| **Unified Analysis** | Standard metrics + Comparison matrix |
| **Extensibility** | Base class inheritance + Decorator registration |
| **Performance** | Data caching + Resource management |

**Estimated Development**: 4-7 weeks for core features

**Code Estimate**: ~2400-3800 lines across 17 files

---

*Document generated: 2026-04-25*
*Project: Campsis Stock Selection System*
