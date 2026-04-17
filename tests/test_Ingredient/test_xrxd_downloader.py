import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock
from KitchenBase.download_enums import DlTaskType, DlTaskStatus
from Ingredient.downloader.xrxd_downloader import XrxdDownloader, continue_download_xrxd, start_new_xrxd_download

# ---------------- 测试类 ----------------
class TestXrxdDownloaderStandard:
    # -------------- 测试初始化 --------------
    def test_init(self, mock_db_conn):
        """测试下载器初始化"""
        downloader = XrxdDownloader(mock_db_conn)
        assert downloader.db_conn == mock_db_conn
        assert downloader.func_name == ""
        assert downloader.progress_manager is not None

    # -------------- 测试获取下一只股票 --------------
    def test_get_next_stock(self, mock_db_conn):
        """测试获取下一只股票"""
        # 清理并重新初始化数据
        cursor = mock_db_conn.cursor()
        cursor.execute("TRUNCATE TABLE stock_fixed_seq")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600000')")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600001')")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600002')")
        mock_db_conn.commit()

        downloader = XrxdDownloader(mock_db_conn)

        # 测试获取第一只股票
        first_stock = downloader._get_next_stock(None)
        assert first_stock == 'sh.600000'

        # 测试获取下一只股票
        next_stock = downloader._get_next_stock('sh.600000')
        assert next_stock == 'sh.600001'

        # 测试最后一只股票
        last_stock = downloader._get_next_stock('sh.600002')
        assert last_stock is None

    # -------------- 测试获取下一年份 --------------
    def test_get_next_year(self, mock_db_conn):
        """测试获取下一年份"""
        downloader = XrxdDownloader(mock_db_conn)

        # 测试正常情况
        next_year = downloader._get_next_year(2020, 2022)
        assert next_year == 2021

        # 测试到达结束年份
        next_year = downloader._get_next_year(2022, 2022)
        assert next_year is None

        # 测试超过结束年份
        next_year = downloader._get_next_year(2023, 2022)
        assert next_year is None

    # -------------- 测试获取下一个区块 --------------
    def test_get_next_block(self, mock_db_conn):
        """测试获取下一个区块"""
        # 清理并重新初始化数据
        cursor = mock_db_conn.cursor()
        cursor.execute("TRUNCATE TABLE stock_fixed_seq")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600000')")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600001')")
        mock_db_conn.commit()

        downloader = XrxdDownloader(mock_db_conn)

        # 测试首次调用（获取第一个区块）
        block = downloader._get_next_block(2020, 2022, None, None)
        assert block == (2020, 'sh.600000')

        # 测试同年份下一个股票
        block = downloader._get_next_block(2020, 2022, 2020, 'sh.600000')
        assert block == (2020, 'sh.600001')

        # 测试年份切换
        block = downloader._get_next_block(2020, 2022, 2020, 'sh.600001')
        assert block == (2021, 'sh.600000')

        # 测试无股票情况
        cursor.execute("TRUNCATE TABLE stock_fixed_seq")
        mock_db_conn.commit()
        block = downloader._get_next_block(2020, 2022, None, None)
        assert block is None

    # -------------- 测试下载原始分红送配数据 --------------
    @patch('Ingredient.downloader.xrxd_downloader.query_dividend_data')
    def test_download_raw_xrxd_data(self, mock_query, mock_db_conn):
        """测试下载原始分红送配数据"""
        # 模拟Baostock返回
        mock_response = MagicMock()
        mock_response.error_code = '0'
        mock_response.get_data.return_value = pd.DataFrame({
            'dividPreNoticeDate': ['2024-01-15'],
            'dividAgmPumDate': ['2024-02-20'],
            'dividPlanAnnounceDate': ['2024-03-01'],
            'dividPlanDate': ['2024-03-15'],
            'dividRegistDate': ['2024-03-20'],
            'dividOperateDate': ['2024-03-25'],
            'dividPayDate': ['2024-03-30'],
            'dividStockMarketDate': ['2024-04-01'],
            'dividCashPsBeforeTax': ['0.5'],
            'dividCashPsAfterTax': ['0.45'],
            'dividStocksPs': ['0.2'],
            'dividCashStock': ['10派5送2'],
            'dividReserveToStockPs': ['0.1']
        })
        mock_query.return_value = mock_response

        downloader = XrxdDownloader(mock_db_conn)
        df = downloader._download_raw_xrxd_data('sh.600000', 2024)
        assert df is not None
        assert not df.empty

    # -------------- 测试下载原始分红送配数据 - API错误 --------------
    @patch('Ingredient.downloader.xrxd_downloader.query_dividend_data')
    def test_download_raw_xrxd_data_api_error(self, mock_query, mock_db_conn):
        """测试下载原始分红送配数据 - API错误"""
        # 模拟Baostock返回错误
        mock_response = MagicMock()
        mock_response.error_code = '1'
        mock_response.error_msg = 'API错误'
        mock_query.return_value = mock_response

        downloader = XrxdDownloader(mock_db_conn)
        df = downloader._download_raw_xrxd_data('sh.600000', 2024)
        assert df is None

    # -------------- 测试下载原始分红送配数据 - 无数据 --------------
    @patch('Ingredient.downloader.xrxd_downloader.query_dividend_data')
    def test_download_raw_xrxd_data_empty(self, mock_query, mock_db_conn):
        """测试下载原始分红送配数据 - 无数据"""
        # 模拟Baostock返回空数据
        mock_response = MagicMock()
        mock_response.error_code = '0'
        mock_response.get_data.return_value = pd.DataFrame()
        mock_query.return_value = mock_response

        downloader = XrxdDownloader(mock_db_conn)
        df = downloader._download_raw_xrxd_data('sh.600000', 2024)
        assert df is None

    # -------------- 测试清洗分红送配数据 --------------
    def test_clean_xrxd_data(self, mock_db_conn):
        """测试分红送配数据清洗"""
        downloader = XrxdDownloader(mock_db_conn)

        # 构造原始数据（模拟Baostock返回）
        raw_df = pd.DataFrame({
            'dividPreNoticeDate': ['2024-01-15'],
            'dividAgmPumDate': ['2024-02-20'],
            'dividPlanAnnounceDate': ['2024-03-01'],
            'dividPlanDate': ['2024-03-15'],
            'dividRegistDate': ['2024-03-20'],
            'dividOperateDate': ['2024-03-25'],
            'dividPayDate': ['2024-03-30'],
            'dividStockMarketDate': ['2024-04-01'],
            'dividCashPsBeforeTax': ['0.5'],
            'dividCashPsAfterTax': ['0.45'],
            'dividStocksPs': ['0.2'],
            'dividCashStock': ['10派5送2'],
            'dividReserveToStockPs': ['0.1']
        })

        # 执行清洗
        cleaned_df = downloader._clean_xrxd_data(raw_df, 'sh.600000', 2024)

        # 断言结果
        assert cleaned_df is not None
        assert 'xrxd_year' in cleaned_df.columns
        assert 'std_stock_code' in cleaned_df.columns
        assert cleaned_df['xrxd_year'].iloc[0] == 2024
        assert cleaned_df['std_stock_code'].iloc[0] == 'sh.600000'
        assert cleaned_df['xrxd_cash_ps_before_tax'].iloc[0] == 0.5
        assert cleaned_df['xrxd_stocks_ps'].iloc[0] == 0.2

    # -------------- 测试清洗分红送配数据 - 无效数据 --------------
    def test_clean_xrxd_data_invalid(self, mock_db_conn):
        """测试分红送配数据清洗 - 无效数据"""
        downloader = XrxdDownloader(mock_db_conn)

        # 构造包含无效数值的数据
        raw_df = pd.DataFrame({
            'dividPreNoticeDate': [''],
            'dividAgmPumDate': [''],
            'dividPlanAnnounceDate': ['2024-03-01'],
            'dividPlanDate': ['2024-03-15'],
            'dividRegistDate': ['2024-03-20'],
            'dividOperateDate': ['2024-03-25'],
            'dividPayDate': ['2024-03-30'],
            'dividStockMarketDate': ['2024-04-01'],
            'dividCashPsBeforeTax': ['invalid'],
            'dividCashPsAfterTax': [''],
            'dividStocksPs': ['0.2'],
            'dividCashStock': ['10派5送2'],
            'dividReserveToStockPs': ['']
        })

        # 执行清洗
        cleaned_df = downloader._clean_xrxd_data(raw_df, 'sh.600000', 2024)

        # 断言结果 - 无效数值应被处理为None
        assert cleaned_df is not None
        assert pd.isna(cleaned_df['xrxd_cash_ps_before_tax'].iloc[0])
        assert cleaned_df['xrxd_stocks_ps'].iloc[0] == 0.2

    # -------------- 测试清洗分红送配数据 - 空数据 --------------
    def test_clean_xrxd_data_empty(self, mock_db_conn):
        """测试分红送配数据清洗 - 空数据"""
        downloader = XrxdDownloader(mock_db_conn)
        cleaned_df = downloader._clean_xrxd_data(pd.DataFrame(), 'sh.600000', 2024)
        assert cleaned_df is None

    # -------------- 测试处理单个分红送配数据下载区块 --------------
    @patch('Ingredient.downloader.xrxd_downloader.query_dividend_data')
    def test_fetch_xrxd_block(self, mock_query, mock_db_conn):
        """测试处理单个分红送配数据下载区块"""
        # 模拟Baostock返回
        mock_response = MagicMock()
        mock_response.error_code = '0'
        mock_response.get_data.return_value = pd.DataFrame({
            'dividPreNoticeDate': ['2024-01-15'],
            'dividAgmPumDate': ['2024-02-20'],
            'dividPlanAnnounceDate': ['2024-03-01'],
            'dividPlanDate': ['2024-03-15'],
            'dividRegistDate': ['2024-03-20'],
            'dividOperateDate': ['2024-03-25'],
            'dividPayDate': ['2024-03-30'],
            'dividStockMarketDate': ['2024-04-01'],
            'dividCashPsBeforeTax': ['0.5'],
            'dividCashPsAfterTax': ['0.45'],
            'dividStocksPs': ['0.2'],
            'dividCashStock': ['10派5送2'],
            'dividReserveToStockPs': ['0.1']
        })
        mock_query.return_value = mock_response

        # 初始化XrxdManager mock
        with patch('Ingredient.downloader.xrxd_downloader.XrxdManager') as mock_manager:
            mock_instance = MagicMock()
            mock_instance.save_xrxd_data.return_value = True
            mock_manager.return_value = mock_instance

            downloader = XrxdDownloader(mock_db_conn)
            downloader._fetch_xrxd_block(2024, 'sh.600000')

            # 断言：数据保存被调用
            mock_instance.save_xrxd_data.assert_called_once()

    # -------------- 测试获取当前正在下载的区块 --------------
    def test_get_downloading_block(self, mock_db_conn):
        """测试获取当前正在下载的区块"""
        downloader = XrxdDownloader(mock_db_conn)
        
        # 测试无下载区块
        block = downloader._get_downloading_block()
        assert block is None

    # -------------- 测试设置当前正在下载的区块 --------------
    def test_set_xrxd_dl_pointer(self, mock_db_conn):
        """测试设置当前正在下载的区块"""
        downloader = XrxdDownloader(mock_db_conn)
        result = downloader._set_xrxd_dl_pointer(2024, 'sh.600000')
        assert isinstance(result, bool)

    # -------------- 测试获取下载状态 --------------
    @patch('Ingredient.downloader.xrxd_downloader.GlobalDlCtrlBlockManager.get_task_status')
    def test_get_download_status(self, mock_get_status, mock_db_conn):
        """测试获取下载状态"""
        # 模拟返回状态
        mock_get_status.return_value = DlTaskStatus.NOT_STARTED
        
        downloader = XrxdDownloader(mock_db_conn)
        status = downloader._get_download_status()
        assert isinstance(status, DlTaskStatus)
        assert status == DlTaskStatus.NOT_STARTED

    # -------------- 测试设置下载状态 --------------
    @patch('Ingredient.downloader.xrxd_downloader.GlobalDlCtrlBlockManager.get_task_status')
    @patch('Ingredient.downloader.xrxd_downloader.GlobalDlCtrlBlockManager.set_task_status')
    def test_set_download_status(self, mock_set_status, mock_get_status, mock_db_conn):
        """测试设置下载状态"""
        # 模拟设置状态成功
        mock_set_status.return_value = True
        # 模拟返回设置后的状态
        mock_get_status.return_value = DlTaskStatus.IN_PROGRESS
        
        downloader = XrxdDownloader(mock_db_conn)
        downloader._set_download_status(DlTaskStatus.IN_PROGRESS)
        status = downloader._get_download_status()
        assert status == DlTaskStatus.IN_PROGRESS

    # -------------- 测试继续下载分红送配数据 --------------
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader._get_next_block')
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader._fetch_xrxd_block')
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader._get_downloading_block')
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader._get_download_status')
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader._set_download_status')
    @patch('Ingredient.downloader.xrxd_downloader.GlobalDlCtrlBlockManager.clear_dl_pointer')
    @patch('Ingredient.downloader.xrxd_downloader.dm.get_total_block_count')
    @patch('Ingredient.downloader.xrxd_downloader.dm.get_completed_block_count')
    def test_continue_download_xrxd(self, mock_get_completed, mock_get_total, mock_clear, mock_set_status, mock_get_status, mock_get_block, mock_fetch, mock_next_block, mock_db_conn):
        """测试继续下载分红送配数据"""
        # 模拟无下载区块
        mock_get_block.return_value = None
        # 模拟无下一个区块
        mock_next_block.return_value = None
        # 模拟下载成功
        mock_fetch.return_value = None
        # 模拟下载状态
        mock_get_status.return_value = DlTaskStatus.NOT_STARTED
        # 模拟设置状态成功
        mock_set_status.return_value = None
        # 模拟清空指针成功
        mock_clear.return_value = None
        # 模拟区块计数
        mock_get_total.return_value = 10
        mock_get_completed.return_value = 10

        downloader = XrxdDownloader(mock_db_conn)
        result = downloader.continue_download_xrxd(2024, 2025)
        assert isinstance(result, bool)
        assert result is True

    # -------------- 测试开始新的分红送配数据下载任务 --------------
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader.continue_download_xrxd')
    def test_start_new_xrxd_download(self, mock_continue, mock_db_conn):
        """测试开始新的分红送配数据下载任务"""
        # 模拟继续下载成功
        mock_continue.return_value = True

        downloader = XrxdDownloader(mock_db_conn)
        result = downloader.start_new_xrxd_download(2024, 2025)
        assert result is True

    # -------------- 测试全局对外接口函数 - continue_download_xrxd --------------
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader.continue_download_xrxd')
    def test_global_continue_download_xrxd(self, mock_continue, mock_db_conn):
        """测试全局对外接口函数 - continue_download_xrxd"""
        # 模拟继续下载成功
        mock_continue.return_value = True

        result = continue_download_xrxd(mock_db_conn, 2024, 2025)
        assert result is True

    # -------------- 测试全局对外接口函数 - start_new_xrxd_download --------------
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader.start_new_xrxd_download')
    def test_global_start_new_xrxd_download(self, mock_start, mock_db_conn):
        """测试全局对外接口函数 - start_new_xrxd_download"""
        # 模拟开始新下载成功
        mock_start.return_value = True

        result = start_new_xrxd_download(mock_db_conn, 2024, 2025)
        assert result is True

    # -------------- 测试全局对外接口函数 - 默认结束年份 --------------
    @patch('Ingredient.downloader.xrxd_downloader.XrxdDownloader.continue_download_xrxd')
    def test_global_continue_download_xrxd_default_year(self, mock_continue, mock_db_conn):
        """测试全局对外接口函数 - 默认结束年份"""
        # 模拟继续下载成功
        mock_continue.return_value = True

        result = continue_download_xrxd(mock_db_conn, 2024)
        assert result is True
