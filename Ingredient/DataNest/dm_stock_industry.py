# dm_stock_industry.py
from typing import Optional, Dict, List, Tuple
import pandas as pd
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlBlockStatus, DlTaskType
from .dm_generic_block_status import GenericBlockStatusDM

logger = get_logger(__name__)

class StockIndustryDataManager:
    """股票行业分类数据管理器"""
    
    def __init__(self, db_conn):
        self.db_conn = db_conn
        self.block_status_manager = GenericBlockStatusDM(db_conn)
    
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型
        :return: 任务类型（DlTaskType枚举）
        """
        return DlTaskType.INDUSTRY
    
    def save_industry_data(self, df: pd.DataFrame) -> bool:
        """
        保存行业分类数据到数据库
        
        :param df: 行业分类数据
        :return: 保存是否成功
        """
        func_name = "save_industry_data"
        logger.debug(f"[{__name__}.{func_name}] 开始保存 {len(df)} 条行业分类数据")
        
        cursor = None
        try:
            # 准备数据
            records = []
            history_records = []
            
            for _, row in df.iterrows():
                # 当前快照表记录
                records.append((
                    row['std_stock_code'],
                    row['stock_name'],
                    row['industry'],
                    row['industry_classification'],
                    row['industry_source'],
                    row['update_date']
                ))
                
                # 历史表记录
                history_records.append((
                    row['std_stock_code'],
                    row['stock_name'],
                    row['industry'],
                    row['industry_classification'],
                    row['industry_source'],
                    row['update_date']
                ))
            
            if not records:
                logger.debug(f"[{__name__}.{func_name}] 无数据可保存")
                return True
            
            # 执行批量插入到当前快照表
            sql = """
            INSERT INTO stock_industry 
            (std_stock_code, stock_name, industry, industry_classification, industry_source, update_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                stock_name = VALUES(stock_name),
                industry = VALUES(industry),
                industry_classification = VALUES(industry_classification),
                industry_source = VALUES(industry_source),
                update_date = VALUES(update_date)
            """
            
            cursor = self.db_conn.cursor()
            cursor.executemany(sql, records)
            
            # 执行批量插入到历史表
            sql_history = """
            INSERT IGNORE INTO stock_industry_history 
            (std_stock_code, stock_name, industry, industry_classification, industry_source, update_date)
            VALUES (%s, %s, %s, %s, %s, %s)
            """
            
            cursor.executemany(sql_history, history_records)
            self.db_conn.commit()
            
            logger.debug(f"[{__name__}.{func_name}] 成功保存 {len(records)} 条行业分类数据")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 保存数据失败: {str(e)}")
            self.db_conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()
    
    def get_industry_by_code(self, std_stock_code: str) -> Optional[Dict]:
        """
        获取指定股票的当前行业分类
        
        :param std_stock_code: 股票代码
        :return: 行业信息字典
        """
        func_name = "get_industry_by_code"
        logger.debug(f"[{__name__}.{func_name}] 查询 {std_stock_code} 的行业分类")
        
        cursor = None
        try:
            cursor = self.db_conn.cursor(dictionary=True)
            sql = """
            SELECT * FROM stock_industry 
            WHERE std_stock_code = %s
            """
            cursor.execute(sql, (std_stock_code,))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_industry_by_date(self, std_stock_code: str, query_date: str) -> Optional[Dict]:
        """
        获取指定日期的行业分类（用于回测）
        
        :param std_stock_code: 股票代码
        :param query_date: 查询日期
        :return: 行业信息字典
        """
        func_name = "get_industry_by_date"
        logger.debug(f"[{__name__}.{func_name}] 查询 {std_stock_code} 在 {query_date} 的行业分类")
        
        cursor = None
        try:
            cursor = self.db_conn.cursor(dictionary=True)
            sql = """
            SELECT * FROM stock_industry_history 
            WHERE std_stock_code = %s AND update_date <= %s
            ORDER BY update_date DESC
            LIMIT 1
            """
            cursor.execute(sql, (std_stock_code, query_date))
            result = cursor.fetchone()
            return result
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def get_all_industries_by_date(self, query_date: str) -> pd.DataFrame:
        """
        获取指定日期所有股票的行业分类
        
        :param query_date: 查询日期
        :return: 行业信息DataFrame
        """
        func_name = "get_all_industries_by_date"
        logger.debug(f"[{__name__}.{func_name}] 查询 {query_date} 所有股票的行业分类")
        
        try:
            sql = """
            SELECT h.* FROM (
                SELECT std_stock_code, MAX(update_date) as max_update_date
                FROM stock_industry_history
                WHERE update_date <= %s
                GROUP BY std_stock_code
            ) latest
            JOIN stock_industry_history h
                ON h.std_stock_code = latest.std_stock_code
                AND h.update_date = latest.max_update_date
            """
            return pd.read_sql(sql, self.db_conn, params=(query_date,))
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败: {str(e)}")
            return pd.DataFrame()