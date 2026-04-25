# Backtrader Integration and Strategy Development Plan

## 1. Project Architecture Analysis

### 1.1 Current Project Structure

| Module | Lines of Code | Files | Responsibility |
|--------|--------------|-------|----------------|
| Ingredient/downloader | 5,135 | 40 | Data download and management |
| Ingredient/DataNest | 3,866 | 19 | Data storage and retrieval |
| KitchenBase | 1,958 | 8 | Infrastructure and utilities |
| CookingEngine | 747 | 5 | Strategy engine and factor calculation |
| tests | 697 | 6 | Testing |
| **Total** | **12,705** | **83** | - |

### 1.2 Data Flow Architecture

```
Data Source (Baostock API) → downloader Module → DataNest Module → CookingEngine Module
```

- **Data Layer (Ingredient)**: Responsible for downloading data from Baostock API and storing to MySQL
- **Strategy Layer (CookingEngine)**: Calculate factors and execute stock selection logic
- **Infrastructure (KitchenBase)**: Provides utilities, enums, and common components

### 1.3 Current Capability Assessment

| Function | Status |
|----------|--------|
| Data Download | ✅ Complete (stock basics, daily data, financial data) |
| Factor Calculation | ✅ Basic implementation (trend, momentum, quality, timing) |
| Data Management | ✅ Complete (MySQL storage and retrieval) |
| Strategy Backtesting | ❌ Not implemented |
| Strategy Execution | ❌ Not implemented |

---

## 2. Backtrader Integration Analysis

### 2.1 Why Backtrader?

| Comparison | Backtrader | Self-built Engine |
|------------|-------------|-------------------|
| Development Cycle | 1-2 weeks integration | 2-4 months development |
| Lines of Code | Minimal adapter code | 2000-5000+ lines |
| Feature Completeness | Mature and stable | Requires continuous iteration |
| Learning Cost | Framework learning curve | Fully自主可控 |
| Customization | Limited by framework | Fully customizable |

### 2.2 Backtrader Advantages for Retail Investors

| Advantage | Description |
|-----------|-------------|
| **Zero Cost** | Completely free, no software or data fees |
| **Complete Features** | 100+ built-in indicators, complete performance analysis |
| **Rich Documentation** | Official docs, blog tutorials, GitHub examples |
| **Open Source** | Source code fully auditable |
| **Active Community** | 10k+ stars, strong community support |

### 2.3 Data Leakage Risk Analysis

**Backtrader framework itself has no data leakage issues.** Data leakage risks come from:

| Risk Type | Source | Responsibility |
|-----------|--------|----------------|
| Indicator Calculation | Using future data (e.g., `self.data.close[0]`) | Strategy developer |
| Financial Data | Using `stat_date` instead of `pub_date` | Strategy developer |
| Order Execution | Assuming full execution at close price | Strategy developer |
| Framework Itself | No leakage risk | N/A |

#### Key Points for Financial Data

| Data Type | Available Time | Note |
|-----------|---------------|------|
| Daily Price | After T-day close | Close price available after market close |
| Financial Data | `pub_date` ≤ T | Must use `pub_date`, not `stat_date` |

---

## 3. Modules Required After Backtrader Integration

### 3.1 Module Overview

| Module | Priority | Status | New Files | Estimated Lines |
|--------|----------|--------|-----------|-----------------|
| Data Adapter Layer | ⭐⭐⭐⭐⭐ | ❌ → ✅ | 3 | 500-800 |
| Strategy Development Framework | ⭐⭐⭐⭐⭐ | ⚠️ → ✅ | 4 | 600-1000 |
| Parameter Optimization | ⭐⭐⭐⭐ | ❌ | 3 | 400-600 |
| Live Trading | ⭐⭐⭐ | ❌ | 4 | 500-800 |
| Performance Analysis | ⭐⭐⭐⭐ | ⚠️ → ✅ | 3 | 400-600 |

### 3.2 Detailed Module List

#### Layer 1: Data Adapter (Backtrader Integration)

| File | Location | Responsibility |
|------|----------|----------------|
| `bt_data_adapter.py` | `CookingEngine/Backtest/` | Convert DataNest data to Backtrader format |
| `bt_pandas_data.py` | `CookingEngine/Backtest/` | Custom PandasData subclass |
| `bt_data_feeder.py` | `CookingEngine/Backtest/` | Batch data feed management |

#### Layer 2: Strategy Development Framework

| File | Location | Responsibility |
|------|----------|----------------|
| `base_strategy.py` | `CookingEngine/Strategies/` | Strategy base class, encapsulate common logic |
| `factor_strategy.py` | `CookingEngine/Strategies/` | Four-factor stock selection strategy |
| `signal_generator.py` | `CookingEngine/Strategies/` | Signal generator |
| `position_manager.py` | `CookingEngine/Strategies/` | Position management |

#### Layer 3: Parameter Optimization

