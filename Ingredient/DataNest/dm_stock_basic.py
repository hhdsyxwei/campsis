# dm_stock_basic.py
import pymysql
import pandas as pd
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

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
                SELECT std_stock_code FROM stock_basic
                WHERE stock_name IS NULL OR list_date IS NULL
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
            cursor.execute("SELECT DISTINCT std_stock_code FROM stock_basic")
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
                SELECT std_stock_code 
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

    def batch_insert_stock_basic(self, df: pd.DataFrame) -> bool:
        """
        批量插入/更新股票基础信息
        【极简版】仅负责数据库写入，所有数据校验、清洗、字段过滤由调用者完成
        """
        func_name = "batch_insert_stock_basic"
        logger.info(f"[{__name__}.{func_name}] 准备写入 {len(df)} 条股票基础数据")

        # 空 DataFrame 直接返回
        if df.empty:
            logger.warning(f"[{__name__}.{func_name}] DataFrame 为空，无数据写入")
            return True

        cursor = None
        try:
            # 直接从 DataFrame 获取列（完全信任调用方已处理好）
            insert_cols = list(df.columns)
            placeholders = ", ".join(["%s"] * len(insert_cols))

            # SQL 完全由传入的 DataFrame 列动态生成
            insert_sql = f"""
            INSERT INTO stock_basic ({', '.join(insert_cols)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE
                pure_symbol = VALUES(pure_symbol),
                market = VALUES(market),
                is_active = VALUES(is_active)
            """

            # 执行批量写入
            records = df.to_numpy().tolist()
            cursor = self.conn.cursor()
            cursor.executemany(insert_sql, records)
            self.conn.commit()

            logger.info(f"[{__name__}.{func_name}] ✅ 成功写入 {len(df)} 条")
            return True

        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 写入失败: {str(e)}")
            self.conn.rollback()
            return False

        finally:
            if cursor:
                cursor.close()

    def get_stock_listing_date(self, ts_code: str) -> tuple:
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
                WHERE std_stock_code = %s
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
