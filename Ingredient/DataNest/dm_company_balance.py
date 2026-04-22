# dm_company_balance.py
import pymysql
import pandas as pd
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

class CompanyBalanceManager:
    def __init__(self, connection):
        self.conn = connection

    def save_balance_data(self, std_stock_code: str, data: pd.DataFrame) -> bool:
        """
        保存偿债能力数据到数据库
        
        Args:
            std_stock_code: 股票代码
            data: DataFrame 格式的偿债能力数据
            
        Returns:
            是否保存成功
        """
        func_name = "save_balance_data"
        
        # 直接使用 DataFrame
        if data.empty:
            logger.info(f"[{__name__}.{func_name}] {std_stock_code} 数据为空，无需保存")
            return True

        logger.info(f"[{__name__}.{func_name}] {std_stock_code} 处理 {len(data)} 条偿债能力数据")

        records = []

        for _, row in data.iterrows():
            try:
                pub_date = row['pubDate']
                stat_date = row['statDate']
                
                # 确保日期是字符串格式
                if isinstance(pub_date, pd.Timestamp):
                    pub_date = pub_date.strftime('%Y-%m-%d')
                if isinstance(stat_date, pd.Timestamp):
                    stat_date = stat_date.strftime('%Y-%m-%d')
                
                records.append((
                    std_stock_code, pub_date, stat_date,
                    float(row['currentRatio']) if pd.notna(row['currentRatio']) else None,
                    float(row['quickRatio']) if pd.notna(row['quickRatio']) else None,
                    float(row['cashRatio']) if pd.notna(row['cashRatio']) else None,
                    float(row['YOYLiability']) if pd.notna(row['YOYLiability']) else None,
                    float(row['liabilityToAsset']) if pd.notna(row['liabilityToAsset']) else None,
                    float(row['assetToEquity']) if pd.notna(row['assetToEquity']) else None,
                ))
            except (ValueError, KeyError) as e:
                logger.warning(f"[{__name__}.{func_name}] 数据转换错误 {std_stock_code} {row.get('statDate', '未知日期')}: {str(e)}")
                logger.warning(f"当前完整记录: {row}")
                continue

        if not records:
            logger.info(f"[{__name__}.{func_name}] {std_stock_code} 无有效数据，无需保存")
            return True

        cursor = None
        sql = """
        INSERT INTO company_balance 
        (std_stock_code, pub_date, stat_date, current_ratio, quick_ratio, cash_ratio, yoy_liability, liability_to_asset, asset_to_equity)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            pub_date = VALUES(pub_date), current_ratio = VALUES(current_ratio), quick_ratio = VALUES(quick_ratio),
            cash_ratio = VALUES(cash_ratio), yoy_liability = VALUES(yoy_liability), liability_to_asset = VALUES(liability_to_asset),
            asset_to_equity = VALUES(asset_to_equity)
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

    def check_balance_data_exists(self, std_stock_code: str, stat_date: str) -> bool:
        """
        检查偿债能力数据是否存在
        
        Args:
            std_stock_code: 股票代码
            stat_date: 统计日期
            
        Returns:
            是否存在
        """
        func_name = "check_balance_data_exists"
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = "SELECT 1 FROM company_balance WHERE std_stock_code = %s AND stat_date = %s LIMIT 1"
            cursor.execute(sql, (std_stock_code, stat_date))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败 {std_stock_code} {stat_date}：{str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_balance_data(self, std_stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取偿债能力数据
        
        Args:
            std_stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 包含偿债能力数据的DataFrame
        """
        func_name = "get_balance_data"
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            # 从company_balance表查询数据
            sql = """
            SELECT pub_date, stat_date, current_ratio, quick_ratio, cash_ratio, yoy_liability, liability_to_asset, asset_to_equity
            FROM company_balance
            WHERE std_stock_code = %s AND stat_date BETWEEN %s AND %s
            ORDER BY stat_date
            """
            
            cursor.execute(sql, (std_stock_code, start_date, end_date))
            rows = cursor.fetchall()
            
            if not rows:
                # 返回空的DataFrame
                columns = ['pub_date', 'stat_date', 'current_ratio', 'quick_ratio', 'cash_ratio', 'yoy_liability', 'liability_to_asset', 'asset_to_equity']
                return pd.DataFrame(columns=columns)
            
            # 转换为DataFrame
            columns = ['pub_date', 'stat_date', 'current_ratio', 'quick_ratio', 'cash_ratio', 'yoy_liability', 'liability_to_asset', 'asset_to_equity']
            df = pd.DataFrame(rows, columns=columns)
            
            logger.info(f"[{__name__}.{func_name}] 获取偿债能力数据 {std_stock_code}: {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 获取偿债能力数据失败 {std_stock_code}: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()
