# Ingredient/__init__.py
# Ingredient 包初始化文件
# 只导出你项目里 **真实存在** 的类
# 没有的一律不写！

# 数据管理器（你有的）
from .data_manager import (
    TradeDateMapManager,
    DailyDataManager,
    KLineUnifiedQuarterlyExtendedManager,
    BasicStockDataManager,
    DataManager,
    create_database_and_tables,
    get_existing_stock_codes_set,
    get_nearest_trade_date_before
)

# 下载器（只导出你真实有的类）
from .kline_unified_downloader import KLineDownloader