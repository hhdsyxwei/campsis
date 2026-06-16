# Campsis Project Analysis

## 项目定位

Campsis 是一个 Python A 股量化数据与回测项目，核心目标是：

- 从 Baostock 下载 A 股行情、财务、指数、行业等数据。
- 存入本地 MySQL 数据库 `ashare`。
- 基于数据库数据做因子计算、股票打分和 Backtrader 回测。
- 支持区块化下载、断点续传和下载状态管理。

项目入口在 `main.py`。

## 核心模块

### KitchenBase

基础设施层，提供全项目共享能力。

- `baostock_wrapper.py`：封装 Baostock API，包括登录、行情、财务、行业、沪深 300 等查询。
- `download_enums.py`：下载任务类型、任务状态、区块状态、指针字段枚举。
- `stock_enums.py`：K 线周期、复权类型、市场类型等枚举。
- `download_parameters.py`：统一下载参数对象 `DownloadParameters`。
- `logger_config.py`：项目日志配置。
- `package_manager.py`：运行时自动扫描并安装缺失依赖。

### Ingredient

数据采集和数据访问层。

`Ingredient/downloader/` 是下载器模块：

- `daily_data_downloader.py`：日线数据。
- `kline_unified_downloader.py`：统一 K 线，按股票、周期、季度分块。
- `stock_basic_downloader.py`：股票基础信息。
- `stock_industry_downloader.py`：行业分类。
- `xrxd_downloader.py`：分红送配。
- `adj_factor_downloader.py`：复权因子。
- `company_profit_downloader.py`：利润数据。
- `company_balance_downloader.py`：偿债能力/资产负债相关数据。
- `company_cash_flow_downloader.py`：现金流数据。
- `index_csi300_downloader.py`：沪深 300 成分股。

`Ingredient/DataNest/` 是数据库管理层：

- 每个 `dm_*.py` 基本对应一张或一组表，例如 `dm_daily.py` 管理 `stock_daily`，`dm_company_profit.py` 管理 `company_profit`。
- `dm_db_init.py` 创建数据库和全部表。
- `dm_global_dl_ctrl.py` 和 `dm_generic_block_status.py` 负责下载进度与区块状态。

### CookingEngine

策略、因子和回测层。

`CookingEngine/Picker/`：

- `data_provider.py`：统一数据读取接口，当前实现是 `HarvestDataProvider`。
- `factor_calculator.py`：趋势、动量、质量、择时等因子计算。
- `stock_scorer.py`：单只或多只股票评分。

`CookingEngine/Strategies/`：

- `registry.py`：策略注册中心。
- `strategy_factory.py`：策略工厂。
- `factors/factor_strategy.py`：因子策略。
- `obs/`：四个次日看涨观察策略：
  - `box_breakout`
  - `bottom_reverse`
  - `trend_pullback`
  - `multi_indicator_resonance`

`CookingEngine/Backtest/`：

- `data_adapter.py`：把 MySQL 日线数据转成 Backtrader 数据源。
- `parallel_runner.py`：批量执行策略回测。目前实现是顺序循环执行，名称中虽然有 `Parallel`，但没有真正并发。

### database

MySQL 初始化与迁移脚本。

- `init/base/`：数据库、交易日历。
- `init/stock/`：股票基础、日线、复权、行业。
- `init/kline/`：统一 K 线表、K 线区块状态。
- `init/finance/`：利润、偿债、现金流。
- `init/download/`：下载进度、任务配置、区块状态。
- `init/index/`：沪深 300 成分股。
- `migration/`：数据库迁移脚本。
- `partition/`：分区相关脚本。
- `query/`：常用查询脚本。

## 主要数据模型

### trade_date_map

- 主键：`calendar_date`
- 字段：是否交易日、创建时间、更新时间。
- 用途：交易日判断、回测日期校正。

### stock_basic

- 主键：`std_stock_code`
- 字段：股票名称、纯代码、行业、市场、上市日期、退市日期、是否活跃。
- 用途：股票池、上市周期判断、市场过滤。

### stock_daily

- 主键：自增 `id`
- 唯一键：`std_stock_code + trade_date`
- 字段：OHLC、前收、涨跌幅、成交量、成交额、换手率、PE/PB/PS/PCF、复权标志、交易状态、ST 标志。
- 用途：日线回测、技术因子、择时。

### kline_unified_quarterly_extended

- 主键：`std_stock_code + time_frame + timestamp`
- 字段：OHLCV、成交额、创建时间、更新时间。
- 特点：按 `timestamp` 做季度分区，预置 2024-2028 分区和 `p_future`。
- 用途：分钟级/多周期 K 线数据。

### stock_xrxd

分红送配数据，包含预案、股权登记、除权除息、派息、送转股等字段。

### stock_adjustment_factor

- 唯一键：`std_stock_code + adjust_date`
- 字段：前复权因子、后复权因子、复权因子。

