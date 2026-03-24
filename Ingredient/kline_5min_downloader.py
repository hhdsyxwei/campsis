# kline_5min_downloader.py
from datetime import datetime
from typing import Optional, List
import pandas as pd
from data_manager import DataManager  # 依赖外部数据管理模块


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

    def download(
        self,
        db_conn,
        stock_code: str,
        start_date: str,
        end_date: str,
        bs_client  # 已登录的baostock客户端实例
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
        # 1. 校验基础参数（前置检查）
        self._validate_base_params(stock_code, start_date, end_date)

        # 2. 获取断点续传进度
        last_success_time = self._get_download_progress(db_conn, stock_code)

        # 3. 步骤1：下载原始数据（异常直接抛出）
        raw_df = self._download_raw_data(bs_client, stock_code, start_date, end_date)
        if raw_df.empty:
            return last_success_time

        # 4. 步骤2：清洗数据为标准格式
        clean_df = self._clean_raw_data(raw_df, stock_code)
        if clean_df.empty:
            return last_success_time

        # 5. 断点过滤：仅处理断点后的新数据
        if last_success_time:
            clean_df = clean_df[clean_df["trade_time"] > last_success_time]
            if clean_df.empty:
                return last_success_time

        # 6. 步骤3：保存数据（调用DataManager）
        DataManager.save_kline_5min(db_conn, clean_df)

        # 7. 更新下载进度
        new_last_time = clean_df["trade_time"].max()
        self._update_download_progress(db_conn, stock_code, new_last_time)

        return new_last_time

    def _validate_base_params(self, stock_code: str, start_date: str, end_date: str) -> None:
        """
        基础参数校验，不合法则抛出ValueError
        """
        # 校验股票代码格式
        if not isinstance(stock_code, str) or not stock_code.startswith(("sh.", "sz.")):
            raise ValueError(f"无效的股票代码格式：{stock_code}，需以sh.或sz.开头")

        # 校验日期格式
        date_format = "%Y-%m-%d"
        for date_str, date_type in [(start_date, "开始日期"), (end_date, "结束日期")]:
            try:
                datetime.strptime(date_str, date_format)
            except ValueError:
                raise ValueError(f"{date_type}格式错误：{date_str}，需符合YYYY-MM-DD格式")

        # 校验日期范围
        if start_date > end_date:
            raise ValueError(f"开始日期{start_date}不能晚于结束日期{end_date}")

    def _download_raw_data(
        self,
        bs_client,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        步骤1：从baostock下载原始5分钟K线数据
        异常：网络/服务器异常直接向上抛出
        """
        # 调用baostock接口（复用已有登录状态）
        rs = bs_client.query_history_k_data_plus(
            code=stock_code,
            fields=self.BAOSTOCK_FIELDS,
            start_date=start_date,
            end_date=end_date,
            frequency=str(self.frequency),
            adjustflag="3"  # 3=后复权（根据业务需求可调整）
        )

        # 检查接口调用状态，异常直接抛出
        if rs.error_code != "0":
            raise RuntimeError(
                f"Baostock接口调用失败 | 股票代码：{stock_code} | "
                f"错误码：{rs.error_code} | 错误信息：{rs.error_msg}"
            )

        # 读取数据（逐行读取，兼容大数量场景）
        raw_data: List[List] = []
        while rs.next():
            raw_data.append(rs.get_row_data())

        # 转换为DataFrame
        return pd.DataFrame(raw_data, columns=rs.fields)

    def _clean_raw_data(self, raw_df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        步骤2：清洗原始数据为标准格式
        输出符合kline_5min表结构的DataFrame
        """
        df = raw_df.copy()

        # 空数据直接返回空DataFrame
        if df.empty:
            return pd.DataFrame(columns=self.TARGET_COLUMNS)

        # 1. 时间字段处理（核心清洗逻辑）
        # 拼接完整时间字符串（处理time字段可能的不规范格式，如长度不足4位）
        df["time"] = df["time"].str.zfill(4)  # 补零至4位（如 "930" → "0930"）
        df["trade_time"] = pd.to_datetime(
            df["date"] + " " +
            df["time"].str[:2] + ":" +
            df["time"].str[2:] + ":00",
            errors="raise"  # 时间格式错误直接抛出
        )
        df["trade_date"] = df["trade_time"].dt.date  # 提取日期
        df["raw_time"] = df["date"] + df["time"]     # 原始时间拼接

        # 2. 固定字段赋值
        df["stock_code"] = stock_code
        df["frequency"] = self.frequency

        # 3. 数值类型转换（保证数据类型正确）
        numeric_fields = ["open", "high", "low", "close", "amount"]
        int_fields = ["volume", "adjustflag"]

        for field in numeric_fields:
            df[field] = df[field].astype(float).round(4)
        for field in int_fields:
            df[field] = df[field].astype(int)

        # 4. 仅保留目标列（与kline_5min表结构对齐）
        return df[self.TARGET_COLUMNS].reset_index(drop=True)

    def _get_download_progress(self, db_conn, stock_code: str) -> Optional[datetime]:
        """
        从kline_download_progress表获取上次下载进度
        """
        return DataManager.get_last_download_time(
            db_conn=db_conn,
            stock_code=stock_code,
            data_type=self.data_type
        )

    def _update_download_progress(self, db_conn, stock_code: str, last_time: datetime) -> None:
        """
        更新kline_download_progress表的下载进度
        """
        DataManager.update_download_progress(
            db_conn=db_conn,
            stock_code=stock_code,
            data_type=self.data_type,
            last_time=last_time
        )


# 示例调用代码（供参考，实际由调用方实现）
if __name__ == "__main__":
    """
    调用示例：
    1. 先登录baostock
    2. 建立数据库连接
    3. 实例化下载器并调用download接口
    """
    import baostock as bs
    import pymysql

    # 1. 登录baostock（调用方负责）
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"Baostock登录失败：{lg.error_msg}")

    # 2. 建立数据库连接（调用方负责）
    db_conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="root",
        password="123456",
        database="stock_db",
        charset="utf8mb4"
    )

    # 3. 实例化下载器并调用
    downloader = KLine5MinDownloader()
    try:
        last_time = downloader.download(
            db_conn=db_conn,
            stock_code="sh.600000",
            start_date="2024-01-01",
            end_date="2024-01-31",
            bs_client=bs
        )
        print(f"下载完成，最后更新时间：{last_time}")
    except Exception as e:
        print(f"下载失败：{str(e)}")
        raise
    finally:
        # 4. 关闭资源（调用方负责）
        db_conn.close()
        bs.logout()