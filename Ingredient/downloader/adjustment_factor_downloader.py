# adjustment_factor_downloader.py
from KitchenBase.download_enums import DlBlockStatus
from Ingredient.DataNest.dm_generic_block_status import GenericBlockStatusDM
from KitchenBase.download_enums import DlTaskType
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from KitchenBase.baostock_wrapper import query_adjust_factor
from Ingredient.DataNest import AdjustmentFactorManager, UnifiedDataManager as dm, GlobalDlCtrlBlockManager
from KitchenBase.download_enums import DlTaskStatus

# ===================== 全局配置 =====================
logger = get_logger(__name__)

# ===================== 下载器核心类 =====================
class AdjustmentFactorDownloader:
    def __init__(self, db_conn):
        """
        初始化下载器
        :param db_conn: 外部传入的数据库连接（使用者管理）
        """
        self.db_conn = db_conn
        self.func_name = ""
        self.progress_manager = GlobalDlCtrlBlockManager(db_conn)
        self.block_status_manager = GenericBlockStatusDM(db_conn)
        self.adj_factor_manager = AdjustmentFactorManager(db_conn)

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
        :param end_year: 结束年份（不包含）
        :return: 下一个年份或None
        """
        next_year = current_year + 1
        return next_year if next_year < end_year else None

    # -------------------------------------------------------------------------
    # 【核心】动态查找：下一个待下载区块（无列表、纯数据库驱动）
    #  当前排序规则：年份(旧→新) → 股票固定顺序
    # -------------------------------------------------------------------------
    def _get_first_block(self, start_year: int, end_year: int) -> Optional[Tuple[int, str]]:
        """
        获取第一个待处理区块
        
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :return: (first_year, first_stock) 或 None（无股票数据）
        """
        self.func_name = "_get_first_block"
        logger.debug(f"[{__name__}.{self.func_name}] 获取第一个区块: {start_year}-{end_year}")
        
        # 调用 _get_next_block 函数，传入 None 作为当前年份和股票，获取第一个区块
        return self._get_next_block(start_year, end_year, None, None)

    def _get_next_block(
        self, 
        start_year: int, 
        end_year: int, 
        current_year: Optional[int] = None, 
        current_stock: Optional[str] = None,
        loop: bool = False
    ) -> Optional[Tuple[int, str]]:
        """
        仅推动区块指针向前，找到下一个待处理区块（不判断下载状态）
        
        区块概念：
        - 一个区块代表一个股票在一个年份的数据
        - 区块排序规则：先按年份升序，同一年内按stock_fixed_seq表顺序
        - 区块序号计算公式：(year - start_year) * 股票总数 + 股票在序列中的位置
        
        迭代规则：年份升序 → 股票固定顺序（stock_fixed_seq表）
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :param current_year: 当前年份（首次调用传None，从start_year开始）
        :param current_stock: 当前股票（首次调用传None，从第一个股票开始）
        :param loop: 是否循环到第一个区块（当处于最后一个区块时）
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
                    # 无下一年份 → 检查是否需要循环
                    if loop:
                        # 循环到第一个区块
                        logger.debug(f"[{__name__}.{self.func_name}] 已到达最后一个区块，循环到第一个区块（年份范围：{start_year}-{end_year}）")
                        first_stock = self._get_next_stock(None)
                        if first_stock:
                            return (start_year, first_stock)
                        else:
                            logger.warning(f"[{__name__}.{self.func_name}] 无股票数据可用，无法循环")
                            return None
                    else:
                        # 迭代结束
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

    def _download_raw_adjustment_factor_data(self, stock_code: str, year: int) -> Optional[pd.DataFrame]:
        """
        从Baostock下载原始复权因子数据
        :param stock_code: 股票代码
        :param year: 年份
        :return: 原始数据DataFrame或None
        """
        self.func_name = "_download_raw_adjustment_factor_data"

        # 构建日期范围
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        
        rs = query_adjust_factor(
            code=stock_code,
            start_date=start_date,
            end_date=end_date
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

    def _clean_adjustment_factor_data(self, raw_df: pd.DataFrame, stock_code: str) -> Optional[pd.DataFrame]:
        """
        清洗复权因子数据
        :param raw_df: 原始数据DataFrame
        :param stock_code: 股票代码
        :return: 清洗后的数据DataFrame或None
        """
        self.func_name = "_clean_adjustment_factor_data"
        if raw_df.empty:
            logger.warning(f"[{__name__}.{self.func_name}] 原始数据为空")
            return None

        df = raw_df.copy()

        # 添加股票代码
        df["std_stock_code"] = stock_code

        # 重命名列名以匹配数据库表结构
        df.rename(columns={
            "dividOperateDate": "adjust_date",
            "foreAdjustFactor": "fore_adjust_factor",
            "backAdjustFactor": "back_adjust_factor",
            "adjustFactor": "adjust_factor"
        }, inplace=True)

        # 清洗日期列：将空字符串、无效日期转换为None
        if "adjust_date" in df.columns:
            # 先将空字符串转换为NaN
            df["adjust_date"] = df["adjust_date"].replace('', pd.NA)
            # 尝试转换为日期，无效值转为NaT
            df["adjust_date"] = pd.to_datetime(df["adjust_date"], errors='coerce')
            # 将NaT转换为None（用于MySQL）
            df["adjust_date"] = df["adjust_date"].where(df["adjust_date"].notna(), None)

        # 定义数值列
        numeric_cols = [
            "fore_adjust_factor", "back_adjust_factor", "adjust_factor"
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

        return df

    def _fetch_adjustment_factor_block(self, year: int, stock_code: str):
        """
        处理单个复权因子数据下载区块

        区块概念：
        - 区块是一只股票在一个年份中的数据集合
        - 每个区块由 (年份, 股票代码) 唯一标识

        :param year: 年份
        :param stock_code: 股票代码
        """
        self.func_name = "_fetch_adjustment_factor_block"
        logger.debug(f"[{__name__}.{self.func_name}] 处理: {year} | {stock_code}")

        # 步骤1：检查当区块是否已完成，已完成则直接返回
        block_status = self.adj_factor_manager.get_block_status(year,stock_code)
        if DlBlockStatus.COMPLETED == block_status:
            logger.debug(f"[{__name__}.{self.func_name}] {year} {stock_code} 区块已完成，跳过")
            return

        # 步骤2：下载原始复权因子数据
        logger.debug(f"[{__name__}.{self.func_name}] 下载: {stock_code} {year}")
        raw_df = self._download_raw_adjustment_factor_data(stock_code, year)

        if raw_df is None or raw_df.empty:
            logger.info(f"[{__name__}.{self.func_name}] 无数据，跳过: {stock_code} {year}")
            self.adj_factor_manager.update_block_status(year,stock_code, DlBlockStatus.ERROR)
            return

        # 步骤3：清洗复权因子数据
        df = self._clean_adjustment_factor_data(raw_df, stock_code)
        if df is None or df.empty:
            logger.info(f"[{__name__}.{self.func_name}] 清洗后数据为空，跳过: {stock_code} {year}")
            self.adj_factor_manager.update_block_status(year,stock_code, DlBlockStatus.ERROR)
            return

        # 步骤4：保存复权因子数据
        ok = self.adj_factor_manager.save_adjustment_factor_data(df)
        if not ok:
            logger.error(f"数据保存失败: {stock_code} {year}")
            self.adj_factor_manager.update_block_status(year,stock_code, DlBlockStatus.ERROR)
            return
        
        # 步骤5：更新区块状态为已完成
        self.adj_factor_manager.update_block_status(year,stock_code, DlBlockStatus.COMPLETED)
        
        logger.info(f"[{__name__}.{self.func_name}] 完成: {stock_code} {year}")

    def _get_dl_pointer(self) -> Optional[Tuple[int, str]]:
        """
        获取当前正在下载的区块（如果有）
        
        区块概念：
        - 区块是一只股票在一个年份中的数据集合
        - 每个区块由 (年份, 股票代码) 唯一标识
        
        :return: (year, stock_code) 或 None（无正在下载的区块）
        """
        try:
            result = self.progress_manager.get_adj_fct_dl_pointer()
            if result:
                year, stock_code = result
                if year > 0 and stock_code:
                    return (year, stock_code)
            return None
        except Exception as e:
            logger.error(f"[{__name__}._get_dl_pointer] 获取下载区块失败: {str(e)}")
            return None

    def _set_dl_pointer(self, year: int, stock_code: str):
        """
        保存下载进度
        :param year: 年份
        :param stock_code: 股票代码
        """
        try:
            self.progress_manager.set_adj_fct_dl_pointer(year, stock_code)
        except Exception as e:
            logger.error(f"[{__name__}._save_download_progress] 保存进度失败: {str(e)}")


    def _get_download_status(self) -> DlTaskStatus:
        """
        获取当前下载状态
        :return: 下载状态
        """
        return self.progress_manager.get_task_status(DlTaskType.ADJUSTMENT_FACTOR)

    def _set_download_status(self, status: DlTaskStatus):
        """
        设置当前下载状态
        :param status: 下载状态
        """ 
        self.progress_manager.set_task_status(DlTaskType.ADJUSTMENT_FACTOR, status)


    def _get_attempted_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取当前下载已尝试的区块数

        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :return: 已尝试的区块数
        """
        self.func_name = "_get_attempted_block_count"

        try:
            # 直接调用 AdjustmentFactorManager 的 get_attempted_block_count 方法
            attempted_count = self.adj_factor_manager.get_attempted_block_count(start_year, end_year)
            logger.debug(f"[{__name__}.{self.func_name}] 已尝试区块数: {attempted_count}")
            return attempted_count
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询失败: {str(e)}")
            return 0
    
    def _get_total_block_count(self, start_year: int, end_year: int) -> int:
        """
        获取当前下载总区块数
        
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :return: 总区块数
        """
        self.func_name = "_get_total_block_count"
        
        try:
            # 直接调用 AdjustmentFactorManager 的 get_total_block_count 方法
            total_count = self.adj_factor_manager.get_total_block_count(start_year, end_year)
            logger.debug(f"[{__name__}.{self.func_name}] 总区块数: {total_count}")
            return total_count
        except Exception as e:
            logger.error(f"[{__name__}.{self.func_name}] 查询失败: {str(e)}")
            return 0


    def continue_download_adjustment_factor(self, start_year: int, end_year: int) -> bool:
        """
        类内核心下载接口：无列表、动态查找、断点续传
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :return: True 表示全部下载完成，False 表示未完成
        """
        self.func_name = "continue_download_adjustment_factor"
        
        # 检查参数有效性
        if start_year >= end_year:
            raise RuntimeError(f"Invalid year range: start_year ({start_year}) must be less than end_year ({end_year})")
        
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
            self._set_download_status(DlTaskStatus.IN_PROGRESS)

        # 步骤1：计算总区块数和已完成区块数
        total_blocks = self._get_total_block_count(start_year, end_year)
        attempted_block_count = self._get_attempted_block_count(start_year, end_year)
        logger.info(f"[{__name__}.{self.func_name}] 已尝试区块数: {attempted_block_count}")
        logger.info(f"[{__name__}.{self.func_name}] 总区块数: {total_blocks} (年份范围: {start_year}-{end_year-1})")

        # 步骤2：优先恢复中断的下载区块
        next_block = self._get_dl_pointer()
        logger.info(f"[{__name__}.{self.func_name}] 启动前：当前下载区块: {next_block}")

        # 步骤3：无中断任务则获取第一个待下载区块
        if not next_block or not self.adj_factor_manager.is_dl_pointer_valid(next_block, start_year, end_year):
            next_block = self._get_first_block(start_year, end_year)
            logger.info(f"[{__name__}.{self.func_name}] 第一个待下载区块: {next_block}")
        logger.info(f"[{__name__}.{self.func_name}] 启动后：第一个下载区块: {next_block}")

        # 核心循环：有下一个区块则执行下载，否则退出循环
        while next_block and attempted_block_count < total_blocks:
            year, stock_code = next_block
            try:
                # 先更新下载指针，确保中断后能从正确位置恢复
                self._set_dl_pointer(year, stock_code)
                # 执行下载
                self._fetch_adjustment_factor_block(year, stock_code)

                # 记录进度
                logger.info(f"[复权因子数据] 区块{year} {stock_code} 下载完成")

                # 输出下载进度（基于已尝试区块数）
                attempted_block_count = self._get_attempted_block_count(start_year, end_year)
                if  total_blocks > 0:
                    progress_percent = (attempted_block_count / total_blocks) * 100
                    logger.info(f"复权因子数据下载进度: {progress_percent:.2f}% ({attempted_block_count}/{total_blocks})")

                # 获取下一个区块
                next_block = self._get_next_block(start_year, end_year, year, stock_code, loop=True)
            except ConnectionRefusedError as e:
                # 网络连接异常，记录错误日志，退出循环体，中止整个下载任务
                logger.error(f"[{__name__}.{self.func_name}] 拒绝连接，下载失败 - {type(e).__name__}: {str(e)}")
                # 虽然退出循环体，但保持下载状态为IN_PROGRESS，方便后续恢复下载
                return False
            except Exception as e:
                logger.error(f"[{__name__}.{self.func_name}] 下载失败: {year} {stock_code}, {str(e)}")
                return False

        if attempted_block_count >= total_blocks:
            self._set_download_status(DlTaskStatus.COMPLETED)
            self.progress_manager.clear_dl_pointer(DlTaskType.ADJUSTMENT_FACTOR)
            logger.info(f"[{__name__}.{self.func_name}] 全部下载完成，已清空下载指针")
            return True
        
        return False

    def start_new_adjustment_factor_download(self, start_year: int, end_year: int) -> bool:
        """
        从头开始下载（删除之前的下载记录）
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :return: True 表示全部下载完成，False 表示未完成
        """
        self.func_name = "start_new_adjustment_factor_download"
        
        # 检查参数有效性
        if start_year >= end_year:
            raise RuntimeError(f"Invalid year range: start_year ({start_year}) must be less than end_year ({end_year})")
        
        logger.info(f"[{__name__}.{self.func_name}] 开始从头下载: {start_year}-{end_year}")

        # 步骤1：删除任务记录
        #self.progress_manager.delete_task('adjustment_factor')
        self.progress_manager.set_task_status(DlTaskType.ADJUSTMENT_FACTOR, DlTaskStatus.NOT_STARTED)
        logger.debug(f"[{__name__}.{self.func_name}] 已删除任务记录")
        
        # 步骤2：调用普通下载方法
        return self.continue_download_adjustment_factor(start_year, end_year)

# ===================== 全局唯一对外接口函数 =====================
def continue_download_adjustment_factor(db_conn, start_year: int, end_year: Optional[int] = None) -> bool:
    """
    【全局唯一对外接口】继续下载复权因子数据（支持断点续传）
    
    功能说明：
    - 从上次中断的位置继续下载复权因子数据
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
    :param end_year: 结束年份（不包含，默认当前年份+1）
    :return: True 表示全部下载完成，False 表示未完成
    """
    if end_year is None:
        end_year = datetime.now().year + 1
    
    # 检查参数有效性
    if start_year >= end_year:
        raise RuntimeError(f"Invalid year range: start_year ({start_year}) must be less than end_year ({end_year})")
    
    downloader = AdjustmentFactorDownloader(db_conn)
    return downloader.continue_download_adjustment_factor(start_year, end_year)

def start_new_adjustment_factor_download(db_conn, start_year: int, end_year: Optional[int] = None) -> bool:
    """
    【全局唯一对外接口】开始新的复权因子数据下载任务（清空之前的下载进度）
    
    功能说明：
    - 清空之前的下载进度记录
    - 从头开始下载指定年份范围的复权因子数据
    - 按照年份和股票代码的顺序下载数据
    - 自动处理下载过程中的异常
    
    下载流程：
    1. 删除之前的任务记录
    2. 调用继续下载方法开始新的下载任务
    3. 按照年份和股票代码的顺序下载所有区块
    4. 完成后清空下载指针
    
    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（不包含，默认当前年份+1）
    :return: True 表示全部下载完成，False 表示未完成
    """
    if end_year is None:
        end_year = datetime.now().year + 1
    
    # 检查参数有效性
    if start_year >= end_year:
        raise RuntimeError(f"Invalid year range: start_year ({start_year}) must be less than end_year ({end_year})")
    
    downloader = AdjustmentFactorDownloader(db_conn)
    return downloader.start_new_adjustment_factor_download(start_year, end_year)
