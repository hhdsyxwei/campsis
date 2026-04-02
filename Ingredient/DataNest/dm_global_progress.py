# dm_global_progress.py
"""
全局下载进度指针管理模块
集中管理对 global_download_progress 表的访问
"""
from typing import Optional, Tuple, Dict, Any
import pymysql
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import KLinePeriod

logger = get_logger(__name__)


class GlobalDownloadProgressManager:
    """全局下载进度指针管理器"""

    def __init__(self, conn):
        self.conn = conn

    # -------------------------------------------------------------------------
    # 内部核心函数：写入任意任务的进度
    # -------------------------------------------------------------------------
    def _write_progress(self, task_type: str, pointers: Dict[str, str]) -> bool:
        """
        内部函数：写入任意任务的进度
        :param task_type: 任务类型
        :param pointers: 进度指针字典，包含 primary_name, primary_value, 
                        secondary_name, secondary_value, tertiary_name, tertiary_value
        :return: 写入是否成功
        """
        func_name = "_write_progress"

        # 提取指针值，使用默认值
        primary_name = pointers.get('primary_name', '')
        primary_value = pointers.get('primary_value', '')
        secondary_name = pointers.get('secondary_name', '')
        secondary_value = pointers.get('secondary_value', '')
        tertiary_name = pointers.get('tertiary_name', '')
        tertiary_value = pointers.get('tertiary_value', '')

        logger.debug(f"[{__name__}.{func_name}] 写入进度: {task_type} "
                    f"primary={primary_name}:{primary_value} "
                    f"secondary={secondary_name}:{secondary_value} "
                    f"tertiary={tertiary_name}:{tertiary_value}")

        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                INSERT INTO global_download_progress 
                (task_type, primary_pointer_name, primary_pointer_value, 
                 secondary_pointer_name, secondary_pointer_value, 
                 tertiary_pointer_name, tertiary_pointer_value, update_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    primary_pointer_name = VALUES(primary_pointer_name),
                    primary_pointer_value = VALUES(primary_pointer_value),
                    secondary_pointer_name = VALUES(secondary_pointer_name),
                    secondary_pointer_value = VALUES(secondary_pointer_value),
                    tertiary_pointer_name = VALUES(tertiary_pointer_name),
                    tertiary_pointer_value = VALUES(tertiary_pointer_value),
                    update_time = CURRENT_TIMESTAMP
            """, (task_type, primary_name, primary_value, secondary_name, secondary_value,
                  tertiary_name, tertiary_value))
            self.conn.commit()
            logger.debug(f"[{__name__}.{func_name}] 进度写入成功: {task_type}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 进度写入失败: {task_type}, {str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    # -------------------------------------------------------------------------
    # 内部核心函数：读取任意任务的进度
    # -------------------------------------------------------------------------
    def _read_progress(self, task_type: str) -> Optional[Dict[str, str]]:
        """
        内部函数：读取任意任务的进度
        :param task_type: 任务类型
        :return: 进度指针字典或None
        """
        func_name = "_read_progress"
        logger.debug(f"[{__name__}.{func_name}] 读取进度: {task_type}")

        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT primary_pointer_name, primary_pointer_value,
                       secondary_pointer_name, secondary_pointer_value,
                       tertiary_pointer_name, tertiary_pointer_value
                FROM global_download_progress 
                WHERE task_type = %s 
                LIMIT 1
            """, (task_type,))
            result = cursor.fetchone()
            if result:
                progress = {
                    'primary_name': result['primary_pointer_name'] or '',
                    'primary_value': result['primary_pointer_value'] or '',
                    'secondary_name': result['secondary_pointer_name'] or '',
                    'secondary_value': result['secondary_pointer_value'] or '',
                    'tertiary_name': result['tertiary_pointer_name'] or '',
                    'tertiary_value': result['tertiary_pointer_value'] or ''
                }
                logger.debug(f"[{__name__}.{func_name}] 进度读取成功: {task_type} = {progress}")
                return progress
            else:
                logger.debug(f"[{__name__}.{func_name}] 无进度记录: {task_type}")
                return None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 进度读取失败: {task_type}, {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    # -------------------------------------------------------------------------
    # K线任务进度管理（基于内部核心函数）
    # -------------------------------------------------------------------------
    def set_kline_progress(self, std_stock_code: str, time_frame: KLinePeriod, quarter: str) -> bool:
        """
        设置K线任务下载进度
        :param std_stock_code: 股票代码
        :param time_frame: 时间周期
        :param quarter: 季度，格式如 '2024-Q1'
        :return: 设置是否成功
        """
        func_name = "set_kline_progress"
        logger.debug(f"[{__name__}.{func_name}] 设置K线下载进度: {std_stock_code} {time_frame.value} {quarter}")

        pointers = {
            'primary_name': 'quarter',
            'primary_value': quarter,
            'secondary_name': 'stock_code',
            'secondary_value': std_stock_code,
            'tertiary_name': 'time_frame',
            'tertiary_value': time_frame.value
        }
        return self._write_progress('kline', pointers)

    def get_kline_progress(self) -> Optional[Tuple[str, str, KLinePeriod]]:
        """
        获取K线任务下载进度
        :return: (quarter, stock_code, time_frame) 或 None
        """
        func_name = "get_kline_progress"
        logger.debug(f"[{__name__}.{func_name}] 获取K线下载进度")

        progress = self._read_progress('kline')
        if progress and progress['primary_value']:
            return (
                progress['primary_value'],
                progress['secondary_value'],
                KLinePeriod(progress['tertiary_value'])
            )
        return None

    # -------------------------------------------------------------------------
    # XRXD任务进度管理（基于内部核心函数）
    # -------------------------------------------------------------------------
    def set_xrxd_progress(self, year: int, stock_code: str) -> bool:
        """
        设置XRXD任务下载进度
        :param year: 年份
        :param stock_code: 股票代码
        :return: 设置是否成功
        """
        func_name = "set_xrxd_progress"
        logger.debug(f"[{__name__}.{func_name}] 设置XRXD下载进度: {year} {stock_code}")

        pointers = {
            'primary_name': 'year',
            'primary_value': str(year),
            'secondary_name': 'stock_code',
            'secondary_value': stock_code,
            'tertiary_name': '',
            'tertiary_value': ''
        }
        return self._write_progress('xrxd', pointers)

    def get_xrxd_progress(self) -> Optional[Tuple[int, str]]:
        """
        获取XRXD任务下载进度
        :return: (year, stock_code) 或 None
        """
        func_name = "get_xrxd_progress"
        logger.debug(f"[{__name__}.{func_name}] 获取XRXD下载进度")

        progress = self._read_progress('xrxd')
        if progress and progress['primary_value']:
            return (
                int(progress['primary_value']),
                progress['secondary_value']
            )
        return None

    # -------------------------------------------------------------------------
    # 通用进度管理（直接使用内部核心函数）
    # -------------------------------------------------------------------------
    def set_progress(self, task_type: str, primary_name: str, primary_value: str,
                     secondary_name: str, secondary_value: str,
                     tertiary_name: str = '', tertiary_value: str = '') -> bool:
        """
        通用方法：设置下载进度
        :param task_type: 任务类型
        :param primary_name: 主指针名称
        :param primary_value: 主指针值
        :param secondary_name: 次指针名称
        :param secondary_value: 次指针值
        :param tertiary_name: 三级指针名称（可选）
        :param tertiary_value: 三级指针值（可选）
        :return: 设置是否成功
        """
        func_name = "set_progress"
        logger.debug(f"[{__name__}.{func_name}] 通用设置进度: {task_type}")

        pointers = {
            'primary_name': primary_name,
            'primary_value': primary_value,
            'secondary_name': secondary_name,
            'secondary_value': secondary_value,
            'tertiary_name': tertiary_name,
            'tertiary_value': tertiary_value
        }
        return self._write_progress(task_type, pointers)

    def get_progress(self, task_type: str) -> Optional[Dict[str, str]]:
        """
        通用方法：获取下载进度
        :param task_type: 任务类型
        :return: 进度字典或None
        """
        func_name = "get_progress"
        logger.debug(f"[{__name__}.{func_name}] 通用获取进度: {task_type}")
        return self._read_progress(task_type)
