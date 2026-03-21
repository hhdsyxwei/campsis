campsis/
├── .gitattributes
├── .gitignore
├── ArchitectureDiagram.md
├── README.md
├── main.py                # 项目入口
├── prompts.md
# 1. 数据库相关（新增核心目录）
├── database/              # 数据库全量资源
│   ├── init/              # 初始化脚本（建库/建表/基础数据）
│   │   ├── 00_create_database.sql  # 建库脚本（优先执行）
│   │   ├── 01_create_table_stock_min_kline.sql  # 分钟级K线表（核心）
│   │   ├── 02_create_table_stock_basic.sql # 股票基础信息表
│   │   └── 03_insert_base_data.sql # 可选：插入交易日历/基础参数等静态数据
│   ├── migration/         # 表结构迭代脚本（按版本命名）
│   │   ├── v1.1_add_column_min_kline.sql  # 示例：新增字段
│   │   └── v1.2_alter_index_min_kline.sql # 示例：调整索引
│   ├── query/             # 常用查询脚本（回测/分析场景）
│   │   ├── query_5min_data.sql       # 查询5分钟K线
│   │   ├── query_stock_daily_volume.sql # 统计日成交量
│   │   └── README.md      # 查询脚本使用说明
│   └── README.md          # 数据库整体说明（建表流程/字段释义/注意事项）
# 2. 原有业务模块
├── Ingredient/            # 数据原料采集（并列模块）
│   ├── __init__.py
│   ├── daily_data_downloader.py
│   ├── data_manager.py
│   ├── stock_basic_downloader.py
│   ├── trade_date_map_downloader.py
│   └── min_kline_downloader.py  # 新增：分钟级K线下载（对接数据库）
├── CookingEngine/         # 数据加工引擎（并列模块）
│   └── __init__.py
├── KitchenBase/           # 基础工具层
│   ├── __init__.py
│   ├── baostock_wrapper.py
│   ├── download_utils.py
│   └── db_utils.py        # 新增：数据库连接/写入工具（适配上述表结构）
└── docs/                  # 可选：补充文档（非必需，若需更详细说明）
    ├── database_design.md # 数据库设计思路（字段/索引/分表说明）
    └── data_flow.md       # 数据流向：下载→入库→加工