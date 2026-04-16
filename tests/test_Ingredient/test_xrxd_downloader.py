import pytest
import pandas as pd
from datetime import datetime
from unittest.mock import patch, MagicMock
from Ingredient.downloader.xrxd_downloader import XrxdDownloader

# ---------------- 测试类 ----------------
class TestXrxdDownloader:
    # -------------- 测试初始化 --------------
    def test_init(self, mock_db_conn):
        """测试下载器初始化"""
        downloader = XrxdDownloader(mock_db_conn)
        assert downloader.db_conn == mock_db_conn
        assert downloader.func_name == ""
        assert downloader.progress_manager is not None

    # -------------- 测试任务总数计算 --------------
    def test_calc_total_tasks(self, mock_db_conn):
        """测试任务总数计算"""
        downloader = XrxdDownloader(mock_db_conn)
        # 插入更多测试股票
        cursor = mock_db_conn.cursor()
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600001')")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600002')")
        mock_db_conn.commit()

        # 计算2020-2022年（3年）的任务总数
        total = downloader._calc_total_tasks(2020, 2022)
        # 3年 * 3只股票 = 9个任务
        assert total == 9

    # -------------- 测试股票计数 --------------
    def test_count_stocks_in_fixed_seq(self, mock_db_conn):
        """测试股票计数"""
        # 清理并重新初始化数据
        cursor = mock_db_conn.cursor()
        cursor.execute("TRUNCATE TABLE stock_fixed_seq")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600000')")
        mock_db_conn.commit()

        downloader = XrxdDownloader(mock_db_conn)
        count = downloader._count_stocks_in_fixed_seq()
        assert count == 1  # 初始只有1只股票

        # 添加更多股票
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600001')")
        mock_db_conn.commit()

        count = downloader._count_stocks_in_fixed_seq()
        assert count == 2

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

    # -------------- 测试获取下一个任务 --------------
    def test_get_next_task(self, mock_db_conn):
        """测试获取下一个任务"""
        # 清理并重新初始化数据
        cursor = mock_db_conn.cursor()
        cursor.execute("TRUNCATE TABLE stock_fixed_seq")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600000')")
        cursor.execute("INSERT INTO stock_fixed_seq (std_stock_code) VALUES ('sh.600001')")
        mock_db_conn.commit()

        downloader = XrxdDownloader(mock_db_conn)

        # 测试首次调用（获取第一个任务）
        task = downloader._get_next_task(2020, 2022, None, None)
        assert task == (2020, 'sh.600000')

        # 测试同年份下一个股票
        task = downloader._get_next_task(2020, 2022, 2020, 'sh.600000')
        assert task == (2020, 'sh.600001')

        # 测试年份切换
        task = downloader._get_next_task(2020, 2022, 2020, 'sh.600001')
        assert task == (2021, 'sh.600000')

    # -------------- 测试数据清洗 --------------
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
        assert 'xrxd_year' in cleaned_df.columns
        assert 'std_stock_code' in cleaned_df.columns
        assert cleaned_df['xrxd_year'].iloc[0] == 2024
        assert cleaned_df['std_stock_code'].iloc[0] == 'sh.600000'
        assert cleaned_df['xrxd_cash_ps_before_tax'].iloc[0] == 0.5
        assert cleaned_df['xrxd_stocks_ps'].iloc[0] == 0.2

        # 测试空数据
        empty_df = downloader._clean_xrxd_data(pd.DataFrame(), 'sh.600000', 2024)
        assert empty_df is None

    # -------------- 测试数据清洗 - 无效数据 --------------
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

    # -------------- 测试进度读写 --------------
    def test_save_and_get_downloading_task(self, mock_db_conn):
        """测试进度保存和读取"""
        downloader = XrxdDownloader(mock_db_conn)

        # 保存进度
        downloader._save_download_progress(2024, 'sh.600000')

        # 读取进度
        progress = downloader._get_downloading_task()
        assert progress == (2024, 'sh.600000')

        # 更新进度
        downloader._save_download_progress(2024, 'sh.600001')
        progress = downloader._get_downloading_task()
        assert progress == (2024, 'sh.600001')

    # -------------- 测试进度读取 - 无记录 --------------
    def test_get_downloading_task_none(self, mock_db_conn):
        """测试进度读取 - 无记录"""
        # 清理之前的测试数据
        cursor = mock_db_conn.cursor()
        cursor.execute("DELETE FROM global_download_progress WHERE task_type = 'xrxd'")
        mock_db_conn.commit()

        downloader = XrxdDownloader(mock_db_conn)

        # 读取无记录的进度
        progress = downloader._get_downloading_task()
        assert progress is None

    # -------------- 测试下载流程（模拟外部依赖） --------------
    @patch('Ingredient.xrxd_downloader.bs.query_dividend_data')
    def test_fetch_xrxd_task(self, mock_query, mock_db_conn):
        """测试单个数据下载（模拟Baostock返回）"""
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
        with patch('Ingredient.xrxd_downloader.XrxdManager') as mock_manager:
            mock_instance = MagicMock()
            mock_instance.save_xrxd_data.return_value = True
            mock_manager.return_value = mock_instance

            downloader = XrxdDownloader(mock_db_conn)
            downloader._fetch_xrxd_task(2024, 'sh.600000')

            # 断言：数据保存被调用
            mock_instance.save_xrxd_data.assert_called_once()

    # -------------- 测试下载流程 - API错误 --------------
    @patch('Ingredient.xrxd_downloader.bs.query_dividend_data')
    def test_fetch_xrxd_task_api_error(self, mock_query, mock_db_conn):
        """测试单个数据下载 - API错误"""
        # 模拟Baostock返回错误
        mock_response = MagicMock()
        mock_response.error_code = '1'
        mock_response.error_msg = 'API错误'
        mock_query.return_value = mock_response

        downloader = XrxdDownloader(mock_db_conn)
        result = downloader._fetch_xrxd_task(2024, 'sh.600000')

        # 断言：返回None
        assert result is None

    # -------------- 测试下载流程 - 无数据 --------------
    @patch('Ingredient.xrxd_downloader.bs.query_dividend_data')
    def test_fetch_xrxd_task_empty(self, mock_query, mock_db_conn):
        """测试单个数据下载 - 无数据"""
        # 模拟Baostock返回空数据
        mock_response = MagicMock()
        mock_response.error_code = '0'
        mock_response.get_data.return_value = pd.DataFrame()
        mock_query.return_value = mock_response

        downloader = XrxdDownloader(mock_db_conn)
        result = downloader._fetch_xrxd_task(2024, 'sh.600000')

        # 断言：返回None
        assert result is None

    # -------------- 测试断点续传逻辑 --------------
    @patch('Ingredient.xrxd_downloader.XrxdDownloader._get_next_task')
    def test_download_xrxd_resume(self, mock_next_task, mock_db_conn):
        """测试断点续传（恢复中断任务）"""
        # 模拟有中断任务
        with patch('Ingredient.xrxd_downloader.XrxdDownloader._get_downloading_task') as mock_get_task:
            mock_get_task.return_value = (2024, 'sh.600000')
            # 模拟下一个任务为None（执行完中断任务后结束）
            mock_next_task.return_value = None

            # 模拟数据获取
            with patch('Ingredient.xrxd_downloader.XrxdDownloader._fetch_xrxd_task') as mock_fetch:
                mock_fetch.return_value = None

                downloader = XrxdDownloader(mock_db_conn)
                downloader.download_xrxd(2024, 2024)

                # 断言：中断任务被处理
                mock_fetch.assert_called_once_with(2024, 'sh.600000')

    # -------------- 测试主下载流程 --------------
    @patch('Ingredient.xrxd_downloader.XrxdDownloader._fetch_xrxd_task')
    @patch('Ingredient.xrxd_downloader.XrxdDownloader._get_next_task')
    def test_download_xrxd_full(self, mock_next_task, mock_fetch, mock_db_conn):
        """测试完整下载流程"""
        # 模拟无中断任务
        with patch('Ingredient.xrxd_downloader.XrxdDownloader._get_downloading_task') as mock_get_task:
            mock_get_task.return_value = None

            # 模拟任务序列
            mock_next_task.side_effect = [
                (2024, 'sh.600000'),
                (2024, 'sh.600001'),
                None  # 结束
            ]

            # 模拟数据获取成功
            mock_fetch.return_value = None

            downloader = XrxdDownloader(mock_db_conn)
            downloader.download_xrxd(2024, 2024)

            # 断言：所有任务都被处理
            assert mock_fetch.call_count == 2
            mock_fetch.assert_any_call(2024, 'sh.600000')
            mock_fetch.assert_any_call(2024, 'sh.600001')
