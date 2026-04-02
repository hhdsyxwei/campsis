# kline_unified_downloader.py
import pandas as pd
from datetime import datetime
from typing import Optional, Tuple
from KitchenBase.logger_config import get_logger
from KitchenBase.baostock_wrapper import query_history_k_data_plus
from KitchenBase.baostock_wrapper import BaostockWrapper as bsw
from Ingredient.DataNest import UnifiedDataManager as dm
from KitchenBase.stock_enums import KLinePeriod

# ===================== 全局配置 =====================
logger = get_logger(__name__)
BLOCK_PENDING = "pending"    # 未完成
BLOCK_COMPLETED = "completed"# 已完成

# ===================== 下载器核心类 =====================
class KLineDownloader:
    def __init__(self, db_conn):
        """
        初始化下载器
        :param db_conn: 外部传入的数据库连接（使用者管理）
        """
        self.db_conn = db_conn
        self.func_name = ""

    def _calc_total_blocks(self, start_year: int, end_year: int, time_frame: KLinePeriod) -> int:
        """
        内部函数：计算指定时间范围和周期下需要下载的block总数
        计算逻辑：季度总数 × 股票总数 = 总区块数
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :param time_frame: K线周期（单个周期，非列表）
        :return: 需要下载的区块总数
        """
        self.func_name = "_calc_total_blocks"
        
        # 步骤1：统计指定时间范围内的季度总数
        quarter_count = self._count_quarters_in_range(start_year, end_year)
        
        # 步骤2：统计stock_fixed_seq表中的股票总数
        stock_count = dm.count_stocks_in_fixed_seq(self.db_conn)
        
        # 步骤3：计算总区块数（季度数 × 股票数，单个时间周期）
        total_blocks = quarter_count * stock_count
        
        logger.debug(
            f"[{__name__}.{self.func_name}] 统计结果："
            f"年份范围[{start_year}-{end_year}) | 季度数={quarter_count} "
            f"| 股票数={stock_count} | 周期={time_frame.value} | 总区块数={total_blocks}"
        )
        return total_blocks

    def _count_quarters_in_range(self, start_year: int, end_year: int) -> int:
        """
        内部辅助函数：计算[start_year, end_year)范围内的季度总数
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :return: 季度总数
        """
        self.func_name = "_count_quarters_in_range"
        
        if start_year >= end_year:
            logger.warning(f"[{__name__}.{self.func_name}] 起始年份{start_year} >= 结束年份{end_year}，季度数为0")
            return 0
        
        # 总季度数 = (结束年份 - 起始年份) × 4
        total_quarters = (end_year - start_year) * 4
        
        logger.debug(
            f"[{__name__}.{self.func_name}] 年份范围[{start_year}-{end_year}) 季度总数：{total_quarters}"
        )
        return total_quarters

    # -------------------------------------------------------------------------
    # 工具方法：计算指定季度的下一个季度标识
    # -------------------------------------------------------------------------
    def _get_next_quarter(self, start_year: int, end_year: int, quarter: str) -> str:
        """
        获取指定季度的下一个季度

        Args:
            start_year: 起始年份（包含）
            end_year: 结束年份（不包含）
            quarter: 当前季度，格式如 '2024-Q1'

        Returns:
            下一个季度字符串，如果已经是最后一个季度则返回None
        """
        self.func_name = "_get_next_quarter"

        # 解析当前季度
        year_str, q_str = quarter.split('-Q')
        current_year = int(year_str)
        current_q = int(q_str)

        # 计算下一个季度
        next_year = current_year
        next_q = current_q + 1

        # 如果当前季度是Q4，则下一年Q1
        if next_q > 4:
            next_year += 1
            next_q = 1

        # 检查是否超出范围
        if next_year >= end_year:
            return None

        return f"{next_year}-Q{next_q}"


    # -------------------------------------------------------------------------
    # 工具方法：季度 ↔ 日期转换
    # -------------------------------------------------------------------------
    def _quarter_to_date_range(self, quarter: str) -> Tuple[str, str]:
        """季度转起止日期"""
        self.func_name = "_quarter_to_date_range"
        year, q = quarter.split("-Q")
        q = int(q)
        mapping = {
            1: (f"{year}-01-01", f"{year}-03-31"),
            2: (f"{year}-04-01", f"{year}-06-30"),
            3: (f"{year}-07-01", f"{year}-09-30"),
            4: (f"{year}-10-01", f"{year}-12-31"),
        }
        if q not in mapping:
            raise ValueError(f"[{__name__}.{self.func_name}] 无效季度: {quarter}")
        return mapping[q]

    # -------------------------------------------------------------------------
    # 核心规则：股票上市/退市时间校验
    # -------------------------------------------------------------------------
    def _is_time_range_overlap_with_listing_period(
        self, std_stock_code: str, start_date: str, end_date: str
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        self.func_name = "_is_time_range_overlap_with_listing_period"
        listing_date, delist_date = dm.get_stock_listing_date(self.db_conn, std_stock_code)

        # 无上市日期直接跳过
        if not listing_date:
            logger.debug(f"[{__name__}.{self.func_name}] {std_stock_code} 无上市日期，跳过")
            return False, None, None

        # 日期转换
        req_s = datetime.strptime(start_date, "%Y-%m-%d")
        req_e = datetime.strptime(end_date, "%Y-%m-%d")
        list_dt = datetime.strptime(listing_date, "%Y-%m-%d")
        delist_dt = datetime.strptime(delist_date, "%Y-%m-%d") if delist_date else None

        # 无交集判断
        if delist_dt and delist_dt < req_s:
            return False, None, None
        if list_dt > req_e:
            return False, None, None

        # 计算实际下载区间
        real_s = max(list_dt, req_s).strftime("%Y-%m-%d")
        real_e = min(delist_dt, req_e).strftime("%Y-%m-%d") if delist_dt else req_e.strftime("%Y-%m-%d")
        return True, real_s, real_e

    # -------------------------------------------------------------------------
    # 数据清洗
    # -------------------------------------------------------------------------
    def _clean_kline_data(self, raw_data, time_frame: KLinePeriod) -> pd.DataFrame:
        self.func_name = "_clean_kline_data"
        if raw_data.empty:
            logger.warning(f"[{__name__}.{self.func_name}] 原始数据为空")
            return pd.DataFrame()

        df = raw_data.copy()
        df.rename(columns={
            "date": "timestamp",
            "open": "open_price",
            "high": "high_price",
            "low": "low_price",
            "close": "close_price",
            "volume": "volume",
            "amount": "turnover"
        }, inplace=True)

        df["time_frame"] = time_frame.value
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        
        # 转换数值列
        numeric_cols = ["open_price", "high_price", "low_price", "close_price", "volume", "turnover"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        
        # 处理数值列的NaN
        # 价格相关列：保留NaN（使用可空浮点类型）
        price_cols = ["open_price", "high_price", "low_price", "close_price", "turnover"]
        for col in price_cols:
            df[col] = df[col].astype("Float64")
        
        # 成交量：NaN填充为0
        df["volume"] = df["volume"].fillna(0).astype("Int64")
        
        df = df.dropna(subset=["timestamp"])
        return df

    def _get_downloading_block(self) -> Optional[Tuple[str, str, KLinePeriod]]:
        """
        获取当前正在下载的区块（如果有）
        :return: (quarter, std_stock_code, time_frame) 或 None（无正在下载的区块）
        """
        return dm.get_downloading_block(self.db_conn)

    # -------------------------------------------------------------------------
    # 【核心】动态查找：下一个待下载区块（无列表、纯数据库驱动）
    #  当前排序规则：季度(旧→新) → 股票固定顺序
    #  将来可能增加time_frame维度，或调整排序规则（如季度内先按股票代码升序）
    # -------------------------------------------------------------------------
    def _get_next_block(
        self, 
        start_year: int, 
        end_year: int, 
        current_quarter: Optional[str] = None, 
        current_stock: Optional[str] = None,
        time_frame: KLinePeriod = KLinePeriod.MIN_5
    ) -> Optional[Tuple[str, str, KLinePeriod]]:
        """
        仅推动区块指针向前，找到下一个待处理区块（不判断下载状态）
        迭代规则：季度升序 → 股票固定顺序（stock_fixed_seq表）
        :param start_year: 起始年份（包含）
        :param end_year: 结束年份（不包含）
        :param current_quarter: 当前季度（首次调用传None，从start_year-Q1开始）
        :param current_stock: 当前股票（首次调用传None，从第一个股票开始）
        :param time_frame: K线周期（仅占位，兼容原有参数结构）
        :return: (next_quarter, next_stock, time_frame) 或 None（无更多区块）
        """
        self.func_name = "_get_next_block"

        # ========== 步骤1：初始化起始季度（首次调用） ==========
        if not current_quarter:
            current_quarter = f"{start_year}-Q1"

        # ========== 步骤2：处理「同季度内的股票迭代」 ==========
        if current_stock:
            # 获取当前股票的下一个股票（按固定顺序）
            next_stock = dm.next_fixed_stock(self.db_conn, current_stock)
            if next_stock:
                # 同季度有下一个股票 → 直接返回
                logger.debug(f"[{__name__}.{self.func_name}] 同季度下一个股票: {current_quarter} -> {next_stock}")
                return (current_quarter, next_stock, time_frame)
            else:
                # 当前季度股票已遍历完 → 获取下一个季度
                next_quarter = self._get_next_quarter(start_year, end_year, current_quarter)
                if not next_quarter:
                    # 无下一季度 → 迭代结束
                    logger.debug(f"[{__name__}.{self.func_name}] 无更多区块（季度范围：{start_year}-{end_year}）")
                    return None
                # 切换到下一季度，重置为第一个股票
                current_quarter = next_quarter
                current_stock = None

        # ========== 步骤3：获取当前季度的第一个股票 ==========
        first_stock = dm.next_fixed_stock(self.db_conn, None)
        if not first_stock:
            logger.warning(f"[{__name__}.{self.func_name}] 无股票数据可用")
            return None

        logger.debug(f"[{__name__}.{self.func_name}] 下一个区块: {current_quarter} -> {first_stock}")
        return (current_quarter, first_stock, time_frame)

    # -------------------------------------------------------------------------
    # 最小下载单元：下载单个区块
    # -------------------------------------------------------------------------
    def _fetch_kline_block(self, quarter: str, std_stock_code: str, time_frame: KLinePeriod):
        self.func_name = "_fetch_kline_block"
        logger.debug(f"[{__name__}.{self.func_name}] 处理: {quarter} | {std_stock_code} | {time_frame}")

        # ========== 1. 参数校验 ==========
        if not isinstance(quarter, str) or "-Q" not in quarter:
            raise ValueError(f"无效季度: {quarter}")
        if not std_stock_code:
            raise ValueError("股票代码不能为空")

        # ========== 2. 检查是否已完成 ==========
        status = dm.get_kline_block_status(self.db_conn, quarter, std_stock_code, time_frame)
        if status == BLOCK_COMPLETED:
            logger.debug(f"[{__name__}.{self.func_name}] 已完成，跳过: {std_stock_code} {quarter}")
            return

        # ========== 3. 上市时间校验 ==========
        s_date, e_date = self._quarter_to_date_range(quarter)
        is_ok, real_s, real_e = self._is_time_range_overlap_with_listing_period(std_stock_code, s_date, e_date)
        if not is_ok:
            dm.update_kline_block_status(self.db_conn, quarter, std_stock_code, time_frame, BLOCK_COMPLETED)
            logger.debug(f"[{__name__}.{self.func_name}] 无有效数据，标记完成: {std_stock_code} {quarter}")
            return

        # ========== 4. 下载数据（假定已登录baostock） ==========
        logger.debug(f"[{__name__}.{self.func_name}] 下载: {std_stock_code} {real_s} ~ {real_e}")
        freq = bsw.convert_kline_period_to_baostock_freq(time_frame)
        res = query_history_k_data_plus(
            code=std_stock_code,
            fields="date,open,high,low,close,volume,amount",
            start_date=real_s,
            end_date=real_e,
            frequency=freq,
            adjustflag="3"
        )

        # 网络/服务异常直接抛出
        if res.error_code != "0":
            raise Exception(f"baostock下载失败 {std_stock_code} {quarter}: {res.error_msg}")

        # ========== 5. 清洗数据 ==========
        df = self._clean_kline_data(res.get_data(), time_frame)

        # ========== 6. 保存数据 ==========
        if not df.empty:
            ok = dm.save_kline_data_unified(
                self.db_conn, std_stock_code, df
            )
            if not ok:
                raise Exception(f"数据保存失败: {std_stock_code} {quarter}")

        # ========== 7. 更新状态为完成 ==========
        dm.update_kline_block_status(self.db_conn, quarter, std_stock_code, time_frame, BLOCK_COMPLETED)
        logger.debug(f"[{__name__}.{self.func_name}] 完成: {std_stock_code} {quarter}")

    # -------------------------------------------------------------------------
    # 【类内唯一对外入口】主下载流程
    # -------------------------------------------------------------------------
    def download_kline(self, start_year: int, end_year: int, time_frame: KLinePeriod):
        """
        类内核心下载接口：无列表、动态查找、断点续传
        """
        self.func_name = "download_kline"
        logger.debug(f"[{__name__}.{self.func_name}] 启动下载: {start_year}-{end_year} {time_frame.value}")

        # 预先计算总区块数（仅计算一次）
        block_total = self._calc_total_blocks(start_year, end_year, time_frame)

        # 步骤1：优先恢复中断的下载区块
        next_block = self._get_downloading_block()
        logger.debug(f"[{__name__}.{self.func_name}] 启动前：当前下载区块: {next_block}")

        # 步骤2：无中断区块则获取第一个待下载区块
        if not next_block:
            next_block = self._get_next_block(start_year, end_year, None, None, time_frame)
        logger.debug(f"[{__name__}.{self.func_name}] 启动后：第一个下载区块: {next_block}")

        # 核心循环：有下一个区块则执行下载
        while next_block:
            quarter, std_stock_code, time_frame = next_block
            try:
                # 先更新下载指针，确保中断后能从正确位置恢复
                dm.set_downloading_block(self.db_conn, std_stock_code, time_frame, quarter)
                # 执行下载
                self._fetch_kline_block(quarter, std_stock_code, time_frame)
                # 获取下一个区块
                next_block = self._get_next_block(start_year, end_year, quarter, std_stock_code, time_frame)
                # 记录进度
                completed_blocks = dm.get_completed_block_total_count(self.db_conn, start_year, end_year, time_frame.value)
                if block_total > 0:
                    progress = completed_blocks / block_total * 100
                else:
                    progress = 0.0
                logger.info(f"已下载区块总数：{completed_blocks}/{block_total}({progress:.2f}%) | 当前区块: {quarter} {std_stock_code} {time_frame.value}")
            except Exception as e:
                logger.error(f"[{__name__}.{self.func_name}] 下载失败: {quarter} {std_stock_code}, {str(e)}")
                raise  # 异常向上抛出

        logger.debug(f"[{__name__}.{self.func_name}] 全部下载完成")

# ===================== 全局唯一对外接口函数 =====================
def download_kline(db_conn, start_year: int, end_year: int, time_frame: KLinePeriod):
    """
    【全局唯一对外接口】
    使用者只需调用此函数，无需关心内部类实现
    :param db_conn: 使用者创建的数据库连接
    :param start_year: 起始年份（包含）
    :param end_year: 结束年份（不包含）
    :param time_frame: K线周期枚举
    """
    downloader = KLineDownloader(db_conn)
    downloader.download_kline(start_year, end_year, time_frame)