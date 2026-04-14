# dm_daily.py
import pymysql
import pandas as pd
from KitchenBase.download_utils import calculate_pre_close
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

class DailyDataManager:
    def __init__(self, connection):
        self.conn = connection

    def save_daily_data(self, std_stock_code: str, data) -> bool:
        """
        保存日线数据到数据库
        
        Args:
            std_stock_code: 股票代码
            data: 数据，可以是 Baostock 结果对象或 DataFrame
            
        Returns:
            是否保存成功
        """
        func_name = "save_daily_data"
        
        # 处理不同类型的输入数据
        if hasattr(data, 'error_code'):
            # Baostock 结果对象
            if data is None or data.error_code != '0':
                err_code = data.error_code if data else 'None'
                logger.error(f"[{__name__}.{func_name}] {std_stock_code} 查询失败，错误码：{err_code}")
                return False

            data_list = []
            while data.next():
                data_list.append(data.get_row_data())

            logger.info(f"[{__name__}.{func_name}] {std_stock_code} 获取到 {len(data_list)} 条日线数据")
            if not data_list:
                return True

            df = pd.DataFrame(data_list, columns=data.fields)
        else:
            # 直接使用 DataFrame
            df = data
            logger.info(f"[{__name__}.{func_name}] {std_stock_code} 处理 {len(df)} 条日线数据")
            if df.empty:
                return True

        records = []

        for _, row in df.iterrows():
            try:
                trade_date = row['date']
                # 确保 trade_date 是字符串格式
                if isinstance(trade_date, pd.Timestamp):
                    trade_date = trade_date.strftime('%Y-%m-%d')
                
                # 计算前收盘价（如果没有提供）
                if 'pre_close' in row and pd.notna(row['pre_close']):
                    pre_close_val = row['pre_close']
                else:
                    pre_close_val = calculate_pre_close(row['close'], row['pctChg'])
                    
                records.append((
                    std_stock_code, trade_date,
                    float(row['open']) if pd.notna(row['open']) else None,
                    float(row['high']) if pd.notna(row['high']) else None,
                    float(row['low']) if pd.notna(row['low']) else None,
                    float(row['close']) if pd.notna(row['close']) else None,
                    pre_close_val,
                    float(row['pctChg']) if pd.notna(row['pctChg']) else None,
                    float(row['volume']) if pd.notna(row['volume']) else None,
                    float(row['amount']) if pd.notna(row['amount']) else None,
                    float(row['turn']) if pd.notna(row['turn']) else None,
                    float(row['peTTM']) if pd.notna(row['peTTM']) else None,
                    float(row['pbMRQ']) if pd.notna(row['pbMRQ']) else None,
                ))
            except (ValueError, ZeroDivisionError) as e:
                logger.warning(f"[{__name__}.{func_name}] 数据转换错误 {std_stock_code} {row['date']}: {str(e)}")
                continue

        if not records:
            return True

        cursor = None
        sql = """
        INSERT INTO stock_daily 
        (std_stock_code, trade_date, open, high, low, close, pre_close, change_rate, volume, amount, turnover_rate, pe, pb)
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
            logger.debug(f"[{__name__}.{func_name}] {std_stock_code} 入库成功 {len(records)} 条")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] {std_stock_code} 入库失败：{str(e)}")
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

    def get_latest_tradedate_for_stock(self, std_stock_code: str) -> str:
        """
        获取股票的最新交易日
        
        Args:
            std_stock_code: 股票代码
            
        Returns:
            最新交易日，格式为 'YYYY-MM-DD'
            
        Raises:
            ValueError: 当股票不存在或无交易数据时
            RuntimeError: 当数据库操作或日期格式错误时
        """
        func_name = "get_latest_tradedate_for_stock"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            
            # 先检查股票是否存在
            cursor.execute("SELECT 1 FROM stock_basic WHERE std_stock_code = %s", (std_stock_code,))
            if not cursor.fetchone():
                raise ValueError(f"股票 {std_stock_code} 不存在")
            
            # 查询最新交易日
            cursor.execute("SELECT MAX(trade_date) AS latest FROM stock_daily WHERE std_stock_code = %s", (std_stock_code,))
            result = cursor.fetchone()
            if not result:
                raise RuntimeError("查询结果异常")
            
            latest = result['latest']
            if not latest:
                raise ValueError(f"股票 {std_stock_code} 无交易数据")
            
            try:
                return latest.strftime('%Y-%m-%d')
            except Exception as e:
                raise RuntimeError(f"日期格式错误: {str(e)}")
        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败 {std_stock_code}：{str(e)}")
            raise RuntimeError(f"数据库操作错误: {str(e)}") from e
        finally:
            if cursor:
                cursor.close()
