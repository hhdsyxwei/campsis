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
PS = "ps"
PCF = "pcf"
ADJUST_FLAG = "adjust_flag"
TRADE_STATUS = "trade_status"
IS_ST = "is_st"

# 分红送配数据列名
XRXD_YEAR = "xrxd_year"
XRXD_PRE_NOTICE_DATE = "xrxd_pre_notice_date"
XRXD_AGM_PUM_DATE = "xrxd_agm_pum_date"
XRXD_PLAN_ANNOUNCE_DATE = "xrxd_plan_announce_date"
XRXD_PLAN_DATE = "xrxd_plan_date"
XRXD_REGIST_DATE = "xrxd_regist_date"
XRXD_OPERATE_DATE = "xrxd_operate_date"
XRXD_PAY_DATE = "xrxd_pay_date"
XRXD_STOCK_MARKET_DATE = "xrxd_stock_market_date"
XRXD_CASH_PS_BEFORE_TAX = "xrxd_cash_ps_before_tax"
XRXD_CASH_PS_AFTER_TAX = "xrxd_cash_ps_after_tax"
XRXD_STOCKS_PS = "xrxd_stocks_ps"
XRXD_CASH_STOCK = "xrxd_cash_stock"
XRXD_RESERVE_TO_STOCK_PS = "xrxd_reserve_to_stock_ps"
CREATE_TIME = "create_time"
UPDATE_TIME = "update_time"

# 下载进度列名
DOWNLOADING_STOCK_CODE = "downloading_stock_code"
DOWNLOADING_TIME_FRAME = "downloading_time_frame"
DOWNLOADING_QUARTER = "downloading_quarter"

# 区块状态列名
QUARTER = "quarter"
STATUS = "status"
COMPLETED_AT = "completed_at"

# 表级列名集合
class KlineUnifiedStandardColumns:
    """K线统一格式标准列名 - 用于统一格式的 K线数据（可能与数据库列名不同）"""
    STD_STOCK_CODE = STD_STOCK_CODE
    TIME_FRAME = TIME_FRAME
    TIMESTAMP = TIMESTAMP
    OPEN_PRICE = OPEN_PRICE
    HIGH_PRICE = HIGH_PRICE
    LOW_PRICE = LOW_PRICE
    CLOSE_PRICE = CLOSE_PRICE
    VOLUME = VOLUME
    TURNOVER = TURNOVER

class StockBasicStandardColumns:
    """股票基础信息标准列名 - 用于 stock_basic 数据库表，与数据库字段完全一致"""
    STD_STOCK_CODE = STD_STOCK_CODE
    STOCK_NAME = STOCK_NAME
    PURE_SYMBOL = PURE_SYMBOL
    INDUSTRY = INDUSTRY
    MARKET = MARKET
    LIST_DATE = LIST_DATE
    DELIST_DATE = DELIST_DATE
    IS_ACTIVE = IS_ACTIVE

class StockDailyStandardColumns:
    """股票日线数据标准列名 - 用于 stock_daily 数据库表，与数据库字段完全一致，是系统内部标准"""
    STD_STOCK_CODE = STD_STOCK_CODE
    TRADE_DATE = TRADE_DATE
    OPEN = "open"
    HIGH = "high"
    LOW = "low"
    CLOSE = "close"
    PRE_CLOSE = PRE_CLOSE
    CHANGE_RATE = CHANGE_RATE
    VOLUME = VOLUME
    AMOUNT = "amount"
    TURNOVER_RATE = TURNOVER_RATE
    PE = PE
    PB = PB
    PS = PS
    PCF = PCF
    ADJUST_FLAG = ADJUST_FLAG
    TRADE_STATUS = TRADE_STATUS
    IS_ST = IS_ST

class StockXrxdStandardColumns:
    """股票分红送配标准列名 - 用于 stock_xrxd 数据库表，与数据库字段完全一致"""
    STD_STOCK_CODE = STD_STOCK_CODE
    XRXD_YEAR = XRXD_YEAR
    XRXD_PRE_NOTICE_DATE = XRXD_PRE_NOTICE_DATE
    XRXD_AGM_PUM_DATE = XRXD_AGM_PUM_DATE
    XRXD_PLAN_ANNOUNCE_DATE = XRXD_PLAN_ANNOUNCE_DATE
    XRXD_PLAN_DATE = XRXD_PLAN_DATE
    XRXD_REGIST_DATE = XRXD_REGIST_DATE
    XRXD_OPERATE_DATE = XRXD_OPERATE_DATE
    XRXD_PAY_DATE = XRXD_PAY_DATE
    XRXD_STOCK_MARKET_DATE = XRXD_STOCK_MARKET_DATE
    XRXD_CASH_PS_BEFORE_TAX = XRXD_CASH_PS_BEFORE_TAX
    XRXD_CASH_PS_AFTER_TAX = XRXD_CASH_PS_AFTER_TAX
    XRXD_STOCKS_PS = XRXD_STOCKS_PS
    XRXD_CASH_STOCK = XRXD_CASH_STOCK
    XRXD_RESERVE_TO_STOCK_PS = XRXD_RESERVE_TO_STOCK_PS
    CREATE_TIME = CREATE_TIME
    UPDATE_TIME = UPDATE_TIME

# 公司利润数据列名
PUB_DATE = "pub_date"
STAT_DATE = "stat_date"
ROE_AVG = "roe_avg"
NP_MARGIN = "np_margin"
GP_MARGIN = "gp_margin"
NET_PROFIT = "net_profit"
EPS_TTM = "eps_ttm"
MB_REVENUE = "mb_revenue"
TOTAL_SHARE = "total_share"
LIQA_SHARE = "liqa_share"

class CompanyProfitStandardColumns:
    """公司利润数据标准列名 - 用于 company_profit 数据库表，与数据库字段完全一致，是系统内部标准"""
    STD_STOCK_CODE = STD_STOCK_CODE
    PUB_DATE = PUB_DATE
    STAT_DATE = STAT_DATE
    ROE_AVG = ROE_AVG
    NP_MARGIN = NP_MARGIN
    GP_MARGIN = GP_MARGIN
    NET_PROFIT = NET_PROFIT
    EPS_TTM = EPS_TTM
    MB_REVENUE = MB_REVENUE
    TOTAL_SHARE = TOTAL_SHARE
    LIQA_SHARE = LIQA_SHARE


# 沪深300成分股数据列名
CSI300_UPDATE_DATE = "update_date"


class IndexCsi300StandardColumns:
    """沪深300成分股数据标准列名 - 用于 index_csi300_component 数据库表，与数据库字段完全一致，是系统内部标准"""
    ID = "id"
    STD_STOCK_CODE = STD_STOCK_CODE
    STOCK_NAME = STOCK_NAME
    CSI300_UPDATE_DATE = CSI300_UPDATE_DATE
    CREATE_TIME = "create_time"
    UPDATE_TIME = "update_time"
