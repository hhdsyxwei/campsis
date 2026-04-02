# dm_columns.py

# 通用列名
STD_STOCK_CODE = "std_stock_code"
TIME_FRAME = "time_frame"
TIMESTAMP = "timestamp"

# K线数据列名
OPEN_PRICE = "open_price"
HIGH_PRICE = "high_price"
LOW_PRICE = "low_price"
CLOSE_PRICE = "close_price"
VOLUME = "volume"
TURNOVER = "turnover"

# 股票基础信息列名
STOCK_NAME = "stock_name"
PURE_SYMBOL = "pure_symbol"
INDUSTRY = "industry"
MARKET = "market"
LIST_DATE = "list_date"
DELIST_DATE = "delist_date"
IS_ACTIVE = "is_active"

# 日线数据列名
TRADE_DATE = "trade_date"
PRE_CLOSE = "pre_close"
CHANGE_RATE = "change_rate"
TURNOVER_RATE = "turnover_rate"
PE = "pe"
PB = "pb"

# 下载进度列名
DOWNLOADING_STOCK_CODE = "downloading_stock_code"
DOWNLOADING_TIME_FRAME = "downloading_time_frame"
DOWNLOADING_QUARTER = "downloading_quarter"
UPDATE_TIME = "update_time"

# 区块状态列名
QUARTER = "quarter"
STATUS = "status"
COMPLETED_AT = "completed_at"

# 表级列名集合
class KlineUnifiedColumns:
    STD_STOCK_CODE = STD_STOCK_CODE
    TIME_FRAME = TIME_FRAME
    TIMESTAMP = TIMESTAMP
    OPEN_PRICE = OPEN_PRICE
    HIGH_PRICE = HIGH_PRICE
    LOW_PRICE = LOW_PRICE
    CLOSE_PRICE = CLOSE_PRICE
    VOLUME = VOLUME
    TURNOVER = TURNOVER

class StockBasicColumns:
    STD_STOCK_CODE = STD_STOCK_CODE
    STOCK_NAME = STOCK_NAME
    PURE_SYMBOL = PURE_SYMBOL
    INDUSTRY = INDUSTRY
    MARKET = MARKET
    LIST_DATE = LIST_DATE
    DELIST_DATE = DELIST_DATE
    IS_ACTIVE = IS_ACTIVE

class StockDailyColumns:
    STD_STOCK_CODE = STD_STOCK_CODE
    TRADE_DATE = TRADE_DATE
    OPEN = OPEN_PRICE
    HIGH = HIGH_PRICE
    LOW = LOW_PRICE
    CLOSE = CLOSE_PRICE
    PRE_CLOSE = PRE_CLOSE
    CHANGE_RATE = CHANGE_RATE
    VOLUME = VOLUME
    AMOUNT = TURNOVER
    TURNOVER_RATE = TURNOVER_RATE
    PE = PE
    PB = PB
