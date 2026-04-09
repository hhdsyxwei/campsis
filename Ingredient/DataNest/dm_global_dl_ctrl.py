# dm_global_dl_ctrl.py
from KitchenBase.download_enums import DlTaskType
"""
全局下载控制块管理模块
集中管理对 global_dl_ctrl_block 表的访问
区块概念：
- 区块代表一定范围的下载集合
- 每个区块包含多个年份和多个股票的下载任务
- 区块排序规则：
  1. 先按年份升序（从start_year到end_year-1）
  2. 同一年内按stock_fixed_seq表的顺序
任务概念：
- 任务代表一定范围的区块集合
- 一个任务通常对应一个完整的下载任务，包含多个年份和多个股票的区块
- 任务类型（task_type）用于区分不同的数据下载任务，如 'xrxd'、'kline' 等
- 任务状态通过下载指针来跟踪，指针指向当前正在下载的区块
指针概念：
- 指针用于跟踪当前正在下载的区块
- 每个任务有一个独立的指针，用于记录当前下载的区块
- 指针包含 primary_name, primary_value, secondary_name, secondary_value, tertiary_name, tertiary_value 等字段
- 指针包含 startup_params, completed_blocks, total_blocks 等字段
"""
from typing import Optional, Tuple, Dict, Any
import pymysql
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import KLinePeriod
from KitchenBase.download_enums import DlTaskStatus, DlTaskType

logger = get_logger(__name__)


