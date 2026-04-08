# xrxd_downloader.py
from KitchenBase.download_enums import DlTaskType
from KitchenBase.download_enums import DlTaskStatus
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
    # 【核心】动态查找：下一个待下载区块（无列表、纯数据库驱动）
    #  当前排序规则：年份(旧→新) → 股票固定顺序
    # -------------------------------------------------------------------------
    def _get_next_block(
        self, 
        start_year: int, 
        end_year: int, 
        current_year: Optional[int] = None, 
        current_stock: Optional[str] = None
    ) -> Optional[Tuple[int, str]]:
        """
        仅推动区块指针向前，找到下一个待处理区块（不判断下载状态）
        
        区块概念：
        - 一个区块代表一个股票在一个年份的数据
        - 区块排序规则：先按年份升序，同一年内按stock_fixed_seq表顺序
        - 区块序号计算公式：(year - start_year) * 股票总数 + 股票在序列中的位置
        
        迭代规则：年份升序 → 股票固定顺序（stock_fixed_seq表）
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（包含）
        :param current_year: 当前年份（首次调用传None，从start_year开始）
        :param current_stock: 当前股票（首次调用传None，从第一个股票开始）
        :return: (next_year, next_stock) 或 None（无更多区块）
        """
        self.func_name = "_get_next_block"

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
                logger.warning(f"[{__name__}.{self.func_name}] 无数据: {stock_code} {year}")
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

    def _fetch_xrxd_block(self, year: int, stock_code: str):
        """
        处理单个分红送配数据下载区块
        
        区块概念：
        - 区块是一只股票在一个年份中的数据集合
        - 每个区块由 (年份, 股票代码) 唯一标识
        
        :param year: 年份
        :param stock_code: 股票代码
        """
        self.func_name = "_fetch_xrxd_block"
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

    def _get_downloading_block(self) -> Optional[Tuple[int, str]]:
        """
        获取当前正在下载的区块（如果有）
        
        区块概念：
        - 区块是一只股票在一个年份中的数据集合
        - 每个区块由 (年份, 股票代码) 唯一标识
        
        :return: (year, stock_code) 或 None（无正在下载的区块）
        """
        try:
            result = self.progress_manager.get_xrxd_dl_pointer()
            if result:
                year, stock_code, _, _, _ = result
                if year > 0 and stock_code:
                    return (year, stock_code)
            return None
        except Exception as e:
            logger.error(f"[{__name__}._get_downloading_block] 获取下载区块失败: {str(e)}")
            return None

    def _set_xrxd_dl_pointer(self, year: int, stock_code: str) -> bool:
        """
        设置当前正在下载的区块
        
        区块概念：
        - 区块是一只股票在一个年份中的数据集合
        - 每个区块由 (年份, 股票代码) 唯一标识
        
        :param year: 年份
        :param stock_code: 股票代码
        :return: 是否设置成功
        """
        try:
            result = self.progress_manager.set_xrxd_dl_pointer(year, stock_code)
            logger.debug(f"[{__name__}._set_xrxd_dl_pointer] 设置下载区块成功: {year} {stock_code}")
            return result
        except Exception as e:
            logger.error(f"[{__name__}._set_xrxd_dl_pointer] 设置下载区块失败: {str(e)}")
            return False

    def _get_download_status(self) -> DlTaskStatus:
        """
        获取当前下载状态
        :return: 下载状态
        """
        return self.progress_manager.get_task_status(DlTaskType.XRXD)
    
    def _set_download_status(self, status: DlTaskStatus):
        """
        设置当前下载状态
        :param status: 下载状态
        """
        self.progress_manager.set_task_status(DlTaskType.XRXD, status)




    def continue_download_xrxd(self, start_year: int, end_year: int) -> bool:
        """
        类内核心下载接口：无列表、动态查找、断点续传
        :return: True 表示全部下载完成，False 表示未完成
        """
        self.func_name = "continue_download_xrxd"
        logger.debug(f"[{__name__}.{self.func_name}] 启动下载: {start_year}-{end_year}")

        # 步骤0：检查下载状态
        status = self._get_download_status()
        if status == DlTaskStatus.COMPLETED:
            logger.info(f"[{__name__}.{self.func_name}] 下载已完成，无需重复执行")
            return True
        elif status == DlTaskStatus.IN_PROGRESS:
            logger.info(f"[{__name__}.{self.func_name}] 下载正在进行，将从断点恢复")
        else:  # 下载未开始
            logger.info(f"[{__name__}.{self.func_name}] 下载未开始，将从头开始")
            self.progress_manager.clear_download_pointer(DlTaskType.XRXD)
            self._set_download_status(DlTaskStatus.IN_PROGRESS)

        # 步骤1：计算总区块数
        total_blocks = dm.get_total_block_count(self.db_conn, DlTaskType.XRXD, start_year, end_year)
        logger.info(f"[{__name__}.{self.func_name}] 总区块数: {total_blocks} (年份范围: {start_year}-{end_year-1})")

        # 步骤3：优先恢复中断的下载区块
        next_block = self._get_downloading_block()
        logger.info(f"[{__name__}.{self.func_name}] 启动前：当前下载区块: {next_block}")

        # 步骤4：无中断任务则获取第一个待下载区块
        if not next_block:
            next_block = self._get_next_block(start_year, end_year, None, None)
        logger.info(f"[{__name__}.{self.func_name}] 启动后：第一个下载区块: {next_block}")

        # 核心循环：有下一个区块则执行下载
        while next_block:
            year, stock_code = next_block
            try:
                # 先更新下载指针，确保中断后能从正确位置恢复
                self._set_xrxd_dl_pointer(year, stock_code)
                # 执行下载
                self._fetch_xrxd_block(year, stock_code)
                # 获取下一个区块
                next_block = self._get_next_block(start_year, end_year, year, stock_code)
                # 记录进度
                logger.info(f"XRXD数据下载完成区块: {year} {stock_code}")
                
                # 输出下载进度（基于已完成的区块数）
                completed_block_count = dm.get_completed_block_count(self.db_conn, 
                                                                     DlTaskType.XRXD, 
                                                                     start_year, end_year, 
                                                                     year, stock_code)
                if completed_block_count is not None and total_blocks > 0:
                    progress_percent = (completed_block_count / total_blocks) * 100
                    logger.info(f"XRXD数据下载进度: {progress_percent:.2f}% ({completed_block_count}/{total_blocks})")
            except Exception as e:
                logger.error(f"[{__name__}.{self.func_name}] 下载失败: {year} {stock_code}, {str(e)}")
                raise  # 异常向上抛出

        # 下载完成，清空下载指针
        self.progress_manager.clear_download_pointer(DlTaskType.XRXD)
        logger.info(f"[{__name__}.{self.func_name}] 全部下载完成，已清空下载指针")
        return True

    def start_new_xrxd_download(self, start_year: int, end_year: int) -> bool:
        """
        从头开始下载（删除之前的下载记录）
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（包含）
        :return: True 表示全部下载完成，False 表示未完成
        """
        self.func_name = "start_new_xrxd_download"
        logger.info(f"[{__name__}.{self.func_name}] 开始从头下载: {start_year}-{end_year}")
        
        # 步骤1：删除任务记录
        #self.progress_manager.delete_task('xrxd')
        self._set_download_status(DlTaskStatus.NOT_STARTED)
        logger.debug(f"[{__name__}.{self.func_name}] 已删除任务记录")
        
        # 步骤2：调用普通下载方法
        return self.continue_download_xrxd(start_year, end_year)

