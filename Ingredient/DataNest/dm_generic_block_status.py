# dm_generic_block_status.py
from typing import Optional, Tuple, Dict, List
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlBlockStatus, DlTaskType

logger = get_logger(__name__)

class GenericBlockStatusDM:
    """通用区块状态管理器"""
    
    def __init__(self, db_conn):
        """
        初始化管理器
        :param db_conn: 数据库连接
        """
        self.db_conn = db_conn
        self.logger = get_logger(__name__)
    
    def get_block_status(self, block_key_1: str, task_type: DlTaskType, block_key_2: str = "", block_key_3: str = "") -> DlBlockStatus:
        """
        获取区块状态
        
        :param block_key_1: 区块主键1
        :param task_type: 任务类型（DlTaskType枚举）
        :param block_key_2: 区块主键2
        :param block_key_3: 区块主键3
        :return: 区块状态
        """
        func_name = "get_block_status"
        self.logger.debug(f"[{__name__}.{func_name}] 获取区块状态: {block_key_1}, {task_type.value}, {block_key_2}, {block_key_3}")
        
        cursor = None
        try:
            cursor = self.db_conn.cursor()
            
            # 构建 WHERE 子句
            where_clause, params = self._build_where_clause(block_key_1, task_type.value, block_key_2, block_key_3)
            
            sql = f"""
            SELECT status FROM generic_block_status
            WHERE {where_clause}
            """
            
            cursor.execute(sql, params)
            result = cursor.fetchone()
            
            if result:
                return DlBlockStatus(result[0])
            return DlBlockStatus.NOT_COMPLETED
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 查询失败: {str(e)}")
            return DlBlockStatus.NOT_COMPLETED
        finally:
            if cursor:
                cursor.close()
    
    def update_block_status(self, block_key_1: str, task_type: DlTaskType, status: DlBlockStatus, 
                          block_key_2: str = "", block_key_3: str = "", **kwargs):
        """
        更新区块状态
        
        :param block_key_1: 区块主键1
        :param task_type: 任务类型（DlTaskType枚举）
        :param status: 区块状态
        :param block_key_2: 区块主键2
        :param block_key_3: 区块主键3
        :param kwargs: 其他参数（block_name, total_items, success_count, fail_count, error_message等）
        """
        func_name = "update_block_status"
        self.logger.debug(f"[{__name__}.{func_name}] 更新区块状态: {block_key_1}, {task_type.value}, {status.value}")
        
        cursor = None
        try:
            cursor = self.db_conn.cursor()
            
            # 验证状态
            if not self._validate_status(status):
                self.logger.error(f"[{__name__}.{func_name}] 无效的状态值: {status}")
                return

            # 构建字段和值
            fields = ['block_key_1', 'block_key_2', 'block_key_3', 'task_type', 'status']
            values = [block_key_1, block_key_2, block_key_3, task_type.value, status.value]
            
            # 处理可选字段
            optional_fields = ['block_name', 'total_items', 'success_count', 'fail_count', 'error_message', 'extra_data']
            for field in optional_fields:
                if field in kwargs:
                    fields.append(field)
                    values.append(kwargs[field])
            
            # 处理完成时间
            completed_at_added = False
            if status == DlBlockStatus.COMPLETED:
                fields.append('completed_at')
                completed_at_added = True
            
            # 构建 SQL
            if completed_at_added:
                # 为除了 completed_at 之外的字段生成占位符
                placeholders = ', '.join(['%s'] * (len(fields) - 1))
                # 添加 CURRENT_TIMESTAMP
                placeholders += ', CURRENT_TIMESTAMP'
            else:
                # 为所有字段生成占位符
                placeholders = ', '.join(['%s'] * len(fields))
            
            sql = f"""
            INSERT INTO generic_block_status ({', '.join(fields)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE
                status = VALUES(status)
            """
            
            # 添加其他字段的更新
            update_fields = optional_fields.copy()
            if completed_at_added:
                update_fields.append('completed_at')
            
            for field in update_fields:
                if field in kwargs:
                    sql += f", {field} = VALUES({field})"
                elif field == 'completed_at' and completed_at_added:
                    sql += f", {field} = CURRENT_TIMESTAMP"
            
            # 执行 SQL
            cursor.execute(sql, values)
            self.db_conn.commit()
            
            self.logger.debug(f"[{__name__}.{func_name}] 区块状态更新成功")
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 更新失败: {str(e)}")
            self.db_conn.rollback()
        finally:
            if cursor:
                cursor.close()
    
    def get_block_count(self, task_type: DlTaskType, start_year: int, end_year: int, status: List[DlBlockStatus] = []) -> int:
        """
        获取指定状态的区块数量

        :param task_type: 任务类型（DlTaskType枚举）
        :param start_year: 起始年份
        :param end_year: 结束年份
        :param status: 区块状态列表（空列表表示所有状态）
        :return: 区块数量
        """
        func_name = "get_block_count"
        # 处理 status 为 None 的情况，设为空列表
        if status is None:
            status = []
        self.logger.debug(f"[{__name__}.{func_name}] 获取区块数量: {task_type.value}, {start_year}-{end_year}, {[s.value for s in status] if status else 'all'}")

        # 确定是否需要股票限制
        need_stock_join = task_type in [DlTaskType.ADJ_FACTOR, 
                                        DlTaskType.KLINE, 
                                        DlTaskType.XRXD,
                                        DlTaskType.STOCK_PROFIT]

        # 构建SQL
        if need_stock_join:
            sql = """
            SELECT COUNT(*) FROM generic_block_status gbs
            JOIN stock_fixed_seq sfs ON gbs.block_key_2 = sfs.std_stock_code
            WHERE gbs.task_type = %s
            """
        else:
            sql = """
            SELECT COUNT(*) FROM generic_block_status
            WHERE task_type = %s
            """

        # 构建参数和条件
        params = [task_type.value]

        # 状态过滤
        if status:
            placeholders = ','.join(['%s'] * len(status))
            sql += f" AND {'gbs.' if need_stock_join else ''}status IN ({placeholders})"
            params.extend([s.value for s in status])

        # 年份过滤
        if start_year:
            sql += f" AND {'gbs.' if need_stock_join else ''}block_key_1 >= %s"
            params.append(str(start_year))

        if end_year:
            sql += f" AND {'gbs.' if need_stock_join else ''}block_key_1 < %s"
            params.append(str(end_year))

        # 执行查询
        cursor = None
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(sql, params)
            count = cursor.fetchone()[0]
            return count
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 查询失败: {str(e)}")
            return 0
        finally:
            if cursor:
                cursor.close()
    
    def _build_where_clause(self, block_key_1: str, task_type: str, 
                          block_key_2: str = "", block_key_3: str = "") -> Tuple[str, list]:
        """
        构建 WHERE 子句
        
        :param block_key_1: 区块主键1
        :param task_type: 任务类型
        :param block_key_2: 区块主键2
        :param block_key_3: 区块主键3
        :return: (WHERE子句, 参数列表)
        """
        conditions = [
            "block_key_1 = %s",
            "block_key_2 = %s",
            "block_key_3 = %s",
            "task_type = %s"
        ]
        params = [block_key_1, block_key_2, block_key_3, task_type]
        
        return " AND ".join(conditions), params
    
    def _validate_status(self, status: DlBlockStatus) -> bool:
        """
        验证状态值
        
        :param status: 状态值
        :return: 是否有效
        """
        valid_statuses = [DlBlockStatus.NOT_COMPLETED, DlBlockStatus.SKIPPED, 
                         DlBlockStatus.COMPLETED, DlBlockStatus.ERROR]
        return status in valid_statuses