### stock_industry 与 stock_industry_history

当前行业快照与历史行业记录。

### company_profit

- 唯一键：`std_stock_code + stat_date`
- 字段：ROE、净利率、毛利率、净利润、EPS、主营收入、总股本、流通股本。

### company_balance

- 唯一键：`std_stock_code + stat_date`
- 字段：流动比率、速动比率、现金比率、负债同比、资产负债率、权益乘数。

### company_cash_flow

- 唯一键：`std_stock_code + stat_date`
- 字段：资产结构、利息保障倍数、经营现金流相关指标。

### index_csi300_component

沪深 300 成分股表。

### global_dl_ctrl_block

下载任务全局状态和指针。

- 记录任务类型、任务状态、一级/二级/三级指针、启动参数、完成区块数、总区块数。

### generic_block_status

通用区块状态表。

- 主键：`block_key_1 + block_key_2 + block_key_3 + task_type`
- 状态：`not_completed`、`skipped`、`completed`、`error`

## 下载模型

下载器分两类：

- `SimpleDownloader`：一次性下载，比如交易日历、股票基础信息、沪深 300 成分股。
- `BlockDownloader`：区块化下载，支持断点续传和状态管理。

区块划分方式：

- 日线：`stock_code + year`
- K 线：`stock_code + time_frame + quarter`
- 财务利润/资产负债/现金流：`quarter + stock_code`
- 复权/分红：通常为 `year + stock_code`
- 行业：按年份或时间块

下载状态保存在 `global_dl_ctrl_block` 和 `generic_block_status`，因此下载中断后可以继续。

## 策略和回测模型

数据流：

1. `DailyDataManager` 从 `stock_daily` 读取日线。
2. `BacktraderDataAdapter` 转成 Backtrader `PandasData`。
3. `ParallelBacktestRunner` 创建 `Cerebro`。
4. 通过 `strategy_registry` 找到策略类。
5. 注入 `HarvestDataProvider` 和 `FactorCalculator`。
6. 执行回测，收集 Sharpe、回撤、收益、交易记录等 analyzer 结果。
7. `PerformanceAnalyzer` 做策略比较。

已注册策略：

- `factor_strategy`
- `box_breakout`
- `bottom_reverse`
- `trend_pullback`
- `multi_indicator_resonance`

## 使用方式

### 运行主程序

```bash
python main.py
```

当前主流程大致是：

1. 自动安装缺失依赖。
2. 初始化日志。
3. 创建 MySQL 数据库和表。
4. 登录 Baostock。
5. 读取沪深 300 成分股。
6. 构造 `DownloadParameters(start_year=2025, end_year=2027, stock_codes=...)`。
7. 下载股票数据。目前 `download_stock_data()` 默认启用：
   - 日线数据下载
   - 公司利润数据下载
8. 运行四个次日看涨策略回测。
9. 关闭数据库并退出 Baostock。

### 下载基础数据

在 `main.py` 的 `main()` 中打开：

```python
download_basic_data(conn, params)
```

它会下载：

- 沪深 300 成分股。
- 交易日历。
- 股票基础信息。

### 打开其他数据下载

在 `download_stock_data()` 中取消对应注释，例如：

```python
start_new_kline_download(conn, params)
start_new_xrxd_download(conn, params)
start_new_adj_factor_download(conn, params)
start_new_balance_download(conn, params)
start_new_cash_flow_download(conn, params)
```

### 运行测试

```bash
pip install -r requirements-test.txt
pytest
```

测试配置在 `pytest.ini`，会统计 `CookingEngine`、`Ingredient`、`KitchenBase` 覆盖率。

## 运行前提

- 本地 MySQL 可连接。
- 默认数据库配置在 `Ingredient/DataNest/dm_config.py`。
- 当前配置硬编码为：
  - host: `localhost`
  - port: `3306`
  - user: `root`
  - database: `ashare`
- 网络能访问 Baostock。
- `main.py` 会登录 Baostock，并处理 IP 黑名单、连接拒绝等错误。

建议把数据库密码从代码移到环境变量或本地未提交配置文件。

## 当前项目状态判断

整体架构已经比较完整：数据下载、数据库模型、断点续传、因子计算、Backtrader 回测都有雏形。

代码实际能力比部分文档更新，尤其是财务、分红、指数、行业下载器已经存在；`docs/project/BacktestDataRequirements.md` 里的“未实现”说明已经滞后。

主要风险点：

- 没有正式 `requirements.txt`，依赖靠运行时自动安装，不利于部署和复现。
- 数据库账号密码硬编码。
- `ParallelBacktestRunner` 名称暗示并行，但当前实现是顺序循环。
- 文档和代码状态不完全一致。
- `main.py` 当前是实验式脚本，下载、回测、策略参数都靠手动注释切换，后续适合抽 CLI 或配置文件。