# ===================== 全局唯一对外接口函数 =====================
def continue_download_xrxd(db_conn, start_year: int, end_year: Optional[int] = None) -> bool:
    """
    【全局唯一对外接口】继续下载分红送配数据（支持断点续传）
    
    功能说明：
    - 从上次中断的位置继续下载分红送配数据
    - 支持断点续传，自动恢复下载进度
    - 按照年份和股票代码的顺序下载数据
    - 自动处理下载过程中的异常
    
    下载流程：
    1. 检查下载状态（未开始、进行中、已完成）
    2. 计算总区块数
    3. 优先恢复中断的下载区块
    4. 按顺序下载所有区块
    5. 完成后清空下载指针
    
    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（包含，默认当前年份）
    :return: True 表示全部下载完成，False 表示未完成
    """
    if end_year is None:
        end_year = datetime.now().year
    
    downloader = XrxdDownloader(db_conn)
    return downloader.continue_download_xrxd(start_year, end_year)

def start_new_xrxd_download(db_conn, start_year: int, end_year: Optional[int] = None) -> bool:
    """
    【全局唯一对外接口】开始新的分红送配数据下载任务（清空之前的下载进度）
    
    功能说明：
    - 清空之前的下载进度记录
    - 从头开始下载指定年份范围的分红送配数据
    - 按照年份和股票代码的顺序下载数据
    - 自动处理下载过程中的异常
    
    下载流程：
    1. 删除之前的任务记录
    2. 调用继续下载方法开始新的下载任务
    3. 按照年份和股票代码的顺序下载所有区块
    4. 完成后清空下载指针
    
    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（包含，默认当前年份）
    :return: True 表示全部下载完成，False 表示未完成
    """
    if end_year is None:
        end_year = datetime.now().year
    
    downloader = XrxdDownloader(db_conn)
    return downloader.start_new_xrxd_download(start_year, end_year)
