# 统一K线数据下载器 - 一页纸最终设计文档（开发交接版）

**适用场景**：全周期K线离线下载、断点续传、动态范围扩展、7×24h稳定运行

**核心特性**：无回溯、不重置指针、零内存、不重复、不遗漏、极简架构

## 1. 设计目标

实现固定顺序、单向推进、无队列、零内存的K线下载器；自动跳过已完成数据，支持时间扩展、股票追加、崩溃续传；全程不回溯、常规操作无需重置指针；单任务极简架构，易开发、易维护、长期稳定运行。

## 2. 核心基础规则

### 最小下载单元

股票代码 + 时间周期 + 季度（不可拆分）

### 全局固定下载顺序

**季度（旧→新） → 股票固定ID（升序） → 时间周期（固定序列）**

### 周期固定排序（不可修改）

1min → 5min → 15min → 30min → 60min → daily → weekly → monthly

### 股票管理规则

新股仅允许追加至`stock_fixed_seq`末尾，禁止中间插入、禁止修改原有排序。

## 3. 四张核心数据表

### 3.1 stock_fixed_seq 股票固定顺序表

|字段|类型|说明|
|---|---|---|
|id|INT UNSIGNED|自增主键，固定排序标识|
|stock_code|VARCHAR(20)|唯一股票代码|
|stock_name|VARCHAR(50)|股票名称|
|create_time|DATETIME|创建时间|
### 3.2 kline_block_status K线单元状态表

|字段|类型|说明|
|---|---|---|
|stock_code|VARCHAR(20)|股票代码|
|time_frame|VARCHAR(10)|K线周期|
|quarter|VARCHAR(10)|季度标识|
|status|ENUM|waiting/completed/failed|
|completed_at|DATETIME|完成时间|
|主键|复合主键|stock_code+time_frame+quarter|
### 3.3 kline_download_progress 全局进度指针表

|字段|类型|说明|
|---|---|---|
|id|INT|固定值1，唯一主键|
|downloading_quarter|VARCHAR(10)|当前下载的季度|
|downloading_stock_code|INT UNSIGNED|当前下载的股票ID|
|downloading_time_frame|VARCHAR(10)|当前下载数据的周期类型(5min/15min)|
|update_time|DATETIME|更新时间|
### 3.4 download_task_config 下载范围配置表

|字段|类型|说明|
|---|---|---|
|id|TINYINT|固定值1，唯一主键|
|start_stock_id|INT UNSIGNED|起始股票ID|
|end_stock_id|INT UNSIGNED|结束股票ID|
|start_time_frame|VARCHAR(10)|起始周期|
|end_time_frame|VARCHAR(10)|结束周期|
|start_quarter|VARCHAR(10)|起始季度|
|end_quarter|VARCHAR(10)|结束季度|
|reset_progress|TINYINT|0=不重置 1=强制重置指针|
|created_at|DATETIME|创建时间|
|update_at|DATETIME|自动更新时间|
## 4. 核心运行逻辑

1. 启动加载`download_task_config`读取全局下载边界范围；

2. 读取`kline_download_progress`断点指针，定位上次结束位置；

3. 严格按【季度→股票ID→周期】顺序查询单个未完成下载单元；

4. 校验状态表，已完成单元自动跳过，仅处理待下载单元；

5. 下载成功后更新状态表为completed并回填完成时间；同步单向推进进度指针；

6. 循环迭代，全程无队列预生成，单次仅处理一条数据；

7. 重启自动读取指针续传，常规运行**不回溯历史、不重置指针**。

## 5. 范围扩展标准流程

1. 向后扩展时间：修改配置表结束季度，无需重置指针、无需回溯；新增季度自动末尾排序，全股票自动补齐数据无缺失。

2. 末尾追加新股：股票表尾部插入新数据，无需任何配置修改；新股从当前指针季度开始向后自动下载。

3. 向前补历史数据：修改配置起始季度，设置reset_progress=1；系统重置指针从头遍历，自动跳过已完成单元，仅补缺失历史。

## 6. 强制约束规范

1. 下载排序规则、周期顺序永久固定，禁止修改；

2. 进度指针仅向前推进，业务流程禁止回溯回滚；

3. 状态表数据永久保留，不得清空删除；

4. 股票仅尾部追加，严禁调整原有ID顺序；

5. 全程无内存任务队列，严格遵循单条查询模式。

## 7. 架构总结

季度优先排序 + 单向只读指针 + 范围配置驱动；常规扩展零重置零回溯，仅历史补全手动重置；架构极简低负载，适配长期后台稳定运行。