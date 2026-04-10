from KitchenBase.download_enums import DlTaskType
"""
行业分类数据下载器

参考复权因子下载器设计，采用单层循环下载，支持断点续传
"""

import datetime
from typing import Optional, Tuple
import pandas as pd
from KitchenBase.baostock_wrapper import query_stock_industry
from KitchenBase.logger_config import get_logger
from KitchenBase.download_enums import DlTaskStatus, DlBlockStatus, DlTaskType
from Ingredient.DataNest import (
    StockIndustryDataManager,
    GlobalDlCtrlBlockManager
)


class StockIndustryDownloader:
    """
    行业分类数据下载器
    
    设计特点：
    1. 参考复权因子下载器设计
    2. 单层循环下载
    3. 支持断点续传
    4. 一次性获取全市场行业数据
    """
    
    def __init__(self, db_conn):
        """
        初始化下载器
        
        :param db_conn: 数据库连接
        """
        self.db_conn = db_conn
        self.industry_manager = StockIndustryDataManager(db_conn)
        self.progress_manager = GlobalDlCtrlBlockManager(db_conn)
        self.logger = get_logger(__name__)
        
        # 任务类型
        self.task_type = DlTaskType.INDUSTRY
        # 默认起始年份
        self.default_start_year = 2000
        # 默认结束年份（当前年份）
        self.default_end_year = datetime.datetime.now().year
    
    def _get_first_block(self) -> Optional[int]:
        """
        获取第一个区块（最新年份）
        
        :return: 最新年份或 None
        """
        return self.default_end_year
    
    def _get_next_block(self, current_year: Optional[int]) -> Optional[int]:
        """
        获取下一个区块（年份降序）
        
        :param current_year: 当前年份
        :return: 下一个年份或 None
        """
        if current_year is None:
            return None
        
        next_year = current_year - 1
        if next_year < self.default_start_year:
            return None
        return next_year
    
    def _get_dl_pointer(self) -> Optional[Tuple[int, str]]:
        """
        获取下载指针
        
        :return: (年份, 股票代码) 或 None
        """
        func_name = "_get_dl_pointer"
        try:
            # 使用新添加的 get_stock_industry_dl_pointer 方法
            progress = self.progress_manager.get_stock_industry_dl_pointer()
            if progress:
                year, stock, _, _, _ = progress
                return year, stock
            return None
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 获取下载指针失败: {str(e)}")
            return None
    
    def _set_dl_pointer(self, year: int, stock: str = ""):
        """
        保存下载指针
        
        :param year: 年份
        :param stock: 股票代码
        """
        func_name = "_set_dl_pointer"
        try:
            # 使用新添加的 set_stock_industry_dl_pointer 方法
            self.progress_manager.set_stock_industry_dl_pointer(
                year=year,
                stock_code=stock
            )
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 保存下载指针失败: {str(e)}")
    
    def _clear_dl_pointer(self):
        """
        清空下载指针
        """
        func_name = "_clear_dl_pointer"
        try:
            # 使用 DlTaskType.INDUSTRY 作为任务类型
            self.progress_manager.clear_dl_pointer(DlTaskType.INDUSTRY)
            self.logger.debug(f"[{__name__}.{func_name}] 下载指针已清空")
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 清空下载指针失败: {str(e)}")
    
    def _get_task_status(self) -> DlTaskStatus:
        """
        获取下载状态
        
        :return: 下载状态
        """
        func_name = "_get_task_status"
        try:
            return self.progress_manager.get_task_status(self.task_type)
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 获取下载状态失败: {str(e)}")
            return DlTaskStatus.NOT_STARTED
    
    def _set_task_status(self, status: DlTaskStatus):
        """
        设置下载状态
        
        :param status: 下载状态
        """
        func_name = "_set_download_status"
        try:
            self.progress_manager.set_task_status(self.task_type, status)
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 设置下载状态失败: {str(e)}")
    
    def _clean_industry_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        清洗行业数据
        
        :param df: 原始数据
        :return: 清洗后的数据
        """
        func_name = "_clean_industry_data"
        
        if df.empty:
            return df
        
        try:
            # 重命名字段
            column_mapping = {
                'code': 'std_stock_code',
                'code_name': 'stock_name',
                'industry': 'industry',
                'industryClassification': 'industry_classification',
                'updateDate': 'update_date'
            }
            
            # 只重命名存在的字段
            rename_dict = {k: v for k, v in column_mapping.items() if k in df.columns}
            df = df.rename(columns=rename_dict)
            
            # 确保必要字段存在
            required_columns = ['std_stock_code', 'stock_name', 'industry', 'industry_classification', 'update_date']
            for col in required_columns:
                if col not in df.columns:
                    df[col] = None
            
            # 填充空值
            df = df.fillna({
                'industry': '未知',
                'industry_classification': '未知',
                'stock_name': ''
            })
            
            # 添加数据源字段
            df['industry_source'] = 'baostock'
            
            self.logger.debug(f"[{__name__}.{func_name}] 数据清洗完成，共 {len(df)} 条记录")
            return df
            
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 数据清洗失败: {str(e)}")
            return pd.DataFrame()
    
    def _save_industry_data(self, df: pd.DataFrame) -> bool:
        """
        保存行业数据到数据库
        
        :param df: 清洗后的数据
        :return: 是否成功
        """
        func_name = "_save_industry_data"
        
        if df.empty:
            self.logger.warning(f"[{__name__}.{func_name}] 数据为空，无需保存")
            return False
        
        try:
            success = self.industry_manager.save_industry_data(df)
            if success:
                self.logger.debug(f"[{__name__}.{func_name}] 数据保存成功，共 {len(df)} 条记录")
            return success
        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 数据保存失败: {str(e)}")
            return False
    
    def _download_raw_stock_industry_data(self, year: int) -> Optional[pd.DataFrame]:
        """
        下载原始行业数据
        
        构建查询日期并调用 Baostock API 获取全市场行业数据
        
        :param year: 年份
        :return: 原始行业数据 DataFrame 或 None
        """
        func_name = "_download_raw_stock_industry_data"
        
        # 构建查询日期
        current_year = datetime.datetime.now().year
        if year == current_year:
            # 如果是当前年份，使用今天的日期
            query_date = datetime.datetime.now().strftime("%Y-%m-%d")
        else:
            # 否则使用该年的最后一天
            query_date = f"{year}-12-31"
        
        # 直接调用 query_stock_industry() 获取全市场行业数据
        # 不传 code 参数，返回所有股票的行业分类
        self.logger.debug(f"[{__name__}.{func_name}] 调用 API 获取 {year} 年行业数据，查询日期: {query_date}")
        rs = query_stock_industry(date=query_date)

        # 检查API返回状态
        if rs.error_code != "0":
            self.logger.warning(f"[{__name__}.{func_name}] Baostock API错误(error_code={rs.error_code}):  {rs.error_msg}")
            return None
        df = rs.get_data()
        if not df.empty:
            self.logger.info(f"[{__name__}.{func_name}] 获取到 {len(df)} 条原始数据")
        return df
    
    def _fetch_stock_industry_block(self, year: int) -> bool:
        """
        下载单个年份的行业数据
        
        优化：直接调用 query_stock_industry() 不传股票代码，获取全市场数据
        
        :param year: 年份
        :return: 是否成功
        """
        func_name = "_fetch_stock_industry_block"
        self.logger.info(f"[{__name__}.{func_name}] 开始下载 {year} 年行业分类数据")
        # 更新区块状态为处理中
        self.industry_manager.update_block_status(
            year,
            DlBlockStatus.NOT_COMPLETED,
            block_name=f"{year}年行业分类"
        )
        
        # 下载原始数据
        raw_df = self._download_raw_stock_industry_data(year)
        
        if raw_df is None or raw_df.empty:
            self.logger.warning(f"[{__name__}.{func_name}] {year} 年行业数据为空")
            self.industry_manager.update_block_status(
                year,
                DlBlockStatus.SKIPPED,
                block_name=f"{year}年行业分类"
            )
            return False
        
        self.logger.info(f"[{__name__}.{func_name}] 获取到 {len(raw_df)} 条原始数据")
        
        # 清洗数据
        cleaned_df = self._clean_industry_data(raw_df)
        
        if cleaned_df.empty:
            self.logger.warning(f"[{__name__}.{func_name}] {year} 年数据清洗后为空")
            self.industry_manager.update_block_status(
                year,
                DlBlockStatus.ERROR,
                error_message="数据清洗后为空",
                block_name=f"{year}年行业分类"
            )
            return False
        
        # 保存数据
        if self._save_industry_data(cleaned_df):
            # 更新区块状态为已完成
            self.industry_manager.update_block_status(
                year,
                DlBlockStatus.COMPLETED,
                total_items=len(cleaned_df),
                success_count=len(cleaned_df),
                fail_count=0,
                block_name=f"{year}年行业分类"
            )
            self.logger.info(f"[{__name__}.{func_name}] {year} 年行业数据下载完成")
            return True
        else:
            # 更新区块状态为错误
            self.industry_manager.update_block_status(
                year,
                DlBlockStatus.ERROR,
                error_message="数据保存失败",
                block_name=f"{year}年行业分类"
            )
            return False
    
    def continue_download_industry(self, start_year: Optional[int] = None, end_year: Optional[int] = None) -> bool:
        """
        继续下载行业分类数据（支持断点续传）
        
        :param start_year: 起始年份（默认使用 2000）
        :param end_year: 结束年份（默认使用当前年份）
        :return: True 表示全部下载完成
        """
        func_name = "continue_download_industry"
        self.logger.info(f"[{__name__}.{func_name}] 开始继续下载行业分类数据")
        
        # 设置年份范围
        self.start_year = start_year if start_year is not None else self.default_start_year
        self.end_year = end_year if end_year is not None else self.default_end_year
        # 检查下载状态
        status = self._get_task_status()
        if status == DlTaskStatus.COMPLETED:
            self.logger.info(f"[{__name__}.{func_name}] 行业分类数据下载已完成")
            return True
        
        # 设置下载状态为进行中
        if status == DlTaskStatus.NOT_STARTED:
            self.logger.info(f"[{__name__}.{func_name}] 行业分类数据下载未开始，设置为进行中")
            self._set_task_status(DlTaskStatus.IN_PROGRESS)
        
        # 计算总区块数（年份范围）
        total_blocks = self.end_year - self.start_year + 1
        self.logger.info(f"[{__name__}.{func_name}] 总区块数: {total_blocks} ({self.start_year}-{self.end_year})")
        
        # 获取下载指针
        pointer = self._get_dl_pointer()
        if pointer:
            current_year, _ = pointer
            self.logger.info(f"[{__name__}.{func_name}] 恢复下载: 从 {current_year} 年开始")
        else:
            # 获取第一个区块（最新年份）
            current_year = self._get_first_block()
            self.logger.info(f"[{__name__}.{func_name}] 开始新下载: 从 {current_year} 年开始")
        
        # 单层循环下载
        completed_blocks = self.industry_manager.get_completed_block_count(
            self.start_year, self.end_year + 1
        )
        
        while current_year is not None and current_year >= self.start_year:
            try:
                # 检查当前年份是否已完成
                block_status = self.industry_manager.get_block_status(current_year)
                if block_status == DlBlockStatus.COMPLETED:
                    self.logger.debug(f"[{__name__}.{func_name}] {current_year} 年已完成，跳过")
                    current_year = self._get_next_block(current_year)
                    continue
                
                # 下载当前年份数据
                self.logger.info(f"[{__name__}.{func_name}] 下载 {current_year} 年数据 ({completed_blocks + 1}/{total_blocks})")
                success = self._fetch_stock_industry_block(current_year)

                if success:
                    completed_blocks += 1
                    # 计算进度
                    progress = (completed_blocks / total_blocks) * 100
                    self.logger.info(f"[{__name__}.{func_name}] 进度: {completed_blocks}/{total_blocks} ({progress:.1f}%)")

                # 获取下一个年份
                next_year = self._get_next_block(current_year)

                # 保存下载指针（指向下一个年份）
                if next_year:
                    self._set_dl_pointer(next_year, "")

                current_year = next_year
            except ConnectionRefusedError as e:
                # 网络连接异常，记录错误日志，退出循环体，中止整个下载任务
                self.logger.error(f"[{__name__}.{func_name}] 拒绝连接，下载失败: {current_year} {str(e)}")
                # 虽然退出循环体，但保持下载状态为IN_PROGRESS，方便后续恢复下载
                return False
            except Exception as e:
                self.logger.error(f"[{__name__}.{func_name}] 下载 {current_year} 年数据失败: {str(e)}")
                return False
        
        # 完成下载
        self._set_task_status(DlTaskStatus.COMPLETED)
        self._clear_dl_pointer()
        self.logger.info(f"[{__name__}.{func_name}] 行业分类数据下载完成")
        return True
    
    def start_new_industry_download(self, start_year: Optional[int] = None, end_year: Optional[int] = None) -> bool:
        """
        开始新的行业分类数据下载任务
        
        :param start_year: 起始年份（默认使用 2000）
        :param end_year: 结束年份（默认使用当前年份）
        :return: True 表示全部下载完成
        """
        func_name = "start_new_industry_download"
        self.logger.info(f"[{__name__}.{func_name}] 开始新的行业分类数据下载")
        
        try:
            # 设置年份范围
            self.start_year = start_year if start_year is not None else self.default_start_year
            self.end_year = end_year if end_year is not None else self.default_end_year
            
            # 清空下载指针
            self._clear_dl_pointer()
            
            # 重置所有区块状态
            for year in range(self.start_year, self.end_year + 1):
                self.industry_manager.update_block_status(
                    year,
                    DlBlockStatus.NOT_COMPLETED,
                    block_name=f"{year}年行业分类"
                )

            # 设置下载状态为未开始
            self._set_task_status(DlTaskStatus.NOT_STARTED)

            # 调用继续下载
            return self.continue_download_industry(start_year, end_year)

        except Exception as e:
            self.logger.error(f"[{__name__}.{func_name}] 开始新下载失败: {str(e)}")
            return False


def continue_download_industry(db_conn, start_year: Optional[int] = None, end_year: Optional[int] = None) -> bool:
    """
    继续下载行业分类数据（支持断点续传）
    
    :param db_conn: 数据库连接
    :param start_year: 起始年份（默认使用 2000）
    :param end_year: 结束年份（默认使用当前年份）
    :return: True 表示全部下载完成
    """
    downloader = StockIndustryDownloader(db_conn)
    return downloader.continue_download_industry(start_year, end_year)


def start_new_industry_download(db_conn, start_year: Optional[int] = None, end_year: Optional[int] = None) -> bool:
    """
    开始新的行业分类数据下载任务
    
    :param db_conn: 数据库连接
    :param start_year: 起始年份（默认使用 2000）
    :param end_year: 结束年份（默认使用当前年份）
    :return: True 表示全部下载完成
    """
    downloader = StockIndustryDownloader(db_conn)
    return downloader.start_new_industry_download(start_year, end_year)
