import pytest
import sqlite3
from KitchenBase.stock_enums import KLinePeriod

# -------------- 全局夹具：模拟数据库连接 --------------
@pytest.fixture(scope="session")
def mock_db_conn():
    """
    模拟数据库连接（使用SQLite内存库，避免污染真实数据）
    作用域：session（整个测试会话仅创建一次）
    """
    conn = sqlite3.connect(":memory:")
    # 初始化测试所需表结构（简化版）
    cursor = conn.cursor()
    # 1. 股票上市时间表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_listing (
            std_stock_code TEXT PRIMARY KEY,
            listing_date TEXT,
            delist_date TEXT
        )
    """)
    # 2. K线区块状态表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS kline_block_status (
            std_stock_code TEXT,
            time_frame TEXT,
            quarter TEXT,
            status TEXT,
            PRIMARY KEY (std_stock_code, time_frame, quarter)
        )
    """)
    # 3. 股票固定顺序表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_fixed_seq (
            std_stock_code TEXT PRIMARY KEY,
            seq_num INTEGER
        )
    """)
    # 插入测试数据
    cursor.execute("INSERT INTO stock_listing VALUES ('sh.600000', '2000-01-01', NULL)")
    cursor.execute("INSERT INTO stock_fixed_seq VALUES ('sh.600000', 1)")
    conn.commit()
    yield conn
    conn.close()

# -------------- 全局夹具：K线周期枚举 --------------
@pytest.fixture(scope="function")
def mock_time_frame():
    """模拟K线周期（5分钟）"""
    return KLinePeriod.MIN_5

# -------------- 全局夹具：测试用季度 --------------
@pytest.fixture(scope="function")
def mock_quarter():
    """测试用季度"""
    return "2024-Q1"