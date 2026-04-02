# dm_kline.py
from typing import Optional, Tuple
import pymysql
import pandas as pd
from datetime import datetime
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import KLinePeriod
from .dm_columns import (
    STD_STOCK_CODE, TIME_FRAME, TIMESTAMP,
    OPEN_PRICE, HIGH_PRICE, LOW_PRICE, CLOSE_PRICE, VOLUME, TURNOVER,
    DOWNLOADING_STOCK_CODE, DOWNLOADING_TIME_FRAME, DOWNLOADING_QUARTER, UPDATE_TIME,
    QUARTER, STATUS, COMPLETED_AT,
    KlineUnifiedColumns as KUC
)
from .dm_global_progress import GlobalDownloadProgressManager

logger = get_logger(__name__)

class KLineUnifiedQuarterlyExtendedManager:
    def __init__(self, conn):
        self.conn = conn
        self.progress_manager = GlobalDownloadProgressManager(conn)

    def set_downloading_block(self, std_stock_code: str, time_frame: KLinePeriod, quarter: str) -> bool:
        """
        设置当前下载的区块信息（更新global_download_progress表）
        委托给 GlobalDownloadProgressManager 处理
        Args:
            std_stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
        
        Returns:
            设置是否成功
        """
        func_name = "set_downloading_block"
        logger.debug(f"[{__name__}.{func_name}] 委托设置下载区块: {std_stock_code} {time_frame.value} {quarter}")
        return self.progress_manager.set_kline_progress(std_stock_code, time_frame, quarter)

    def get_downloading_block(self) -> Optional[Tuple[str, str, KLinePeriod]]:
        """
        获取当前下载的区块信息（股票代码、时间周期、季度）
        委托给 GlobalDownloadProgressManager 处理
        """
        func_name = "get_downloading_block"
        logger.debug(f"[{__name__}.{func_name}] 委托获取下载区块")
        return self.progress_manager.get_kline_progress()

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
                SELECT std_stock_code
                FROM stock_fixed_seq
                WHERE
                    -- 传入 None：取所有数据
                    (%s IS NULL)
                    OR
                    -- 传入股票代码：取 id 比当前大的
                    id > (SELECT id FROM stock_fixed_seq WHERE std_stock_code = %s)
                ORDER BY id ASC
                LIMIT 1
            """
            cursor.execute(sql, (current_stock_code, current_stock_code))
            result = cursor.fetchone()

            if result:
                logger.debug(f"[{__name__}.{func_name}] 获取到下一只股票: {result['std_stock_code']}")
                return result['std_stock_code']
            else:
                logger.debug(f"[{__name__}.{func_name}] 无下一只股票 / 表为空，返回None")
                return None

        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 获取下一只股票失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

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
            cursor = self.conn.cursor()
            cursor.executemany(sql, records)
            self.conn.commit()
            
            logger.debug(f"[{__name__}.{func_name}] 成功保存 {len(records)} 条K线数据 for {std_stock_code}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 保存数据失败 for {std_stock_code}: {str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def get_kline_block_status(self, quarter: str, std_stock_code: str, time_frame: KLinePeriod) -> str:
        """
        获取K线下载状态
        
        Args:
            quarter: 季度，格式如 '2024-Q1'
            std_stock_code: 股票代码
            time_frame: 时间周期
        
        Returns:
            状态字符串: 'completed' 或 'not_completed'
        """
        func_name = "get_kline_block_status"
        logger.debug(f"[{__name__}.{func_name}] 查询 {std_stock_code} {time_frame} {quarter} 的下载状态")
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            query = f"""
            SELECT status FROM kline_block_status 
            WHERE quarter = %s AND std_stock_code = %s AND time_frame = %s
            """
            cursor.execute(query, (quarter, std_stock_code, time_frame.value))
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

    def update_kline_block_status(self, quarter: str, std_stock_code: str, time_frame: KLinePeriod, status: str):
        """
        更新K线下载进度（统一格式）
        
        Args:
            std_stock_code: 股票代码
            time_frame: 时间周期
            quarter: 季度，格式如 '2024-Q1'
            status: 状态，'completed' 或 'not_completed'
        """
        func_name = "update_kline_block_status"
        logger.debug(f"[{__name__}.{func_name}] 更新 {quarter} {std_stock_code} {time_frame.value}  的状态为: {status}")
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            # 使用INSERT ... ON DUPLICATE KEY UPDATE来处理记录存在与否的情况
            query = f"""
            INSERT INTO kline_block_status (quarter, std_stock_code, time_frame,  status, completed_at) 
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE 
            status = VALUES(status),
            completed_at = CASE 
                WHEN VALUES(status) = 'completed' THEN VALUES(completed_at) 
                ELSE completed_at 
            END
            """

            completed_at = datetime.now() if status == 'completed' else None
            cursor.execute(query, (quarter, std_stock_code, time_frame.value, status, completed_at))
            self.conn.commit()
            
            logger.debug(f"[{__name__}.{func_name}] {quarter} {std_stock_code} {time_frame.value}  的状态已更新为: {status}")
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 更新进度失败: {str(e)}")
            self.conn.rollback()
            raise
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
            cursor = self.conn.cursor()
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

    def get_completed_block_total_count(self, start_year: Optional[int] = None, end_year: Optional[int] = None, time_frame: Optional[str] = None) -> int:
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
        func_name = "get_completed_block_total_count"
        logger.debug(
            f"[{__name__}.{func_name}] 查询completed状态区块总数，年份范围："
            f"start_year={start_year}, end_year={end_year}, time_frame={time_frame}"
        )

        cursor = None
        try:
            # 基础SQL：查询completed状态的总数
            sql = """
            SELECT COUNT(*) FROM kline_block_status 
            WHERE status = 'completed'
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
                params.append(time_frame)

            if conditions:
                sql += " AND " + " AND ".join(conditions)

            # 执行查询
            cursor = self.conn.cursor()
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
            INSERT INTO stock_fixed_seq (std_stock_code)
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

    def count_stocks_in_fixed_seq(self) -> int:
        """
        内部辅助函数：统计stock_fixed_seq表中的股票总数
        :return: 股票总数
        """
        self.func_name = "count_stocks_in_fixed_seq"
        
        # 实际场景中需根据数据库表结构实现查询逻辑
        # 示例：查询stock_fixed_seq表的总行数
        try:
            # 替换为真实的数据库查询逻辑（适配你的db_conn类型）
            # 以下是通用示例（需根据实际ORM/数据库驱动调整）
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM stock_fixed_seq")
            stock_count = cursor.fetchone()[0]
            cursor.close()
            
            if stock_count <= 0:
                logger.warning(f"[{__name__}.{self.func_name}] stock_fixed_seq表无股票数据")
            return stock_count
        
        except Exception as e:
            logger.error(
                f"[{__name__}.{self.func_name}] 查询股票总数失败: {str(e)}",
                exc_info=True
            )
            return 0
