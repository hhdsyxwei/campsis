# dm_stock_cash_flow.py
import pymysql
import pandas as pd
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

class CompanyCashFlowManager:
    def __init__(self, connection):
        self.conn = connection

    def save_cash_flow_data(self, std_stock_code: str, data: pd.DataFrame) -> bool:
        """
        保存现金流量数据到数据库

        Args:
            std_stock_code: 股票代码
            data: DataFrame 格式的现金流量数据

        Returns:
            是否保存成功
        """
        func_name = "save_cash_flow_data"

        if data.empty:
            logger.info(f"[{__name__}.{func_name}] {std_stock_code} 数据为空，无需保存")
            return True

        logger.info(f"[{__name__}.{func_name}] {std_stock_code} 处理 {len(data)} 条现金流量数据")

        records = []

        for _, row in data.iterrows():
            try:
                pub_date = row['pubDate']
                stat_date = row['statDate']

                if isinstance(pub_date, pd.Timestamp):
                    pub_date = pub_date.strftime('%Y-%m-%d')
                if isinstance(stat_date, pd.Timestamp):
                    stat_date = stat_date.strftime('%Y-%m-%d')

                records.append((
                    std_stock_code, pub_date, stat_date,
                    float(row['CAToAsset']) if pd.notna(row.get('CAToAsset')) else None,
                    float(row['NCAToAsset']) if pd.notna(row.get('NCAToAsset')) else None,
                    float(row['tangibleAssetToAsset']) if pd.notna(row.get('tangibleAssetToAsset')) else None,
                    float(row['ebitToInterest']) if pd.notna(row.get('ebitToInterest')) else None,
                    float(row['CFOToOR']) if pd.notna(row.get('CFOToOR')) else None,
                    float(row['CFOToNP']) if pd.notna(row.get('CFOToNP')) else None,
                    float(row['CFOToGr']) if pd.notna(row.get('CFOToGr')) else None,
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
        INSERT INTO company_cash_flow
        (std_stock_code, pub_date, stat_date, cato_asset, ncato_asset, tangible_asset_to_asset,
         ebit_to_interest, cfo_to_or, cfo_to_np, cfo_to_gr)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            pub_date = VALUES(pub_date), cato_asset = VALUES(cato_asset), ncato_asset = VALUES(ncato_asset),
            tangible_asset_to_asset = VALUES(tangible_asset_to_asset), ebit_to_interest = VALUES(ebit_to_interest),
            cfo_to_or = VALUES(cfo_to_or), cfo_to_np = VALUES(cfo_to_np), cfo_to_gr = VALUES(cfo_to_gr)
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

    def check_cash_flow_data_exists(self, std_stock_code: str, stat_date: str) -> bool:
        """
        检查现金流量数据是否存在

        Args:
            std_stock_code: 股票代码
            stat_date: 统计日期

        Returns:
            是否存在
        """
        func_name = "check_cash_flow_data_exists"
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = "SELECT 1 FROM company_cash_flow WHERE std_stock_code = %s AND stat_date = %s LIMIT 1"
            cursor.execute(sql, (std_stock_code, stat_date))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败 {std_stock_code} {stat_date}：{str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_cash_flow_data(self, std_stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取现金流量数据

        Args:
            std_stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            pd.DataFrame: 包含现金流量数据的DataFrame
        """
        func_name = "get_cash_flow_data"
        cursor = None
        try:
            cursor = self.conn.cursor()

            sql = """
            SELECT pub_date, stat_date, cato_asset, ncato_asset, tangible_asset_to_asset,
                   ebit_to_interest, cfo_to_or, cfo_to_np, cfo_to_gr
            FROM company_cash_flow
            WHERE std_stock_code = %s AND stat_date BETWEEN %s AND %s
            ORDER BY stat_date
            """

            cursor.execute(sql, (std_stock_code, start_date, end_date))
            rows = cursor.fetchall()

            if not rows:
                columns = ['pub_date', 'stat_date', 'cato_asset', 'ncato_asset', 'tangible_asset_to_asset',
                           'ebit_to_interest', 'cfo_to_or', 'cfo_to_np', 'cfo_to_gr']
                return pd.DataFrame(columns=columns)

            columns = ['pub_date', 'stat_date', 'cato_asset', 'ncato_asset', 'tangible_asset_to_asset',
                        'ebit_to_interest', 'cfo_to_or', 'cfo_to_np', 'cfo_to_gr']
            df = pd.DataFrame(rows, columns=columns)

            logger.info(f"[{__name__}.{func_name}] 获取现金流量数据 {std_stock_code}: {len(df)} 条")
            return df

        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 获取现金流量数据失败 {std_stock_code}: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()
