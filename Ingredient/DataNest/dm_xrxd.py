# dm_xrxd.py
from typing import Optional, List
import pandas as pd
import numpy as np
from datetime import datetime
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlBlockStatus
from .dm_base import BaseDataManager

# ===================== 全局配置 =====================
logger = get_logger(__name__)

# ===================== 分红送配数据管理器 =====================
class XrxdManager(BaseDataManager):
    def __init__(self, db_conn):
        """
        初始化分红送配数据管理器
        :param db_conn: 数据库连接
        """
        super().__init__(db_conn)
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
                params.append(str(start_year))
            if end_year:
                sql += " AND xrxd_year <= %s"
                params.append(str(end_year))
            
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

    def get_completed_block_count(self, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        根据指针位置计算已完成的XRXD区块数
        支持按年份范围过滤

        Args:
            start_year: 起始年份
            end_year: 结束年份
            *args: 其他参数，用于过滤当前股票和年份的区块数
            **kwargs: 其他参数，用于过滤当前股票和年份的区块数

        Returns:
            已完成的区块总数
        """
        func_name = "get_completed_block_count"
        logger.debug(
            f"[{__name__}.{func_name}] 根据指针位置计算已完成区块数，年份范围："
            f"start_year={start_year}, end_year={end_year}"
            f", 其他参数：{args}"
        )

        cursor = None
        try:
            # 从args中解包获取下载指针
            current_year = None
            current_stock = None
            if len(args) >= 2:
                current_year = args[0]
                current_stock = args[1]
            
            # 如果没有提供下载指针，则返回0
            if not current_year or not current_stock:
                return 0

            # 计算已处理的年份数
            years_processed = current_year - start_year
            if years_processed < 0:
                return 0
            
            # 计算当前年份已处理的股票数
            from .dm_unified import UnifiedDataManager
            stock_position = UnifiedDataManager.get_stock_position(self.db_conn, current_stock)
            if stock_position is None:
                stock_position = 0
            
            # 计算已处理的总区块数
            stock_count = UnifiedDataManager.count_stocks_in_fixed_seq(self.db_conn)
            processed_blocks = years_processed * stock_count + stock_position + 1
            
            logger.debug(
                f"[{__name__}.{func_name}] 计算完成，已完成区块数：{processed_blocks} "
                f"(年份范围：{start_year or '不限'} - {end_year or '不限'})"
            )
            return processed_blocks
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 计算已完成区块数失败: {str(e)}")
            return 0
        finally:
            if cursor:
                cursor.close()

    def get_skipped_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取跳过的XRXD区块数（固定返回0）

        Args:
            start_year: 起始年份
            end_year: 结束年份

        Returns:
            跳过的区块总数（固定为0）
        """
        func_name = "get_skipped_block_count"
        logger.debug(
            f"[{__name__}.{func_name}] 获取跳过区块数，年份范围："
            f"start_year={start_year}, end_year={end_year}"
        )
        
        # XRXD数据一般不会因为股票未上市或已退市而跳过，固定返回0
        return 0

    def get_total_block_count(self, start_year: int, end_year: int) -> int:
        """
        计算XRXD数据的区块总数
        计算逻辑：年份总数 × 股票总数 = 总区块数

        Args:
            start_year: 起始年份（包含）
            end_year: 结束年份（不包含）

        Returns:
            区块总数
        """
        func_name = "get_total_block_count"
        logger.debug(
            f"[{__name__}.{func_name}] 计算区块总数，年份范围："
            f"start_year={start_year}, end_year={end_year}"
        )

        try:
            # 计算年份范围内的年份总数
            year_count = end_year - start_year
            
            # 统计股票总数
            from .dm_unified import UnifiedDataManager
            stock_count = UnifiedDataManager.count_stocks_in_fixed_seq(self.db_conn)
            
            # 计算总区块数
            total_blocks = year_count * stock_count
            
            logger.debug(
                f"[{__name__}.{func_name}] 计算完成，区块总数：{total_blocks} "
                f"(年份范围：{start_year} - {end_year}, 年份数：{year_count}, 股票数：{stock_count})"
            )
            return total_blocks
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 计算区块总数失败: {str(e)}")
            raise

    def get_block_status(self, year: int, std_stock_code: str) -> DlBlockStatus:
        """
        获取XRXD区块状态（固定返回COMPLETED）
        
        Args:
            year: 年份
            std_stock_code: 股票代码
        
        Returns:
            固定返回DlBlockStatus.COMPLETED
        """
        func_name = "get_block_status"
        logger.debug(
            f"[{__name__}.{func_name}] 获取 {std_stock_code} {year} 的状态（固定返回COMPLETED）"
        )
        # 由于使用指针位置计算进度，固定返回COMPLETED
        return DlBlockStatus.COMPLETED

    def update_block_status(self, year: int, std_stock_code: str, status: DlBlockStatus):
        """
        更新XRXD区块状态（空实现）
        
        Args:
            year: 年份
            std_stock_code: 股票代码
            status: 状态
        """
        func_name = "update_block_status"
        logger.debug(
            f"[{__name__}.{func_name}] 更新 {year} {std_stock_code} 的状态为: {status.value}（空实现）"
        )
        # 由于使用指针位置计算进度，不需要实际更新状态
        pass
