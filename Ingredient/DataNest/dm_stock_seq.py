# dm_stock_seq.py
from typing import Optional
import pymysql
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

class StockFixedSeqManager:
    def __init__(self, conn):
        self.conn = conn


    def get_first_stock(self) -> Optional[str]:
        """
        获取序列中的第一只股票
        
        Returns:
            第一只股票代码 | None
        """
        func_name = "get_first_stock"
        logger.debug(f"[{__name__}.{func_name}] 获取序列中的第一只股票")
        return self.get_next_stock(None)

    def get_next_stock(self, current_stock_code: Optional[str]) -> Optional[str]:
        """
        获取固定序列中的下一只股票代码
        
        Args:
            current_stock_code: 当前股票代码，None表示获取第一只
            
        Returns:
            下一只股票代码 | None（无数据/已是最后一只）
        """
        func_name = "get_next_stock"
        cursor = None
        try:
            cursor = self.conn.cursor(pymysql.cursors.DictCursor)

            # 一条 SQL 搞定所有场景：性能最优
            sql = """
                SELECT std_stock_code
                FROM stock_fixed_seq
                WHERE
                    -- 传入 None：取所有数据
                    (%s IS NULL)
                    OR
                    -- 传入股票代码：取 id 比当前大的
                    id > (SELECT id FROM stock_fixed_seq WHERE std_stock_code = %s)
                ORDER BY id ASC
                LIMIT 1
            """
            cursor.execute(sql, (current_stock_code, current_stock_code))
            result = cursor.fetchone()

            if result:
                logger.debug(f"[{__name__}.{func_name}] 获取到下一只股票: {result['std_stock_code']}")
                return result['std_stock_code']
            else:
                logger.debug(f"[{__name__}.{func_name}] 无下一只股票 / 表为空，返回None")
                return None

        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 获取下一只股票失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()

    def truncate_table(self) -> bool:
        """
        清空 stock_fixed_seq 表
        
        Returns:
            操作是否成功
        """
        func_name = "truncate_table"
        logger.info(f"[{__name__}.{func_name}] 开始清空 stock_fixed_seq 表")

        cursor = None
        try:
            cursor = self.conn.cursor()

            # 步骤1：清空表
            truncate_sql = "TRUNCATE TABLE stock_fixed_seq"
            cursor.execute(truncate_sql)
            logger.debug(f"[{__name__}.{func_name}] 已清空 stock_fixed_seq 表")
            return True
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 操作失败: {str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def save_stock_codes(self, stock_data: list) -> bool:
        """
        批量插入股票代码到 stock_fixed_seq 表
        不清空表、仅执行批量插入，提升数据库操作效率

        Args:
            stock_data: 股票代码列表，格式示例 ['000001', '000002', '600000', ...]

        Returns:
            操作是否成功
        """
        func_name = "save_stock_codes"
        logger.info(f"[{__name__}.{func_name}] 开始批量写入 {len(stock_data)} 条股票代码数据")

        cursor = None
        try:
            cursor = self.conn.cursor()

            # 空列表校验
            if not stock_data:
                logger.warning(f"[{__name__}.{func_name}] 股票代码列表为空，无数据写入")
                return True

            # 格式标准化：确保每个元素都是字符串类型的股票代码
            standardized_data = []
            for code in stock_data:
                if isinstance(code, str) and code.strip():
                    standardized_data.append((code.strip(),))  # 转成元组格式适配 executemany
                else:
                    logger.warning(f"[{__name__}.{func_name}] 无效股票代码，跳过：{code}")

            if not standardized_data:
                logger.warning(f"[{__name__}.{func_name}] 无有效股票代码，终止插入")
                return True

            # 批量插入 SQL（仅插入 stock_code，ID 由数据库自增）
            insert_sql = """
            INSERT INTO stock_fixed_seq (std_stock_code)
            VALUES (%s)
            """
            cursor.executemany(insert_sql, standardized_data)
            self.conn.commit()

            logger.info(f"[{__name__}.{func_name}] 成功写入 {len(standardized_data)} 条有效股票代码数据")
            return True

        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 批量插入股票代码失败: {str(e)}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def count_stocks(self) -> int:
        """
        统计 stock_fixed_seq 表中的股票总数
        
        Returns:
            股票总数
        """
        func_name = "count_stocks"
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM stock_fixed_seq")
            stock_count = cursor.fetchone()[0]
            cursor.close()
            
            if stock_count <= 0:
                logger.warning(f"[{__name__}.{func_name}] stock_fixed_seq表无股票数据")
            return stock_count
        
        except Exception as e:
            logger.error(
                f"[{__name__}.{func_name}] 查询股票总数失败: {str(e)}",
                exc_info=True
            )
            return 0


    def get_stock_position(self, stock_code: str) -> Optional[int]:
        """
        查询指定股票的顺序位置
        首只股票顺序位置为0，后面依次增加
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票的顺序位置 | None（股票不存在）
        """
        func_name = "get_stock_position"
        logger.debug(f"[{__name__}.{func_name}] 查询股票 {stock_code} 的顺序位置")
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            # 查询指定股票的ID
            sql = """
                SELECT id FROM stock_fixed_seq WHERE std_stock_code = %s
            """
            cursor.execute(sql, (stock_code,))
            result = cursor.fetchone()
            
            if not result:
                logger.debug(f"[{__name__}.{func_name}] 股票 {stock_code} 不存在")
                return None
            
            # 计算该股票前面的股票数量，即为顺序位置（从0开始）
            stock_id = result[0]
            position_sql = """
                SELECT COUNT(*) FROM stock_fixed_seq WHERE id < %s
            """
            cursor.execute(position_sql, (stock_id,))
            position = cursor.fetchone()[0]
            
            logger.debug(f"[{__name__}.{func_name}] 股票 {stock_code} 的顺序位置为: {position}")
            return position
        
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 查询股票顺序位置失败: {str(e)}")
            return None
        finally:
            if cursor:
                cursor.close()
    
    def stock_exists(self, stock_code: str) -> bool:
        """
        检查股票代码是否在 stock_fixed_seq 表中
        
        Args:
            stock_code: 股票代码
            
        Returns:
            股票是否存在
        """
        func_name = "is_stock_exists"
        logger.debug(f"[{__name__}.{func_name}] 检查股票 {stock_code} 是否存在")
        
        cursor = None
        try:
            cursor = self.conn.cursor()
            
            # 查询股票是否存在
            sql = """
                SELECT COUNT(*) FROM stock_fixed_seq WHERE std_stock_code = %s
            """
            cursor.execute(sql, (stock_code,))
            count = cursor.fetchone()[0]
            
            exists = count > 0
            logger.debug(f"[{__name__}.{func_name}] 股票 {stock_code} {'存在' if exists else '不存在'}")
            return exists
        
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 检查股票是否存在失败: {str(e)}")
            return False
        finally:
            if cursor:
                cursor.close()
