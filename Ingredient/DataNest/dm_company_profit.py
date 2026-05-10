# dm_stock_profit.py
import pymysql
import pandas as pd
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest.dm_standard_columns import CompanyProfitStandardColumns

logger = get_logger(__name__)

class CompanyProfitManager:
    def __init__(self, connection):
        self.conn = connection

    def save_profit_data(self, std_stock_code: str, data: pd.DataFrame) -> bool:
        """
        保存利润数据到数据库
        
        Args:
            std_stock_code: 股票代码
            data: DataFrame 格式的利润数据
            
        Returns:
            是否保存成功
        """
        func_name = "save_profit_data"
        
        # 直接使用 DataFrame
        if data.empty:
            logger.info(f"[{__name__}.{func_name}] {std_stock_code} 数据为空，无需保存")
            return True

        logger.info(f"[{__name__}.{func_name}] {std_stock_code} 处理 {len(data)} 条利润数据")
        logger.debug(f"[{__name__}.{func_name}] 数据列名: {list(data.columns)}")

        records = []

        for _, row in data.iterrows():
            try:
                pub_date = row[CompanyProfitStandardColumns.PUB_DATE]
                stat_date = row[CompanyProfitStandardColumns.STAT_DATE]
                
                # 确保日期是字符串格式
                if isinstance(pub_date, pd.Timestamp):
                    pub_date = pub_date.strftime('%Y-%m-%d')
                if isinstance(stat_date, pd.Timestamp):
                    stat_date = stat_date.strftime('%Y-%m-%d')
                
                records.append((
                    std_stock_code, pub_date, stat_date,
                    float(row[CompanyProfitStandardColumns.ROE_AVG]) if pd.notna(row[CompanyProfitStandardColumns.ROE_AVG]) else None,
                    float(row[CompanyProfitStandardColumns.NP_MARGIN]) if pd.notna(row[CompanyProfitStandardColumns.NP_MARGIN]) else None,
                    float(row[CompanyProfitStandardColumns.GP_MARGIN]) if pd.notna(row[CompanyProfitStandardColumns.GP_MARGIN]) else None,
                    float(row[CompanyProfitStandardColumns.NET_PROFIT]) if pd.notna(row[CompanyProfitStandardColumns.NET_PROFIT]) else None,
                    float(row[CompanyProfitStandardColumns.EPS_TTM]) if pd.notna(row[CompanyProfitStandardColumns.EPS_TTM]) else None,
                    float(row[CompanyProfitStandardColumns.MB_REVENUE]) if pd.notna(row[CompanyProfitStandardColumns.MB_REVENUE]) else None,
                    int(float(row[CompanyProfitStandardColumns.TOTAL_SHARE])) if pd.notna(row[CompanyProfitStandardColumns.TOTAL_SHARE]) else None,
                    int(float(row[CompanyProfitStandardColumns.LIQA_SHARE])) if pd.notna(row[CompanyProfitStandardColumns.LIQA_SHARE]) else None,
                ))
            except (ValueError, KeyError) as e:
                logger.warning(f"[{__name__}.{func_name}] 数据转换错误 {std_stock_code} {row.get(CompanyProfitStandardColumns.STAT_DATE, '未知日期')}: {str(e)}")
                logger.warning(f"当前完整记录: {row}")
                continue
            except Exception as e:
                logger.error(f"[{__name__}.{func_name}] 未预期的异常 {std_stock_code} {row.get(CompanyProfitStandardColumns.STAT_DATE, '未知日期')}: {str(e)}")
                logger.error(f"当前完整记录: {row}")
                import traceback
                logger.error(f"[{__name__}.{func_name}] 抛出异常时的调用栈:")
                logger.error(traceback.format_exc())
            

        if not records:
            logger.info(f"[{__name__}.{func_name}] {std_stock_code} 无有效数据，无需保存")
            return True

        cursor = None
        sql = """
        INSERT INTO company_profit 
        (std_stock_code, pub_date, stat_date, roe_avg, np_margin, gp_margin, net_profit, eps_ttm, mb_revenue, total_share, liqa_share)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            pub_date = VALUES(pub_date), roe_avg = VALUES(roe_avg), np_margin = VALUES(np_margin),
            gp_margin = VALUES(gp_margin), net_profit = VALUES(net_profit), eps_ttm = VALUES(eps_ttm),
            mb_revenue = VALUES(mb_revenue), total_share = VALUES(total_share), liqa_share = VALUES(liqa_share)
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

    def check_profit_data_exists(self, std_stock_code: str, stat_date: str) -> bool:
        """
        检查利润数据是否存在
        
        Args:
            std_stock_code: 股票代码
            stat_date: 统计日期
            
        Returns:
            是否存在
        """
        func_name = "check_profit_data_exists"
        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = "SELECT 1 FROM company_profit WHERE std_stock_code = %s AND stat_date = %s LIMIT 1"
            cursor.execute(sql, (std_stock_code, stat_date))
            return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败 {std_stock_code} {stat_date}：{str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_profit_data(self, std_stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        获取利润数据
        
        Args:
            std_stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            pd.DataFrame: 包含利润数据的DataFrame
        """
        func_name = "get_profit_data"
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            # 从company_profit表查询数据
            sql = """
            SELECT pub_date, stat_date, roe_avg, np_margin, gp_margin, net_profit, eps_ttm, mb_revenue, total_share, liqa_share
            FROM company_profit
            WHERE std_stock_code = %s AND stat_date BETWEEN %s AND %s
            ORDER BY stat_date
            """
            
            cursor.execute(sql, (std_stock_code, start_date, end_date))
            rows = cursor.fetchall()
            
            if not rows:
                # 返回空的DataFrame
                columns = [
                    CompanyProfitStandardColumns.PUB_DATE,
                    CompanyProfitStandardColumns.STAT_DATE,
                    CompanyProfitStandardColumns.ROE_AVG,
                    CompanyProfitStandardColumns.NP_MARGIN,
                    CompanyProfitStandardColumns.GP_MARGIN,
                    CompanyProfitStandardColumns.NET_PROFIT,
                    CompanyProfitStandardColumns.EPS_TTM,
                    CompanyProfitStandardColumns.MB_REVENUE,
                    CompanyProfitStandardColumns.TOTAL_SHARE,
                    CompanyProfitStandardColumns.LIQA_SHARE
                ]
                return pd.DataFrame(columns=columns)
            
            # 转换为DataFrame
            columns = [
                CompanyProfitStandardColumns.PUB_DATE,
                CompanyProfitStandardColumns.STAT_DATE,
                CompanyProfitStandardColumns.ROE_AVG,
                CompanyProfitStandardColumns.NP_MARGIN,
                CompanyProfitStandardColumns.GP_MARGIN,
                CompanyProfitStandardColumns.NET_PROFIT,
                CompanyProfitStandardColumns.EPS_TTM,
                CompanyProfitStandardColumns.MB_REVENUE,
                CompanyProfitStandardColumns.TOTAL_SHARE,
                CompanyProfitStandardColumns.LIQA_SHARE
            ]
            df = pd.DataFrame(rows, columns=columns)
            
            logger.info(f"[{__name__}.{func_name}] 获取利润数据 {std_stock_code}: {len(df)} 条")
            return df
            
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 获取利润数据失败 {std_stock_code}: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()
