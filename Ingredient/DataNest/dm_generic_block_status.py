# dm_generic_block_status.py
from KitchenBase.download_enums import PointerField
from typing import Optional, Tuple, Dict, List, Union
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlBlockStatus, DlTaskType
from KitchenBase import DownloadParameters

logger = get_logger(__name__)

class GenericBlockStatusDM:
    """
    通用区块状态管理器
    
    注意：
    - 相关函数（如get_block_count）添加了stock_table参数，用于指定股票范围的来源表
    - 这样设计的原因是为了支持灵活的股票范围过滤，不再局限于默认的stock_fixed_seq表
    - 当需要统计特定股票集合的区块状态时，可以通过指定不同的股票表来实现
    - 默认值仍为"stock_fixed_seq"，保持向后兼容性
    """
    
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

    def clear_task_statuses(self, task_type: DlTaskType) -> int:
        """
        清理指定任务的所有区块状态。

        :param task_type: 任务类型
        :return: 删除的行数
        """
        func_name = "clear_task_statuses"
        cursor = None
        try:
            cursor = self.db_conn.cursor()
            cursor.execute(
                "DELETE FROM generic_block_status WHERE task_type = %s",
                (task_type.value,)
            )
            deleted_count = cursor.rowcount
            self.db_conn.commit()
            self.logger.info(f"[{__name__}.{func_name}] 已清理 {task_type.value} 区块状态 {deleted_count} 条")
            return deleted_count
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 清理失败: {str(e)}")
            self.db_conn.rollback()
            return 0
        finally:
            if cursor:
                cursor.close()

    def _map_pointer_fields_to_block_keys(self, pointer_fields: Tuple[PointerField, ...]) -> Dict[PointerField, Optional[str]]:
        """
        将 pointer_fields 映射到实际数据库字段名称

        Args:
            pointer_fields: 指针字段元组，描述 block_key_1/2/3 的含义

        Returns:
            Dict[PointerField, Optional[str]]: 包含 PointerField 到 block_key_n 映射的字典
        """
        field_mapping: Dict[PointerField, Optional[str]] = {}

        for field in pointer_fields:
            try:
                idx = pointer_fields.index(field)
                block_key = f'block_key_{idx + 1}'
                field_mapping[field] = block_key
            except ValueError:
                field_mapping[field] = None

        return field_mapping

    def get_block_count(self,
                        task_type: DlTaskType,
                        pointer_fields: Tuple[PointerField, ...],
                        download_params: DownloadParameters,
                        status_list: Optional[List[DlBlockStatus]] = None) -> int:
        """
        获取指定状态的股票时间周期区块数量

        过滤条件（根据 pointer_fields 动态启用）：
        1. task_type 类型匹配
        2. status_list 状态匹配（可选，默认所有状态）
        3. STOCK_CODE 存在时：进行股票过滤
        4. TIME_FRAME 存在时：使用 download_params.kline_period_list 进行过滤
        5. YEAR/QUARTER 存在时：使用 download_params.year_range 进行年份过滤

        字段映射（通过 pointer_fields 参数指定）：
        - pointer_fields[0] 对应 block_key_1
        - pointer_fields[1] 对应 block_key_2
        - pointer_fields[2] 对应 block_key_3

        特殊处理：
        - PointerField.YEAR 优先于 PointerField.QUARTER
        - 如果 pointer_fields 不包含 STOCK_CODE，则不进行股票过滤
        - 如果 pointer_fields 不包含 TIME_FRAME，则不进行时间周期过滤
        - 如果 status_list 为空或 None，则匹配所有状态

        :param task_type: 任务类型（DlTaskType枚举）
        :param pointer_fields: 指针字段元组，描述 block_key_1/2/3 的含义
        :param download_params: 下载参数容器
        :param status_list: 状态列表，用于过滤指定状态的区块，默认为 None（匹配所有状态）
        :return: 区块数量
        """
        func_name = "get_block_count"

        self.logger.debug(f"[{__name__}.{func_name}] 获取区块数量: {task_type.value}, pointer_fields={pointer_fields}, status_list={status_list}")

        year_range = download_params.year_range
        start_year, end_year = year_range

        field_mapping = self._map_pointer_fields_to_block_keys(pointer_fields)
        stock_block_key = field_mapping.get(PointerField.STOCK_CODE)
        time_frame_block_key = field_mapping.get(PointerField.TIME_FRAME)
        quarter_block_key = field_mapping.get(PointerField.QUARTER)
        year_block_key = field_mapping.get(PointerField.YEAR)

        time_period_block_key = year_block_key if year_block_key else quarter_block_key
        use_year = bool(year_block_key)

        kline_period_list = download_params.kline_period_list
        time_frame_values = [kp.value for kp in kline_period_list] if kline_period_list else []

        sql = """
        SELECT COUNT(*)
        FROM generic_block_status gbs
        """

        where_conditions = ["gbs.task_type = %s"]
        params = [task_type.value]

        if status_list:
            status_values = [s.value for s in status_list]
            status_placeholders = ','.join(['%s'] * len(status_values))
            where_conditions.append(f"gbs.status IN ({status_placeholders})")
            params.extend(status_values)

        if stock_block_key:
            if download_params.has_custom_stock_list() and download_params.stock_codes:
                stock_codes = download_params.stock_codes
                placeholders = ','.join(['%s'] * len(stock_codes))
                where_conditions.append(f"gbs.{stock_block_key} IN ({placeholders})")
                params.extend(stock_codes)
            else:
                stock_table = download_params.stock_table
                sql += f" JOIN {stock_table} sfs ON gbs.{stock_block_key} = sfs.std_stock_code\n"

        if time_frame_block_key and time_frame_values:
            time_frame_placeholders = ','.join(['%s'] * len(time_frame_values))
            where_conditions.append(f"gbs.{time_frame_block_key} IN ({time_frame_placeholders})")
            params.extend(time_frame_values)

        if time_period_block_key:
            if use_year:
                where_conditions.append(f"gbs.{time_period_block_key} >= %s")
                where_conditions.append(f"gbs.{time_period_block_key} < %s")
                params.extend([str(start_year), str(end_year)])
            else:
                where_conditions.append(f"SUBSTRING(gbs.{time_period_block_key}, 1, 4) >= %s")
                where_conditions.append(f"SUBSTRING(gbs.{time_period_block_key}, 1, 4) < %s")
                params.extend([str(start_year), str(end_year)])

        if where_conditions:
            sql += "WHERE " + " AND ".join(where_conditions)

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
