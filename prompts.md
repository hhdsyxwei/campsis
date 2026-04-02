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

## 2. stock_basic_downloader.py 模块要求
实现核心接口 `download_stock_basic` 函数，具体要求如下：
1. 下载前，本模块的使用者调用download_stock_basic前需自行完成数据库连接，完成baostock登录，本模块直接利用已有连接下载数据
2. download_stock_basic的参数列表：数据库连接conn，market_type_list(需要下载的市场类型清单)
3. market_type_list采用MarketType类型列表，MarketType由stock.enums.py定义
4. download_stock_basic的下载流程分4个部分，参数检验，通过baostock的query_stock_basic接口下载原生数据，数据清洗，数据保存，分别封装成内部函数
5. 下载数据保存在stock_basic表中
6. 数据保存或者其它操纵数据的过程统一通过data_manager.py模块进行，本模块不可直接访问数据库，不可直接执行sql语句
7. 数据下载后统一转成pandas的DataFrame格式，提升数据的标准化
8. 需要依赖其它模块实现的函数直接设置为空函数，定义好参数列表，返回值，准备好详细的注释即可

### 协作方式
先讲解实现思路，确认后再进行代码实现。

---

## 3. kline_5min_downloader.py模块：
统一K线数据下载器

### 统一K线数据的下载器的设计思路：
download_kline函数的要求如下：
1. 下载前，本模块的使用者自己连接数据库，并提供连接句柄作为参数
2. 下载前，本模块的使用者自行完成baostock登录，本模块假定登录已经完成，复用已有的登录状态。
3. 数据库表kline_block_status记录每个下载单元的状态，为了简化实现，只记录2个状态，未完成和完成
4. 数据库表kline_unified_quarterly_extended记录实际的K线数据
5. 数据库表stock_fixed_seq记录预设的股票代码下载顺序
6. 数据库表download_task_config记录用户请求的下载参数，下载范围
7. 数据库表kline_download_progress记录当前下载指针，也就是当前正常下载的区块的信息
8. 一个下载单元是某只股票的某种时间周期time_frame(1分钟，5分钟，15分钟等)在指定的季度的所有数据。
9. 本模块提供的唯一对外接口是download_kline，接口参数仅start_year，end_year，time_frame。下载年份范围包括start_year,不包括end_year。
10. download_kline函数按照固定的顺序下载区块，循环处理每个区块。初始化时指向第1个区块，单次循环首先获得下一个区块，再下载一个区块，直到最后一个区块
11. 区块排序包含2个字段，季度(比如2025-Q1)，股票代码
12. download_kline函数不要生成下载区块列表，而是依照规则，以数据信息为支撑，找到下一个区块
13. 内部接口_fetch_kline_block实现指定股票指定某个季度k线数据下载(可以指定time_frame即时间周期)，即实现最小单元的下载任务
14. 最小单元的下载任务包括以下步骤：参数校验，上市时间检验，获取最小单元状态，下载原始数据，清洗数据，保存数据，保存进度.
15. 上市时间检验通过_is_time_range_overlap_with_listing_period完成
16. 数据保存由外部模块data_manager实现
17. 网络异常，或者服务器异常时向上抛出异常。
18. 利用外部模块logger_config输出日志，每条日志都需要包含当前模块，当前函数信息
19. 利用外部模块baostock_wrapper.py查询baostock提供的k线数据

### 数据库设计思路：
1. 请基于下载器的设计思路先告诉我kline_download_progress表的设计思路和方案，我再决定是否输出相应的数据库DDL
2. 根据我的下载器设计思路，请生成kline_unified_quarterly_extended表的设计思路，由我决定是否生成数据库表的DDL

#### kline_unified_quarterly_extended表设计要求：
1. 以(std_stock_code, time_frame, timestamp)为主键
2. 去除当前需求不涉及的字段，简化表设计
3. 预建2024-2028年所有季度分区，便于按季度查询和管理数据生命周期
4. 与kline_download_progress表配合，确保下载单元的完整性