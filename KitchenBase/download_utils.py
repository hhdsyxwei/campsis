import os

import pymysql
from pymysql.err import OperationalError
from datetime import datetime, timedelta
from KitchenBase.stock_enums import MarketType
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)


print("=== download_utils 正在加载 ===")  # 看是否执行到

# ================= 配置区域 =================
# 数据库连接配置，需要根据您的实际环境进行修改
DB_CONFIG = {
    'host': os.getenv('CAMPSIS_DB_HOST', 'localhost'),             # 数据库主机地址
    'port': int(os.getenv('CAMPSIS_DB_PORT', '3306')),             # 数据库端口号
    'user': os.getenv('CAMPSIS_DB_USER', 'root'),                  # 数据库用户名
    'password': os.getenv('CAMPSIS_DB_PASSWORD', '123456'),      # 数据库密码
    'database': os.getenv('CAMPSIS_DB_NAME', 'ashare'),            # 要连接的数据库名
    'charset': os.getenv('CAMPSIS_DB_CHARSET', 'utf8mb4')          # 连接字符集，支持中文
}

if os.getenv('CAMPSIS_DB_UNIX_SOCKET'):
    DB_CONFIG['unix_socket'] = os.getenv('CAMPSIS_DB_UNIX_SOCKET')

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
    将 Baostock 代码格式 (sh.600000) 转换为 数据库格式(标准股票代码格式) (600000.SH)
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

def convert_to_baostock_code(std_stock_code: str) -> str:
    """
    将标准股票代码格式 (600000.SH) 转换为 Baostock 格式 (sh.600000)
    标准格式使用 'SH'/'SZ' 后缀，Baostock 使用 'sh.'/'sz.' 前缀。
    
    Args:
        std_stock_code: 标准股票代码，格式为 "6位代码.SH" 或 "6位代码.SZ"
        
    Returns:
        Baostock 格式的股票代码，格式为 "sh.6位代码" 或 "sz.6位代码"
    """
    func_name = "convert_to_baostock_code"
    logger.debug(f"[{func_name}] 开始转换标准股票代码，输入: {std_stock_code}")
    
    try:
        if not std_stock_code:
            logger.warning(f"[{func_name}] 输入为空，返回空字符串")
            return ""
        
        parts = std_stock_code.split('.')
        if len(parts) != 2:
            logger.warning(f"[{func_name}] 输入格式不正确: {std_stock_code}，期望格式为 '代码.市场'，返回原输入")
            return std_stock_code
        
        symbol, market = parts
        market = market.upper()
        
        market_map = {'SH': 'sh', 'SZ': 'sz', 'BJ': 'bj'}
        if market not in market_map:
            logger.warning(f"[{func_name}] 不支持的市场类型: {market}，支持的类型: {list(market_map.keys())}，返回原输入")
            return std_stock_code
        
        result = f"{market_map[market]}.{symbol}"
        logger.debug(f"[{func_name}] 转换成功: {std_stock_code} -> {result}")
        return result
        
    except Exception as e:
        logger.error(f"[{func_name}] 转换过程发生异常: {str(e)}", exc_info=True)
        import traceback
        logger.error(f"[{func_name}] 完整调用栈: {traceback.format_exc()}")
        return std_stock_code

def calculate_pre_close(close_price, change_rate) -> float:
    """
    根据收盘价和涨跌幅计算昨收价。
    公式: close = pre_close * (1 + pctChg / 100)，则 pre_close = close / (1 + pctChg / 100)
    
    Args:
        close_price: 收盘价（可以是字符串或浮点数）
        change_rate: 涨跌幅（可以是字符串或浮点数，百分比）
        
    Returns:
        计算得到的昨收价
        
    Raises:
        ValueError: 当输入参数为空或无法转换为浮点数时
        ZeroDivisionError: 当涨跌幅为 -100% 时
    """
    if close_price is None:
        raise ValueError("收盘价不能为空")
    if change_rate is None:
        raise ValueError("涨跌幅不能为空")
    
    # 处理空字符串情况
    if isinstance(close_price, str) and not close_price.strip():
        raise ValueError("收盘价不能为空")
    if isinstance(change_rate, str) and not change_rate.strip():
        raise ValueError("涨跌幅不能为空")
    
    try:
        close_val = float(close_price)
        change_rate_val = float(change_rate)
        
        if change_rate_val == -100:
            raise ZeroDivisionError("涨跌幅不能为 -100%，否则会导致除以零")
            
        pre_close_val = close_val / (1 + change_rate_val / 100.0)
        return round(pre_close_val, 2)
    except ValueError as e:
        raise ValueError(f"输入参数格式错误: {e}")

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
