import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock
from Ingredient.downloader.kline_unified_downloader import KLineDownloader, BLOCK_COMPLETED
from KitchenBase.stock_enums import KLinePeriod

# ---------------- 测试类 ----------------
class TestKLineDownloader:
    # -------------- 测试初始化 --------------
    def test_init(self, mock_db_conn):
        """测试下载器初始化"""
        downloader = KLineDownloader(mock_db_conn)
        assert downloader.db_conn == mock_db_conn
        assert downloader.func_name == ""

    # -------------- 测试季度转换 --------------
    def test_quarter_to_date_range(self, mock_db_conn, mock_quarter):
        """测试季度转日期范围"""
        downloader = KLineDownloader(mock_db_conn)
        start_date, end_date = downloader._quarter_to_date_range(mock_quarter)
        assert start_date == "2024-01-01"
        assert end_date == "2024-03-31"

        # 测试无效季度
        with pytest.raises(ValueError, match="无效季度"):
            downloader._quarter_to_date_range("2024-Q5")

    # -------------- 测试上市时间校验 --------------
    def test_is_time_range_overlap_with_listing_period(self, mock_db_conn):
        """测试上市时间重叠校验"""
        downloader = KLineDownloader(mock_db_conn)
        # 测试有效重叠
        is_ok, real_s, real_e = downloader._is_time_range_overlap_with_listing_period(
            "sh.600000", "2024-01-01", "2024-03-31"
        )
        assert is_ok is True
        assert real_s == "2024-01-01"
        assert real_e == "2024-03-31"

        # 测试无上市日期（模拟）
        with patch("Ingredient.DataNest.UnifiedDataManager.get_stock_listing_date") as mock_get:
            mock_get.return_value = (None, None)
            is_ok, _, _ = downloader._is_time_range_overlap_with_listing_period(
                "sh.600001", "2024-01-01", "2024-03-31"
            )
            assert is_ok is False

    # -------------- 测试数据清洗 --------------
    def test_clean_kline_data(self, mock_db_conn, mock_time_frame):
        """测试K线数据清洗"""
        downloader = KLineDownloader(mock_db_conn)
        # 构造原始数据
        raw_data = pd.DataFrame({
            "date": ["2024-01-01", "2024-01-02"],
            "open": ["10.0", "10.5"],
            "high": ["10.2", "10.7"],
            "low": ["9.8", "10.3"],
            "close": ["10.1", "10.6"],
            "volume": ["10000", "20000"],
            "amount": ["100000", "212000"]
        })
        # 执行清洗
        cleaned_df = downloader._clean_kline_data(raw_data, mock_time_frame)
        # 断言结果
        assert "timestamp" in cleaned_df.columns
        assert "open_price" in cleaned_df.columns
        assert cleaned_df["volume"].dtype == "Int64"
        assert cleaned_df["timestamp"].dtype == "datetime64[ns]"
        assert cleaned_df["open_price"].iloc[0] == 10.0

        # 测试空数据
        empty_df = downloader._clean_kline_data(pd.DataFrame(), mock_time_frame)
        assert empty_df.empty

    # -------------- 测试区块下载（模拟外部依赖） --------------
    @patch("Ingredient.kline_unified_downloader.query_history_k_data_plus")
    @patch("Ingredient.DataNest.UnifiedDataManager.get_kline_block_status")
    def test_fetch_kline_block(
        self, mock_get_status, mock_download, mock_db_conn, mock_quarter, mock_time_frame
    ):
        """测试单个区块下载（模拟baostock返回）"""
        # 模拟依赖返回
        mock_get_status.return_value = None  # 未完成状态
        mock_bs_response = MagicMock()
        mock_bs_response.error_code = "0"
        mock_bs_response.get_data.return_value = pd.DataFrame({
            "date": ["2024-01-01"],
            "open": ["10.0"],
            "high": ["10.2"],
            "low": ["9.8"],
            "close": ["10.1"],
            "volume": ["10000"],
            "amount": ["100000"]
        })
        mock_download.return_value = mock_bs_response

        # 执行下载
        downloader = KLineDownloader(mock_db_conn)
        downloader._fetch_kline_block(mock_quarter, "sh.600000", mock_time_frame)

        # 断言：状态已更新为完成
        cursor = mock_db_conn.cursor()
        cursor.execute("""
            SELECT status FROM kline_block_status 
            WHERE std_stock_code='sh.600000' AND time_frame=? AND quarter=?
        """, (mock_time_frame.value, mock_quarter))
        result = cursor.fetchone()
        assert result[0] == BLOCK_COMPLETED

    # -------------- 测试断点续传逻辑 --------------
    @patch("Ingredient.kline_unified_downloader.KLineDownloader._get_next_block")
    def test_download_kline_resume(self, mock_next_block, mock_db_conn, mock_time_frame):
        """测试断点续传（恢复中断区块）"""
        # 模拟有中断区块
        with patch("Ingredient.DataNest.UnifiedDataManager.get_downloading_block") as mock_get_block:
            mock_get_block.return_value = ("2024-Q1", "sh.600000", mock_time_frame)
            # 模拟下一个区块为None（执行完中断区块后结束）
            mock_next_block.return_value = None

            downloader = KLineDownloader(mock_db_conn)
            downloader.continue_download_kline(2024, 2025, mock_time_frame)

            # 断言：中断区块被处理
            mock_next_block.assert_not_called()  # 优先处理中断区块，未调用_next_block