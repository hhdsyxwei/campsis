# 各模块开发/重构提示词

## 1. baostock_wrapper.py 重构要求
重新实现 `baostock_wrapper.py` 模块，需满足以下核心要求：

### 核心功能要求
1. **无感知封装**：完全保留原有 `query_history_k_data_plus` 函数的参数、返回值、异常抛出逻辑，保证调用方无感知。
2. **循环执行流程**：
   - 整个执行流程包含可配置次数的循环
   - 单次循环包含 3 个步骤：
     - 设定全局超时时间
     - 调用原生 `query_history_k_data_plus` 方法
     - 异常恢复：当原生方法发生超时/其他异常时，执行重新登录操作
3. **登录复用**：流程复用已有登录状态（假定已完成登录）。
4. **日志要求**：
   - 所有日志信息需打印当前函数名称
   - 导入 `download_utils` 的日志依赖

---

## 2. stock_basic_downloader.py 函数拆解要求
将 `init_stock_basic_table` 函数拆分为两个独立部分，具体要求如下：

### 第一部分：基础股票代码写入
- 核心职责：调用 `_fetch_stock_codes` 获取股票代码基础信息并写入数据库
- 数据处理：无需断点续传，每次执行完整覆盖原有数据
- 扩展能力：允许用户指定「排除市场类型列表」参数

### 第二部分：其他字段下载
- 核心职责：下载除基础代码外的其他字段数据
- 逻辑继承：直接继承原 `init_stock_basic_table` 的下载逻辑
- 核心能力：
  - 支持断点续传
  - 支持参数化分组下载方式
- 数据范围：下载的股票代码集合不超过第一部分获取的代码集合

### 协作方式
先讲解实现思路，确认后再进行代码实现。

---

## 3. kline_5min_downloader.py模块：
统一K线数据下载器

### 统一K线数据的下载器的设计思路：
请为我设计K线数据下载器模块，设计思路如下：
1. 下载前，本模块的使用者自己连接数据库，并提供连接句柄作为参数
2. 下载前，本模块的使用者自行完成baostock登录，本模块假定登录已经完成，复用已有的登录状态。
3. 数据库表kline_download_progress记录每个下载单元的状态，为了简化实现，只记录2个状态，未完成和完成
4. 数据库表kline_unified_quarterly_extended记录实际的K线数据
5. 一个下载单元是某只股票的某种时间类型(1分钟，5分钟，15分钟等)在指定的季度的所有数据。
6. 本模块提供的唯一对外接口是download_kline，接口参数仅start_year，end_year，time_frame。下载年份范围包括start_year,不包括end_year。
7. download_kline函数将下载任务拆分成多个季度(可以指定time_frame即时间类型)，内部函数_download_quarter_kline实现单个季度所有股票的下载。
8. 内部接口_fetch_quarterly_kline实现某个季度所有股票的下载功能(可以指定time_frame即时间类型)，所有股票列表通过data_manager模块的接口查询，不要在本模块实现。
9. 内部接口_fetch_stock_quarterly_kline实现指定股票指定某个季度k线数据下载(可以指定time_frame即时间类型)，即实现最小单元的下载任务
10. 最小单元的下载任务包括以下步骤：参数校验，获取最小单元状态，下载原始数据，清洗数据，保存数据，保存进度.
11. 数据保存由外部模块data_manager实现
12. 网络异常，或者服务器异常时向上抛出异常。
13. 利用外部模块logger_config输出日志，每条日志都需要包含当前模块，当前函数信息
14. 利用外部模块baostock_wrapper.py查询baostock提供的k线数据

### 数据库设计思路：
1. 请基于下载器的设计思路先告诉我kline_download_progress表的设计思路和方案，我再决定是否输出相应的数据库DDL
2. 根据我的下载器设计思路，请生成kline_unified_quarterly_extended表的设计思路，由我决定是否生成数据库表的DDL

#### kline_unified_quarterly_extended表设计要求：
1. 以(stock_code, time_frame, timestamp)为主键
2. 去除当前需求不涉及的字段，简化表设计
3. 预建2024-2028年所有季度分区，便于按季度查询和管理数据生命周期
4. 与kline_download_progress表配合，确保下载单元的完整性