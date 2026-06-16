# Backtest Persistence Design and Implementation Plan

## Goal

Persist backtest runs, strategy-level metrics, order transactions, closed trades, and future equity-curve data into MySQL so every backtest can be queried and reviewed after execution.

## Design

The persistence layer should stay outside strategy code. Strategies and Backtrader analyzers produce runtime results; `main.py` and the runner pass those results to a DataNest manager that owns SQL persistence.

Flow:

```text
main.py
  -> ParallelBacktestRunner.run_batch()
    -> Backtrader executes strategy
    -> Runner returns metrics, transactions, trades
  -> PerformanceAnalyzer.compare()
  -> BacktestResultManager saves results
```

## Tables

### backtest_run

Stores one backtest execution.

- `id`
- `run_id`
- `run_name`
- `stock_code`
- `start_date`
- `end_date`
- `initial_cash`
- `commission_rate`
- `risk_free_rate`
- `status`
- `error_message`
- `created_at`
- `finished_at`

### backtest_strategy_result

Stores one strategy result inside a run.

- `id`
- `run_id`
- `strategy_name`
- `strategy_params_json`
- `final_value`
- `total_return`
- `annual_return`
- `sharpe_ratio`
- `max_drawdown`
- `calmar_ratio`
- `win_rate`
- `profit_factor`
- `trade_count`
- `created_at`

### backtest_order_transaction

Stores executed order transactions.

- `id`
- `run_id`
- `strategy_name`
- `stock_code`
- `trade_date`
- `side`
- `quantity`
- `price`
- `commission`
- `amount`
- `raw_json`
- `created_at`

### backtest_closed_trade

Stores closed trade PnL records.

- `id`
- `run_id`
- `strategy_name`
- `stock_code`
- `close_date`
- `net_pnl`
- `raw_json`
- `created_at`

### backtest_equity_curve

Reserved for daily portfolio/equity curve persistence after a dedicated analyzer is added.

- `id`
- `run_id`
- `strategy_name`
- `trade_date`
- `portfolio_value`
- `cash`
- `position_value`
- `daily_return`
- `drawdown`
- `created_at`

## Implementation Plan

- [x] Add table creation SQL to the project database initialization flow.
- [x] Add `Ingredient/DataNest/dm_backtest.py` with `BacktestResultManager`.
- [x] Add run lifecycle methods: create, success, failed.
- [x] Add save methods for strategy metrics, transactions, and closed trades.
- [x] Connect `run_backtest` and bullish backtest entry points to persistence.
- [x] Keep strategy code free of database writes.
- [x] Compile changed files.
- [x] Run a small `factor` backtest and verify rows are inserted.

## Progress Log

- 2026-06-11: Design written.
- 2026-06-11: Added MySQL table templates for backtest run, strategy result, order transaction, closed trade, and reserved equity curve.
- 2026-06-11: Added `BacktestResultManager` for run lifecycle and result persistence.
- 2026-06-11: Connected factor and bullish backtest entry points to persistence without adding database writes to strategy code.
- 2026-06-11: Verified `python3 -m compileall main.py Ingredient/DataNest/dm_backtest.py Ingredient/DataNest/dm_db_init.py Ingredient/DataNest/__init__.py`.
- 2026-06-11: Ran `python3 main.py init-db` successfully.
- 2026-06-11: Ran factor backtest and verified database persistence with run_id `9823d380e506487b96e867b7fea404fe`.
  - `backtest_run`: status `success`
  - `backtest_strategy_result`: 1 row, final value `99990.4213`, total return `-0.0000957874`, trade count `6`
  - `backtest_order_transaction`: 13 rows
  - `backtest_closed_trade`: 6 rows
