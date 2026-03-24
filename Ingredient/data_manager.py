# data_manager.py
import pymysql
from pymysql.err import OperationalError
import pandas as pd
from datetime import datetime
from KitchenBase.download_utils import logger, calculate_pre_close

# ================= 配置区域 =================
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'ta225924',
    'database': 'ashare',
    'charset': 'utf8mb4'
}


# ================= 交易日历管理器 =================
class TradeDateMapManager:
    def __init__(self, conn):
        self.conn = conn

    def save_trade_date_map(self, df: pd.DataFrame) -> bool:
        current_func = self.save_trade_date_map.__name__
        if df.empty:
            logger.warning(f"[{current_func}] 空的交易日数据，无需保存")
            return True

        records = [
            (row['calendar_date'], row['is_trading_day'])
            for _, row in df.iterrows()
        ]

        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = """
            INSERT INTO trade_date_map (calendar_date, is_trading_day)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE is_trading_day = VALUES(is_trading_day)
            """
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.info(f"[{current_func}] 成功保存 {len(records)} 条交易日数据")
            return True
        except Exception as e:
            logger.error(f"[{current_func}] 保存失败：{e}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()


# ================= 日线数据管理器 =================
class DailyDataManager:
    def __init__(self, connection):
        self.conn = connection

    def save_daily_data(self, ts_code: str, baostock_rs) -> bool:
        current_func = self.save_daily_data.__name__
        if baostock_rs is None or baostock_rs.error_code != '0':
            logger.error(f"[{current_func}] {ts_code} 查询失败，错误码：{baostock_rs.error_code if baostock_rs else 'None'}")
            return False

        data_list = []
        while baostock_rs.next():
            data_list.append(baostock_rs.get_row_data())

        logger.info(f"[{current_func}] {ts_code} 获取到 {len(data_list)} 条日线数据")
        if not data_list:
            return True

        df = pd.DataFrame(data_list, columns=baostock_rs.fields)
        records = []

        for _, row in df.iterrows():
            try:
                trade_date = row['date']
                pre_close_val = calculate_pre_close(row['close'], row['pctChg'])
                records.append((
                    ts_code, trade_date,
                    float(row['open']) if row['open'] else None,
                    float(row['high']) if row['high'] else None,
                    float(row['low']) if row['low'] else None,
                    float(row['close']) if row['close'] else None,
                    pre_close_val,
                    float(row['pctChg']) if row['pctChg'] else None,
                    float(row['volume']) if row['volume'] else None,
                    float(row['amount']) if row['amount'] else None,
                    float(row['turn']) if row['turn'] else None,
                    float(row['peTTM']) if row['peTTM'] else None,
                    float(row['pbMRQ']) if row['pbMRQ'] else None,
                ))
            except ValueError as e:
                logger.warning(f"[{current_func}] 数据转换错误 {ts_code} {row['date']}: {e}")
                continue

        if not records:
            return True

        cursor = self.conn.cursor()
        sql = """
        INSERT INTO stock_daily 
        (ts_code, trade_date, open, high, low, close, pre_close, change_rate, volume, amount, turnover_rate, pe, pb)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            open = VALUES(open), high = VALUES(high), low = VALUES(low), close = VALUES(close),
            pre_close = VALUES(pre_close), change_rate = VALUES(change_rate), volume = VALUES(volume),
            amount = VALUES(amount), turnover_rate = VALUES(turnover_rate), pe = VALUES(pe), pb = VALUES(pb)
        """
        try:
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.debug(f"[{current_func}] {ts_code} 入库成功 {len(records)} 条")
            return True
        except Exception as e:
            logger.error(f"[{current_func}] {ts_code} 入库失败：{e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def check_date_range_exists(self, ts_code: str, start_date=None, end_date=None) -> bool:
        current_func = self.check_date_range_exists.__name__
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = "SELECT 1 FROM stock_daily WHERE ts_code = %s LIMIT 1"
            cursor.execute(sql, (ts_code,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[{current_func}] 查询失败 {ts_code}：{e}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_active_stocks(self) -> list:
        cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute("""
                SELECT ts_code FROM stock_basic 
                WHERE market IN ('主板(深A)', '主板(沪A)', '科创板', '创业板', '北交所') 
                AND is_active = 1
            """)
            return [stock['ts_code'] for stock in cursor.fetchall()]
        finally:
            cursor.close()

    def get_stock_listing_date(self, ts_code: str) -> str:
        cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute("SELECT list_date FROM stock_basic WHERE ts_code = %s", (ts_code,))
            res = cursor.fetchone()
            return res['list_date'].strftime('%Y-%m-%d') if res and res['list_date'] else None
        finally:
            cursor.close()

    def get_latest_tradedate_for_stock(self, ts_code: str) -> str:
        current_func = self.get_latest_tradedate_for_stock.__name__
        cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute("SELECT MAX(trade_date) AS latest FROM stock_daily WHERE ts_code = %s", (ts_code,))
            latest = cursor.fetchone()['latest']
            return latest.strftime('%Y-%m-%d') if latest else None
        except Exception as e:
            logger.error(f"[{current_func}] 查询失败 {ts_code}：{e}")
            return None
        finally:
            cursor.close()


# ================= 5分钟K线数据管理器 =================
class KLine5MinManager:
    def __init__(self, conn):
        self.conn = conn

    def save_kline_5min(self, stock_code: str, df: pd.DataFrame) -> bool:
        current_func = self.save_kline_5min.__name__
        if df.empty:
            logger.warning(f"[{current_func}] {stock_code} 空数据，无需保存")
            return True

        records = [
            (
                row['stock_code'], row['frequency'], row['trade_date'],
                row['trade_time'], row['raw_time'], row['open'], row['high'],
                row['low'], row['close'], row['volume'], row['amount'], row['adjustflag']
            )
            for _, row in df.iterrows()
        ]

        cursor = self.conn.cursor()
        sql = """
        INSERT INTO kline_5min 
        (stock_code, frequency, trade_date, trade_time, raw_time, open, high, low, close, volume, amount, adjustflag)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            open = VALUES(open), high = VALUES(high), low = VALUES(low), close = VALUES(close),
            volume = VALUES(volume), amount = VALUES(amount), adjustflag = VALUES(adjustflag)
        """
        try:
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.info(f"[{current_func}] {stock_code} 保存 {len(records)} 条5分钟K线成功")
            return True
        except Exception as e:
            logger.error(f"[{current_func}] {stock_code} 保存失败：{e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()


# ================= 【新增】K线下载进度管理器（独立专用） =================
class KlineDownloadProgressManager:
    def __init__(self, conn):
        self.conn = conn
        self.table = "kline_download_progress"

    def get_last_download_time(self, stock_code: str, data_type: str) -> datetime | None:
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = f"SELECT last_time FROM {self.table} WHERE stock_code = %s AND data_type = %s"
            cursor.execute(sql, (stock_code, data_type))
            res = cursor.fetchone()
            return pd.to_datetime(res[0]) if res else None
        except Exception as e:
            logger.error(f"[KlineProgress] 查询进度失败 {stock_code} {data_type}：{e}")
            raise
        finally:
            if cursor:
                cursor.close()

    def update_download_progress(self, stock_code: str, data_type: str, last_time: datetime):
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = f"""
            INSERT INTO {self.table} (stock_code, data_type, last_time)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE last_time = VALUES(last_time)
            """
            cursor.execute(sql, (stock_code, data_type, last_time))
            self.conn.commit()
            logger.debug(f"[KlineProgress] 更新进度 {stock_code} {data_type} -> {last_time}")
        except Exception as e:
            logger.error(f"[KlineProgress] 更新进度失败 {stock_code} {data_type}：{e}")
            self.conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()


# ================= 股票基础信息管理器 =================
class BasicStockDataManager:
    def __init__(self, connection):
        self.conn = connection

    def get_need_fill_detail_codes(self) -> set:
        codes = set()
        cursor = None
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT ts_code FROM stock_basic
                WHERE code_name IS NULL OR list_date IS NULL
            """)
            codes = {row[0] for row in cursor.fetchall()}
            logger.info(f"需补全信息股票数量：{len(codes)}")
        except Exception as e:
            logger.error(f"查询需补全股票失败：{e}")
        finally:
            if cursor:
                cursor.close()
        return codes

    def get_existing_stock_codes_set(self) -> set:
        current_func = self.get_existing_stock_codes_set.__name__
        cursor = self.conn.cursor(pymysql.cursors.SSCursor)
        try:
            cursor.execute("SELECT DISTINCT ts_code FROM stock_basic")
            codes = {row[0] for row in cursor.fetchall()}
            logger.debug(f"[{current_func}] 已加载 {len(codes)} 个股票代码")
            return codes
        except Exception as e:
            logger.error(f"[{current_func}] 查询失败：{e}")
            return set()
        finally:
            cursor.close()

    def batch_insert_stock_basic(self, records: list) -> bool:
        current_func = self.batch_insert_stock_basic.__name__
        if not records:
            logger.warning(f"[{current_func}] 无数据可插入")
            return True

        cursor = self.conn.cursor()
        sql = """
        INSERT INTO stock_basic 
        (ts_code, code_name, pure_symbol, industry, market, list_date, delist_date, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            code_name = VALUES(code_name), industry = VALUES(industry), market = VALUES(market),
            list_date = VALUES(list_date), delist_date = VALUES(delist_date), is_active = VALUES(is_active)
        """
        try:
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.info(f"[{current_func}] 成功插入/更新 {len(records)} 条基础信息")
            return True
        except Exception as e:
            logger.error(f"[{current_func}] 插入失败：{e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()


# ================= 全局统一入口 DataManager =================
class DataManager:
    @staticmethod
    def save_kline_5min(db_conn, stock_code: str, df: pd.DataFrame):
        return KLine5MinManager(db_conn).save_kline_5min(stock_code, df)

    @staticmethod
    def get_kline_download_progress(db_conn, stock_code: str, data_type: str) -> datetime | None:
        return KlineDownloadProgressManager(db_conn).get_last_download_time(stock_code, data_type)

    @staticmethod
    def update_kline_download_progress(db_conn, stock_code: str, data_type: str, last_time: datetime):
        return KlineDownloadProgressManager(db_conn).update_download_progress(stock_code, data_type, last_time)


# ================= 工具函数 =================
def get_existing_stock_codes_set(conn) -> set:
    return BasicStockDataManager(conn).get_existing_stock_codes_set()


def get_nearest_trade_date_before(conn, date_str: str) -> str:
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        cursor.execute("""
            SELECT calendar_date FROM trade_date_map 
            WHERE calendar_date <= %s AND is_trading_day = 1
            ORDER BY calendar_date DESC LIMIT 1
        """, (date_str,))
        res = cursor.fetchone()
        return res['calendar_date'].strftime('%Y-%m-%d') if res else date_str
    finally:
        cursor.close()

# ======================== 【升级】自动建表 + 季度分区 ========================
def create_tables_if_not_exist(conn):
    current_func = create_tables_if_not_exist.__name__
    cursor = None
    try:
        cursor = conn.cursor()

        # 1. stock_basic
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_basic (
          ts_code varchar(20) NOT NULL,
          code_name varchar(100) DEFAULT NULL,
          pure_symbol varchar(10) DEFAULT NULL,
          industry varchar(50) DEFAULT NULL,
          market varchar(20) DEFAULT NULL,
          list_date date DEFAULT NULL,
          delist_date date DEFAULT NULL,
          is_active tinyint(1) DEFAULT 1,
          create_time timestamp DEFAULT CURRENT_TIMESTAMP,
          update_time timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (ts_code),
          INDEX idx_market (market),
          INDEX idx_list_date (list_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 2. stock_daily
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_daily (
          id bigint unsigned NOT NULL AUTO_INCREMENT,
          ts_code varchar(20) NOT NULL,
          trade_date date NOT NULL,
          open decimal(10,3) DEFAULT NULL,
          high decimal(10,3) DEFAULT NULL,
          low decimal(10,3) DEFAULT NULL,
          close decimal(10,3) DEFAULT NULL,
          pre_close decimal(10,3) DEFAULT NULL,
          change_rate decimal(10,4) DEFAULT NULL,
          volume bigint DEFAULT NULL,
          amount decimal(15,2) DEFAULT NULL,
          turnover_rate decimal(10,4) DEFAULT NULL,
          pe decimal(12,2) DEFAULT NULL,
          pb decimal(10,2) DEFAULT NULL,
          create_time timestamp DEFAULT CURRENT_TIMESTAMP,
          update_time timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (id, trade_date),
          UNIQUE KEY uk_tscode_date (ts_code,trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 3. trade_date_map
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_date_map (
          calendar_date date NOT NULL,
          is_trading_day tinyint(1) DEFAULT 0,
          create_time timestamp DEFAULT CURRENT_TIMESTAMP,
          update_time timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (calendar_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 4. kline_download_progress
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kline_download_progress (
          stock_code varchar(20) NOT NULL,
          data_type varchar(30) NOT NULL,
          last_time datetime NOT NULL,
          create_time timestamp DEFAULT CURRENT_TIMESTAMP,
          update_time timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (stock_code, data_type)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 5. kline_5min 【季度分区 · 2023-2028 · 海量数据优化】
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kline_5min (
          id bigint unsigned NOT NULL AUTO_INCREMENT,
          stock_code varchar(20) NOT NULL,
          frequency int NOT NULL,
          trade_date date NOT NULL,
          trade_time datetime NOT NULL,
          raw_time varchar(20) DEFAULT NULL,
          open decimal(10,3) DEFAULT NULL,
          high decimal(10,3) DEFAULT NULL,
          low decimal(10,3) DEFAULT NULL,
          close decimal(10,3) DEFAULT NULL,
          volume bigint DEFAULT NULL,
          amount decimal(15,2) DEFAULT NULL,
          adjustflag int DEFAULT NULL,
          create_time timestamp DEFAULT CURRENT_TIMESTAMP,
          update_time timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (id, trade_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        PARTITION BY RANGE (TO_DAYS(trade_date)) (
            PARTITION p2023q1 VALUES LESS THAN (TO_DAYS('2023-04-01')),
            PARTITION p2023q2 VALUES LESS THAN (TO_DAYS('2023-07-01')),
            PARTITION p2023q3 VALUES LESS THAN (TO_DAYS('2023-10-01')),
            PARTITION p2023q4 VALUES LESS THAN (TO_DAYS('2024-01-01')),
            PARTITION p2024q1 VALUES LESS THAN (TO_DAYS('2024-04-01')),
            PARTITION p2024q2 VALUES LESS THAN (TO_DAYS('2024-07-01')),
            PARTITION p2024q3 VALUES LESS THAN (TO_DAYS('2024-10-01')),
            PARTITION p2024q4 VALUES LESS THAN (TO_DAYS('2025-01-01')),
            PARTITION p2025q1 VALUES LESS THAN (TO_DAYS('2025-04-01')),
            PARTITION p2025q2 VALUES LESS THAN (TO_DAYS('2025-07-01')),
            PARTITION p2025q3 VALUES LESS THAN (TO_DAYS('2025-10-01')),
            PARTITION p2025q4 VALUES LESS THAN (TO_DAYS('2026-01-01')),
            PARTITION p2026q1 VALUES LESS THAN (TO_DAYS('2026-04-01')),
            PARTITION p2026q2 VALUES LESS THAN (TO_DAYS('2026-07-01')),
            PARTITION p2026q3 VALUES LESS THAN (TO_DAYS('2026-10-01')),
            PARTITION p2026q4 VALUES LESS THAN (TO_DAYS('2027-01-01')),
            PARTITION p2027q1 VALUES LESS THAN (TO_DAYS('2027-04-01')),
            PARTITION p2027q2 VALUES LESS THAN (TO_DAYS('2027-07-01')),
            PARTITION p2027q3 VALUES LESS THAN (TO_DAYS('2027-10-01')),
            PARTITION p2027q4 VALUES LESS THAN (TO_DAYS('2028-01-01')),
            PARTITION p2028q1 VALUES LESS THAN (TO_DAYS('2028-04-01')),
            PARTITION p2028q2 VALUES LESS THAN (TO_DAYS('2028-07-01')),
            PARTITION p2028q3 VALUES LESS THAN (TO_DAYS('2028-10-01')),
            PARTITION p2028q4 VALUES LESS THAN (TO_DAYS('2029-01-01')),
            PARTITION p_max VALUES LESS THAN MAXVALUE
        );
        """)

        conn.commit()
        logger.info(f"[{current_func}] 所有表创建完成（kline_5min 已启用季度分区 2023~2028）")
        return True
    except Exception as e:
        logger.error(f"[{current_func}] 建表失败：{e}")
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()


def create_database_if_not_exists():
    config_no_db = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
    try:
        conn = pymysql.connect(**config_no_db)
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} DEFAULT CHARACTER SET utf8mb4")
        conn.close()
    except OperationalError as e:
        logger.error(f"连接MySQL失败：{e}")
        raise

    return pymysql.connect(**DB_CONFIG)


def create_database_and_tables():
    conn = create_database_if_not_exists()
    if create_tables_if_not_exist(conn):
        return conn
    else:
        conn.close()
        raise RuntimeError("数据库表初始化失败")