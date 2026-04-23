# dm_adjustment_factor.py
from typing import Tuple
from KitchenBase.download_enums import DlTaskType
from typing import Optional, List
import pandas as pd
import numpy as np
from datetime import datetime
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlBlockStatus
from .dm_base import BaseDataManager

# ===================== 全局配置 =====================
logger = get_logger(__name__)

# ===================== 复权因子数据管理器 =====================
class AdjustmentFactorManager(BaseDataManager):
    def __init__(self, db_conn):
        """
        初始化复权因子数据管理器
        :param db_conn: 数据库连接
        """
        super().__init__(db_conn)
        self.func_name = ""
    
    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型
        :return: 任务类型（DlTaskType枚举）
        """
        return DlTaskType.ADJ_FACTOR

    def save_adjustment_factor_data(self, df: pd.DataFrame) -> bool:
        """
        保存复权因子数据到数据库
        :param df: 复权因子数据DataFrame
        :return: 是否保存成功
        """
        self.func_name = "save_adjustment_factor_data"
        if df.empty:
            logger.warning(f"[{__name__}.{self.func_name}] 空数据，无需保存")
            return True

        cursor = self.db_conn.cursor()
        try:
            # 构建插入/更新语句
            sql = """
            INSERT INTO stock_adjustment_factor (
                std_stock_code, adjust_date, fore_adjust_factor, 
                back_adjust_factor, adjust_factor
            ) VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                fore_adjust_factor = VALUES(fore_adjust_factor),
                back_adjust_factor = VALUES(back_adjust_factor),
                adjust_factor = VALUES(adjust_factor)
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
                    convert_value(row.get('adjust_date')),
                    convert_value(row.get('fore_adjust_factor')),
                    convert_value(row.get('back_adjust_factor')),
                    convert_value(row.get('adjust_factor'))
                ))

            # 执行批量插入/更新
            if records:
                cursor.executemany(sql, records)
                self.db_conn.commit()
                logger.info(f"[{__name__}.{self.func_name}] 成功保存 {len(records)} 条复权因子数据")
            else:
                logger.warning(f"[{__name__}.{self.func_name}] 无数据可保存")

            return True
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 保存复权因子数据失败: {str(e)}")
            self.db_conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def get_adjustment_factor_by_stock(self, stock_code: str, start_date: Optional[str] = None, end_date: Optional[str] = None) -> pd.DataFrame:
        """
        获取指定股票的复权因子数据
        :param stock_code: 股票代码
        :param start_date: 开始日期（可选）
        :param end_date: 结束日期（可选）
        :return: 复权因子数据DataFrame
        """
        self.func_name = "get_adjustment_factor_by_stock"
        cursor = self.db_conn.cursor()
        try:
            sql = """
            SELECT 
                std_stock_code, adjust_date, fore_adjust_factor, 
                back_adjust_factor, adjust_factor
            FROM stock_adjustment_factor
            WHERE std_stock_code = %s
            """
            params = [stock_code]
            
            if start_date:
                sql += " AND adjust_date >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND adjust_date <= %s"
                params.append(end_date)
            
            sql += " ORDER BY adjust_date ASC"
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            # 构建DataFrame
            columns = [
                'std_stock_code', 'adjust_date', 'fore_adjust_factor', 
                'back_adjust_factor', 'adjust_factor'
            ]
            df = pd.DataFrame(rows, columns=columns)
            return df
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询复权因子数据失败: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def get_adjustment_factor_by_date(self, date: str) -> pd.DataFrame:
        """
        获取指定日期的复权因子数据
        :param date: 日期（格式：YYYY-MM-DD）
        :return: 复权因子数据DataFrame
        """
        self.func_name = "get_adjustment_factor_by_date"
        cursor = self.db_conn.cursor()
        try:
            sql = """
            SELECT 
                std_stock_code, adjust_date, fore_adjust_factor, 
                back_adjust_factor, adjust_factor
            FROM stock_adjustment_factor
            WHERE adjust_date = %s
            ORDER BY std_stock_code
            """
            cursor.execute(sql, (date,))
            rows = cursor.fetchall()
            
            # 构建DataFrame
            columns = [
                'std_stock_code', 'adjust_date', 'fore_adjust_factor', 
                'back_adjust_factor', 'adjust_factor'
            ]
            df = pd.DataFrame(rows, columns=columns)
            return df
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询复权因子数据失败: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def get_adjustment_factor_count(self, stock_code: Optional[str] = None, start_date: Optional[str] = None, end_date: Optional[str] = None) -> int:
        """
        获取复权因子数据数量
        :param stock_code: 股票代码（可选）
        :param start_date: 开始日期（可选）
        :param end_date: 结束日期（可选）
        :return: 数据数量
        """
        self.func_name = "get_adjustment_factor_count"
        cursor = self.db_conn.cursor()
        try:
            sql = "SELECT COUNT(*) FROM stock_adjustment_factor WHERE 1=1"
            params = []
            
            if stock_code:
                sql += " AND std_stock_code = %s"
                params.append(stock_code)
            if start_date:
                sql += " AND adjust_date >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND adjust_date <= %s"
                params.append(end_date)
            
            cursor.execute(sql, params)
            result = cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询复权因子数据数量失败: {str(e)}")
            return 0
        finally:
            if cursor:
                cursor.close()

    def get_completed_block_count(self, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        获取已完成区块数
        
        :param start_year: 起始年份
        :param end_year: 结束年份
        :return: 已完成区块数
        """
        func_name = "get_completed_block_count"
        logger.debug(f"[{__name__}.{func_name}] 查询已完成区块数: {start_year}-{end_year}")
        
        try:
            # 直接调用 GenericBlockStatusManager 的 get_block_count 方法
            completed_count = self.block_status_manager.get_block_count(
                task_type=DlTaskType.ADJ_FACTOR,
                start_year=start_year,
                end_year=end_year,
                status=[DlBlockStatus.COMPLETED]
            )
            logger.debug(f"[{__name__}.{func_name}] 已完成区块数: {completed_count}")
            return completed_count
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败: {str(e)}")
            return 0
    
    def get_skipped_block_count(self, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        获取跳过区块数
        
        :param start_year: 起始年份
        :param end_year: 结束年份
        :return: 跳过区块数
        """
        func_name = "get_skipped_block_count"
        logger.debug(f"[{__name__}.{func_name}] 查询跳过区块数: {start_year}-{end_year}")
        
        try:
            # 直接调用 GenericBlockStatusManager 的 get_block_count 方法
            skipped_count = self.block_status_manager.get_block_count(
                task_type=DlTaskType.ADJ_FACTOR,
                start_year=start_year,
                end_year=end_year,
                status=[DlBlockStatus.SKIPPED]
            )
            logger.debug(f"[{__name__}.{func_name}] 跳过区块数: {skipped_count}")
            return skipped_count
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询失败: {str(e)}")
            return 0
    
    def get_total_block_count(self, start_year: int, end_year: int, *args, **kwargs) -> int:
        """
        获取总区块数
        
        :param start_year: 起始年份
        :param end_year: 结束年份，不包含在内
        :return: 总区块数
        """
        func_name = "get_total_block_count"
        logger.debug(f"[{__name__}.{func_name}] 计算总区块数: {start_year}-{end_year}")
        
        try:
            # 计算年份范围内的区块数（每个年份一个区块）
            from .dm_unified import UnifiedDataManager
            stock_count = UnifiedDataManager.count_stocks_in_fixed_seq(self.db_conn)
            total_years = end_year - start_year
            total_blocks = total_years * stock_count
            logger.debug(f"[{__name__}.{func_name}] 总区块数: {total_blocks}")
            return total_blocks
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 计算失败: {str(e)}")
            return 0
    
    def get_block_status(self, year: int, std_stock_code: str, *args, **kwargs) -> DlBlockStatus:
        """
        获取区块状态
        
        :param year: 年份
        :param std_stock_code: 股票代码
        :return: 区块状态
        """
        func_name = "get_block_status"
        logger.debug(f"[{__name__}.{func_name}] 获取 {std_stock_code} {year} 的复权因子区块状态")
        
        try:
            # 利用父类的 block_status_manager 获取区块状态
            # 任务类型为 DlTaskType.ADJ_FACTOR，block_key_1 为年份字符串，block_key_2 为股票代码
            status = self.block_status_manager.get_block_status(
                block_key_1=str(year),
                block_key_2=std_stock_code,
                task_type=DlTaskType.ADJ_FACTOR
            )
            logger.debug(f"[{__name__}.{func_name}] 区块状态: {status.value}")
            return status
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 获取区块状态失败: {str(e)}")
            return DlBlockStatus.NOT_COMPLETED
    
    def update_block_status(self, year: int, std_stock_code: str, status: DlBlockStatus, **kwargs):
        """
        更新复权因子区块状态
        
        :param year: 年份
        :param std_stock_code: 股票代码
        :param status: 区块状态
        :param kwargs: 其他参数（block_name, total_items, success_count, fail_count, error_message等）
        """
        func_name = "update_block_status"
        logger.debug(f"[{__name__}.{func_name}] 更新 {std_stock_code} {year} 的复权因子区块状态为: {status.value}")
        
        try:
            # 利用父类的 block_status_manager 更新区块状态
            self.block_status_manager.update_block_status(
                block_key_1=str(year),
                block_key_2=std_stock_code,
                task_type=DlTaskType.ADJ_FACTOR,
                status=status,
                **kwargs
            )
            logger.debug(f"[{__name__}.{func_name}] 复权因子区块状态更新成功")
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 更新复权因子区块状态失败: {str(e)}")

