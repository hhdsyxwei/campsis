# download_utils.py
import pymysql
from pymysql.err import OperationalError
import logging
from datetime import datetime, timedelta
from enum import Enum # 导入 Enum

# ================= 配置区域 =================
# 数据库连接配置，需要根据您的实际环境进行修改
DB_CONFIG = {
    'host': 'localhost',         # 数据库主机地址
    'port': 3306,                # 数据库端口号
    'user': 'root',              # 数据库用户名
    'password': 'ta225924',      # 数据库密码
    'database': 'ashare',        # 要连接的数据库名
    'charset': 'utf8mb4'         # 连接字符集，支持中文
}

# 配置日志系统，将信息同时输出到控制台和文件
logging.basicConfig(
    level=logging.DEBUG,  # 设置日志级别为 DEBUG
    format='%(asctime)s - %(levelname)s - %(message)s',  # 日志输出格式
    handlers=[
        # ✅ 强制 UTF-8 写入日志文件
        logging.FileHandler("stock_download.log", encoding='utf-8'),  # 写入日志到文件
        logging.StreamHandler()                     # 同时输出到控制台
    ]
)
logger = logging.getLogger(__name__)

# ================= 枚举定义 =================

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

# ================= 工具函数 =================

def create_database_if_not_exists():
    """
    自动创建 ashare 数据库（如果不存在），然后返回数据库连接
    全程使用你现有的 DB_CONFIG，无需修改配置
    """
    # ---------------------- 第一步：先连接 MySQL 服务，不指定库 ----------------------
    # 复制配置并临时去掉 database，避免“找不到库”报错
    config_no_db = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
    
    try:
        conn = pymysql.connect(**config_no_db)
        with conn.cursor() as cursor:
            # 自动创建库（不存在才创建）
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} DEFAULT CHARACTER SET utf8mb4")
        conn.close()

    except OperationalError as e:
        print(f"❌ 连接 MySQL 服务失败：{e}")
        raise

    # ---------------------- 第二步：使用完整配置连接 ashare 库 ----------------------
    try:
        db_conn = pymysql.connect(**DB_CONFIG)
        print("✅ 成功连接到 ashare 数据库")
        return db_conn

    except OperationalError as e:
        print(f"❌ 连接 ashare 失败：{e}")
        raise

def convert_baostock_code(bs_code: str) -> str:
    """
    将 Baostock 代码格式 (sh.600000) 转换为 数据库格式 (600000.SH)
    Baostock 使用 'sh.'/'sz.' 前缀，数据库使用 'SH'/'SZ' 后缀。
    """
    if not bs_code:
        return ""
    parts = bs_code.split('.')
    if len(parts) != 2:
        return bs_code
    market, symbol = parts
    market_map = {'sh': 'SH', 'sz': 'SZ'}
    return f"{symbol}.{market_map.get(market.lower(), market.upper())}"

def calculate_pre_close(close_price_str: str, change_rate_str: str) -> float:
    """
    根据收盘价和涨跌幅计算昨收价。
    公式: close = pre_close * (1 + pctChg / 100)，则 pre_close = close / (1 + pctChg / 100)
    """
    try:
        close_val = float(close_price_str) if close_price_str else None
        change_rate_val = float(change_rate_str) if change_rate_str else None
        if close_val is not None and change_rate_val is not None and change_rate_val != -100:
            pre_close_val = close_val / (1 + change_rate_val / 100.0)
            return round(pre_close_val, 2)
    except (ValueError, ZeroDivisionError):
        pass
    return None

def baostock_code_to_market(baostock_code: str) -> MarketType:
    if not baostock_code:
        return MarketType.UNKNOWN

    parts = baostock_code.lower().split('.')
    if len(parts) != 2:
        return MarketType.UNKNOWN
    
    exchange, symbol = parts

    # ========== 上海市场 ==========
    if exchange == 'sh':
        if symbol.startswith(('51', '52', '53', '56', '58')):
            return MarketType.ETF
        elif symbol.startswith('501'):
            return MarketType.LOF
        elif symbol.startswith('508'):
            return MarketType.REIT
        elif symbol.startswith(('000', '950', '930', '980', '990')):
            return MarketType.INDEX
        elif symbol.startswith('900'):
            return MarketType.SH_B_STOCK
        elif symbol.startswith('688'):
            return MarketType.STAR_MARKET
        elif symbol.startswith(('600', '601', '603', '605')):
            return MarketType.SH_MAIN_BOARD
        else:
            return MarketType.UNKNOWN

    # ========== 深圳市场 ==========
    elif exchange == 'sz':
        if symbol.startswith(('159', '161', '162')):
            return MarketType.ETF
        elif symbol.startswith('16'):
            return MarketType.LOF
        elif symbol.startswith('180'):
            return MarketType.REIT
        elif symbol.startswith('399'):
            return MarketType.INDEX
        elif symbol.startswith(('300', '301', '302', '303')):
            return MarketType.CHI_NEXT
        elif symbol.startswith('12'):
            return MarketType.CONVERTIBLE_BOND
        elif symbol.startswith('200'):
            return MarketType.SZ_B_STOCK
        elif symbol.startswith(('000', '001', '002', '003', '004', '005', '006')):
            return MarketType.SZ_MAIN_BOARD
        else:
            return MarketType.UNKNOWN

    # ========== 北交所 ==========
    elif exchange == 'bj':
        if symbol.startswith(('83', '87', '88', '43')):
            return MarketType.BSE
        else:
            return MarketType.UNKNOWN

    else:
        return MarketType.UNKNOWN