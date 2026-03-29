# data_manager.py
import os
from typing import List, Optional, Tuple, Dict
import pymysql
from pymysql.err import OperationalError
import pandas as pd
from datetime import datetime

from KitchenBase.download_utils import calculate_pre_close
from KitchenBase.logger_config import get_logger
from KitchenBase.download_utils import get_project_root
from KitchenBase.stock_enums import KLinePeriod

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

    def set_downloading_block(self, stock_code: str, time_frame: KLinePeriod, quarter: str) -> bool:
        """
        设置当前下载的区块信息（更新kline_download_progress表）
        Args:
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            设置是否成功
        """
        func_name = "set_downloading_block"
        logger.debug(f"[{__name__}.{func_name}] 开始设置下载区块: {stock_code} {time_frame.value} {quarter}")
        
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            # 使用 INSERT ... ON DUPLICATE KEY UPDATE 处理记录存在/不存在的情况
            cursor.execute("""
                INSERT INTO kline_download_progress 
                (id, downloading_stock_code, downloading_time_frame, downloading_quarter, update_time)
                VALUES (1, %s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    downloading_stock_code = VALUES(downloading_stock_code),
                    downloading_time_frame = VALUES(downloading_time_frame),
                    downloading_quarter = VALUES(downloading_quarter),
                    update_time = CURRENT_TIMESTAMP
            """, (stock_code, time_frame.value, quarter))
            
            self.conn.commit()
            logger.info(f"[{__name__}.{func_name}] 成功设置下载区块: {stock_code} {time_frame.value} {quarter}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 设置下载区块失败: {str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    # 通过kline_download_progress表获取当前下载的区块信息（股票代码、时间周期、季度）
    def get_downloading_block(self) -> Optional[Tuple[str, str, KLinePeriod]]:
        func_name = "get_downloading_block"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT downloading_stock_code, downloading_time_frame, downloading_quarter 
                FROM kline_download_progress 
                WHERE id = 1 
                LIMIT 1
            """)
            result = cursor.fetchone()
            if result:
                logger.debug(f"[{__name__}.{func_name}] 当前下载区块: {result}")
                return result['downloading_quarter'], result['downloading_stock_code'], KLinePeriod(result['downloading_time_frame'])
            else:
                logger.debug(f"[{__name__}.{func_name}] 无正在下载的区块")
                return None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询下载区块失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def get_next_stock_in_fixed_seq(self, current_stock_code: Optional[str]) -> Optional[str]:
        """
        获取固定序列中的下一只股票代码（按stock_fixed_seq表自增id排序）
        Args:
            current_stock_code: 当前股票代码，None表示获取第一只

        Returns:
            下一只股票代码 | None（无数据/已是最后一只）
        """
        func_name = "get_next_stock_in_fixed_seq"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)

            # ==============================================
            # 🔥 一条 SQL 搞定所有场景：性能最优
            # ==============================================
            sql = """
                SELECT stock_code
                FROM stock_fixed_seq
                WHERE
                    -- 传入 None：取所有数据
                    (%s IS NULL)
                    OR
                    -- 传入股票代码：取 id 比当前大的
                    id > (SELECT id FROM stock_fixed_seq WHERE stock_code = %s)
                ORDER BY id ASC
                LIMIT 1
            """
            cursor.execute(sql, (current_stock_code, current_stock_code))
            result = cursor.fetchone()

            if result:
                logger.debug(f"[{__name__}.{func_name}] 获取到下一只股票: {result['stock_code']}")
                return result['stock_code']
            else:
                logger.debug(f"[{__name__}.{func_name}] 无下一只股票 / 表为空，返回None")
                return None

        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 获取下一只股票失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

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

            if records and len(records) > 2:
                logger.debug(f"第1条记录示例: {records[0] if records else '无数据'}")
                logger.debug(f"第2条记录示例: {records[1] if len(records) > 1 else '无数据'}")
                logger.debug(f"第3条记录示例: {records[2] if len(records) > 2 else '无数据'}")
            
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
                update_time = CURRENT_TIMESTAMP
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

    def get_kline_block_status(self, stock_code: str, time_frame: KLinePeriod, quarter: str) -> str:
        """
        获取K线下载状态
        
        Args:
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            状态字符串: 'completed' 或 'not_completed'
        """
        func_name = "get_kline_block_status"
        logger.debug(f"[{__name__}.{func_name}] 查询 {stock_code} {time_frame} {quarter} 的下载状态")
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            query = """
            SELECT status FROM kline_block_status 
            WHERE quarter = %s AND stock_code = %s AND time_frame = %s
            """
            cursor.execute(query, (quarter, stock_code, time_frame.value))
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

    def update_kline_block_status(self, quarter: str, stock_code: str, time_frame: KLinePeriod, status: str):
        """
        更新K线下载进度（统一格式）
        
        Args:
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
            status: 状态，'completed' 或 'not_completed'
        """
        func_name = "update_kline_block_status"
        logger.debug(f"[{__name__}.{func_name}] 更新 {quarter} {stock_code} {time_frame.value}  的状态为: {status}")
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            # 使用INSERT ... ON DUPLICATE KEY UPDATE来处理记录存在与否的情况
            query = """
            INSERT INTO kline_block_status (quarter, stock_code, time_frame,  status, completed_at) 
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            status = VALUES(status),
            completed_at = CASE 
                WHEN VALUES(status) = 'completed' THEN VALUES(completed_at) 
                ELSE completed_at 
            END
            """

            completed_at = datetime.now() if status == 'completed' else None
            cursor.execute(query, (quarter, stock_code, time_frame.value, status, completed_at))
            self.conn.commit()
            
            logger.debug(f"[{__name__}.{func_name}] {quarter} {stock_code} {time_frame.value}  的状态已更新为: {status}")
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 更新进度失败: {str(e)}")
            self.conn.rollback()
            raise
        finally:
            if cursor:
                cursor.close()

    def get_quarter_data_count(self, stock_code: str, time_frame: KLinePeriod, quarter: str) -> int:
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
        logger.debug(f"[{__name__}.{func_name}] 查询 {stock_code} {time_frame.value} {quarter} 的数据条数")
        
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
            cursor.execute(sql, (stock_code, time_frame.value, start_date, end_date))
            count = cursor.fetchone()[0]
            
            logger.debug(f"[{__name__}.{func_name}] {stock_code} {time_frame.value} {quarter} 的数据条数: {count}")
            return count
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询数据条数失败: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()

    def truncate_table_stock_fixed_seq(self) -> bool:
        """
        清空 stock_fixed_seq 表并批量插入新的股票代码数据
        Returns:
            操作是否成功
        """
        func_name = "truncate_table_stock_fixed_seq"
        logger.info(f"[{__name__}.{func_name}] 开始清空 stock_fixed_seq 表")

        cursor = None
        try:
            cursor = self.conn.cursor()

            # 步骤1：清空表
            truncate_sql = "TRUNCATE TABLE stock_fixed_seq"
            cursor.execute(truncate_sql)
            logger.debug(f"[{__name__}.{func_name}] 已清空 stock_fixed_seq 表")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 操作失败: {str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def save_stock_fixed_seq(self, stock_data: list) -> bool:
        """
        批量插入股票代码到 stock_fixed_seq 表（仅插入股票代码，无股票名称，ID 由数据库自增生成）
        不清空表、仅执行批量插入，提升数据库操作效率

        Args:
            stock_data: 股票代码列表，格式示例 ['000001', '000002', '600000', ...]

        Returns:
            操作是否成功
        """
        func_name = "save_stock_fixed_seq"
        logger.info(f"[{__name__}.{func_name}] 开始批量写入 {len(stock_data)} 条股票代码数据")

        cursor = None
        try:
            cursor = self.conn.cursor()

            # 空列表校验
            if not stock_data:
                logger.warning(f"[{__name__}.{func_name}] 股票代码列表为空，无数据写入")
                return True

            # 格式标准化：确保每个元素都是字符串类型的股票代码
            standardized_data = []
            for code in stock_data:
                if isinstance(code, str) and code.strip():
                    standardized_data.append((code.strip(),))  # 转成元组格式适配 executemany
                else:
                    logger.warning(f"[{__name__}.{func_name}] 无效股票代码，跳过：{code}")

            if not standardized_data:
                logger.warning(f"[{__name__}.{func_name}] 无有效股票代码，终止插入")
                return True

            # 批量插入 SQL（仅插入 stock_code，ID 由数据库自增）
            insert_sql = """
            INSERT INTO stock_fixed_seq (stock_code)
            VALUES (%s)
            """
            cursor.executemany(insert_sql, standardized_data)
            self.conn.commit()

            logger.info(f"[{__name__}.{func_name}] 成功写入 {len(standardized_data)} 条有效股票代码数据")
            return True

        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 批量插入股票代码失败: {str(e)}")
            self.conn.rollback()
            return False
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

    def get_stock_listing_date(self, ts_code: str) -> tuple[Optional[str], Optional[str]]:
        """
        查询指定股票代码的 上市日期 和 退市日期
        Args:
            ts_code: 股票代码（如 600000.SH）
        Returns:
            tuple: (上市日期, 退市日期) 格式 YYYY-MM-DD，无则返回 None
        """
        func_name = "get_stock_listing_date"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT list_date, delist_date FROM stock_basic 
                WHERE ts_code = %s
            """, (ts_code,))
            result = cursor.fetchone()
    
            if result:
                # 处理上市日期
                listing_date = result['list_date'].strftime('%Y-%m-%d') if result['list_date'] else None
                # 处理退市日期（新增）
                delist_date = result['delist_date'].strftime('%Y-%m-%d') if result['delist_date'] else None
                
                logger.debug(f"[{__name__}.{func_name}] 股票 {ts_code} 上市:{listing_date} 退市:{delist_date}")
                return listing_date, delist_date
            else:
                logger.warning(f"[{__name__}.{func_name}] 股票 {ts_code} 未查询到基础信息")
                return None, None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询股票 {ts_code} 失败：{str(e)}")
            return None, None
        finally:
            if cursor:
                cursor.close()

