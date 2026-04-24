import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock
from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
from KitchenBase.stock_enums import KLinePeriod
from KitchenBase.block_pointer import BlockPointer
from Ingredient.downloader.kline_unified_downloader import KLineDownloader, continue_download_kline, start_new_kline_download


class TestKLineDownloader:
    """K线下载器测试类"""

    def test_init(self, mock_db_conn):
        """测试下载器初始化"""
        downloader = KLineDownloader(mock_db_conn)
        assert downloader.db_conn == mock_db_conn
        assert downloader.support_block_status is True

    def test_get_task_type(self, mock_db_conn):
        """测试获取任务类型"""
        downloader = KLineDownloader(mock_db_conn)
        task_type = downloader.get_task_type()
        assert task_type == DlTaskType.KLINE

    def test_get_pointer_fields(self, mock_db_conn):
        """测试获取指针字段"""
        downloader = KLineDownloader(mock_db_conn)
        fields = downloader.get_pointer_fields()
        assert len(fields) == 3
        assert fields[0] == PointerField.STOCK_CODE
        assert fields[1] == PointerField.TIME_FRAME
        assert fields[2] == PointerField.QUARTER

    def test_create_block_manager(self, mock_db_conn):
        """测试创建区块管理器"""
        downloader = KLineDownloader(mock_db_conn)
        block_manager = downloader.create_block_manager()
        assert block_manager is not None

    def test_create_status_manager(self, mock_db_conn):
        """测试创建状态管理器"""
        downloader = KLineDownloader(mock_db_conn)
        status_manager = downloader.create_status_manager()
        assert status_manager is not None

    def test_create_pointer_manager(self, mock_db_conn):
        """测试创建指针管理器"""
        downloader = KLineDownloader(mock_db_conn)
        pointer_manager = downloader.create_pointer_manager()
        assert pointer_manager is not None

    def test_create_progress_manager(self, mock_db_conn):
        """测试创建进度管理器"""
        downloader = KLineDownloader(mock_db_conn)
        progress_manager = downloader.create_progress_manager()
        assert progress_manager is not None

    def test_validate_parameters_valid(self, mock_db_conn):
        """测试验证有效参数"""
        downloader = KLineDownloader(mock_db_conn)
        result = downloader.validate_parameters(2020, 2021)
        assert result is True

    def test_validate_parameters_invalid_year(self, mock_db_conn):
        """测试验证无效年份"""
        downloader = KLineDownloader(mock_db_conn)
        result = downloader.validate_parameters(2021, 2020)
        assert result is False

    def test_validate_parameters_invalid_pointer(self, mock_db_conn):
        """测试验证无效指针"""
        downloader = KLineDownloader(mock_db_conn)
        # 创建缺少字段的指针
        invalid_pointer = MagicMock()
        invalid_pointer.get_value.side_effect = lambda field: None
        result = downloader.validate_parameters(2020, 2021, block_pointer=invalid_pointer)
        assert result is False

    def test_quarter_to_date_range(self, mock_db_conn):
        """测试季度转日期范围"""
        downloader = KLineDownloader(mock_db_conn)
        start_date, end_date = downloader._quarter_to_date_range("2024-Q1")
        assert start_date == "2024-01-01"
        assert end_date == "2024-03-31"

        # 测试无效季度
        with pytest.raises(ValueError, match="无效季度"):
            downloader._quarter_to_date_range("2024-Q5")

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

        # 测试无上市日期
        with patch("Ingredient.DataNest.UnifiedDataManager.get_stock_listing_date") as mock_get:
            mock_get.return_value = (None, None)
            is_ok, _, _ = downloader._is_time_range_overlap_with_listing_period(
                "sh.600001", "2024-01-01", "2024-03-31"
            )
            assert is_ok is False

    def test_clean_data(self, mock_db_conn):
        """测试数据清洗"""
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
        cleaned_df = downloader.clean_data(raw_data)
        # 断言结果
        assert "timestamp" in cleaned_df.columns
        assert "open_price" in cleaned_df.columns
        assert "volume" in cleaned_df.columns
        assert "time_frame" not in cleaned_df.columns  # time_frame 在 save_data 中添加

    def test_save_data(self, mock_db_conn):
        """测试数据保存"""
        downloader = KLineDownloader(mock_db_conn)
        # 构造清洗后的数据
        cleaned_data = pd.DataFrame({
            "timestamp": ["2024-01-01", "2024-01-02"],
            "open_price": [10.0, 10.5],
            "high_price": [10.2, 10.7],
            "low_price": [9.8, 10.3],
            "close_price": [10.1, 10.6],
            "volume": [10000, 20000],
            "turnover": [100000, 212000]
        })
        # 创建区块指针
        block_pointer = BlockPointer(
            (PointerField.STOCK_CODE, PointerField.TIME_FRAME, PointerField.QUARTER),
            ("sh.600000", "5m", "2024-Q1")
        )
        # 模拟数据保存
        with patch("Ingredient.DataNest.UnifiedDataManager.save_kline_data_unified") as mock_save:
            mock_save.return_value = True
            result = downloader.save_data(cleaned_data, 2024, 2025, block_pointer=block_pointer)
            assert result is True

    @patch("Ingredient.downloader.kline_unified_downloader.query_history_k_data_plus")
    def test_download_raw_data(self, mock_download, mock_db_conn):
        """测试下载原始数据"""
        # 模拟 Baostock 响应
        mock_response = MagicMock()
        mock_response.error_code = "0"
        mock_response.get_data.return_value = pd.DataFrame({
            "date": ["2024-01-01"],
            "open": ["10.0"],
            "high": ["10.2"],
            "low": ["9.8"],
            "close": ["10.1"],
            "volume": ["10000"],
            "amount": ["100000"]
        })
        mock_download.return_value = mock_response

        downloader = KLineDownloader(mock_db_conn)
        # 创建区块指针
        block_pointer = BlockPointer(
            (PointerField.STOCK_CODE, PointerField.TIME_FRAME, PointerField.QUARTER),
            ("sh.600000", "5m", "2024-Q1")
        )
        # 执行下载
        raw_data = downloader.download_raw_data(2024, 2025, block_pointer=block_pointer)
        assert raw_data is not None
        assert not raw_data.empty

    @patch("Ingredient.downloader.kline_unified_downloader.KLineDownloader.continue_download")
    def test_continue_download_kline(self, mock_continue, mock_db_conn):
        """测试继续下载函数"""
        mock_continue.return_value = True
        result = continue_download_kline(mock_db_conn, 2024, 2025)
        assert result is True

    @patch("Ingredient.downloader.kline_unified_downloader.KLineDownloader.start_new_download")
    def test_start_new_kline_download(self, mock_start, mock_db_conn):
        """测试开始新下载函数"""
        mock_start.return_value = True
        result = start_new_kline_download(mock_db_conn, 2024, 2025)
        assert result is True