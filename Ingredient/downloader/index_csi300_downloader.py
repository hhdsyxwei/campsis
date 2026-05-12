# index_csi300_downloader.py
import pandas as pd
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlTaskType
from KitchenBase.download_parameters import DownloadParameters
from KitchenBase.baostock_wrapper import query_hs300_stocks
from KitchenBase.download_utils import convert_baostock_code
from Ingredient.DataNest.dm_index_csi300 import IndexCsi300Manager
from Ingredient.DataNest.dm_standard_columns import IndexCsi300StandardColumns
from .core.abstract_downloader import SimpleDownloader

logger = get_logger(__name__)


class Csi300Downloader(SimpleDownloader):
    """
    沪深300成分股下载器，基于 SimpleDownloader 实现
    从 BaoStock 获取沪深300成分股数据，并保存到 index_csi300_component 表
    """

    def __init__(self, db_conn):
        """
        初始化沪深300成分股下载器

        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn)
        self.csi300_manager = IndexCsi300Manager(db_conn)
        self.cols = IndexCsi300StandardColumns

    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识

        Returns:
            DlTaskType: 任务类型枚举值
        """
        return DlTaskType.INDEX_CSI300

    def validate_parameters(self, params=None, **kwargs) -> bool:
        """
        验证参数有效性

        Args:
            params: 下载参数（可选）
            **kwargs: 额外参数

        Returns:
            bool: 参数是否有效
        """
        logger.debug("[validate_parameters] 参数校验通过")
        return True

    def download_raw_data(self, params=None, **kwargs) -> pd.DataFrame:
        """
        下载原始数据

        Args:
            params: 下载参数（可选）
            **kwargs: 额外参数，包含 date（查询日期）

        Returns:
            pd.DataFrame: 原生数据
        """
        func_name = "download_raw_data"
        
        date = kwargs.get('date', '')
        logger.info(f"[{func_name}] 开始下载沪深300成分股数据 | 查询日期: {date or '最新'}")

        try:
            rs = query_hs300_stocks(date=date)

            if rs.error_code != '0':
                logger.error(f"[{func_name}] BaoStock接口调用失败 | {rs.error_code} {rs.error_msg}")
                return pd.DataFrame()

            df = rs.get_data()
            
            if df.empty:
                logger.warning(f"[{func_name}] BaoStock返回数据为空")
                return pd.DataFrame()

            logger.info(f"[{func_name}] 成功获取 {len(df)} 条沪深300成分股数据")
            return df

        except Exception as e:
            logger.error(f"[{func_name}] 下载数据异常: {str(e)}")
            import traceback
            logger.error(f"[{func_name}] 调用栈:")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def clean_data(self, raw_data: pd.DataFrame) -> pd.DataFrame:
        """
        清洗数据

        Args:
            raw_data: 原始数据

        Returns:
            pd.DataFrame: 清洗后的数据
        """
        func_name = "clean_data"

        if raw_data.empty:
            return pd.DataFrame()

        logger.debug(f"[{func_name}] 开始清洗 {len(raw_data)} 条数据")

        try:
            df = raw_data.rename(columns={
                'updateDate': self.cols.CSI300_UPDATE_DATE,
                'code': self.cols.STD_STOCK_CODE,
                'code_name': self.cols.STOCK_NAME
            })

            if self.cols.STD_STOCK_CODE in df.columns:
                df[self.cols.STD_STOCK_CODE] = df[self.cols.STD_STOCK_CODE].apply(
                    lambda x: convert_baostock_code(x) if pd.notna(x) else x
                )

            if self.cols.CSI300_UPDATE_DATE in df.columns:
                df[self.cols.CSI300_UPDATE_DATE] = pd.to_datetime(df[self.cols.CSI300_UPDATE_DATE], errors='coerce')

            result_df = df[[self.cols.STD_STOCK_CODE, self.cols.STOCK_NAME, self.cols.CSI300_UPDATE_DATE]]

            logger.debug(f"[{func_name}] 清洗完成，保留 {len(result_df)} 条有效数据")
            return result_df

        except Exception as e:
            logger.error(f"[{func_name}] 数据清洗异常: {str(e)}")
            import traceback
            logger.error(f"[{func_name}] 调用栈:")
            logger.error(traceback.format_exc())
            return pd.DataFrame()

    def save_data(self, cleaned_data: pd.DataFrame, params=None, **kwargs) -> bool:
        """
        保存数据

        Args:
            cleaned_data: 清洗后的数据
            params: 下载参数（可选）
            **kwargs: 额外参数

        Returns:
            bool: 是否保存成功
        """
        func_name = "save_data"

        if cleaned_data.empty:
            logger.info(f"[{func_name}] 无数据需要保存")
            return True

        logger.info(f"[{func_name}] 准备保存 {len(cleaned_data)} 条沪深300成分股数据")

        try:
            success = self.csi300_manager.save_csi300_component(cleaned_data)
            
            if success:
                logger.info(f"[{func_name}] 沪深300成分股数据保存成功")
            else:
                logger.error(f"[{func_name}] 沪深300成分股数据保存失败")

            return success

        except Exception as e:
            logger.error(f"[{func_name}] 保存数据异常: {str(e)}")
            import traceback
            logger.error(f"[{func_name}] 调用栈:")
            logger.error(traceback.format_exc())
            return False


def download_csi300_components(db_conn, date: str = "", **kwargs) -> bool:
    """
    下载沪深300成分股数据的便捷函数

    Args:
        db_conn: 数据库连接对象
        date: 查询日期，格式 YYYY-MM-DD，为空时默认最新日期
        **kwargs: 额外参数

    Returns:
        bool: 是否下载成功
    """
    logger.info("开始执行沪深300成分股下载任务")

    downloader = Csi300Downloader(db_conn)
    
    dummy_params = DownloadParameters(start_year=0, end_year=0)
    success = downloader.download(dummy_params, date=date)
    
    if success:
        logger.info("沪深300成分股下载任务完成")
    else:
        logger.error("沪深300成分股下载任务失败")

    return success