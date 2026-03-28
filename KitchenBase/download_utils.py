# download_utils.py
import os

import pymysql
from pymysql.err import OperationalError
from datetime import datetime, timedelta
from KitchenBase.stock_enums import MarketType


print("=== download_utils 正在加载 ===")  # 看是否执行到

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

# ================= 工具函数 =================

def get_project_root() -> str:
    """
    获取项目根目录的绝对路径。
    这个函数假设 download_utils.py 位于项目的某个子目录下，通过向上遍历目录来找到根目录。
    """
    current_file_path = os.path.abspath(__file__)
    project_root = os.path.dirname(os.path.dirname(current_file_path))
    return project_root

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