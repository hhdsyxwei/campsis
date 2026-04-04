# xrxd_downloader.py
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from KitchenBase.baostock_wrapper import query_dividend_data
from Ingredient.DataNest import XrxdManager, BasicStockDataManager, UnifiedDataManager as dm, GlobalDlCtrlBlockManager

# ===================== 全局配置 =====================
logger = get_logger(__name__)

# ===================== 下载器核心类 =====================
class XrxdDownloader:
    def __init__(self, db_conn):
        """
        初始化下载器
        :param db_conn: 外部传入的数据库连接（使用者管理）
        """
        self.db_conn = db_conn
        self.func_name = ""
        self.progress_manager = GlobalDlCtrlBlockManager(db_conn)

    def _calc_total_tasks(self, start_year: int, end_year: int) -> int:
        """
        内部函数：计算指定时间范围下需要下载的任务总数
        计算逻辑：年份总数 × 股票总数 = 总任务数
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（包含）
        :return: 需要下载的任务总数
        """
        self.func_name = "_calc_total_tasks"
        
        # 步骤1：统计指定时间范围内的年份总数
        year_count = end_year - start_year + 1
        
        # 步骤2：统计stock_fixed_seq表中的股票总数
        stock_count = self._count_stocks_in_fixed_seq()
        
        # 步骤3：计算总任务数（年份数 × 股票数）
        total_tasks = year_count * stock_count
        
        logger.debug(
            f"[{__name__}.{self.func_name}] 统计结果："
            f"年份范围[{start_year}-{end_year}] | 年份数={year_count} "
            f"| 股票数={stock_count} | 总任务数={total_tasks}"
        )
        return total_tasks

    def _count_stocks_in_fixed_seq(self) -> int:
        """
        统计stock_fixed_seq表中的股票总数
        :return: 股票总数
        """
        self.func_name = "_count_stocks_in_fixed_seq"
        try:
            return dm.count_stocks_in_fixed_seq(self.db_conn)
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 统计股票数量失败: {str(e)}")
            return 0

    def _get_next_stock(self, current_stock: Optional[str]) -> Optional[str]:
        """
        获取当前股票的下一个股票（按stock_fixed_seq顺序）
        直接利用DataNest模块的next_fixed_stock函数
        :param current_stock: 当前股票代码
        :return: 下一个股票代码或None
        """
        self.func_name = "_get_next_stock"
        return dm.next_fixed_stock(self.db_conn, current_stock)

    def _get_next_year(self, current_year: int, end_year: int) -> Optional[int]:
        """
        获取当前年份的下一个年份
        :param current_year: 当前年份
        :param end_year: 结束年份
        :return: 下一个年份或None
        """
        next_year = current_year + 1
        return next_year if next_year <= end_year else None

    # -------------------------------------------------------------------------
    # 【核心】动态查找：下一个待下载任务（无列表、纯数据库驱动）
    #  当前排序规则：年份(旧→新) → 股票固定顺序
    # -------------------------------------------------------------------------
    def _get_next_task(
        self, 
        start_year: int, 
        end_year: int, 
        current_year: Optional[int] = None, 
        current_stock: Optional[str] = None
    ) -> Optional[Tuple[int, str]]:
        """
        仅推动任务指针向前，找到下一个待处理任务（不判断下载状态）
        迭代规则：年份升序 → 股票固定顺序（stock_fixed_seq表）
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（包含）
        :param current_year: 当前年份（首次调用传None，从start_year开始）
        :param current_stock: 当前股票（首次调用传None，从第一个股票开始）
        :return: (next_year, next_stock) 或 None（无更多任务）
        """
        self.func_name = "_get_next_task"

        # ========== 步骤1：初始化起始年份（首次调用） ==========
        if current_year is None:
            current_year = start_year

        # ========== 步骤2：处理「同年份内的股票迭代」 ==========
        if current_stock:
            # 获取当前股票的下一个股票（按固定顺序）
            next_stock = self._get_next_stock(current_stock)
            if next_stock:
                # 同年份有下一个股票 → 直接返回
                logger.debug(f"[{__name__}.{self.func_name}] 同年份下一个股票: {current_year} -> {next_stock}")
                return (current_year, next_stock)
            else:
                # 当前年份股票已遍历完 → 获取下一个年份
                next_year = self._get_next_year(current_year, end_year)
                if not next_year:
                    # 无下一年份 → 迭代结束
                    logger.debug(f"[{__name__}.{self.func_name}] 无更多任务（年份范围：{start_year}-{end_year}）")
                    return None
                # 切换到下一年份，重置为第一个股票
                current_year = next_year
                current_stock = None

        # ========== 步骤3：获取当前年份的第一个股票 ==========
        first_stock = self._get_next_stock(None)
        if not first_stock:
            logger.warning(f"[{__name__}.{self.func_name}] 无股票数据可用")
            return None

        logger.debug(f"[{__name__}.{self.func_name}] 下一个任务: {current_year} -> {first_stock}")
        return (current_year, first_stock)

    def _download_raw_xrxd_data(self, stock_code: str, year: int) -> Optional[pd.DataFrame]:
        """
        从Baostock下载原始分红送配数据
        :param stock_code: 股票代码
        :param year: 年份
        :return: 原始数据DataFrame或None
        """
        self.func_name = "_download_raw_xrxd_data"
        try:
            rs = query_dividend_data(
                code=stock_code,
                year=str(year),
                yearType="report"
            )
            
            # 检查API返回状态
            if rs.error_code != "0":
                logger.warning(f"[{__name__}.{self.func_name}] Baostock API错误: {rs.error_msg}")
                return None
            
            # 获取数据
            df = rs.get_data()
            if df.empty:
                logger.debug(f"[{__name__}.{self.func_name}] 无数据: {stock_code} {year}")
                return None
            
            return df
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 下载失败: {stock_code} {year}, {str(e)}")
            return None

    def _clean_xrxd_data(self, raw_df: pd.DataFrame, stock_code: str, year: int) -> Optional[pd.DataFrame]:
        """
        清洗分红送配数据
        :param raw_df: 原始数据DataFrame
        :param stock_code: 股票代码
        :param year: 年份
        :return: 清洗后的数据DataFrame或None
        """
        self.func_name = "_clean_xrxd_data"
        if raw_df.empty:
            logger.warning(f"[{__name__}.{self.func_name}] 原始数据为空")
            return None

        df = raw_df.copy()

        # 添加股票代码和年份
        df["std_stock_code"] = stock_code
        df["xrxd_year"] = year

        # 重命名列名以匹配数据库表结构
        df.rename(columns={
            "dividPreNoticeDate": "xrxd_pre_notice_date",
            "dividAgmPumDate": "xrxd_agm_pum_date",
            "dividPlanAnnounceDate": "xrxd_plan_announce_date",
            "dividPlanDate": "xrxd_plan_date",
            "dividRegistDate": "xrxd_regist_date",
            "dividOperateDate": "xrxd_operate_date",
            "dividPayDate": "xrxd_pay_date",
            "dividStockMarketDate": "xrxd_stock_market_date",
            "dividCashPsBeforeTax": "xrxd_cash_ps_before_tax",
            "dividCashPsAfterTax": "xrxd_cash_ps_after_tax",
            "dividStocksPs": "xrxd_stocks_ps",
            "dividCashStock": "xrxd_cash_stock",
            "dividReserveToStockPs": "xrxd_reserve_to_stock_ps"
        }, inplace=True)

        # 定义日期列
        date_cols = [
            "xrxd_pre_notice_date", "xrxd_agm_pum_date", "xrxd_plan_announce_date",
            "xrxd_plan_date", "xrxd_regist_date", "xrxd_operate_date",
            "xrxd_pay_date", "xrxd_stock_market_date"
        ]

        # 清洗日期列：将空字符串、无效日期转换为None
        for col in date_cols:
            if col in df.columns:
                # 先将空字符串转换为NaN
                df[col] = df[col].replace('', pd.NA)
                # 尝试转换为日期，无效值转为NaT
                df[col] = pd.to_datetime(df[col], errors='coerce')
                # 将NaT转换为None（用于MySQL）
                df[col] = df[col].where(df[col].notna(), None)

        # 定义数值列
        numeric_cols = [
            "xrxd_cash_ps_before_tax", "xrxd_cash_ps_after_tax",
            "xrxd_stocks_ps", "xrxd_reserve_to_stock_ps"
        ]

        # 清洗数值列：将空字符串、无效数值转换为None
        for col in numeric_cols:
            if col in df.columns:
                # 先将空字符串转换为NaN
                df[col] = df[col].replace('', pd.NA)
                # 转换为数值，无效值转为NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # 将NaN转换为None（用于MySQL）
                df[col] = df[col].where(df[col].notna(), None)

        # 清洗字符串列：将空字符串转换为None，截断过长字符串
        string_cols = [("xrxd_cash_stock", 200)]  # (列名, 最大长度)
        for col, max_len in string_cols:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: None if pd.isna(x) or str(x).strip() == '' else str(x)[:max_len]
                )

        return df

    def _fetch_xrxd_task(self, year: int, stock_code: str):
        """
        处理单个分红送配数据下载任务
        :param year: 年份
        :param stock_code: 股票代码
        """
        self.func_name = "_fetch_xrxd_task"
        logger.debug(f"[{__name__}.{self.func_name}] 处理: {year} | {stock_code}")

        # ========== 1. 下载数据 ==========
        logger.debug(f"[{__name__}.{self.func_name}] 下载: {stock_code} {year}")
        raw_df = self._download_raw_xrxd_data(stock_code, year)
        
        if raw_df is None or raw_df.empty:
            logger.debug(f"[{__name__}.{self.func_name}] 无数据，跳过: {stock_code} {year}")
            return

        # ========== 2. 清洗数据 ==========
        df = self._clean_xrxd_data(raw_df, stock_code, year)
        if df is None or df.empty:
            logger.debug(f"[{__name__}.{self.func_name}] 清洗后数据为空，跳过: {stock_code} {year}")
            return

        # ========== 3. 保存数据 ==========
        xrxd_manager = XrxdManager(self.db_conn)
        ok = xrxd_manager.save_xrxd_data(df)
        if not ok:
            raise Exception(f"数据保存失败: {stock_code} {year}")

        logger.debug(f"[{__name__}.{self.func_name}] 完成: {stock_code} {year}")

    def _get_downloading_task(self) -> Optional[Tuple[int, str]]:
        """
        获取当前正在下载的任务（如果有）
        :return: (year, stock_code) 或 None（无正在下载的任务）
        """
        try:
            result = self.progress_manager.get_xrxd_progress()
            if result:
                year, stock_code, _, _, _ = result
                if year > 0 and stock_code:
                    return (year, stock_code)
            return None
        except Exception as e:
            logger.error(f"[{__name__}._get_downloading_task] 获取下载任务失败: {str(e)}")
            return None

    def _save_download_progress(self, year: int, stock_code: str):
        """
        保存下载进度
        :param year: 年份
        :param stock_code: 股票代码
        """
        try:
            self.progress_manager.set_xrxd_progress(year, stock_code)
        except Exception as e:
            logger.error(f"[{__name__}._save_download_progress] 保存进度失败: {str(e)}")

    # -------------------------------------------------------------------------
    # 【类内唯一对外入口】主下载流程
    # -------------------------------------------------------------------------
    def get_download_status(self) -> str:
        """
        获取当前下载状态
        :return: 下载状态描述
        """
        # 步骤1：检查任务是否存在
        task_exists = self.progress_manager.task_exists('xrxd')
        
        if not task_exists:
            return "下载未开始"
        
        # 步骤2：检查指针是否为空
        pointer_empty = self.progress_manager.is_download_pointer_empty('xrxd')
        
        if pointer_empty:
            return "下载已完成"
        else:
            # 步骤3：获取当前任务
            task = self._get_downloading_task()
            if task:
                year, stock_code = task
                return f"下载进行中: {year} {stock_code}"
            return "下载进行中"


    def download_xrxd(self, start_year: int, end_year: int) -> bool:
        """
        类内核心下载接口：无列表、动态查找、断点续传
        :return: True 表示全部下载完成，False 表示未完成
        """
        self.func_name = "download_xrxd"
        logger.debug(f"[{__name__}.{self.func_name}] 启动下载: {start_year}-{end_year}")

        # 步骤0：检查下载状态
        status = self.get_download_status()
        if status == "下载已完成":
            logger.info(f"[{__name__}.{self.func_name}] 下载已完成，无需重复执行")
            return True
        elif status == "下载进行中":
            logger.info(f"[{__name__}.{self.func_name}] 下载正在进行，将从断点恢复")
        else:  # 下载未开始
            logger.info(f"[{__name__}.{self.func_name}] 下载未开始，将从头开始")

        # 步骤1：优先恢复中断的下载任务
        next_task = self._get_downloading_task()
        logger.debug(f"[{__name__}.{self.func_name}] 启动前：当前下载任务: {next_task}")

        # 步骤2：无中断任务则获取第一个待下载任务
        if not next_task:
            next_task = self._get_next_task(start_year, end_year, None, None)
        logger.debug(f"[{__name__}.{self.func_name}] 启动后：第一个下载任务: {next_task}")

        # 核心循环：有下一个任务则执行下载
        while next_task:
            year, stock_code = next_task
            try:
                # 先更新下载指针，确保中断后能从正确位置恢复
                self._save_download_progress(year, stock_code)
                # 执行下载
                self._fetch_xrxd_task(year, stock_code)
                # 获取下一个任务
                next_task = self._get_next_task(start_year, end_year, year, stock_code)
                # 记录进度
                logger.info(f"完成任务: {year} {stock_code}")
            except Exception as e:
                logger.error(f"[{__name__}.{self.func_name}] 下载失败: {year} {stock_code}, {str(e)}")
                raise  # 异常向上抛出

        # 下载完成，清空下载指针
        self.progress_manager.clear_download_pointer('xrxd')
        logger.debug(f"[{__name__}.{self.func_name}] 全部下载完成，已清空下载指针")
        return True

    def download_xrxd_from_scratch(self, start_year: int, end_year: int) -> bool:
        """
        从头开始下载（删除之前的下载记录）
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（包含）
        :return: True 表示全部下载完成，False 表示未完成
        """
        self.func_name = "download_xrxd_from_scratch"
        logger.info(f"[{__name__}.{self.func_name}] 开始从头下载: {start_year}-{end_year}")
        
        # 步骤1：删除任务记录
        self.progress_manager.delete_task('xrxd')
        logger.debug(f"[{__name__}.{self.func_name}] 已删除任务记录")
        
        # 步骤2：调用普通下载方法
        return self.download_xrxd(start_year, end_year)

# ===================== 全局唯一对外接口函数 =====================
def download_xrxd(db_conn, start_year: int, end_year: Optional[int] = None) -> bool:
    """
    【全局唯一对外接口】
    使用者只需调用此函数，无需关心内部类实现
    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（包含，默认当前年份）
    :return: True 表示全部下载完成，False 表示未完成
    """
    if end_year is None:
        end_year = datetime.now().year
    
    downloader = XrxdDownloader(db_conn)
    return downloader.download_xrxd(start_year, end_year)

def download_xrxd_from_scratch(db_conn, start_year: int, end_year: Optional[int] = None) -> bool:
    """
    【全局唯一对外接口】
    从头开始下载（清空之前的下载进度）
    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（包含，默认当前年份）
    :return: True 表示全部下载完成，False 表示未完成
    """
    if end_year is None:
        end_year = datetime.now().year
    
    downloader = XrxdDownloader(db_conn)
    return downloader.download_xrxd_from_scratch(start_year, end_year)
