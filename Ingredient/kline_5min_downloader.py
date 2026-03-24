# kline_5min_downloader.py
from datetime import datetime
from typing import Optional, List
import pandas as pd
from KitchenBase.download_utils import logger  # 引入统一日志
from data_manager import DataManager


class KLine5MinDownloader:
    """
    5分钟K线数据下载器
    核心流程：断点续传 → 原始数据下载 → 数据清洗 → 数据保存 → 更新进度
    异常策略：网络/服务器异常直接向上抛出，由调用方处理
    """
    # 固定配置（类级常量，便于维护）
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
        logger.debug(f"KLine5MinDownloader 初始化完成，频率={self.frequency}")

    def download(
        self,
        db_conn,
        stock_code: str,
        start_date: str,
        end_date: str,
        bs_client
    ) -> Optional[datetime]:
        """
        对外核心接口：完成5分钟K线数据的下载、清洗、保存全流程
        :param db_conn: 数据库连接句柄（调用方已建立）
        :param stock_code: 股票代码（如 sh.600000）
        :param start_date: 开始日期（格式：YYYY-MM-DD）
        :param end_date: 结束日期（格式：YYYY-MM-DD）
        :param bs_client: 已登录的baostock客户端实例
        :return: 最后成功下载的时间 | None（无数据时）
        :raise: 网络异常/服务器异常/数据操作异常（直接向上抛出）
        """
        # 日志入口
        logger.info(f"===== 开始下载 5分钟K线 | {stock_code} | {start_date} ~ {end_date} =====")
        logger.debug(f"参数：stock_code={stock_code}, start={start_date}, end={end_date}")

        try:
            # 1. 校验基础参数（前置检查）
            self._validate_base_params(stock_code, start_date, end_date)
            logger.debug(f"[{stock_code}] 参数校验通过")

            # 2. 获取断点续传进度
            last_success_time = self._get_download_progress(db_conn, stock_code)
            if last_success_time:
                logger.info(f"[{stock_code}] 断点续传模式，上次成功时间：{last_success_time}")
            else:
                logger.info(f"[{stock_code}] 无断点，执行全量下载")

            # 3. 步骤1：下载原始数据
            logger.debug(f"[{stock_code}] 开始从 baostock 获取原始数据")
            raw_df = self._download_raw_data(bs_client, stock_code, start_date, end_date)

            if raw_df.empty:
                logger.info(f"[{stock_code}] 未获取到任何原始数据，退出")
                return last_success_time
            logger.debug(f"[{stock_code}] 原始数据下载完成，共 {len(raw_df)} 条")

            # 4. 步骤2：清洗数据
            logger.debug(f"[{stock_code}] 开始数据清洗")
            clean_df = self._clean_raw_data(raw_df, stock_code)

            if clean_df.empty:
                logger.warning(f"[{stock_code}] 数据清洗后结果为空")
                return last_success_time
            logger.debug(f"[{stock_code}] 数据清洗完成，有效数据 {len(clean_df)} 条")

            # 5. 断点过滤
            if last_success_time:
                before = len(clean_df)
                clean_df = clean_df[clean_df["trade_time"] > last_success_time]
                after = len(clean_df)
                logger.debug(f"[{stock_code}] 断点过滤：{before} → {after} 条")

                if clean_df.empty:
                    logger.info(f"[{stock_code}] 无新增数据，无需保存")
                    return last_success_time

            # 6. 步骤3：保存数据
            logger.info(f"[{stock_code}] 开始保存数据，共 {len(clean_df)} 条")
            DataManager.save_kline_5min(db_conn, clean_df)
            logger.debug(f"[{stock_code}] 数据保存成功")

            # 7. 更新下载进度
            new_last_time = clean_df["trade_time"].max()
            logger.debug(f"[{stock_code}] 本次最新时间：{new_last_time}")
            self._update_download_progress(db_conn, stock_code, new_last_time)
            logger.info(f"[{stock_code}] 下载进度已更新")

            # 完成
            logger.info(f"✅ [{stock_code}] 5分钟K线下载任务全部完成")
            return new_last_time

        except Exception as e:
            logger.error(f"❌ [{stock_code}] 下载任务执行失败：{str(e)}", exc_info=True)
            raise  # 向上抛出异常

    def _validate_base_params(self, stock_code: str, start_date: str, end_date: str) -> None:
        """基础参数校验，不合法则抛出ValueError"""
        logger.debug(f"开始参数校验：{stock_code}, {start_date} ~ {end_date}")

        if not isinstance(stock_code, str) or not stock_code.startswith(("sh.", "sz.")):
            logger.error(f"股票代码格式错误：{stock_code}")
            raise ValueError(f"无效的股票代码格式：{stock_code}，需以sh.或sz.开头")

        date_format = "%Y-%m-%d"
        for date_str, date_type in [(start_date, "开始日期"), (end_date, "结束日期")]:
            try:
                datetime.strptime(date_str, date_format)
            except ValueError:
                logger.error(f"{date_type}格式错误：{date_str}")
                raise ValueError(f"{date_type}格式错误：{date_str}，需符合YYYY-MM-DD格式")

        if start_date > end_date:
            logger.error(f"日期范围错误：{start_date} > {end_date}")
            raise ValueError(f"开始日期{start_date}不能晚于结束日期{end_date}")

        logger.debug("参数校验全部通过")

    def _download_raw_data(
        self,
        bs_client,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """步骤1：从baostock下载原始5分钟K线数据"""
        rs = bs_client.query_history_k_data_plus(
            code=stock_code,
            fields=self.BAOSTOCK_FIELDS,
            start_date=start_date,
            end_date=end_date,
            frequency=str(self.frequency),
            adjustflag="3"
        )

        if rs.error_code != "0":
            err_msg = f"Baostock接口异常：{rs.error_code} | {rs.error_msg}"
            logger.error(f"[{stock_code}] {err_msg}")
            raise RuntimeError(f"[{stock_code}] {err_msg}")

        raw_data: List[List] = []
        while rs.next():
            raw_data.append(rs.get_row_data())

        logger.debug(f"[{stock_code}] 成功读取 {len(raw_data)} 条原始记录")
        return pd.DataFrame(raw_data, columns=rs.fields)

    def _clean_raw_data(self, raw_df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """步骤2：清洗原始数据为标准格式"""
        df = raw_df.copy()

        if df.empty:
            logger.warning(f"[{stock_code}] 原始数据为空，清洗后直接返回空")
            return pd.DataFrame(columns=self.TARGET_COLUMNS)

        # 时间处理
        df["time"] = df["time"].str.zfill(4)
        df["trade_time"] = pd.to_datetime(
            df["date"] + " " + df["time"].str[:2] + ":" + df["time"].str[2:] + ":00",
            errors="raise"
        )
        df["trade_date"] = df["trade_time"].dt.date
        df["raw_time"] = df["date"] + df["time"]

        # 字段赋值
        df["stock_code"] = stock_code
        df["frequency"] = self.frequency

        # 类型转换
        try:
            for field in ["open", "high", "low", "close", "amount"]:
                df[field] = df[field].astype(float).round(4)
            for field in ["volume", "adjustflag"]:
                df[field] = df[field].astype(int)
        except Exception as e:
            logger.error(f"[{stock_code}] 数据类型转换失败：{str(e)}")
            raise

        return df[self.TARGET_COLUMNS].reset_index(drop=True)

    def _get_download_progress(self, db_conn, stock_code: str) -> Optional[datetime]:
        """获取上次下载进度"""
        logger.debug(f"[{stock_code}] 查询下载进度")
        try:
            res = DataManager.get_last_download_time(
                db_conn=db_conn,
                stock_code=stock_code,
                data_type=self.data_type
            )
            return res
        except Exception as e:
            logger.error(f"[{stock_code}] 查询进度失败：{str(e)}")
            raise

    def _update_download_progress(self, db_conn, stock_code: str, last_time: datetime) -> None:
        """更新下载进度"""
        logger.debug(f"[{stock_code}] 更新下载进度：{last_time}")
        try:
            DataManager.update_download_progress(
                db_conn=db_conn,
                stock_code=stock_code,
                data_type=self.data_type,
                last_time=last_time
            )
        except Exception as e:
            logger.error(f"[{stock_code}] 更新进度失败：{str(e)}")
            raise


# 示例调用
if __name__ == "__main__":
    import baostock as bs
    import pymysql

    lg = bs.login()
    if lg.error_code != "0":
        logger.error(f"Baostock登录失败：{lg.error_msg}")
        raise RuntimeError("登录失败")

    db_conn = pymysql.connect(
        host="localhost",
        port=330,
        user="root",
        password="123456",
        database="stock_db",
        charset="utf8mb4"
    )

    downloader = KLine5MinDownloader()
    try:
        last_time = downloader.download(
            db_conn=db_conn,
            stock_code="sh.600000",
            start_date="2024-01-01",
            end_date="2024-01-31",
            bs_client=bs
        )
        logger.info(f"最终完成时间：{last_time}")
    except Exception as e:
        logger.error(f"主流程异常：{str(e)}", exc_info=True)
        raise
    finally:
        db_conn.close()
        bs.logout()