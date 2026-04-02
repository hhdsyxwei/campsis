# dm_xrxd.py
from typing import Optional, List
import pandas as pd
import numpy as np
from KitchenBase.logger_config import get_logger

# ===================== 全局配置 =====================
logger = get_logger(__name__)

# ===================== 分红送配数据管理器 =====================
class XrxdManager:
    def __init__(self, db_conn):
        """
        初始化分红送配数据管理器
        :param db_conn: 数据库连接
        """
        self.db_conn = db_conn
        self.func_name = ""

    def save_xrxd_data(self, df: pd.DataFrame) -> bool:
        """
        保存分红送配数据到数据库
        :param df: 分红送配数据DataFrame
        :return: 是否保存成功
        """
        self.func_name = "save_xrxd_data"
        if df.empty:
            logger.warning(f"[{__name__}.{self.func_name}] 空数据，无需保存")
            return True

        cursor = self.db_conn.cursor()
        try:
            # 构建插入/更新语句
            sql = """
            INSERT INTO stock_xrxd (
                std_stock_code, xrxd_year, xrxd_pre_notice_date, 
                xrxd_agm_pum_date, xrxd_plan_announce_date, xrxd_plan_date, 
                xrxd_regist_date, xrxd_operate_date, xrxd_pay_date, 
                xrxd_stock_market_date, xrxd_cash_ps_before_tax, xrxd_cash_ps_after_tax, 
                xrxd_stocks_ps, xrxd_cash_stock, xrxd_reserve_to_stock_ps
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                xrxd_pre_notice_date = VALUES(xrxd_pre_notice_date),
                xrxd_agm_pum_date = VALUES(xrxd_agm_pum_date),
                xrxd_plan_announce_date = VALUES(xrxd_plan_announce_date),
                xrxd_plan_date = VALUES(xrxd_plan_date),
                xrxd_regist_date = VALUES(xrxd_regist_date),
                xrxd_operate_date = VALUES(xrxd_operate_date),
                xrxd_pay_date = VALUES(xrxd_pay_date),
                xrxd_stock_market_date = VALUES(xrxd_stock_market_date),
                xrxd_cash_ps_before_tax = VALUES(xrxd_cash_ps_before_tax),
                xrxd_cash_ps_after_tax = VALUES(xrxd_cash_ps_after_tax),
                xrxd_stocks_ps = VALUES(xrxd_stocks_ps),
                xrxd_cash_stock = VALUES(xrxd_cash_stock),
                xrxd_reserve_to_stock_ps = VALUES(xrxd_reserve_to_stock_ps)
            """

            # 准备数据，将NaN值转换为None
            records = []
            for _, row in df.iterrows():
                def convert_value(val):
                    """转换值：将NaN/NaT/空字符串转换为None"""
                    if pd.isna(val):
                        return None
                    if isinstance(val, str) and val.strip() == '':
                        return None
                    if isinstance(val, (int, float, np.integer, np.floating)):
                        if isinstance(val, float) and np.isnan(val):
                            return None
                    return val

                records.append((
                    row['std_stock_code'],
                    row['xrxd_year'],
                    convert_value(row.get('xrxd_pre_notice_date')),
                    convert_value(row.get('xrxd_agm_pum_date')),
                    convert_value(row.get('xrxd_plan_announce_date')),
                    convert_value(row.get('xrxd_plan_date')),
                    convert_value(row.get('xrxd_regist_date')),
                    convert_value(row.get('xrxd_operate_date')),
                    convert_value(row.get('xrxd_pay_date')),
                    convert_value(row.get('xrxd_stock_market_date')),
                    convert_value(row.get('xrxd_cash_ps_before_tax')),
                    convert_value(row.get('xrxd_cash_ps_after_tax')),
                    convert_value(row.get('xrxd_stocks_ps')),
                    convert_value(row.get('xrxd_cash_stock')),
                    convert_value(row.get('xrxd_reserve_to_stock_ps'))
                ))

            # 执行批量插入/更新
            if records:
                cursor.executemany(sql, records)
                self.db_conn.commit()
                logger.info(f"[{__name__}.{self.func_name}] 成功保存 {len(records)} 条分红送配数据")
            else:
                logger.warning(f"[{__name__}.{self.func_name}] 无数据可保存")

            return True
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 保存分红送配数据失败: {str(e)}")
            self.db_conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def get_xrxd_by_year(self, stock_code: str, year: int) -> pd.DataFrame:
        """
        获取指定股票和年份的分红送配数据
        :param stock_code: 股票代码
        :param year: 年份
        :return: 分红送配数据DataFrame
        """
        self.func_name = "get_xrxd_by_year"
        cursor = self.db_conn.cursor()
        try:
            sql = """
            SELECT 
                std_stock_code, xrxd_year, xrxd_pre_notice_date, 
                xrxd_agm_pum_date, xrxd_plan_announce_date, xrxd_plan_date, 
                xrxd_regist_date, xrxd_operate_date, xrxd_pay_date, 
                xrxd_stock_market_date, xrxd_cash_ps_before_tax, xrxd_cash_ps_after_tax, 
                xrxd_stocks_ps, xrxd_cash_stock, xrxd_reserve_to_stock_ps
            FROM stock_xrxd
            WHERE std_stock_code = %s AND xrxd_year = %s
            """
            cursor.execute(sql, (stock_code, year))
            rows = cursor.fetchall()
            
            # 构建DataFrame
            columns = [
                'std_stock_code', 'xrxd_year', 'xrxd_pre_notice_date', 
                'xrxd_agm_pum_date', 'xrxd_plan_announce_date', 'xrxd_plan_date', 
                'xrxd_regist_date', 'xrxd_operate_date', 'xrxd_pay_date', 
                'xrxd_stock_market_date', 'xrxd_cash_ps_before_tax', 'xrxd_cash_ps_after_tax', 
                'xrxd_stocks_ps', 'xrxd_cash_stock', 'xrxd_reserve_to_stock_ps'
            ]
            df = pd.DataFrame(rows, columns=columns)
            return df
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询分红送配数据失败: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def get_xrxd_by_stock(self, stock_code: str, start_year: Optional[int] = None, end_year: Optional[int] = None) -> pd.DataFrame:
        """
        获取指定股票的分红送配数据
        :param stock_code: 股票代码
        :param start_year: 起始年份（可选）
        :param end_year: 结束年份（可选）
        :return: 分红送配数据DataFrame
        """
        self.func_name = "get_xrxd_by_stock"
        cursor = self.db_conn.cursor()
        try:
            sql = """
            SELECT 
                std_stock_code, xrxd_year, xrxd_pre_notice_date, 
                xrxd_agm_pum_date, xrxd_plan_announce_date, xrxd_plan_date, 
                xrxd_regist_date, xrxd_operate_date, xrxd_pay_date, 
                xrxd_stock_market_date, xrxd_cash_ps_before_tax, xrxd_cash_ps_after_tax, 
                xrxd_stocks_ps, xrxd_cash_stock, xrxd_reserve_to_stock_ps
            FROM stock_xrxd
            WHERE std_stock_code = %s
            """
            params = [stock_code]
            
            if start_year:
                sql += " AND xrxd_year >= %s"
                params.append(start_year)
            if end_year:
                sql += " AND xrxd_year <= %s"
                params.append(end_year)
            
            sql += " ORDER BY xrxd_year DESC"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            # 构建DataFrame
            columns = [
                'std_stock_code', 'xrxd_year', 'xrxd_pre_notice_date', 
                'xrxd_agm_pum_date', 'xrxd_plan_announce_date', 'xrxd_plan_date', 
                'xrxd_regist_date', 'xrxd_operate_date', 'xrxd_pay_date', 
                'xrxd_stock_market_date', 'xrxd_cash_ps_before_tax', 'xrxd_cash_ps_after_tax', 
                'xrxd_stocks_ps', 'xrxd_cash_stock', 'xrxd_reserve_to_stock_ps'
            ]
            df = pd.DataFrame(rows, columns=columns)
            return df
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询分红送配数据失败: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def get_xrxd_by_year_range(self, start_year: int, end_year: int) -> pd.DataFrame:
        """
        获取指定年份范围的分红送配数据
        :param start_year: 起始年份
        :param end_year: 结束年份
        :return: 分红送配数据DataFrame
        """
        self.func_name = "get_xrxd_by_year_range"
        cursor = self.db_conn.cursor()
        try:
            sql = """
            SELECT 
                std_stock_code, xrxd_year, xrxd_pre_notice_date, 
                xrxd_agm_pum_date, xrxd_plan_announce_date, xrxd_plan_date, 
                xrxd_regist_date, xrxd_operate_date, xrxd_pay_date, 
                xrxd_stock_market_date, xrxd_cash_ps_before_tax, xrxd_cash_ps_after_tax, 
                xrxd_stocks_ps, xrxd_cash_stock, xrxd_reserve_to_stock_ps
            FROM stock_xrxd
            WHERE xrxd_year BETWEEN %s AND %s
            ORDER BY std_stock_code, xrxd_year
            """
            cursor.execute(sql, (start_year, end_year))
            rows = cursor.fetchall()
            
            # 构建DataFrame
            columns = [
                'std_stock_code', 'xrxd_year', 'xrxd_pre_notice_date', 
                'xrxd_agm_pum_date', 'xrxd_plan_announce_date', 'xrxd_plan_date', 
                'xrxd_regist_date', 'xrxd_operate_date', 'xrxd_pay_date', 
                'xrxd_stock_market_date', 'xrxd_cash_ps_before_tax', 'xrxd_cash_ps_after_tax', 
                'xrxd_stocks_ps', 'xrxd_cash_stock', 'xrxd_reserve_to_stock_ps'
            ]
            df = pd.DataFrame(rows, columns=columns)
            return df
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询分红送配数据失败: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def get_xrxd_count(self, stock_code: Optional[str] = None, year: Optional[int] = None) -> int:
        """
        获取分红送配数据数量
        :param stock_code: 股票代码（可选）
        :param year: 年份（可选）
        :return: 数据数量
        """
        self.func_name = "get_xrxd_count"
        cursor = self.db_conn.cursor()
        try:
            sql = "SELECT COUNT(*) FROM stock_xrxd WHERE 1=1"
            params = []
            
            if stock_code:
                sql += " AND std_stock_code = %s"
                params.append(stock_code)
            if year:
                sql += " AND xrxd_year = %s"
                params.append(year)
            
            cursor.execute(sql, params)
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询分红送配数据数量失败: {str(e)}")
            return 0
        finally:
            if cursor:
                cursor.close()
