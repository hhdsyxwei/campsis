# dm_kline.py
from typing import Optional, Tuple
import pymysql
import pandas as pd
from datetime import datetime
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import KLinePeriod
from KitchenBase.download_enums import DlBlockStatus, DlTaskType
from .dm_generic_block_status import GenericBlockStatusDM
from .dm_columns import (
    STD_STOCK_CODE, TIME_FRAME, TIMESTAMP,
    OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, VOLUME, TURNOVER,
    DOWNLOADING_STOCK_CODE, DOWNLOADING_TIME_FRAME, DOWNLOADING_QUARTER, UPDATE_TIME,
    QUARTER, STATUS, COMPLETED_AT,
    KlineUnifiedColumns as KUC
)
from .dm_global_dl_ctrl import GlobalDlCtrlBlockManager

logger = get_logger(__name__)

class KLineUnifiedQuarterlyExtendedManager:
    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.block_status_manager = GenericBlockStatusDM(db_conn)
        self.progress_manager = GlobalDlCtrlBlockManager(db_conn)

    def save_kline_data_unified(self, std_stock_code: str, df: pd.DataFrame) -> bool:
        """
        保存统一格式的K线数据
        
        Args:
            std_stock_code: 股票代码
            df: K线数据，包含time_frame, timestamp等字段
        
        Returns:
            保存是否成功
        """
        func_name = "save_kline_data_unified"
        logger.debug(f"[{__name__}.{func_name}] 开始保存 {len(df)} 条统一格式K线数据 for {std_stock_code}")

        cursor = None
        try:
            # 准备数据
            records = []
            for _, row in df.iterrows():
                records.append((
                    std_stock_code,
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
            sql = f"""
            INSERT INTO kline_unified_quarterly_extended 
            ({KUC.STD_STOCK_CODE}, {KUC.TIME_FRAME}, {KUC.TIMESTAMP}, {KUC.OPEN_PRICE}, {KUC.HIGH_PRICE}, {KUC.LOW_PRICE}, {KUC.CLOSE_PRICE}, {KUC.VOLUME}, {KUC.TURNOVER})
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                {KUC.OPEN_PRICE} = VALUES({KUC.OPEN_PRICE}), 
                {KUC.HIGH_PRICE} = VALUES({KUC.HIGH_PRICE}), 
                {KUC.LOW_PRICE} = VALUES({KUC.LOW_PRICE}), 
                {KUC.CLOSE_PRICE} = VALUES({KUC.CLOSE_PRICE}),
                {KUC.VOLUME} = VALUES({KUC.VOLUME}),
                {KUC.TURNOVER} = VALUES({KUC.TURNOVER}),
                update_time = CURRENT_TIMESTAMP
            """
            cursor = self.db_conn.cursor()
            cursor.executemany(sql, records)
            self.db_conn.commit()
            
            logger.debug(f"[{__name__}.{func_name}] 成功保存 {len(records)} 条K线数据 for {std_stock_code}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 保存数据失败 for {std_stock_code}: {str(e)}")
            self.db_conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def get_quarter_data_count(self, std_stock_code: str, time_frame: KLinePeriod, quarter: str) -> int:
        """
        获取指定股票、时间周期和季度的数据条数
        
        Args:
            std_stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            数据条数
        """
        func_name = "get_quarter_data_count"
        logger.debug(f"[{__name__}.{func_name}] 查询 {std_stock_code} {time_frame.value} {quarter} 的数据条数")
        
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
            cursor = self.db_conn.cursor()
            sql = f"""
            SELECT COUNT(*) FROM kline_unified_quarterly_extended 
            WHERE std_stock_code = %s AND time_frame = %s 
            AND timestamp >= %s AND timestamp <= %s
            """
            cursor.execute(sql, (std_stock_code, time_frame.value, start_date, end_date))
            count = cursor.fetchone()[0]
            
            logger.debug(f"[{__name__}.{func_name}] {std_stock_code} {time_frame.value} {quarter} 的数据条数: {count}")
            return count
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询数据条数失败: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()

    def get_completed_block_count(self, start_year: int, end_year: int, time_frame: KLinePeriod) -> int:
        """
        查询kline_block_status表中状态为completed的区块总数
        支持按年份范围过滤（仅匹配quarter字段中的年份部分）

        Args:
            start_year: 可选，起始年份（如2024），不传则不限制起始年份
            end_year: 可选，结束年份（如2025），不传则不限制结束年份
            time_frame: 可选，时间周期，不传则不限制

        Returns:
            状态为completed的区块总数
        """
        func_name = "get_completed_block_count"
        logger.debug(
            f"[{__name__}.{func_name}] 查询completed状态区块总数，年份范围："
            f"start_year={start_year}, end_year={end_year}, time_frame={time_frame.value}"
        )

        cursor = None
        try:
            # 基础SQL：查询completed状态的总数，过滤掉不在stock_fixed_seq表中的股票代码
            sql = """
            SELECT COUNT(*) FROM kline_block_status kbs
            WHERE kbs.status = 'completed'
            AND EXISTS (
                SELECT 1 FROM stock_fixed_seq sfs
                WHERE sfs.std_stock_code = kbs.std_stock_code
            )
            """
            params = []
            conditions = []

            # 动态添加年份范围过滤条件（解析quarter字段的年份部分）
            # 注意：包含 start_year，不包含 end_year（惯例：[start_year, end_year)）
            if start_year is not None:
                conditions.append("CAST(SUBSTRING(quarter, 1, 4) AS UNSIGNED) >= %s")
                params.append(start_year)
            if end_year is not None:
                conditions.append("CAST(SUBSTRING(quarter, 1, 4) AS UNSIGNED) < %s")
                params.append(end_year)
            
            # 动态添加time_frame过滤条件
            if time_frame is not None:
                conditions.append("time_frame = %s")
                params.append(time_frame.value)

            if conditions:
                sql += " AND " + " AND ".join(conditions)

            # 执行查询
            cursor = self.db_conn.cursor()
            cursor.execute(sql, params)
            count = cursor.fetchone()[0]

            logger.debug(
                f"[{__name__}.{func_name}] 查询完成，completed状态区块总数：{count} "
                f"(年份范围：{start_year or '不限'} - {end_year or '不限'})"
            )
            return count
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询completed状态区块总数失败: {str(e)}")
            raise  # 保持和其他函数一致的异常抛出逻辑
        finally:
            if cursor:
                cursor.close()

    def get_skipped_block_count(self, start_year: int, end_year: int, time_frame: KLinePeriod) -> int:
        """
        查询kline_block_status表中状态为skipped的区块总数
        支持按年份范围过滤（仅匹配quarter字段中的年份部分）

        Args:
            start_year: 可选，起始年份（如2024），不传则不限制起始年份
            end_year: 可选，结束年份（如2025），不传则不限制结束年份
            time_frame: 可选，时间周期，不传则不限制

        Returns:
            状态为skipped的区块总数
        """
        func_name = "get_skipped_block_count"
        logger.debug(
            f"[{__name__}.{func_name}] 查询skipped状态区块总数，年份范围："
            f"start_year={start_year}, end_year={end_year}, time_frame={time_frame.value}"
        )

        cursor = None
        try:
            # 基础SQL：查询skipped状态的总数，过滤掉不在stock_fixed_seq表中的股票代码
            sql = """
            SELECT COUNT(*) FROM kline_block_status kbs
            WHERE kbs.status = 'skipped'
            AND EXISTS (
                SELECT 1 FROM stock_fixed_seq sfs
                WHERE sfs.std_stock_code = kbs.std_stock_code
            )
            """
            params = []
            conditions = []

            # 动态添加年份范围过滤条件（解析quarter字段的年份部分）
            # 注意：包含 start_year，不包含 end_year（惯例：[start_year, end_year)）
            if start_year is not None:
                conditions.append("CAST(SUBSTRING(quarter, 1, 4) AS UNSIGNED) >= %s")
                params.append(start_year)
            if end_year is not None:
                conditions.append("CAST(SUBSTRING(quarter, 1, 4) AS UNSIGNED) < %s")
                params.append(end_year)
            
            # 动态添加time_frame过滤条件
            if time_frame is not None:
                conditions.append("time_frame = %s")
                params.append(time_frame.value)

            if conditions:
                sql += " AND " + " AND ".join(conditions)

            # 执行查询
            cursor = self.db_conn.cursor()
            cursor.execute(sql, params)
            count = cursor.fetchone()[0]

            logger.debug(
                f"[{__name__}.{func_name}] 查询完成，skipped状态区块总数：{count} "
                f"(年份范围：{start_year or '不限'} - {end_year or '不限'})"
            )
            return count
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询skipped状态区块总数失败: {str(e)}")
            raise
        finally:
            if cursor:
                cursor.close()
