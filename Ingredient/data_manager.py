# data_manager.py
import pymysql
from pymysql.err import OperationalError
import pandas as pd
from datetime import datetime
from KitchenBase.download_utils import calculate_pre_close
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

# ================= 配置区域 =================
DB_CONFIG = {
    'host': 'localhost',
    'port': 3306,
    'user': 'root',
    'password': 'ta225924',
    'database': 'ashare',
    'charset': 'utf8mb4'
}

# ================= K线统一表管理器 =================
class KLineUnifiedQuarterlyExtendedManager:
    def __init__(self, conn):
        self.conn = conn

    def save_kline_data_unified(self, stock_code: str, df: pd.DataFrame) -> bool:
        """
        保存统一格式的K线数据
        
        Args:
            stock_code: 股票代码
            df: K线数据，包含time_frame, timestamp等字段
        
        Returns:
            保存是否成功
        """
        func_name = "save_kline_data_unified"
        logger.info(f"[{__name__}.{func_name}] 开始保存 {len(df)} 条统一格式K线数据 for {stock_code}")
        
        cursor = None
        try:
            # 准备数据
            records = []
            for _, row in df.iterrows():
                records.append((
                    stock_code,
                    row['time_frame'],
                    row['timestamp'],
                    row['open_price'],
                    row['high_price'],
                    row['low_price'],
                    row['close_price'],
                    row['volume'],
                    row['turnover']
                ))
            
            # 执行批量插入
            sql = """
            INSERT INTO kline_unified_quarterly_extended 
            (stock_code, time_frame, timestamp, open_price, high_price, low_price, close_price, volume, turnover)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                open_price = VALUES(open_price), 
                high_price = VALUES(high_price), 
                low_price = VALUES(low_price), 
                close_price = VALUES(close_price),
                volume = VALUES(volume),
                turnover = VALUES(turnover),
                updated_at = CURRENT_TIMESTAMP
            """
            cursor = self.conn.cursor()
            cursor.executemany(sql, records)
            self.conn.commit()
            
            logger.info(f"[{__name__}.{func_name}] 成功保存 {len(records)} 条K线数据 for {stock_code}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 保存数据失败 for {stock_code}: {str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def get_kline_download_status(self, stock_code: str, time_frame: str, quarter: str) -> str:
        """
        获取K线下载状态
        
        Args:
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            状态字符串: 'completed' 或 'not_completed'
        """
        func_name = "get_kline_download_status"
        logger.debug(f"[{__name__}.{func_name}] 查询 {stock_code} {time_frame} {quarter} 的下载状态")
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            query = """
            SELECT status FROM kline_download_progress 
            WHERE stock_code = %s AND time_frame = %s AND quarter = %s
            """
            cursor.execute(query, (stock_code, time_frame, quarter))
            result = cursor.fetchone()
            
            if result:
                return result[0]
            else:
                return None  # 表示记录不存在
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询状态失败: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()

    def update_kline_download_progress_unified(self, stock_code: str, time_frame: str, quarter: str, status: str):
        """
        更新K线下载进度（统一格式）
        
        Args:
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
            status: 状态，'completed' 或 'not_completed'
        """
        func_name = "update_kline_download_progress_unified"
        logger.debug(f"[{__name__}.{func_name}] 更新 {stock_code} {time_frame} {quarter} 的状态为: {status}")
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            # 使用INSERT ... ON DUPLICATE KEY UPDATE来处理记录存在与否的情况
            query = """
            INSERT INTO kline_download_progress (stock_code, time_frame, quarter, status, completed_at) 
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            status = VALUES(status),
            completed_at = CASE 
                WHEN VALUES(status) = 'completed' THEN VALUES(completed_at) 
                ELSE completed_at 
            END
            """

            completed_at = datetime.now() if status == 'completed' else None
            cursor.execute(query, (stock_code, time_frame, quarter, status, completed_at))
            self.conn.commit()
            
            logger.debug(f"[{__name__}.{func_name}] {stock_code} {time_frame} {quarter} 的状态已更新为: {status}")
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 更新进度失败: {str(e)}")
            self.conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()

    def get_quarter_data_count(self, stock_code: str, time_frame: str, quarter: str) -> int:
        """
        获取指定股票、时间周期和季度的数据条数
        
        Args:
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            数据条数
        """
        func_name = "get_quarter_data_count"
        logger.debug(f"[{__name__}.{func_name}] 查询 {stock_code} {time_frame} {quarter} 的数据条数")
        
        # 解析季度得到日期范围
        year, q = quarter.split('-Q')
        q = int(q)
        
        start_month = (q - 1) * 3 + 1
        end_month = q * 3
        
        # 计算季度的第一天和最后一天
        if q == 1:
            start_date = f"{year}-01-01"
            end_date = f"{year}-03-31"
        elif q == 2:
            start_date = f"{year}-04-01"
            end_date = f"{year}-06-30"
        elif q == 3:
            start_date = f"{year}-07-01"
            end_date = f"{year}-09-30"
        else:  # q == 4
            start_date = f"{year}-10-01"
            end_date = f"{year}-12-31"
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = """
            SELECT COUNT(*) FROM kline_unified_quarterly_extended 
            WHERE stock_code = %s AND time_frame = %s 
            AND timestamp >= %s AND timestamp <= %s
            """
            cursor.execute(sql, (stock_code, time_frame, start_date, end_date))
            count = cursor.fetchone()[0]
            
            logger.debug(f"[{__name__}.{func_name}] {stock_code} {time_frame} {quarter} 的数据条数: {count}")
            return count
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询数据条数失败: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()


# ================= 交易日历管理器 =================
class TradeDateMapManager:
    def __init__(self, conn):
        self.conn = conn

    def save_trade_date_map(self, df: pd.DataFrame) -> bool:
        func_name = "save_trade_date_map"
        if df.empty:
            logger.warning(f"[{__name__}.{func_name}] 空的交易日数据，无需保存")
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
            logger.info(f"[{__name__}.{func_name}] 成功保存 {len(records)} 条交易日数据")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 保存失败：{str(e)}")
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
        func_name = "save_daily_data"
        if baostock_rs is None or baostock_rs.error_code != '0':
            err_code = baostock_rs.error_code if baostock_rs else 'None'
            logger.error(f"[{__name__}.{func_name}] {ts_code} 查询失败，错误码：{err_code}")
            return False

        data_list = []
        while baostock_rs.next():
            data_list.append(baostock_rs.get_row_data())

        logger.info(f"[{__name__}.{func_name}] {ts_code} 获取到 {len(data_list)} 条日线数据")
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
                logger.warning(f"[{__name__}.{func_name}] 数据转换错误 {ts_code} {row['date']}: {str(e)}")
                continue

        if not records:
            return True

        cursor = None
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
            cursor = self.conn.cursor()
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.debug(f"[{__name__}.{func_name}] {ts_code} 入库成功 {len(records)} 条")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] {ts_code} 入库失败：{str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def check_date_range_exists(self, ts_code: str, start_date=None, end_date=None) -> bool:
        func_name = "check_date_range_exists"
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = "SELECT 1 FROM stock_daily WHERE ts_code = %s LIMIT 1"
            cursor.execute(sql, (ts_code,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败 {ts_code}：{str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_active_stocks(self) -> list:
        func_name = "get_active_stocks"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT ts_code FROM stock_basic 
                WHERE market IN ('主板(深A)', '主板(沪A)', '科创板', '创业板', '北交所') 
                AND is_active = 1
            """)
            return [stock['ts_code'] for stock in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败：{str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_stock_listing_date(self, ts_code: str) -> str:
        func_name = "get_stock_listing_date"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT list_date FROM stock_basic WHERE ts_code = %s", (ts_code,))
            res = cursor.fetchone()
            return res['list_date'].strftime('%Y-%m-%d') if res and res['list_date'] else None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败 {ts_code}：{str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def get_latest_tradedate_for_stock(self, ts_code: str) -> str:
        func_name = "get_latest_tradedate_for_stock"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT MAX(trade_date) AS latest FROM stock_daily WHERE ts_code = %s", (ts_code,))
            latest = cursor.fetchone()['latest']
            return latest.strftime('%Y-%m-%d') if latest else None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败 {ts_code}：{str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()


# ================= 股票基础信息管理器 =================
class BasicStockDataManager:
    def __init__(self, connection):
        self.conn = connection

    def get_need_fill_detail_codes(self) -> set:
        func_name = "get_need_fill_detail_codes"
        codes = set()
        cursor = None
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT ts_code FROM stock_basic
                WHERE code_name IS NULL OR list_date IS NULL
            """)
            codes = {row[0] for row in cursor.fetchall()}
            logger.info(f"[{__name__}.{func_name}] 需补全信息股票数量：{len(codes)}")
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败：{str(e)}")
        finally:
            if cursor:
                cursor.close()
        return codes

    def get_existing_stock_codes_set(self) -> set:
        func_name = "get_existing_stock_codes_set"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.SSCursor)
            cursor.execute("SELECT DISTINCT ts_code FROM stock_basic")
            codes = {row[0] for row in cursor.fetchall()}
            logger.debug(f"[{__name__}.{func_name}] 已加载 {len(codes)} 个股票代码")
            return codes
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败：{str(e)}")
            return set()
        finally:
            if cursor:
                cursor.close()

    def get_all_active_stock_codes(self) -> list:
        """
        通过stock_basic表获取所有活跃股票代码
        
        Returns:
            list: 所有活跃股票代码列表
        """
        func_name = "get_all_active_stock_codes"
        cursor = None
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT ts_code 
                FROM stock_basic 
                WHERE is_active = 1
                  AND market IN ('主板(深A)', '主板(沪A)', '科创板', '创业板', '北交所')
            """)
            active_codes = [row[0] for row in cursor.fetchall()]
            logger.info(f"[{__name__}.{func_name}] 查询到 {len(active_codes)} 个活跃股票代码")
            return active_codes
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询活跃股票代码失败：{str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    def batch_insert_stock_basic(self, records: list) -> bool:
        func_name = "batch_insert_stock_basic"
        if not records:
            logger.warning(f"[{__name__}.{func_name}] 无数据可插入")
            return True

        cursor = None
        sql = """
        INSERT INTO stock_basic 
        (ts_code, code_name, pure_symbol, industry, market, list_date, delist_date, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            -- 只更新代码、市场、状态，不覆盖已存在的名称/上市日/行业
            pure_symbol = VALUES(pure_symbol),
            market = VALUES(market),
            is_active = VALUES(is_active)
        """
        try:
            cursor = self.conn.cursor()
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.info(f"[{__name__}.{func_name}] 成功插入/更新 {len(records)} 条基础信息")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 插入失败：{str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()


# ================= 全局统一入口 DataManager =================
class DataManager:
    @staticmethod
    def save_kline_data_unified(db_conn, stock_code: str, df: pd.DataFrame) -> bool:
        """
        保存统一格式的K线数据
        
        Args:
            db_conn: 数据库连接
            stock_code: 股票代码
            df: K线数据，包含time_frame, timestamp等字段
        
        Returns:
            保存是否成功
        """
        func_name = "save_kline_data_unified"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.save_kline_data_unified(stock_code, df)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return False

    @staticmethod
    def get_kline_download_status(db_conn, stock_code: str, time_frame: str, quarter: str) -> str:
        """
        获取K线下载状态
        
        Args:
            db_conn: 数据库连接
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            状态字符串: 'completed' 或 'not_completed'
        """
        func_name = "get_kline_download_status"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.get_kline_download_status(stock_code, time_frame, quarter)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return 'not_completed'

    @staticmethod
    def update_kline_download_progress_unified(db_conn, stock_code: str, time_frame: str, quarter: str, status: str):
        """
        更新K线下载进度（统一格式）
        
        Args:
            db_conn: 数据库连接
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
            status: 状态，'completed' 或 'not_completed'
        """
        func_name = "update_kline_download_progress_unified"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.update_kline_download_progress_unified(stock_code, time_frame, quarter, status)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return None

    @staticmethod
    def get_quarter_data_count(db_conn, stock_code: str, time_frame: str, quarter: str) -> int:
        """
        获取指定股票、时间周期和季度的数据条数
        
        Args:
            db_conn: 数据库连接
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            数据条数
        """
        func_name = "get_quarter_data_count"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.get_quarter_data_count(stock_code, time_frame, quarter)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return 0

    @staticmethod
    def get_all_active_stock_codes(db_conn) -> list:
        """
        通过stock_basic表获取所有活跃股票代码
        
        Args:
            db_conn: 数据库连接
        
        Returns:
            list: 所有活跃股票代码列表
        """
        func_name = "get_all_active_stock_codes"
        try:
            manager = BasicStockDataManager(db_conn)
            return manager.get_all_active_stock_codes()
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return []


# ================= 工具函数 =================
def get_existing_stock_codes_set(conn) -> set:
    func_name = "get_existing_stock_codes_set"
    try:
        return BasicStockDataManager(conn).get_existing_stock_codes_set()
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] 失败：{str(e)}")
        return set()


def get_all_active_stock_codes(conn) -> list:
    """
    通过stock_basic表获取所有活跃股票代码
    
    Args:
        conn: 数据库连接
    
    Returns:
        list: 所有活跃股票代码列表
    """
    func_name = "get_all_active_stock_codes"
    try:
        return BasicStockDataManager(conn).get_all_active_stock_codes()
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] 失败：{str(e)}")
        return []


def get_nearest_trade_date_before(conn, date_str: str) -> str:
    func_name = "get_nearest_trade_date_before"
    cursor = None
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT calendar_date FROM trade_date_map 
            WHERE calendar_date <= %s AND is_trading_day = 1
            ORDER BY calendar_date DESC LIMIT 1
        """, (date_str,))
        res = cursor.fetchone()
        return res['calendar_date'].strftime('%Y-%m-%d') if res else date_str
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] 查询失败：{str(e)}")
        return date_str
    finally:
        if cursor:
            cursor.close()


# ================= 自动建表 =================
def create_tables_if_not_exist(conn):
    func_name = "create_tables_if_not_exist"
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

        # 4. kline_download_progress - 修正表结构
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kline_download_progress (
          stock_code varchar(20) NOT NULL,
          time_frame varchar(30) NOT NULL,
          quarter varchar(10) NOT NULL,
          status varchar(20) DEFAULT 'not_completed',
          completed_at datetime NULL,
          create_time timestamp DEFAULT CURRENT_TIMESTAMP,
          update_time timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (stock_code, time_frame, quarter)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 5. kline_unified_quarterly_extended - 新增表
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kline_unified_quarterly_extended (
          id bigint unsigned NOT NULL AUTO_INCREMENT,
          stock_code varchar(20) NOT NULL,
          time_frame varchar(30) NOT NULL,
          timestamp datetime NOT NULL,
          open_price decimal(10,3) DEFAULT NULL,
          high_price decimal(10,3) DEFAULT NULL,
          low_price decimal(10,3) DEFAULT NULL,
          close_price decimal(10,3) DEFAULT NULL,
          volume bigint DEFAULT NULL,
          turnover decimal(15,2) DEFAULT NULL,
          create_time timestamp DEFAULT CURRENT_TIMESTAMP,
          updated_at timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (id, timestamp),
          UNIQUE KEY uk_stock_timeframe_timestamp (stock_code, time_frame, timestamp),
          INDEX idx_stock_code (stock_code),
          INDEX idx_time_frame (time_frame),
          INDEX idx_timestamp (timestamp)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        PARTITION BY RANGE (TO_DAYS(timestamp)) (
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
        logger.info(f"[{__name__}.{func_name}] 所有表创建完成（kline_unified_quarterly_extended 已启用季度分区）")
        return True
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] 建表失败：{str(e)}")
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()


def create_database_if_not_exists():
    func_name = "create_database_if_not_exists"
    config_no_db = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
    try:
        conn = pymysql.connect(**config_no_db)
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} DEFAULT CHARACTER SET utf8mb4")
        conn.close()
        logger.info(f"[{__name__}.{func_name}] 数据库确认完成")
    except OperationalError as e:
        logger.error(f"[{__name__}.{func_name}] 连接MySQL失败：{str(e)}")
        raise
    return pymysql.connect(**DB_CONFIG)


def create_database_and_tables():
    func_name = "create_database_and_tables"
    try:
        conn = create_database_if_not_exists()
        if create_tables_if_not_exist(conn):
            logger.info(f"[{__name__}.{func_name}] ✅ 数据库初始化全部完成")
            return conn
        else:
            conn.close()
            raise RuntimeError("数据库表初始化失败")
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] ❌ 数据库初始化失败：{str(e)}")
        raise 