# ================= 全局统一入口 DataManager =================
class DataManager:
    @staticmethod
    def save_stock_fixed_seq(db_conn, records: list) -> bool:
        """
        向stock_fixed_seq表中插入股票代码记录

        Args:
            db_conn: 数据库连接
            records: 股票代码记录列表，例如 [('000001',), ('000002',), ...]

        Returns:
            操作是否成功
        """
        func_name = "insert_single_stock_code_for_seq"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.save_stock_fixed_seq(records)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return False

    @staticmethod
    def truncate_table_stock_fixed_seq(db_conn) -> bool:
        """
        清空stock_fixed_seq表，然后写入新的股票代码和名称列表

        Args:
            db_conn: 数据库连接
            stock_data: 股票数据列表，每个元素为元组(stock_code, stock_name)，例如 [('000001', '平安银行'), ...]

        Returns:
            操作是否成功
        """
        func_name = "truncate_table_stock_fixed_seq"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.truncate_table_stock_fixed_seq()
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败: {str(e)}")
            return False


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
    def get_kline_block_status(db_conn, quarter: str, stock_code: str, time_frame: KLinePeriod) -> str:
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
        func_name = "get_kline_block_status"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.get_kline_block_status(quarter, stock_code, time_frame)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return 'not_completed'

    @staticmethod
    def update_kline_block_status(db_conn, quarter: str, stock_code: str, time_frame: KLinePeriod, status: str):
        """
        更新K线下载进度（统一格式）
        
        Args:
            db_conn: 数据库连接
            stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
            status: 状态，'completed' 或 'not_completed'
        """
        func_name = "update_kline_block_status"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.update_kline_block_status(quarter, stock_code, time_frame, status)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 调用失败：{str(e)}")
            return None

    @staticmethod
    def get_quarter_data_count(db_conn, stock_code: str, time_frame: KLinePeriod, quarter: str) -> int:
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
    def next_fixed_stock(db_conn, current_stock: Optional[str] = None) -> Optional[str]:
        """
        【对外标准接口】获取固定序列中的下一只股票
        :param current_stock: 当前股票代码，不传/传None → 返回序列第一只
        :return: 下一只股票代码 | None
        """

        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            return manager.get_next_stock_in_fixed_seq(current_stock)
        except Exception as e:
            logger.error(f"[{__name__}.next_fixed_stock] 调用失败: {str(e)}")
            return None

    @staticmethod
    def set_downloading_block(db_conn, stock_id: str, time_frame: KLinePeriod, quarter: str) -> bool:
        """
        【对外标准接口】设置当前下载的区块信息（股票代码、时间周期、季度）
        Args:
            db_conn: 数据库连接
            stock_id: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            设置是否成功
        """
        func_name = "set_downloading_block"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            result = manager.set_downloading_block(stock_id, time_frame, quarter)
            logger.debug(f"[{__name__}.{func_name}] 对外接口调用完成，返回结果: {result}")
            return result
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 对外接口调用失败: {str(e)}")
            return False

    @staticmethod
    def get_downloading_block(db_conn) -> Optional[Tuple[str, str, KLinePeriod]]:
        """
        【对外标准接口】获取当前下载的区块信息（股票代码、时间周期、季度）
        :param db_conn: 数据库连接
        :return: 元组(downloading_stock_code, downloading_time_frame, downloading_quarter) | None
        """
        func_name = "get_downloading_block"
        try:
            manager = KLineUnifiedQuarterlyExtendedManager(db_conn)
            result = manager.get_downloading_block()
            logger.debug(f"[{__name__}.{func_name}] 对外接口调用完成，返回结果: {result}")
            return result
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 对外接口调用失败: {str(e)}")
            return None

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

    @staticmethod
    def get_stock_listing_date(db_conn, stock_code: str) -> tuple[Optional[str], Optional[str]]:
        """
        便捷调用BasicStockDataManager的get_stock_listing_date方法
        返回：(上市日期，退市日期)
        """
        return BasicStockDataManager(db_conn).get_stock_listing_date(stock_code)

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

