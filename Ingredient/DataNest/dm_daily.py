# dm_daily.py
import pymysql
import pandas as pd
import pyarrow as pa
from KitchenBase.logger_config import get_logger
from .dm_standard_columns import StockDailyStandardColumns

logger = get_logger(__name__)

class DailyDataManager:
    def __init__(self, connection):
        self.conn = connection

    def save_daily_data(self, std_stock_code: str, data: pd.DataFrame) -> bool:
        """
        保存日线数据到数据库
        
        Args:
            std_stock_code: 股票代码
            data: 标准格式的 DataFrame，必须包含 StockDailyStandardColumns 中定义的列
            
        Returns:
            是否保存成功
        """
        func_name = "save_daily_data"
        
        # 直接使用 DataFrame
        df = data
        logger.info(f"[{__name__}.{func_name}] {std_stock_code} 处理 {len(df)} 条日线数据")
        if df.empty:
            return True

        records = []

        for _, row in df.iterrows():
            try:
                # 只使用内部标准列名
                trade_date = row[StockDailyStandardColumns.TRADE_DATE]
                # 确保 trade_date 是字符串格式
                if isinstance(trade_date, pd.Timestamp):
                    trade_date = trade_date.strftime('%Y-%m-%d')
                
                # 直接使用 pre_close，数据已经在下载器中清洗过了
                pre_close_val = row[StockDailyStandardColumns.PRE_CLOSE] if pd.notna(row[StockDailyStandardColumns.PRE_CLOSE]) else None
                
                records.append((
                    std_stock_code, trade_date,
                    float(row[StockDailyStandardColumns.OPEN]) if pd.notna(row[StockDailyStandardColumns.OPEN]) else None,
                    float(row[StockDailyStandardColumns.HIGH]) if pd.notna(row[StockDailyStandardColumns.HIGH]) else None,
                    float(row[StockDailyStandardColumns.LOW]) if pd.notna(row[StockDailyStandardColumns.LOW]) else None,
                    float(row[StockDailyStandardColumns.CLOSE]) if pd.notna(row[StockDailyStandardColumns.CLOSE]) else None,
                    pre_close_val if pd.notna(pre_close_val) else None,
                    float(row[StockDailyStandardColumns.CHANGE_RATE]) if pd.notna(row[StockDailyStandardColumns.CHANGE_RATE]) else None,
                    float(row[StockDailyStandardColumns.VOLUME]) if pd.notna(row[StockDailyStandardColumns.VOLUME]) else None,
                    float(row[StockDailyStandardColumns.AMOUNT]) if pd.notna(row[StockDailyStandardColumns.AMOUNT]) else None,
                    float(row[StockDailyStandardColumns.TURNOVER_RATE]) if pd.notna(row[StockDailyStandardColumns.TURNOVER_RATE]) else None,
                    float(row[StockDailyStandardColumns.PE]) if pd.notna(row[StockDailyStandardColumns.PE]) else None,
                    float(row[StockDailyStandardColumns.PB]) if pd.notna(row[StockDailyStandardColumns.PB]) else None,
                    float(row[StockDailyStandardColumns.PS]) if pd.notna(row[StockDailyStandardColumns.PS]) else None,
                    float(row[StockDailyStandardColumns.PCF]) if pd.notna(row[StockDailyStandardColumns.PCF]) else None,
                    int(row[StockDailyStandardColumns.ADJUST_FLAG]) if pd.notna(row[StockDailyStandardColumns.ADJUST_FLAG]) else None,
                    int(row[StockDailyStandardColumns.TRADE_STATUS]) if pd.notna(row[StockDailyStandardColumns.TRADE_STATUS]) else None,
                    int(row[StockDailyStandardColumns.IS_ST]) if pd.notna(row[StockDailyStandardColumns.IS_ST]) else None,
                ))
            except (ValueError, ZeroDivisionError, NameError) as e:
                date_val = row.get(StockDailyStandardColumns.TRADE_DATE, 'unknown')
                logger.warning(f"[{__name__}.{func_name}] 数据转换错误 {std_stock_code} {date_val}: {str(e)}")
                logger.warning(f"当前完整记录: {row}")
                continue
            except Exception as e:
                date_val = row.get(StockDailyStandardColumns.TRADE_DATE, 'unknown')
                logger.error(f"[{__name__}.{func_name}] 未预期的异常 {std_stock_code} {date_val}: {str(e)}")
                logger.error(f"当前完整记录: {row}")
                import traceback
                logger.error(f"异常堆栈: {traceback.format_exc()}")
                continue

        if not records:
            return True
        
        logger.warning(f"record[0]:{records[0]}")

        cursor = None
        sql = """
        INSERT INTO stock_daily 
        (std_stock_code, trade_date, open, high, low, close, pre_close, change_rate, volume, amount, turnover_rate, pe, pb, ps, pcf, adjust_flag, trade_status, is_st)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            open = VALUES(open), high = VALUES(high), low = VALUES(low), close = VALUES(close),
            pre_close = VALUES(pre_close), change_rate = VALUES(change_rate), volume = VALUES(volume),
            amount = VALUES(amount), turnover_rate = VALUES(turnover_rate), pe = VALUES(pe), pb = VALUES(pb),
            ps = VALUES(ps), pcf = VALUES(pcf), adjust_flag = VALUES(adjust_flag), trade_status = VALUES(trade_status), is_st = VALUES(is_st)
        """
        try:
            cursor = self.conn.cursor()
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.info(f"[{__name__}.{func_name}] ✅ {std_stock_code} 日线数据(stock_daily)入库成功 {len(records)} 条")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] {std_stock_code} 日线数据(stock_daily)入库失败：{str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def check_date_range_exists(self, std_stock_code: str, start_date=None, end_date=None) -> bool:
        func_name = "check_date_range_exists"
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = "SELECT 1 FROM stock_daily WHERE std_stock_code = %s LIMIT 1"
            cursor.execute(sql, (std_stock_code,))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败 {std_stock_code}：{str(e)}")
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
                SELECT std_stock_code FROM stock_basic 
                WHERE market IN ('主板(深A)', '主板(沪A)', '科创板', '创业板', '北交所') 
                AND is_active = 1
            """)
            return [stock['std_stock_code'] for stock in cursor.fetchall()]
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败：{str(e)}")
            return []
        finally:
            if cursor:
                cursor.close()

    def get_price_data(self, std_stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取股票价格数据
        
        Args:
            std_stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 包含日期、开盘价、最高价、最低价、收盘价、成交量等数据的DataFrame
        """
        func_name = "get_price_data"
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            # ========== 调试信息 ==========
            logger.debug(f"[{__name__}.{func_name}] 开始查询 - 股票代码: {std_stock_code}")
            logger.debug(f"[{__name__}.{func_name}] 查询日期范围: {start_date} ~ {end_date}")
            logger.debug(f"[{__name__}.{func_name}] 股票代码类型: {type(std_stock_code)}")
            logger.debug(f"[{__name__}.{func_name}] 开始日期类型: {type(start_date)}")
            logger.debug(f"[{__name__}.{func_name}] 结束日期类型: {type(end_date)}")
            
            # 先检查数据库连接
            try:
                cursor.execute("SELECT DATABASE()")
                db_name = cursor.fetchone()[0]
                logger.debug(f"[{__name__}.{func_name}] 当前数据库: {db_name}")
            except Exception as e:
                logger.warning(f"[{__name__}.{func_name}] 获取数据库名称失败: {str(e)}")
            # ==============================
            
            # 从stock_daily表查询数据
            sql = """
            SELECT trade_date, open, high, low, close, volume, amount, pe, pb, ps, pcf, adjust_flag, trade_status, is_st
            FROM stock_daily
            WHERE std_stock_code = %s AND trade_date BETWEEN %s AND %s
            ORDER BY trade_date
            """
            
            logger.debug(f"[{__name__}.{func_name}] 执行SQL查询")
            logger.debug(f"[{__name__}.{func_name}] 查询参数: ({std_stock_code}, {start_date}, {end_date})")
            
            cursor.execute(sql, (std_stock_code, start_date, end_date))
            rows = cursor.fetchall()
            
            logger.debug(f"[{__name__}.{func_name}] 查询结果行数: {len(rows) if rows else 0}")
            
            if not rows:
                # 调试：检查是否存在该股票的任何数据
                cursor.execute("SELECT COUNT(*) FROM stock_daily WHERE std_stock_code = %s", (std_stock_code,))
                total_count = cursor.fetchone()[0]
                logger.warning(f"[{__name__}.{func_name}] 日期范围内无数据，但该股票总记录数: {total_count}")
                
                if total_count > 0:
                    # 获取该股票的日期范围
                    cursor.execute("SELECT MIN(trade_date), MAX(trade_date) FROM stock_daily WHERE std_stock_code = %s", (std_stock_code,))
                    date_range = cursor.fetchone()
                    logger.warning(f"[{__name__}.{func_name}] 该股票实际日期范围: {date_range[0]} ~ {date_range[1]}")
                
                # 返回空的DataFrame
                columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pe', 'pb', 'ps', 'pcf', 'adjust_flag', 'trade_status', 'is_st']
                return pd.DataFrame(columns=columns)
            
            # 转换为DataFrame，使用PyArrow类型
            columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pe', 'pb', 'ps', 'pcf', 'adjust_flag', 'trade_status', 'is_st']
            df = pd.DataFrame(rows, columns=columns)
            
            logger.debug(f"[{__name__}.{func_name}] 转换后DataFrame行数: {len(df)}")
            logger.debug(f"[{__name__}.{func_name}] DataFrame列: {df.columns.tolist()}")
            if not df.empty:
                logger.debug(f"[{__name__}.{func_name}] 数据日期范围: {df['date'].min()} ~ {df['date'].max()}")
            
            # 转换为PyArrow类型
            from pandas import ArrowDtype
            
            try:
                df = df.astype({
                    'date': ArrowDtype(pa.date32()),
                    'open': ArrowDtype(pa.decimal128(10, 3)),
                    'high': ArrowDtype(pa.decimal128(10, 3)),
                    'low': ArrowDtype(pa.decimal128(10, 3)),
                    'close': ArrowDtype(pa.decimal128(10, 3)),
                    'volume': ArrowDtype(pa.int64()),
                    'amount': ArrowDtype(pa.decimal128(15, 2))
                })
                logger.debug(f"[{__name__}.{func_name}] PyArrow类型转换成功")
            except Exception as e:
                logger.error(f"[{__name__}.{func_name}] PyArrow类型转换失败: {str(e)}")
                # 回退到普通类型
                df['date'] = pd.to_datetime(df['date'])
                numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
                for col in numeric_cols:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                logger.info(f"[{__name__}.{func_name}] 已回退到普通类型转换")
            
            logger.debug(f"[{__name__}.{func_name}] 获取价格数据完成 {std_stock_code}: {len(df)} 条")
            logger.debug(f"数据类型: {df.dtypes}")
            return df
            
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 获取价格数据失败 {std_stock_code}: {str(e)}", exc_info=True)
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

