# dm_trade_date.py
import pandas as pd
import pymysql
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

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
            logger.info(f"[{__name__}.{func_name}] ✅ 交易日映射表(trade_date_map) 成功保存 {len(records)} 条交易日数据")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 交易日映射表(trade_date_map) 保存失败：{str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