def create_tables_if_not_exist2(conn):
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

        # 4. kline_unified_quarterly_extended - 新增表
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
          update_time timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
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

        # 5. stock_fixed_seq
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS stock_fixed_seq (
            id INT AUTO_INCREMENT COMMENT '自增ID',
            stock_code VARCHAR(20) NOT NULL COMMENT '股票代码',
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_stock_code (stock_code),
            INDEX idx_seq_num (id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票固定下载顺序表';
        """)

        # 6. kline_download_progress
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS kline_download_progress (
            id TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '固定为1，单条记录',
            downloading_quarter VARCHAR(20) VARCHAR(10) NOT NULL DEFAULT '' COMMENT '当前下载的季度标识，格式：YYYY-QN',
            downloading_stock_code VARCHAR(20) NOT NULL COMMENT '当前下载的股票代码',
            current_quarter VARCHAR(10) COMMENT '当前下载季度',
            last_update DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_stock_timeframe (stock_code, time_frame)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='K线下载进度表';
        """)

        # 7. download_task_config
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS download_task_config (
            id INT AUTO_INCREMENT COMMENT '自增ID',
            time_frame VARCHAR(10) NOT NULL COMMENT '时间周期：1min/5min/daily等',
            start_year INT NOT NULL COMMENT '起始年份',
            end_year INT NOT NULL COMMENT '结束年份',
            is_enabled TINYINT(1) DEFAULT 1 COMMENT '是否启用：1-是 0-否',
            create_time DATETIME DEFAULT CURRENT_TIMESTAMP,
            update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (id),
            UNIQUE KEY uk_time_frame (time_frame)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='下载任务配置表';
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

# ================= 通用工具函数（新增） =================
def load_table_create_sql(table_name: str) -> str:
    """
    根据表名自动加载对应的SQL文件
    规则：table_name -> database/Ingredient/{table_name}.sql
    
    Args:
        table_name: 数据库表名
    
    Returns:
        表创建SQL语句
    
    Raises:
        FileNotFoundError: SQL文件不存在时抛出
        ValueError: SQL文件内容为空时抛出
    """
    sql_file_path = SQL_DIR / f"{table_name}.sql"
    if not sql_file_path.exists():
        raise FileNotFoundError(f"表 {table_name} 的SQL文件不存在：{sql_file_path}")
    
    with open(sql_file_path, "r", encoding="utf8") as f:
        sql = f.read().strip()
    
    if not sql:
        raise ValueError(f"表 {table_name} 的SQL文件内容为空：{sql_file_path}")
    
    return sql


# ================= 批量创建所有表的入口函数（修改版） =================
import re
from typing import List
import os
import logging

logger = logging.getLogger(__name__)

def _get_sql_statements_from_file(sql_file_path: str) -> List[str]:
    """
    增强版：从 .sql 文件读取内容，拆分并清洗为可执行的 SQL 语句列表
    修复：处理/* */注释、编码兼容、分号在字符串/注释内的问题
    :param sql_file_path: SQL 文件路径
    :return: 清洗后的 SQL 语句列表
    """
    if not os.path.exists(sql_file_path):
        logger.error(f"SQL 文件不存在：{sql_file_path}")
        return []

    # 尝试多种编码读取
    encodings = ['utf-8', 'gbk', 'gb2312']
    sql_content = ""
    for encoding in encodings:
        try:
            with open(sql_file_path, 'r', encoding=encoding) as f:
                sql_content = f.read().strip()
            break  # 读取成功则退出编码循环
        except (UnicodeDecodeError, PermissionError) as e:
            logger.warning(f"编码 {encoding} 读取失败：{str(e)}")
            continue
    if not sql_content:
        logger.warning(f"SQL 文件内容为空/读取失败：{sql_file_path}")
        return []

    # 步骤1：移除 /* ... */ 多行注释
    sql_content = re.sub(r'/\*[\s\S]*?\*/', '', sql_content)
    # 步骤2：移除 -- 行内注释（保留行内非开头的语句）
    sql_content = re.sub(r'--.*?$', '', sql_content, flags=re.MULTILINE)
    # 步骤3：按分号拆分，过滤空语句（处理末尾无分号的情况）
    statements = []
    for stmt in sql_content.split(';'):
        stmt_clean = stmt.strip()
        if stmt_clean:  # 仅过滤空语句，不再过滤--开头（已提前移除注释）
            statements.append(stmt_clean)
    
    logger.info(f"从 {sql_file_path} 解析出 {len(statements)} 条 SQL 语句")
    return statements


def _execute_sql_statements(conn, cursor, statements: List[str], action_name: str) -> bool:
    """
    批量执行 SQL 语句，自带事务提交/回滚
    :param conn: 数据库连接
    :param cursor: 游标
    :param statements: SQL 语句列表
    :param action_name: 操作名称
    :return: 执行成功 True / 失败 False
    """
    if not statements:
        return True

    try:
        for stmt in statements:
            cursor.execute(stmt)
        conn.commit()
        logger.info(f"执行 {action_name} SQL 成功，共 {len(statements)} 条语句")
        return True

    except pymysql.MySQLError as e:
        logger.error(f"执行{action_name} SQL 失败：{str(e)}")
        conn.rollback()
        return False


def create_all_tables_if_not_exist(conn) -> bool:
    """
    遍历内部字典（表名→路径），依次执行所有 SQL 脚本创建库表
    :param conn: 数据库连接
    :return: 全部成功返回 True
    """
    func_name = "create_all_tables_if_not_exist"

    prj_dir = get_project_root()
    database_dir = os.path.join(prj_dir, "database")

    # ===================== 【字典类型】SQL 路径常量 =====================
    SQL_FILE_MAP: Dict[str, str] = {
        # 库
        # "database": "./init/00_database.sql",
        # 基础表
        "trade_date_map": f"{database_dir}/init/01_table_trade_date_map.sql",
        "stock_basic": f"{database_dir}/init/02_table_stock_basic.sql",
        "stock_daily": f"{database_dir}/init/03_table_stock_daily.sql",
        # "kline_1min": "./init/04_table_kline_1min.sql",
        # 统一K线表
        "kline_unified": f"{database_dir}/init/UnifiedKLine/01_table_kline_unified.sql",
        "kline_block_status": f"{database_dir}/init/UnifiedKLine/02_table_kline_block_status.sql",
        "stock_fixed_seq": f"{database_dir}/init/UnifiedKLine/03_stock_fixed_seq.sql",
        "kline_download_progress": f"{database_dir}/init/UnifiedKLine/04_kline_download_progress.sql",
        "download_task_config": f"{database_dir}/init/UnifiedKLine/05_download_task_config.sql",
    }

    cursor = None
    overall_success = True

    try:
        cursor = conn.cursor()
        logger.info(f"[{func_name}] 开始执行 {len(SQL_FILE_MAP)} 个库表初始化脚本")

        # 遍历字典（表名 → 路径）
        for action_name, sql_path in SQL_FILE_MAP.items():
            logger.info(f"[{func_name}] 正在初始化：{action_name}")

            # 1. 从文件获取 SQL 语句
            statements = _get_sql_statements_from_file(sql_path)
            if not statements:
                logger.error(f"[{func_name}] 获取 {action_name} SQL 语句失败，跳过该表")
                overall_success = False
                continue

            # 2. 执行 SQL 语句
            success = _execute_sql_statements(conn, cursor, statements, action_name)
            if not success:
                overall_success = False
            else:
                logger.info(f"[{func_name}] 初始化完成：{action_name}")

    except Exception as e:
        logger.error(f"[{func_name}] 整体异常：{str(e)}")
        overall_success = False
        if conn:
            conn.rollback()

    finally:
        if cursor:
            cursor.close()

    logger.info(f"[{func_name}] 全部执行完毕，结果：{'成功' if overall_success else '失败'}")
    return overall_success


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
        if create_all_tables_if_not_exist(conn):
            logger.info(f"[{__name__}.{func_name}] ✅ 数据库初始化全部完成")
            return conn
        else:
            conn.close()
            raise RuntimeError("数据库表初始化失败")
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] ❌ 数据库初始化失败：{str(e)}")
        raise 
