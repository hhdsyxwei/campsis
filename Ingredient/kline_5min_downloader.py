# kline_5min_downloader.py
from datetime import datetime
from typing import Optional, List
import pandas as pd
from KitchenBase.logger_config import get_logger
from Ingredient.data_manager import DataManager


logger = get_logger(__name__)
class KLine5MinDownloader:
    """
    5分钟K线数据下载器
    核心流程：断点续传 → 原始数据下载 → 数据清洗 → 数据保存 → 更新进度
    异常策略：网络/服务器异常直接向上抛出，由调用方处理
    """
    # 固定配置
    FREQUENCY = 5
    DATA_TYPE = "5min_kline"
    BAOSTOCK_FIELDS = "date,time,open,high,low,close,volume,amount,adjustflag"
    TARGET_COLUMNS = [
        "stock_code", "frequency", "trade_date", "trade_time",
        "raw_time", "open", "high", "low", "close",
        "volume", "amount", "adjustflag"
    ]

    def __init__(self):
        self.frequency = self.FREQUENCY
        self.data_type = self.DATA_TYPE
        logger.debug(f"KLine5MinDownloader 初始化完成，周期={self.frequency}分钟")

    def download(
        self,
        db_conn,
        stock_code: str,
        start_date: str,
        end_date: str,
        bs_client
    ) -> Optional[datetime]:
        """
        对外核心接口
        :param db_conn: 调用方提供的数据库连接
        :param stock_code: 股票代码 sh.600000
        :param start_date: 开始日期 YYYY-MM-DD
        :param end_date: 结束日期 YYYY-MM-DD
        :param bs_client: 已登录的 baostock 客户端
        :return: 最后成功下载时间
        :raise: 所有异常直接向上抛出
        """
        logger.info(f"===== 启动 5分钟K线下载 | {stock_code} | {start_date} ~ {end_date} =====")

        try:
            # 1. 参数校验
            self._validate_params(stock_code, start_date, end_date)
            logger.debug(f"[{stock_code}] 参数校验通过")

            # 2. 获取断点进度
            last_success = self._get_download_progress(db_conn, stock_code)
            if last_success:
                logger.info(f"[{stock_code}] 断点续传：上次成功时间 → {last_success}")
            else:
                logger.info(f"[{stock_code}] 无断点，执行全量下载")

            # 3. 下载原始数据
            raw_df = self._download_raw(bs_client, stock_code, start_date, end_date)
            if raw_df.empty:
                logger.info(f"[{stock_code}] 无原始数据，任务结束")
                return last_success
            logger.debug(f"[{stock_code}] 原始数据下载完成，共 {len(raw_df)} 条")

            # 4. 清洗数据
            clean_df = self._clean_data(raw_df, stock_code)
            if clean_df.empty:
                logger.warning(f"[{stock_code}] 数据清洗后为空")
                return last_success
            logger.debug(f"[{stock_code}] 数据清洗完成，有效 {len(clean_df)} 条")

            # 5. 断点过滤
            if last_success:
                before = len(clean_df)
                clean_df = clean_df[clean_df["trade_time"] > last_success]
                after = len(clean_df)
                logger.debug(f"[{stock_code}] 断点过滤：{before} → {after} 条")
                if clean_df.empty:
                    logger.info(f"[{stock_code}] 无新增数据，无需保存")
                    return last_success

            # 6. 保存数据
            logger.info(f"[{stock_code}] 开始保存 {len(clean_df)} 条 5分钟K线数据")
            DataManager.save_kline_5min(db_conn, stock_code, clean_df)
            logger.debug(f"[{stock_code}] 数据保存成功")

            # 7. 更新进度
            new_last_time = clean_df["trade_time"].max()
            self._update_progress(db_conn, stock_code, new_last_time)
            logger.info(f"[{stock_code}] 进度已更新 → {new_last_time}")

            logger.info(f"✅ [{stock_code}] 5分钟K线下载任务全部完成")
            return new_last_time

        except Exception as e:
            logger.error(f"❌ [{stock_code}] 下载任务异常：{str(e)}", exc_info=True)
            raise  # 向上抛出异常

    def _validate_params(self, stock_code: str, start_date: str, end_date: str) -> None:
        if not isinstance(stock_code, str) or not stock_code.startswith(("sh.", "sz.")):
            raise ValueError(f"股票代码格式错误：{stock_code}，必须以 sh./sz. 开头")

        date_fmt = "%Y-%m-%d"
        for d, name in [(start_date, "开始日期"), (end_date, "结束日期")]:
            try:
                datetime.strptime(d, date_fmt)
            except ValueError:
                raise ValueError(f"{name}格式错误：{d}，必须为 {date_fmt}")

        if start_date > end_date:
            raise ValueError(f"开始日期 {start_date} 不能晚于结束日期 {end_date}")

    def _download_raw(self, bs_client, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        rs = bs_client.query_history_k_data_plus(
            code=stock_code,
            fields=self.BAOSTOCK_FIELDS,
            start_date=start_date,
            end_date=end_date,
            frequency=str(self.frequency),
            adjustflag="3"
        )

        if rs.error_code != "0":
            raise RuntimeError(f"Baostock接口异常 {stock_code}：{rs.error_code} | {rs.error_msg}")

        data = []
        while rs.next():
            data.append(rs.get_row_data())

        return pd.DataFrame(data, columns=rs.fields)

    def _clean_data(self, raw_df: pd.DataFrame, stock_code: str) -> pd.DataFrame:

        logger.debug(f"第一条原始数据预览：{raw_df.iloc[0].to_dict() if not raw_df.empty else '无数据'}")
        logger.debug(f"最后一条原始数据预览：{raw_df.iloc[-1].to_dict() if not raw_df.empty else '无数据'}")

        df = raw_df.copy()
        if df.empty:
            return pd.DataFrame(columns=self.TARGET_COLUMNS)

        # 时间清洗
        df["time"] = df["time"].str.zfill(4)
        df["trade_time"] = pd.to_datetime(df["time"], format="%Y%m%d%H%M%S%f")
        df["trade_date"] = df["trade_time"].dt.date
        df["raw_time"] = df["date"] + df["time"]

        # 固定字段
        df["stock_code"] = stock_code
        df["frequency"] = self.frequency

        # 数值类型
        for f in ["open", "high", "low", "close", "amount"]:
            df[f] = df[f].astype(float).round(4)
        for f in ["volume", "adjustflag"]:
            df[f] = df[f].astype(int)

        return df[self.TARGET_COLUMNS].reset_index(drop=True)

    def _get_download_progress(self, db_conn, stock_code: str) -> Optional[datetime]:
        return DataManager.get_kline_download_progress(
            db_conn=db_conn,
            stock_code=stock_code,
            data_type=self.data_type
        )

    def _update_progress(self, db_conn, stock_code: str, last_time: datetime):
        DataManager.update_kline_download_progress(
            db_conn=db_conn,
            stock_code=stock_code,
            data_type=self.data_type,
            last_time=last_time
        )


# 示例调用（可直接运行）
if __name__ == "__main__":
    import baostock as bs
    import pymysql

    # 登录
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"Baostock 登录失败：{lg.error_msg}")

    # 数据库连接
    conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="root",
        password="ta225924",
        database="ashare",
        charset="utf8mb4"
    )

    # 执行下载
    downloader = KLine5MinDownloader()
    try:
        last = downloader.download(
            db_conn=conn,
            stock_code="sh.600000",
            start_date="2024-01-01",
            end_date="2024-01-31",
            bs_client=bs
        )
        logger.info(f"最终完成时间：{last}")
    except Exception as e:
        logger.error(f"主流程失败：{e}", exc_info=True)
    finally:
        conn.close()
        bs.logout()