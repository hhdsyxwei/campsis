# stock_basic_downloader.py
import logging
from typing import List
import pandas as pd
import baostock as bs
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import MarketType
from KitchenBase.download_utils import baostock_code_to_market, convert_baostock_code
from KitchenBase.download_enums import DlTaskType
from Ingredient.DataNest import BasicStockDataManager, UnifiedDataManager as UDM
from .core.abstract_downloader import SimpleDownloader
from .core.download_parameters import DownloadParameters

logger = get_logger(__name__)


class StockBasicDownloader(SimpleDownloader):
    """
    股票基础信息下载器，基于 SimpleDownloader 实现
    下载指定市场类型的股票基础信息，并保存到 stock_basic 表和 stock_fixed_seq 表
    """

    def __init__(self, db_conn):
        """
        初始化股票基础信息下载器

        Args:
            db_conn: 数据库连接对象
        """
        super().__init__(db_conn)
        self.basic_stock_manager = BasicStockDataManager(db_conn)

    def get_task_type(self) -> DlTaskType:
        """
        获取任务类型标识

        Returns:
            DlTaskType: 任务类型枚举值
        """
        return DlTaskType.STOCK_BASIC

    def validate_parameters(self, params: DownloadParameters, **kwargs) -> bool:
        """
        验证参数有效性

        Args:
            params: 下载参数
            **kwargs: 额外参数，包含 market_type_list

        Returns:
            bool: 参数是否有效
        """
        func_name = "validate_parameters"
        market_type_list = kwargs.get('market_type_list')

        if market_type_list is None:
            logger.error(f"[{func_name}] market_type_list 必须提供")
            return False

        if not isinstance(market_type_list, list) or len(market_type_list) == 0:
            logger.error(f"[{func_name}] market_type_list 必须为非空列表")
            return False

        for mt in market_type_list:
            if not isinstance(mt, MarketType):
                logger.error(f"[{func_name}] 元素必须为 MarketType 枚举 | 非法元素: {mt}")
                return False

        logger.debug(f"[{func_name}] 参数校验通过")
        return True

    def download_raw_data(self, params: DownloadParameters, **kwargs) -> pd.DataFrame:
        """
        下载原始数据

        Args:
            params: 下载参数（占位，实际参数通过 kwargs 传递）
            **kwargs: 额外参数，包含 market_type_list

        Returns:
            pd.DataFrame: 原生数据
        """
        func_name = "download_raw_data"
        market_type_list: List[MarketType] = kwargs.get('market_type_list', [])

        logger.debug(f"[{func_name}] 开始全量下载股票基础数据")

        rs = bs.query_stock_basic()

        if rs.error_code != '0':
            logger.error(f"[{func_name}] baostock接口调用失败 | {rs.error_code} {rs.error_msg}")
            return pd.DataFrame()

        fields = rs.fields
        if "code" not in fields:
            logger.error(f"[{func_name}] baostock返回数据不包含code字段，无法识别市场")
            return pd.DataFrame()

        code_index = fields.index("code")
        data_list = []

        while rs.next() and rs.error_code == '0':
            row = rs.get_row_data()

            bs_code = row[code_index].strip() if row[code_index] else ""
            if not bs_code:
                continue

            stock_market = baostock_code_to_market(bs_code)

            if stock_market is MarketType.UNKNOWN or stock_market not in market_type_list:
                continue

            data_list.append(row)

        if not data_list:
            logger.warning(f"[{func_name}] 未获取到任何符合市场条件的股票数据")
            return pd.DataFrame()

        raw_df = pd.DataFrame(data_list, columns=fields)
        logger.info(f"[{func_name}] 原生数据处理完成 | 最终数据量: {len(raw_df)}")

        return raw_df

    def clean_data(self, raw_data) -> pd.DataFrame:
        """
        清洗数据

        Args:
            raw_data: 原始数据

        Returns:
            pd.DataFrame: 清洗后的数据
        """
        func_name = "clean_data"
        logger.debug(f"[{func_name}] 开始清洗股票基础数据")

        if raw_data.empty:
            return pd.DataFrame()

        cleaned_df = raw_data.copy()

        field_mapping = {
            "code": "std_stock_code",
            "code_name": "stock_name",
            "ipoDate": "list_date",
            "outDate": "delist_date",
            "status": "is_active"
        }

        valid_keys = [k for k in field_mapping.keys() if k in cleaned_df.columns]
        cleaned_df = cleaned_df[valid_keys]
        cleaned_df.rename(columns=field_mapping, inplace=True)

        if "std_stock_code" in cleaned_df.columns:
            cleaned_df["pure_symbol"] = cleaned_df["std_stock_code"].apply(
                lambda x: x.split(".")[1] if isinstance(x, str) and "." in x else None
            )

        if "std_stock_code" in cleaned_df.columns:
            cleaned_df["market"] = cleaned_df["std_stock_code"].apply(
                lambda x: baostock_code_to_market(x).value
            )
            cleaned_df["std_stock_code"] = cleaned_df["std_stock_code"].apply(convert_baostock_code)

        cleaned_df["industry"] = ""

        for col in ["list_date", "delist_date"]:
            if col in cleaned_df.columns:
                cleaned_df[col] = pd.to_datetime(
                    cleaned_df[col],
                    errors="coerce"
                ).dt.date
                cleaned_df[col] = cleaned_df[col].where(cleaned_df[col].notna(), None)

        if "is_active" in cleaned_df.columns:
            cleaned_df["is_active"] = cleaned_df["is_active"].map({
                "1": 1,
                "0": 0
            }).fillna(0).astype(int)

        core_fields = ["std_stock_code", "stock_name", "pure_symbol", "market"]
        cleaned_df = cleaned_df.dropna(subset=core_fields)
        cleaned_df = cleaned_df.drop_duplicates(subset=["std_stock_code"], keep="last")

        final_columns = [
            "std_stock_code",
            "stock_name",
            "pure_symbol",
            "industry",
            "market",
            "list_date",
            "delist_date",
            "is_active"
        ]
        cleaned_df = cleaned_df[final_columns]

        logger.info(f"[{func_name}] 数据清洗完成 | 清洗后数据量: {len(cleaned_df)}")
        return cleaned_df

    def save_data(self, data: pd.DataFrame, params: DownloadParameters, **kwargs) -> bool:
        """
        保存数据到数据库

        Args:
            data: 清洗后的数据
            params: 下载参数
            **kwargs: 额外参数

        Returns:
            bool: 保存是否成功
        """
        func_name = "save_data"
        logger.debug(f"[{func_name}] 开始保存数据 | 待入库条数：{len(data)}")

        if data.empty:
            logger.warning(f"[{func_name}] 数据为空，无需保存")
            return False

        try:
            save_result = self.basic_stock_manager.batch_insert_stock_basic(data)
            if save_result:
                logger.info(f"[{func_name}] stock_basic 数据保存成功 | 保存数量: {len(data)}")
            else:
                logger.error(f"[{func_name}] stock_basic 数据保存失败")
            return save_result

        except Exception as e:
            logger.error(f"[{func_name}] 保存异常: {str(e)}", exc_info=True)
            return False

    def on_download_completed(self, params: DownloadParameters, cleaned_data: pd.DataFrame, success: bool, **kwargs) -> None:
        """
        下载完成后的钩子，保存 stock_fixed_seq

        Args:
            params: 下载参数
            cleaned_data: 清洗后的数据
            success: 下载是否成功
            **kwargs: 额外参数
        """
        if not success:
            self.logger.warning(f"[{self.get_task_type().value}] 下载未成功，跳过 stock_fixed_seq 保存")
            return

        stock_codes = cleaned_data['std_stock_code'].tolist()
        seq_result = self._save_stock_fixed_seq(stock_codes)

        if seq_result:
            self.logger.info(f"[{self.get_task_type().value}] stock_fixed_seq 保存成功 | 股票数量: {len(stock_codes)}")
        else:
            self.logger.warning(f"[{self.get_task_type().value}] stock_fixed_seq 保存失败")

    def _save_stock_fixed_seq(self, stock_codes: List[str]) -> bool:
        """
        保存股票固定顺序表

        Args:
            stock_codes: 股票代码列表

        Returns:
            bool: 保存是否成功
        """
        func_name = "_save_stock_fixed_seq"
        logger.debug(f"[{func_name}] 开始保存股票固定顺序表 | 股票数量: {len(stock_codes)}")

        try:
            truncate_success = UDM.truncate_table_stock_fixed_seq(self.db_conn)
            if not truncate_success:
                logger.error(f"[{func_name}] 清空股票固定顺序表失败")
                return False

            stock_data = [(code,) for code in stock_codes]
            save_success = UDM.save_stock_fixed_seq(self.db_conn, stock_data)

            if save_success:
                logger.info(f"[{func_name}] 股票固定顺序表保存成功 | 保存数量: {len(stock_codes)}")
            else:
                logger.error(f"[{func_name}] 股票固定顺序表保存失败")

            return save_success

        except Exception as e:
            logger.error(f"[{func_name}] 保存股票固定顺序表异常: {str(e)}", exc_info=True)
            return False


def download_stock_basic(
    conn,
    params: DownloadParameters,
    market_type_list: List[MarketType] = [MarketType.SH_MAIN_BOARD, MarketType.SZ_MAIN_BOARD]
) -> bool:
    """
    下载指定市场类型的股票基础信息，并保存到 stock_basic 表

    Args:
        conn: 数据库连接对象
        params: 下载参数
        market_type_list: 市场类型列表，元素为 MarketType 枚举值

    Returns:
        下载及保存是否成功（True/False）
    """
    func_name = "download_stock_basic"
    logger.info(f"[{func_name}] 开始执行股票基础信息下载流程 | 市场类型: {[mt.value for mt in market_type_list]}")

    try:
        downloader = StockBasicDownloader(conn)
        return downloader.download(params, market_type_list=market_type_list)

    except Exception as e:
        logger.error(f"[{func_name}] 下载流程执行失败: {str(e)}", exc_info=True)
        return False
