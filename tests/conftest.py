import pytest
import pymysql
from KitchenBase.stock_enums import KLinePeriod
from Ingredient.DataNest import DB_CONFIG

# -------------- 全局夹具：测试数据库连接 --------------
@pytest.fixture(scope="session")
def mock_db_conn():
    """
    测试数据库连接（使用测试数据库，避免污染生产数据）
    作用域：session（整个测试会话仅创建一次）
    """
    # 使用测试数据库配置
    test_config = DB_CONFIG.copy()
    test_db_name = 'ashare_test'

    # 先连接到MySQL服务器（不指定数据库）
    admin_config = test_config.copy()
    admin_config.pop('database', None)
    admin_conn = pymysql.connect(**admin_config)

    try:
        # 创建测试数据库
        with admin_conn.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {test_db_name}")
        admin_conn.commit()
    finally:
        admin_conn.close()

    # 连接到测试数据库
    test_config['database'] = test_db_name
    conn = pymysql.connect(**test_config)

    try:
        # 初始化测试所需表结构
        cursor = conn.cursor()

        # 1. 股票上市时间表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_listing (
                std_stock_code VARCHAR(10) PRIMARY KEY,
                listing_date DATE,
                delist_date DATE
            )
        """)

        # 2. K线区块状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kline_block_status (
                std_stock_code VARCHAR(10),
                time_frame VARCHAR(10),
                quarter VARCHAR(10),
                status VARCHAR(20),
                completed_at DATETIME,
                PRIMARY KEY (std_stock_code, time_frame, quarter)
            )
        """)

        # 3. 股票固定顺序表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_fixed_seq (
                id INT AUTO_INCREMENT PRIMARY KEY,
                std_stock_code VARCHAR(10) UNIQUE
            )
        """)

        # 4. 全局下载进度表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS global_download_progress (
                id TINYINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                task_type VARCHAR(20) UNIQUE,
                primary_pointer_name VARCHAR(50),
                primary_pointer_value VARCHAR(50),
                secondary_pointer_name VARCHAR(50),
                secondary_pointer_value VARCHAR(50),
                tertiary_pointer_name VARCHAR(50),
                tertiary_pointer_value VARCHAR(50),
                update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        # 5. 分红送配数据表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_xrxd (
                id INT AUTO_INCREMENT PRIMARY KEY,
                std_stock_code VARCHAR(10),
                xrxd_year INT,
                xrxd_pre_notice_date DATE,
                xrxd_agm_pum_date DATE,
                xrxd_plan_announce_date DATE,
                xrxd_plan_date DATE,
                xrxd_regist_date DATE,
                xrxd_operate_date DATE,
                xrxd_pay_date DATE,
                xrxd_stock_market_date DATE,
                xrxd_cash_ps_before_tax DECIMAL(10,4),
                xrxd_cash_ps_after_tax DECIMAL(10,4),
                xrxd_stocks_ps DECIMAL(10,4),
                xrxd_cash_stock VARCHAR(50),
                xrxd_reserve_to_stock_ps DECIMAL(10,4),
                create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uk_stock_year (std_stock_code, xrxd_year)
            )
        """)

        # 清空测试数据
        cursor.execute("TRUNCATE TABLE stock_listing")
        cursor.execute("TRUNCATE TABLE stock_fixed_seq")
        cursor.execute("TRUNCATE TABLE global_download_progress")
        cursor.execute("TRUNCATE TABLE stock_xrxd")
        cursor.execute("TRUNCATE TABLE kline_block_status")

        # 插入测试数据
        cursor.execute("INSERT INTO stock_listing VALUES ('sh.600000', '2000-01-01', NULL)")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600000')")

        conn.commit()
        yield conn
    finally:
        # 清理测试数据
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE stock_listing")
        cursor.execute("TRUNCATE TABLE stock_fixed_seq")
        cursor.execute("TRUNCATE TABLE global_download_progress")
        cursor.execute("TRUNCATE TABLE stock_xrxd")
        cursor.execute("TRUNCATE TABLE kline_block_status")
        conn.commit()
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
