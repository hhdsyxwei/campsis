import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock
from KitchenBase.download_enums import DlTaskType, DlBlockStatus, PointerField
from KitchenBase.block_pointer import BlockPointer
from Ingredient.downloader.xrxd_downloader import XrxdDownloader, continue_download_xrxd, start_new_xrxd_download


class TestXrxdDownloader:
    """分红送配下载器测试类"""

    def test_init(self, mock_db_conn):
        """测试下载器初始化"""
        downloader = XrxdDownloader(mock_db_conn)
        assert downloader.db_conn == mock_db_conn
        assert downloader.support_block_status is True
        assert downloader.xrxd_manager is not None
        assert downloader.stock_manager is not None

    def test_get_task_type(self, mock_db_conn):
        """测试获取任务类型"""
        downloader = XrxdDownloader(mock_db_conn)
        task_type = downloader.get_task_type()
        assert task_type == DlTaskType.XRXD

    def test_get_pointer_fields(self, mock_db_conn):
        """测试获取指针字段"""
        downloader = XrxdDownloader(mock_db_conn)
        fields = downloader.get_pointer_fields()
        assert len(fields) == 2
        assert fields[0] == PointerField.YEAR
        assert fields[1] == PointerField.STOCK_CODE

    def test_create_block_manager(self, mock_db_conn):
        """测试创建区块管理器"""
        downloader = XrxdDownloader(mock_db_conn)
        block_manager = downloader.create_block_manager()
        assert block_manager is not None

    def test_create_status_manager(self, mock_db_conn):
        """测试创建状态管理器"""
        downloader = XrxdDownloader(mock_db_conn)
        status_manager = downloader.create_status_manager()
        assert status_manager is not None

    def test_create_pointer_manager(self, mock_db_conn):
        """测试创建指针管理器"""
        downloader = XrxdDownloader(mock_db_conn)
        pointer_manager = downloader.create_pointer_manager()
        assert pointer_manager is not None

    def test_create_progress_manager(self, mock_db_conn):
        """测试创建进度管理器"""
        downloader = XrxdDownloader(mock_db_conn)
        progress_manager = downloader.create_progress_manager()
        assert progress_manager is not None

    def test_validate_parameters_valid(self, mock_db_conn):
        """测试验证有效参数"""
        downloader = XrxdDownloader(mock_db_conn)
        result = downloader.validate_parameters(2020, 2021)
        assert result is True

    def test_validate_parameters_invalid_year(self, mock_db_conn):
        """测试验证无效年份"""
        downloader = XrxdDownloader(mock_db_conn)
        result = downloader.validate_parameters(2021, 2020)
        assert result is False

    def test_validate_parameters_invalid_pointer(self, mock_db_conn):
        """测试验证无效指针"""
        downloader = XrxdDownloader(mock_db_conn)
        # 创建缺少字段的指针
        invalid_pointer = MagicMock()
        invalid_pointer.get_value.side_effect = lambda field: None
        result = downloader.validate_parameters(2020, 2021, block_pointer=invalid_pointer)
        assert result is False

    def test_clean_data(self, mock_db_conn):
        """测试数据清洗"""
        downloader = XrxdDownloader(mock_db_conn)
        # 构造原始数据
        raw_data = pd.DataFrame({
            "dividPreNoticeDate": ["2024-01-15"],
            "dividAgmPumDate": ["2024-02-20"],
            "dividPlanAnnounceDate": ["2024-03-01"],
            "dividPlanDate": ["2024-03-15"],
            "dividRegistDate": ["2024-03-20"],
            "dividOperateDate": ["2024-03-25"],
            "dividPayDate": ["2024-03-30"],
            "dividStockMarketDate": ["2024-04-01"],
            "dividCashPsBeforeTax": ["0.5"],
            "dividCashPsAfterTax": ["0.45"],
            "dividStocksPs": ["0.2"],
            "dividCashStock": ["10派5送2"],
            "dividReserveToStockPs": ["0.1"]
        })
        # 执行清洗
        cleaned_df = downloader.clean_data(raw_data)
        # 断言结果
        assert "xrxd_pre_notice_date" in cleaned_df.columns
        assert "xrxd_cash_ps_before_tax" in cleaned_df.columns
        assert "xrxd_stocks_ps" in cleaned_df.columns
        assert "std_stock_code" not in cleaned_df.columns  # 在 save_data 中添加
        assert "xrxd_year" not in cleaned_df.columns  # 在 save_data 中添加

    def test_save_data(self, mock_db_conn):
        """测试数据保存"""
        downloader = XrxdDownloader(mock_db_conn)
        # 构造清洗后的数据
        cleaned_data = pd.DataFrame({
            "xrxd_pre_notice_date": ["2024-01-15"],
            "xrxd_agm_pum_date": ["2024-02-20"],
            "xrxd_cash_ps_before_tax": [0.5],
            "xrxd_stocks_ps": [0.2]
        })
        # 创建区块指针
        block_pointer = BlockPointer(
            (PointerField.YEAR, PointerField.STOCK_CODE),
            (2024, "sh.600000")
        )
        # 模拟数据保存
        with patch("Ingredient.DataNest.XrxdManager.save_xrxd_data") as mock_save:
            mock_save.return_value = True
            result = downloader.save_data(cleaned_data, 2024, 2025, block_pointer=block_pointer)
            assert result is True

    @patch("Ingredient.downloader.xrxd_downloader.query_dividend_data")
    def test_download_raw_data(self, mock_query, mock_db_conn):
        """测试下载原始数据"""
        # 模拟 Baostock 响应
        mock_response = MagicMock()
        mock_response.error_code = "0"
        mock_response.get_data.return_value = pd.DataFrame({
            "dividPreNoticeDate": ["2024-01-15"],
            "dividAgmPumDate": ["2024-02-20"],
            "dividCashPsBeforeTax": ["0.5"]
        })
        mock_query.return_value = mock_response

        downloader = XrxdDownloader(mock_db_conn)
        # 创建区块指针
        block_pointer = BlockPointer(
            (PointerField.YEAR, PointerField.STOCK_CODE),
            (2024, "sh.600000")
        )
        # 执行下载
        raw_data = downloader.download_raw_data(2024, 2025, block_pointer=block_pointer)
        assert raw_data is not None
        assert not raw_data.empty

    @patch("Ingredient.downloader.xrxd_downloader.XrxdDownloader.continue_download")
    def test_continue_download_xrxd(self, mock_continue, mock_db_conn):
        """测试继续下载函数"""
        mock_continue.return_value = True
        result = continue_download_xrxd(mock_db_conn, 2024, 2025)
        assert result is True

    @patch("Ingredient.downloader.xrxd_downloader.XrxdDownloader.start_new_download")
    def test_start_new_xrxd_download(self, mock_start, mock_db_conn):
        """测试开始新下载函数"""
        mock_start.return_value = True
        result = start_new_xrxd_download(mock_db_conn, 2024, 2025)
        assert result is True

    @patch("Ingredient.downloader.xrxd_downloader.XrxdDownloader.continue_download")
    def test_continue_download_xrxd_default_year(self, mock_continue, mock_db_conn):
        """测试继续下载函数（默认结束年份）"""
        mock_continue.return_value = True
        result = continue_download_xrxd(mock_db_conn, 2024)
        assert result is True

    @patch("Ingredient.downloader.xrxd_downloader.XrxdDownloader.start_new_download")
    def test_start_new_xrxd_download_default_year(self, mock_start, mock_db_conn):
        """测试开始新下载函数（默认结束年份）"""
        mock_start.return_value = True
        result = start_new_xrxd_download(mock_db_conn, 2024)
        assert result is True