| File | Location | Responsibility |
|------|----------|----------------|
| `optimizer.py` | `CookingEngine/Backtest/` | Parameter optimization engine |
| `param_space.py` | `CookingEngine/Backtest/` | Parameter space definition |
| `walk_forward.py` | `CookingEngine/Backtest/` | Walk-Forward analysis |

#### Layer 4: Live Trading (Optional)

| File | Location | Responsibility |
|------|----------|----------------|
| `broker_adapter.py` | `CookingEngine/Trading/` | Broker interface adapter |
| `order_manager.py` | `CookingEngine/Trading/` | Order management |
| `risk_manager.py` | `CookingEngine/Trading/` | Risk management |
| `position_tracker.py` | `CookingEngine/Trading/` | Position tracking |

#### Layer 5: Performance Analysis

| File | Location | Responsibility |
|------|----------|----------------|
| `performance_analyzer.py` | `CookingEngine/Analysis/` | Performance metrics calculation |
| `tearsheet.py` | `CookingEngine/Analysis/` | Backtest report generation |
| `chart_generator.py` | `CookingEngine/Analysis/` | Chart generation |

### 3.3 Module Dependency

```
                    ┌─────────────────────┐
                    │   Data Layer (Existing)│
                    │  DataNest/MySQL      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Data Adapter Layer  │
                    │  bt_data_adapter     │
                    └──────────┬──────────┘
                               │
          ┌────────────────────┼────────────────────┐
          │                    │                    │
┌─────────▼─────────┐ ┌───────▼────────┐ ┌────────▼────────┐
│ Strategy Framework│ │ Optimization   │ │ Performance     │
│ base_strategy     │ │ optimizer      │ │ performance    │
│ factor_strategy   │ │ walk_forward   │ │ tearsheet      │
└─────────┬─────────┘ └────────────────┘ └─────────────────┘
          │                    │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │   Backtest/Trading  │
          │   Backtrader        │
          └──────────┬──────────┘
                     │
          ┌──────────▼──────────┐
          │ Live Trading (Opt)  │
          │ broker_adapter      │
          └─────────────────────┘
```

---

## 4. Development Priority

### Phase 1: Core Functionality (2-4 weeks)

| Priority | Module | Estimated Time |
|----------|--------|----------------|
| 1 | bt_data_adapter | 3-5 days |
| 2 | base_strategy | 2-3 days |
| 3 | factor_strategy | 3-5 days |
| 4 | Basic backtest execution | 2-3 days |
| **Subtotal** | | **2-3 weeks** |

### Phase 2: Enhanced Features (2-3 weeks)

| Priority | Module | Estimated Time |
|----------|--------|----------------|
| 5 | performance_analyzer | 3-5 days |
| 6 | tearsheet | 2-3 days |
| 7 | optimizer | 3-5 days |
| **Subtotal** | | **2-3 weeks** |

### Phase 3: Advanced Features (Optional)

| Priority | Module | Estimated Time |
|----------|--------|----------------|
| 8 | walk_forward | 1-2 weeks |
| 9 | broker_adapter | 2-3 weeks |
| 10 | risk_manager | 1-2 weeks |

---

## 5. Code Estimate Summary

| Category | New Files | Estimated Lines |
|----------|-----------|-----------------|
| Data Adapter Layer | 3 | 500-800 |
| Strategy Framework | 4 | 600-1000 |
| Parameter Optimization | 3 | 400-600 |
| Live Trading | 4 | 500-800 |
| Performance Analysis | 3 | 400-600 |
| **Total** | **17** | **2400-3800** |

---

## 6. Security Considerations

### 6.1 Backtrader Security

| Aspect | Assessment |
|--------|------------|
| Open Source | ✅ GPL v3, full source available |
| Code Audit | ✅ Any malicious code would be discovered |
| Network Communication | ✅ All data is local, no cloud dependency |
| Dependencies | ⚠️ Standard Python packages, auditable |

### 6.2 Security Recommendations

1. **Code Audit**: Review Backtrader source before installation
2. **Network Monitoring**: Use Wireshark to monitor network connections
3. **Virtual Environment**: Use isolated venv for Backtrader
4. **Local Operation**: All backtesting runs locally

---

## 7. Conclusion

After integrating Backtrader, the project will have:

| Phase | Modules | Necessity |
|-------|---------|-----------|
| **Phase 1** | Data adapter + Strategy base + Factor strategy + Basic backtest | Required |
| **Phase 2** | Performance analysis + Parameter optimization | Recommended |
| **Phase 3** | Walk-Forward + Live trading | Optional |

**Estimated new code**: 2400-3800 lines
**Estimated development time**: 4-8 weeks (depending on time investment)

---

## 8. Next Steps

1. Install Backtrader and run official examples (1-2 days)
2. Understand Backtrader core concepts (3-5 days)
3. Implement data adapter (1 week)
4. Port four-factor strategy (2 weeks)
5. Run complete backtest (1 week)

---

*Document generated: 2026-04-25*
*Project: Campsis Stock Selection System*