class GlobalDlCtrlBlockManager:
    """全局下载控制块管理器"""

    def __init__(self, conn):
        self.conn = conn

    # -------------------------------------------------------------------------   
    def write_dl_pointer(self, task_type: DlTaskType, pointers: Dict[str, str], 
                      startup_params: Optional[Dict] = None, 
                      completed_blocks: int = 0, 
                      total_blocks: int = 0) -> bool:
        """
        完整进度更新接口
        :param task_type: 任务类型
        :param pointers: 指针信息，包含 primary_name, primary_value, secondary_name, secondary_value, tertiary_name, tertiary_value
        :param startup_params: 启动参数
        :param completed_blocks: 已下载区块数量
        :param total_blocks: 区块总数量
        :return: 是否成功
        """
        func_name = "write_dl_pointer"
        primary_name = pointers.get('primary_name', '')
        primary_value = pointers.get('primary_value', '')
        secondary_name = pointers.get('secondary_name', '')
        secondary_value = pointers.get('secondary_value', '')
        tertiary_name = pointers.get('tertiary_name', '')
        tertiary_value = pointers.get('tertiary_value', '')

        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                INSERT INTO global_dl_ctrl_block 
                (task_type, primary_pointer_name, primary_pointer_value, 
                 secondary_pointer_name, secondary_pointer_value, 
                 tertiary_pointer_name, tertiary_pointer_value, 
                 startup_params, completed_blocks, total_blocks, update_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    primary_pointer_name = VALUES(primary_pointer_name),
                    primary_pointer_value = VALUES(primary_pointer_value),
                    secondary_pointer_name = VALUES(secondary_pointer_name),
                    secondary_pointer_value = VALUES(secondary_pointer_value),
                    tertiary_pointer_name = VALUES(tertiary_pointer_name),
                    tertiary_pointer_value = VALUES(tertiary_pointer_value),
                    startup_params = VALUES(startup_params),
                    completed_blocks = VALUES(completed_blocks),
                    total_blocks = VALUES(total_blocks),
                    update_time = CURRENT_TIMESTAMP
            """, (task_type.value, primary_name, primary_value, secondary_name, secondary_value,
                  tertiary_name, tertiary_value, startup_params, completed_blocks, total_blocks))
            self.conn.commit()
            logger.debug(f"[{__name__}.{func_name}] 进度写入成功: {task_type.value}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 进度写入失败: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def read_dl_pointer(self, task_type: DlTaskType) -> Optional[Dict[str, Any]]:
        """
        完整进度读取接口
        :param task_type: 任务类型
        :return: 包含指针信息、启动参数、区块数量的字典
        """
        func_name = "read_progress"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT primary_pointer_name, primary_pointer_value,
                       secondary_pointer_name, secondary_pointer_value,
                       tertiary_pointer_name, tertiary_pointer_value,
                       startup_params, completed_blocks, total_blocks
                FROM global_dl_ctrl_block 
                WHERE task_type = %s 
                LIMIT 1
            """, (task_type.value,))
            result = cursor.fetchone()
            # 主指针不空指才认为指针存在
            if result and result['primary_pointer_name']:
                # 检查主指针是否为空
                progress = {
                    'primary_name': result['primary_pointer_name'] or '',
                    'primary_value': result['primary_pointer_value'] or '',
                    'secondary_name': result['secondary_pointer_name'] or '',
                    'secondary_value': result['secondary_pointer_value'] or '',
                    'tertiary_name': result['tertiary_pointer_name'] or '',
                    'tertiary_value': result['tertiary_pointer_value'] or '',
                    'startup_params': result['startup_params'],
                    'completed_blocks': result['completed_blocks'] or 0,
                    'total_blocks': result['total_blocks'] or 0
                }
                return progress
            return None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 进度读取失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    # -------------------------------------------------------------------------   
    def save_startup_params(self, task_type: str, startup_params: Dict) -> bool:
        """
        单独保存启动参数
        :param task_type: 任务类型
        :param startup_params: 启动参数
        :return: 是否成功
        """
        func_name = "save_startup_params"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                INSERT INTO global_dl_ctrl_block 
                (task_type, startup_params, update_time)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    startup_params = VALUES(startup_params),
                    update_time = CURRENT_TIMESTAMP
            """, (task_type, startup_params))
            self.conn.commit()
            logger.debug(f"[{__name__}.{func_name}] 启动参数保存成功: {task_type}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 启动参数保存失败: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def read_startup_params(self, task_type: str) -> Optional[Dict]:
        """
        单独读取启动参数
        :param task_type: 任务类型
        :return: 启动参数
        """
        func_name = "read_startup_params"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT startup_params
                FROM global_dl_ctrl_block 
                WHERE task_type = %s 
                LIMIT 1
            """, (task_type,))
            result = cursor.fetchone()
            return result['startup_params'] if result else None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 启动参数读取失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    # -------------------------------------------------------------------------   
    def update_block_count(self, task_type: str, completed_blocks: int, total_blocks: int) -> bool:
        """
        更新区块计数
        :param task_type: 任务类型
        :param completed_blocks: 已下载区块数量
        :param total_blocks: 区块总数量
        :return: 是否成功
        """
        func_name = "update_block_count"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                INSERT INTO global_dl_ctrl_block 
                (task_type, completed_blocks, total_blocks, update_time)
                VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    completed_blocks = VALUES(completed_blocks),
                    total_blocks = VALUES(total_blocks),
                    update_time = CURRENT_TIMESTAMP
            """, (task_type, completed_blocks, total_blocks))
            self.conn.commit()
            logger.debug(f"[{__name__}.{func_name}] 区块计数更新成功: {task_type}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 区块计数更新失败: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()

    def get_block_count(self, task_type: str) -> Tuple[int, int]:
        """
        获取区块计数
        :param task_type: 任务类型
        :return: (已下载区块数量, 区块总数量)
        """
        func_name = "get_block_count"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT completed_blocks, total_blocks
                FROM global_dl_ctrl_block 
                WHERE task_type = %s 
                LIMIT 1
            """, (task_type,))
            result = cursor.fetchone()
            if result:
                return (result['completed_blocks'] or 0, result['total_blocks'] or 0)
            return (0, 0)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 区块计数读取失败: {str(e)}")
            return (0, 0)
        finally:
            if cursor:
                cursor.close()

    # -------------------------------------------------------------------------   
    def set_kline_dl_pointer(self, quarter: str, stock_code: str, time_frame: KLinePeriod, 
                          startup_params: Optional[Dict] = None, 
                          completed_blocks: int = 0, 
                          total_blocks: int = 0) -> bool:
        """
        设置K线下载进度
        :param quarter: 季度 (如: 2024-Q1)
        :param stock_code: 股票代码
        :param time_frame: 时间周期
        :param startup_params: 启动参数
        :param completed_blocks: 已下载区块数量
        :param total_blocks: 区块总数量
        :return: 是否成功
        """
        pointers = {
            'primary_name': 'quarter',
            'primary_value': quarter,
            'secondary_name': 'stock_code',
            'secondary_value': stock_code,
            'tertiary_name': 'time_frame',
            'tertiary_value': time_frame.value
        }
        return self.write_dl_pointer(DlTaskType.KLINE, pointers, startup_params, completed_blocks, total_blocks)

    def get_kline_dl_pointer(self) -> Optional[Tuple[str, str, KLinePeriod, Optional[Dict], int, int]]:
        """
        获取K线下载进度
        :return: (季度, 股票代码, 时间周期, 启动参数, 已下载区块数量, 区块总数量)
        """
        progress = self.read_dl_pointer(DlTaskType.KLINE)
        if progress:
            try:
                quarter = progress['primary_value']
                stock_code = progress['secondary_value']
                time_frame = KLinePeriod(progress['tertiary_value']) if progress['tertiary_value'] else KLinePeriod.MIN_5
                startup_params = progress['startup_params']
                completed_blocks = progress['completed_blocks']
                total_blocks = progress['total_blocks']
                return (quarter, stock_code, time_frame, startup_params, completed_blocks, total_blocks)
            except (ValueError, KeyError) as e:
                logger.warning(f"[{__name__}.get_kline_progress] 进度数据格式错误: {str(e)}")
                return None
        return None

    # -------------------------------------------------------------------------   
    def set_xrxd_dl_pointer(self, year: int, stock_code: str, 
                         startup_params: Optional[Dict] = None, 
                         completed_blocks: int = 0, 
                         total_blocks: int = 0) -> bool:
        """
        设置XRXD下载进度
        :param year: 年份
        :param stock_code: 股票代码
        :param startup_params: 启动参数
        :param completed_blocks: 已下载区块数量
        :param total_blocks: 区块总数量
        :return: 是否成功
        """
        pointers = {
            'primary_name': 'year',
            'primary_value': str(year),
            'secondary_name': 'stock_code',
            'secondary_value': stock_code,
            'tertiary_name': '',
            'tertiary_value': ''
        }
        return self.write_dl_pointer(DlTaskType.XRXD, pointers, startup_params, completed_blocks, total_blocks)

    def get_xrxd_dl_pointer(self) -> Optional[Tuple[int, str, Optional[Dict], int, int]]:
        """
        获取XRXD下载进度
        :return: (年份, 股票代码, 启动参数, 已下载区块数量, 区块总数量)
        """
        progress = self.read_dl_pointer(DlTaskType.XRXD)
        if progress:
            try:
                year = int(progress['primary_value']) if progress['primary_value'] else 0
                stock_code = progress['secondary_value']
                startup_params = progress['startup_params']
                completed_blocks = progress['completed_blocks']
                total_blocks = progress['total_blocks']
                return (year, stock_code, startup_params, completed_blocks, total_blocks)
            except (ValueError, KeyError) as e:
                logger.warning(f"[{__name__}.get_xrxd_progress] 进度数据格式错误: {str(e)}")
                return None
        return None

    # -------------------------------------------------------------------------
    def set_adj_fct_dl_pointer(self, year: int, stock_code: str, 
                                     startup_params: Optional[Dict] = None, 
                                     completed_blocks: int = 0, 
                                     total_blocks: int = 0) -> bool:
        """
        设置复权因子下载进度
        :param year: 年份
        :param stock_code: 股票代码
        :param startup_params: 启动参数
        :param completed_blocks: 已下载区块数量
        :param total_blocks: 区块总数量
        :return: 是否成功
        """
        pointers = {
            'primary_name': 'year',
            'primary_value': str(year),
            'secondary_name': 'stock_code',
            'secondary_value': stock_code,
            'tertiary_name': '',
            'tertiary_value': ''
        }
        return self.write_dl_pointer(DlTaskType.ADJUSTMENT_FACTOR, pointers, startup_params, completed_blocks, total_blocks)

    def get_adj_fct_dl_pointer(self) -> Optional[Tuple[int, str, Optional[Dict], int, int]]:
        """
        获取复权因子下载进度
        :return: (年份, 股票代码, 启动参数, 已下载区块数量, 区块总数量)
        """
        progress = self.read_dl_pointer(DlTaskType.ADJUSTMENT_FACTOR)
        if progress:
            try:
                year = int(progress['primary_value']) if progress['primary_value'] else 0
                stock_code = progress['secondary_value']
                startup_params = progress['startup_params']
                completed_blocks = progress['completed_blocks']
                total_blocks = progress['total_blocks']
                return (year, stock_code, startup_params, completed_blocks, total_blocks)
            except (ValueError, KeyError) as e:
                logger.warning(f"[{__name__}.get_adjustment_factor_progress] 进度数据格式错误: {str(e)}")
                return None
        return None

    def set_stock_industry_dl_pointer(self, year: int, stock_code: str, 
                                        startup_params: Optional[Dict] = None, 
                                        completed_blocks: int = 0, 
                                        total_blocks: int = 0) -> bool:
        """
        设置行业分类下载进度
        :param year: 年份
        :param stock_code: 股票代码
        :param startup_params: 启动参数
        :param completed_blocks: 已下载区块数量
        :param total_blocks: 区块总数量
        :return: 是否成功
        """
        pointers = {
            'primary_name': 'year',
            'primary_value': str(year),
            'secondary_name': 'stock_code',
            'secondary_value': stock_code,
            'tertiary_name': '',
            'tertiary_value': ''
        }
        return self.write_dl_pointer(DlTaskType.INDUSTRY, pointers, startup_params, completed_blocks, total_blocks)

    def get_stock_industry_dl_pointer(self) -> Optional[Tuple[int, str, Optional[Dict], int, int]]:
        """
        获取行业分类下载进度
        :return: (年份, 股票代码, 启动参数, 已下载区块数量, 区块总数量)
        """
        progress = self.read_dl_pointer(DlTaskType.INDUSTRY)
        if progress:
            try:
                year = int(progress['primary_value']) if progress['primary_value'] else 0
                stock_code = progress['secondary_value']
                startup_params = progress['startup_params']
                completed_blocks = progress['completed_blocks']
                total_blocks = progress['total_blocks']
                return (year, stock_code, startup_params, completed_blocks, total_blocks)
            except (ValueError, KeyError) as e:
                logger.warning(f"[{__name__}.get_stock_industry_dl_pointer] 进度数据格式错误: {str(e)}")
                return None
        return None

    def clear_dl_pointer(self, task_type: DlTaskType) -> bool:
        """
        将下载指针设置为空
        :param task_type: 任务类型
        :return: 是否成功
        """
        func_name = "clear_download_pointer"
        try:
            pointers = {
                'primary_name': '',
                'primary_value': '',
                'secondary_name': '',
                'secondary_value': '',
                'tertiary_name': '',
                'tertiary_value': ''
            }
            return self.write_dl_pointer(task_type, pointers)
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 清空下载指针失败: {str(e)}")
            return False

    def delete_task(self, task_type: str) -> bool:
        """
        删除指定类型的任务记录
        :param task_type: 任务类型
        :return: 是否成功
        """
        func_name = "delete_task"
        try:
            cursor = self.conn.cursor()
            sql = "DELETE FROM global_dl_ctrl_block WHERE task_type = %s"
            cursor.execute(sql, (task_type,))
            self.conn.commit()
            logger.debug(f"[{__name__}.{func_name}] 任务删除成功: {task_type}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 任务删除失败: {str(e)}")
            return False

    def task_exists(self, task_type: DlTaskType) -> bool:
        """
        查询指定类型的任务是否存在
        
        任务概念：
        - 任务代表一定范围的区块集合
        - 一个任务通常对应一个完整的下载任务，包含多个年份和多个股票的区块
        - 任务类型（task_type）用于区分不同的数据下载任务，如 'xrxd'、'kline' 等
        - 任务状态通过下载指针来跟踪，指针指向当前正在下载的区块
        
        :param task_type: 任务类型
        :return: True 表示任务存在，False 表示任务不存在
        """
        func_name = "task_exists"
        try:
            progress = self.read_dl_pointer(task_type)
            return progress is not None
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询任务是否存在失败: {str(e)}")
            return False

    def is_dl_pointer_empty(self, task_type: DlTaskType) -> bool:
        """
        判断当前下载指针是否为空
        :param task_type: 任务类型
        :return: True 表示指针为空，False 表示指针不为空
        """
        func_name = "is_download_pointer_empty"
        try:
            progress = self.read_dl_pointer(task_type)
            if progress:
                primary_value = progress['primary_value']
                secondary_value = progress['secondary_value']
                tertiary_value = progress['tertiary_value']
                # 主指针为空时，认为指针为空
                return not primary_value
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 判断下载指针失败: {str(e)}")
            return False

    def set_task_status(self, task_type: DlTaskType, status: DlTaskStatus) -> bool:
        """
        设置指定任务类型的状态
        :param task_type: 任务类型
        :param status: 任务状态
        :return: 是否成功
        """
        func_name = "set_task_status"
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                INSERT INTO global_dl_ctrl_block 
                (task_type, task_status, update_time)
                VALUES (%s, %s, CURRENT_TIMESTAMP)
                ON DUPLICATE KEY UPDATE
                    task_status = VALUES(task_status),
                    update_time = CURRENT_TIMESTAMP
            """, (task_type.value, status.value))
            self.conn.commit()
            logger.info(f"[{__name__}.{func_name}] 任务状态设置成功: {task_type} -> {status.value}")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 任务状态设置失败: {str(e)}")
            return False
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()

    def get_task_status(self, task_type: DlTaskType) -> DlTaskStatus:
        """
        获取指定任务类型的状态
        如果任务不存在，或者状态值异常，返回DlTaskStatus.NOT_STARTED
        如果发生其它未知异常，则异常向外抛出
        因此，该方法正常返回时返回值永不为None
        :param task_type: 任务类型
        :return: 任务状态或None
        """
        func_name = "get_task_status"
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT task_status
                FROM global_dl_ctrl_block 
                WHERE task_type = %s 
                LIMIT 1
            """, (task_type.value,))
            result = cursor.fetchone()
            if result and result['task_status']:
                try:
                    return DlTaskStatus(result['task_status'])
                except ValueError:
                    logger.warning(f"[{__name__}.{func_name}] 任务状态值无效: {result['task_status']}")
                    return DlTaskStatus.NOT_STARTED
            return DlTaskStatus.NOT_STARTED
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 任务状态获取失败: {str(e)}")
            raise e
        finally:
            if 'cursor' in locals() and cursor:
                cursor.close()