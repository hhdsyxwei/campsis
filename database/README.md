
## 目录说明

### database/ - 数据库相关目录
- **init/** - 初始化脚本（建库/建表/基础数据）,仅保留 “一次性执行” 的基础结构初始化脚本（建库、建表），按数字前缀保证执行顺序
  - `00_create_database.sql` - 建库脚本（优先执行）
  - `01_create_table_stock_min_kline.sql` - 分钟级K线表（核心）
  - `02_create_table_stock_basic.sql` - 股票基础信息表
  - `03_insert_base_data.sql` - 可选：插入交易日历/基础参数等静态数据

- **init/** - 按业务域（如stock/）或通用型（common/）拆分，每个存储过程单独一个 SQL 文件，便于修改和版本追踪；


- **migration/** - 表结构迭代脚本（按版本命名）
  - `v1.1_add_column_min_kline.sql` - 示例：新增字段
  - `v1.2_alter_index_min_kline.sql` - 示例：调整索引

- **query/** - 常用查询脚本（回测/分析场景）
  - `query_5min_data.sql` - 查询5分钟K线
  - `query_stock_daily_volume.sql` - 统计日成交量
  - `README.md` - 查询脚本使用说明

### Ingredient/ - 数据原料采集模块
- `daily_data_downloader.py` - 日线数据下载器
- `data_manager.py` - 数据管理器
- `stock_basic_downloader.py` - 股票基础信息下载器
- `trade_date_map_downloader.py` - 交易日历映射下载器
- `min_kline_downloader.py` - 分钟级K线下载器（对接数据库）

### KitchenBase/ - 基础工具层
- `baostock_wrapper.py` - Baostock包装器
- `download_utils.py` - 下载工具集
- `db_utils.py` - 数据库连接/写入工具（适配上述表结构）

## 注意事项

GitHub Markdown 预览可能出现显示混乱的情况，通常是由于以下原因导致：

1. 缩进问题：使用空格而非制表符进行缩进
2. 特殊字符：确保特殊字符正确转义
3. 代码块标记：确保代码块正确闭合
4. 标题层级：保持正确的标题层级结构
