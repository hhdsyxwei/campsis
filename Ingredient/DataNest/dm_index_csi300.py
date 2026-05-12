# dm_index_csi300.py
import pymysql
import pandas as pd
from KitchenBase.logger_config import get_logger
from Ingredient.DataNest.dm_standard_columns import IndexCsi300StandardColumns

logger = get_logger(__name__)


class IndexCsi300Manager:
    """沪深300成分股数据管理器"""

    def __init__(self, connection):
        self.conn = connection

    def save_csi300_component(self, data: pd.DataFrame) -> bool:
        """
        保存沪深300成分股数据到数据库

        Args:
            data: DataFrame 格式的成分股数据，需包含以下列：
                - std_stock_code: 股票代码
                - stock_name: 股票名称
                - update_date: 数据更新日期

        Returns:
            是否保存成功
        """
        func_name = "save_csi300_component"

        if data.empty:
            logger.info(f"[{__name__}.{func_name}] 数据为空，无需保存")
            return True

        logger.info(f"[{__name__}.{func_name}] 处理 {len(data)} 条沪深300成分股数据")
        logger.debug(f"[{__name__}.{func_name}] 数据列名: {list(data.columns)}")

        records = []
        cols = IndexCsi300StandardColumns

        for _, row in data.iterrows():
            try:
                stock_code = row[cols.STD_STOCK_CODE]
                stock_name = row.get(cols.STOCK_NAME, None)
                update_date = row.get(cols.CSI300_UPDATE_DATE, None)

                # 确保日期是字符串格式
                if isinstance(update_date, pd.Timestamp):
                    update_date = update_date.strftime('%Y-%m-%d')

                records.append((
                    stock_code,
                    stock_name,
                    update_date
                ))
            except (ValueError, KeyError) as e:
                logger.warning(f"[{__name__}.{func_name}] 数据转换错误: {str(e)}")
                logger.warning(f"当前完整记录: {row}")
                continue
            except Exception as e:
                logger.error(f"[{__name__}.{func_name}] 未预期的异常: {str(e)}")
                logger.error(f"当前完整记录: {row}")
                import traceback
                logger.error(f"[{__name__}.{func_name}] 抛出异常时的调用栈:")
                logger.error(traceback.format_exc())
                continue

        if not records:
            logger.info(f"[{__name__}.{func_name}] 无有效数据，无需保存")
            return True

        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = """
            INSERT INTO index_csi300_component 
            (std_stock_code, stock_name, update_date)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                stock_name = VALUES(stock_name),
                update_date = VALUES(update_date)
            """
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.info(f"[{__name__}.{func_name}] ✅ 成功保存 {len(records)} 条沪深300成分股数据")
            return True
        except pymysql.MySQLError as e:
            logger.error(f"[{__name__}.{func_name}] 数据库操作失败: {str(e)}")
            if self.conn.open:
                self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def get_all_csi300_stocks(self) -> pd.DataFrame:
        """
        获取所有沪深300成分股

        Returns:
            DataFrame 格式的成分股列表
        """
        func_name = "get_all_csi300_stocks"

        cursor = None
        try:
            cursor = self.conn.cursor()
            cols = IndexCsi300StandardColumns
            sql = f"""
            SELECT {cols.STD_STOCK_CODE}, {cols.STOCK_NAME}, {cols.CSI300_UPDATE_DATE}
            FROM index_csi300_component
            ORDER BY {cols.STD_STOCK_CODE}
            """
            cursor.execute(sql)
            result = cursor.fetchall()

            if not result:
                logger.info(f"[{__name__}.{func_name}] 未查询到沪深300成分股数据")
                return pd.DataFrame()

            df = pd.DataFrame(
                result,
                columns=[cols.STD_STOCK_CODE, cols.STOCK_NAME, cols.CSI300_UPDATE_DATE]
            )
            logger.info(f"[{__name__}.{func_name}] 查询到 {len(df)} 条沪深300成分股数据")
            return df
        except pymysql.MySQLError as e:
            logger.error(f"[{__name__}.{func_name}] 数据库查询失败: {str(e)}")
            return pd.DataFrame()
        finally:
            if cursor:
                cursor.close()

    def get_csi300_stock_codes(self) -> list:
        """
        获取所有沪深300成分股代码列表

        Returns:
            股票代码列表
        """
        func_name = "get_csi300_stock_codes"

        df = self.get_all_csi300_stocks()
        if df.empty:
            return []

        codes = df[IndexCsi300StandardColumns.STD_STOCK_CODE].tolist()
        logger.info(f"[{__name__}.{func_name}] 获取到 {len(codes)} 只沪深300成分股")
        return codes

    def clear_all_data(self) -> bool:
        """
        清空所有沪深300成分股数据

        Returns:
            是否清空成功
        """
        func_name = "clear_all_data"

        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = "DELETE FROM index_csi300_component"
            cursor.execute(sql)
            self.conn.commit()
            logger.info(f"[{__name__}.{func_name}] 已清空沪深300成分股表")
            return True
        except pymysql.MySQLError as e:
            logger.error(f"[{__name__}.{func_name}] 清空数据失败: {str(e)}")
            if self.conn.open:
                self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

    def get_stock_count(self) -> int:
        """
        获取沪深300成分股数量

        Returns:
            成分股数量
        """
        func_name = "get_stock_count"

        cursor = None
        try:
            cursor = self.conn.cursor()
            sql = "SELECT COUNT(*) FROM index_csi300_component"
            cursor.execute(sql)
            result = cursor.fetchone()
            count = result[0] if result else 0
            logger.info(f"[{__name__}.{func_name}] 当前沪深300成分股数量: {count}")
            return count
        except pymysql.MySQLError as e:
            logger.error(f"[{__name__}.{func_name}] 查询数量失败: {str(e)}")
            return 0
        finally:
            if cursor:
                cursor.close()
