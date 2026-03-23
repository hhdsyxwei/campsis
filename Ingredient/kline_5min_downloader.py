from datetime import datetime
from typing import Optional
import pandas as pd
from data_manager import DataManager  # 统一数据操作入口


class KLine5MinDownloader:
    """
    5分钟K线下载器（严格遵循三层架构：下载 → 清洗 → 保存）
    依赖外部传入：baostock客户端、数据库连接
    通过 DataManager 完成所有数据库操作
    """

    def __init__(self):
        self.frequency = 5  # 固定5分钟K线
        self.data_type = "5min_kline"

    # ====================== 对外主接口 ======================
    def download(
        self,
        bs_client,
        db_conn,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> Optional[datetime]:
        """
        完整下载流程：断点续传 + 下载 → 清洗 → 保存
        :return: 最后成功下载时间
        """
        # 1. 获取上次断点
        last_success = self._get_last_progress(db_conn, stock_code)

        # 2. 下载原始数据
        raw_data = self._download_raw(
            bs_client=bs_client,
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date
        )

        if raw_data.empty:
            return last_success

        # 3. 清洗为标准格式
        clean_df = self._clean_data(raw_data, stock_code)

        # 4. 断点过滤
        if last_success:
            clean_df = clean_df[clean_df["trade_time"] > last_success]

        if clean_df.empty:
            return last_success

        # 5. 保存数据（通过 DataManager）
        DataManager.save_kline_5min(db_conn, clean_df)

        # 6. 更新最新进度
        new_last_time = clean_df["trade_time"].max()
        self._update_progress(db_conn, stock_code, new_last_time)

        print(f"✅ {stock_code} 下载完成 | 最新时间：{new_last_time}")
        return new_last_time

    # ====================== 步骤1：下载原始数据 ======================
    def _download_raw(
        self,
        bs_client,
        stock_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """从baostock下载原始数据，不做任何修改"""
        rs = bs_client.query_history_k_data_plus(
            code=stock_code,
            fields="date,time,open,high,low,close,volume,amount,adjustflag",
            start_date=start_date,
            end_date=end_date,
            frequency=str(self.frequency),
            adjustflag="3"
        )

        data = []
        while rs.next() and rs.error_code == "0":
            data.append(rs.get_row_data())

        return pd.DataFrame(data, columns=rs.fields)

    # ====================== 步骤2：清洗为标准格式 ======================
    def _clean_data(self, raw_df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """清洗为kline_5min表标准格式"""
        df = raw_df.copy()

        # 时间处理
        df["trade_time"] = pd.to_datetime(
            df["date"] + " " +
            df["time"].str.slice(0, 2) + ":" +
            df["time"].str.slice(2, 4) + ":00"
        )
        df["trade_date"] = pd.to_datetime(df["date"]).dt.date
        df["raw_time"] = df["date"] + df["time"]

        # 固定字段
        df["stock_code"] = stock_code
        df["frequency"] = self.frequency

        # 类型转换
        df["open"] = df["open"].astype(float).round(4)
        df["high"] = df["high"].astype(float).round(4)
        df["low"] = df["low"].astype(float).round(4)
        df["close"] = df["close"].astype(float).round(4)
        df["volume"] = df["volume"].astype(int)
        df["amount"] = df["amount"].astype(float).round(4)
        df["adjustflag"] = df["adjustflag"].astype(int)

        # 输出与数据表完全一致
        return df[[
            "stock_code", "frequency", "trade_date", "trade_time",
            "raw_time", "open", "high", "low", "close",
            "volume", "amount", "adjustflag"
        ]]

    # ====================== 进度管理 ======================
    def _get_last_progress(self, db_conn, stock_code: str) -> Optional[datetime]:
        """从DataManager获取上次下载进度"""
        return DataManager.get_last_download_time(db_conn, stock_code, self.data_type)

    def _update_progress(self, db_conn, stock_code: str, last_time: datetime):
        """通过DataManager更新下载进度"""
        DataManager.update_download_progress(
            db_conn=db_conn,
            stock_code=stock_code,
            data_type=self.data_type,
            last_time=last_time
        )