from enum import Enum


class KLinePeriod(Enum):
    """
    K线周期类型枚举（标准金融行业命名）
    包含：分时、分钟线、日线、周线、月线、季度线、年线等
    """
    # 分时
    TIME_LINE = "time_line"

    # 分钟级 K 线
    MIN_1 = "1m"
    MIN_5 = "5m"
    MIN_15 = "15m"
    MIN_30 = "30m"
    MIN_60 = "60m"

    # 日级别
    DAILY = "1d"
    WEEKLY = "1w"
    MONTHLY = "1Month"

    # 季度 / 年度
    QUARTERLY = "1q"
    YEARLY = "1y"


class AdjustType(Enum):
    """
    股票复权类型枚举
    用于K线数据是否复权、前复权 / 后复权
    """
    NONE = "none"          # 不复权
    FORWARD = "forward"    # 前复权（常用）
    BACKWARD = "backward"  # 后复权



class MarketType(Enum):
    """定义股票/证券的市场类型枚举。"""
    # 主板
    SH_MAIN_BOARD = "主板(沪A)"           # 沪市主板
    SZ_MAIN_BOARD = "主板(深A)"           # 深市主板

    # 创业板 / 科创板 / 北交所
    STAR_MARKET = "科创板(沪A)"           # 科创板Star Market
    CHI_NEXT = "创业板(深A)"              # 创业板ChiNext
    BSE = "北交所"                       # 北京证券交易所

    # B股
    SH_B_STOCK = "B股(沪市)"              # 上海B股
    SZ_B_STOCK = "B股(深市)"              # 深圳B股

    # 可转债
    CONVERTIBLE_BOND = "可转债"           # 可转换公司债券

    # 基金 / ETF
    ETF = "ETF"                          # ETF基金
    LOF = "LOF基金"                      # LOF基金
    FUND = "场外基金"                    # 其他基金

    # 指数
    INDEX = "指数"                       # 股票指数

    # REITs
    REIT = "公募REITs"                   # 基础设施公募REITs

    # 无法识别
    UNKNOWN = "未知"                     # 无法识别的类型


class DataSource(Enum):
    """
    数据源枚举（方便扩展多数据源）
    """
    TUSHARE = "tushare"
    AK_SHARE = "akshare"
    JOIN_QUANT = "join_quant"
    LOCAL = "local"


