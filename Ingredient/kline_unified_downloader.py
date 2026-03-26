# kline_downloader.py
import pandas as pd
from datetime import datetime
from KitchenBase.logger_config import get_logger
from KitchenBase.baostock_wrapper import query_history_k_data_plus
from KitchenBase.baostock_wrapper import BaostockWrapper as bsw
from Ingredient.data_manager import DataManager as dm
from Ingredient.data_manager import get_existing_stock_codes_set
from KitchenBase.stock_enums import KLinePeriod, AdjustType, MarketType, DataSource

logger = get_logger(__name__)

class KLineDownloader:
    def __init__(self, db_conn):
        """
        初始化K线下载器
        
        Args:
            db_conn: 数据库连接句柄
        """
        func_name = "KLineDownloader.__init__"
        logger.info(f"[{__name__}.{func_name}] 初始化K线下载器")
        self.db_conn = db_conn

    def _generate_quarters(self, start_year: int, end_year: int):
        """
        生成指定年份范围内的所有季度列表
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            
        Returns:
            list: 季度列表，格式如 ['2024-Q1', '2024-Q2', ...]
        """
        func_name = "_generate_quarters"
        logger.debug(f"[{__name__}.{func_name}] 生成 {start_year}-{end_year-1} 年份范围内的季度列表")
        
        quarters = []
        for year in range(start_year, end_year):
            for q in range(1, 5):
                quarters.append(f"{year}-Q{q}")
        
        logger.debug(f"[{__name__}.{func_name}] 生成了 {len(quarters)} 个季度")
        return quarters

    def download_kline(self, start_year: int, end_year: int, time_frame: KLinePeriod):
        """
        下载K线数据的主接口
        
        Args:
            start_year: 开始年份（包含）
            end_year: 结束年份（不包含）
            time_frame: 时间周期，使用KLinePeriod枚举类型
        """
        func_name = "download_kline"
        logger.info(f"[{__name__}.{func_name}] 开始下载K线数据，时间范围: {start_year}-{end_year-1}，时间周期: {time_frame.value}")
        
        # 验证时间周期参数
        valid_time_frames = [
            KLinePeriod.MIN_1,
            KLinePeriod.MIN_5,
            KLinePeriod.MIN_15,
            KLinePeriod.MIN_30,
            KLinePeriod.MIN_60,
            KLinePeriod.DAILY,
            KLinePeriod.WEEKLY,
            KLinePeriod.MONTHLY
        ]
        if time_frame not in valid_time_frames:
            raise ValueError(f"无效的时间周期: {time_frame.value}，支持的时间周期: {[tf.value for tf in valid_time_frames]}")
        
        # 生成所有季度
        quarters = self._generate_quarters(start_year, end_year)
        
        logger.info(f"[{__name__}.{func_name}] 计划下载 {len(quarters)} 个季度的数据")
        
        # 逐个季度下载
        for quarter in quarters:
            logger.info(f"[{__name__}.{func_name}] 开始下载季度 {quarter}")
            try:
                self._fetch_quarterly_kline(quarter, time_frame)
                logger.info(f"[{__name__}.{func_name}] 季度 {quarter} 下载完成")
            except Exception as e:
                logger.error(f"[{__name__}.{func_name}] 季度 {quarter} 下载失败: {str(e)}")
                raise e  # 向上传播异常

    # 新增：封装时间段与上市/退市期间交集判断的内部函数
    def _is_time_range_overlap_with_listing_period(self, stock_code: str, start_date: str, end_date: str) -> tuple[bool, str, str]:
        """
        判断请求的时间段与股票上市/退市期间是否有交集，兼容退市场景
        :param stock_code: 股票代码
        :param start_date: 请求时间段起始日期（YYYY-MM-DD）
        :param end_date: 请求时间段结束日期（YYYY-MM-DD）
        :return: (是否有交集, 实际下载起始日期, 实际下载结束日期)
        """
        func_name = "_is_time_range_overlap_with_listing_period"
        # 1. 获取股票上市/退市日期
        listing_date, delist_date = dm.get_stock_listing_date(self.db_conn, stock_code)

        # 2. 转换日期为datetime对象（方便比较）
        req_start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        req_end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        list_dt = datetime.strptime(listing_date, "%Y-%m-%d") if listing_date else None
        delist_dt = datetime.strptime(delist_date, "%Y-%m-%d") if delist_date else None

        # 3. 核心交集判断逻辑
        # 无上市日期 → 无交集（跳过）
        if not list_dt:
            logger.debug(f"[{__name__}.{func_name}] 股票 {stock_code} 无上市日期，跳过下载")
            return False, None, None
        
        # 已退市且退市日期早于请求起始日期 → 无交集（跳过）
        if delist_dt and delist_dt < req_start_dt:
            logger.debug(f"[{__name__}.{func_name}] 股票 {stock_code} 退市日期 {delist_date} 早于请求起始日期 {start_date}，跳过下载")
            return False, None, None
        
        # 上市日期晚于请求结束日期 → 无交集（跳过）
        if list_dt > req_end_dt:
            logger.debug(f"[{__name__}.{func_name}] 股票 {stock_code} 上市日期 {listing_date} 晚于请求结束日期 {end_date}，跳过下载")
            return False, None, None
        
        # 4. 计算实际下载的起止日期（取交集）
        actual_start_dt = max(list_dt, req_start_dt)
        # 未退市则取请求结束日期，已退市则取退市日期
        actual_end_dt = min(delist_dt, req_end_dt) if delist_dt else req_end_dt
        
        actual_start_date = actual_start_dt.strftime("%Y-%m-%d")
        actual_end_date = actual_end_dt.strftime("%Y-%m-%d")
        
        logger.debug(
            f"[{__name__}.{func_name}] 股票 {stock_code} 实际下载范围：{actual_start_date} ~ {actual_end_date} "
            f"(请求范围：{start_date} ~ {end_date} | 上市/退市：{listing_date} ~ {delist_date or '未退市'})"
        )
        return True, actual_start_date, actual_end_date

    def _fetch_quarterly_kline(self, quarter: str, time_frame: KLinePeriod) -> None:
        """
        下载单个季度所有股票的K线数据

        Args:
            quarter: 季度，格式如 '2024-Q1'
            time_frame: 时间周期，使用KLinePeriod枚举类型
        """
        func_name = "_fetch_quarterly_kline"
        logger.debug(f"[{__name__}.{func_name}] 开始下载季度 {quarter} 的 {time_frame.value} K线数据")

        # 获取所有股票列表
        all_stocks = get_existing_stock_codes_set(self.db_conn)
        all_stocks_sorted = sorted(all_stocks)
        logger.info(f"[{__name__}.{func_name}] 获取到 {len(all_stocks_sorted)} 只股票")
        if all_stocks_sorted and len(all_stocks_sorted) > 2:
            logger.info(f"前3条股票代码示例: {list(all_stocks_sorted)[:3]} ...")

        # 计算季度开始和结束日期 (调用内部封装函数)
        start_date, end_date = self._quarter_to_date_range(quarter)
        # 转换为datetime对象，方便日期比较
        quarter_start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        quarter_end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        # 遍历所有股票，下载每只股票的数据
        success_count = 0
        fail_count = 0
        skip_count = 0  # 新增：记录因未上市跳过的股票数量
        for stock_code in all_stocks_sorted:
            try:
                # 调用封装的交集判断函数
                is_overlap, actual_start, actual_end = self._is_time_range_overlap_with_listing_period(
                    stock_code, start_date, end_date
                )
                if not is_overlap:
                    skip_count += 1
                    continue  # 无交集，跳过下载

                logger.debug(f"[{__name__}.{func_name}] 开始下载股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 数据")
                # 传入调整后的起始日期
                self._fetch_stock_quarterly_kline(stock_code, time_frame, quarter, actual_start, actual_end)
                success_count += 1
                logger.debug(f"[{__name__}.{func_name}] 股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 数据下载完成")
            except Exception as e:
                fail_count += 1
                logger.error(f"[{__name__}.{func_name}] 股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 数据下载失败: {str(e)}")
                # 不中断整个季度下载，继续处理下一个股票
    
        # 新增：打印跳过数量日志
        logger.info(f"[{__name__}.{func_name}] 季度 {quarter} 下载完成，成功: {success_count}，失败: {fail_count}，因未上市跳过: {skip_count}")

    def _quarter_to_date_range(self, quarter: str):
        """
        将季度字符串转换为开始和结束日期
        
        Args:
            quarter: 季度，格式如 '2024-Q1'
            
        Returns:
            tuple: (start_date, end_date) 格式为 'YYYY-MM-DD'
        """
        year, q = quarter.split('-Q')
        q = int(q)
        
        if q == 1:
            start_date = f"{year}-01-01"
            end_date = f"{year}-03-31"
        elif q == 2:
            start_date = f"{year}-04-01"
            end_date = f"{year}-06-30"
        elif q == 3:
            start_date = f"{year}-07-01"
            end_date = f"{year}-09-30"
        else:  # q == 4
            start_date = f"{year}-10-01"
            end_date = f"{year}-12-31"
            
        return start_date, end_date

    def _clean_kline_data(self, raw_data, time_frame: KLinePeriod):
        """
        清洗K线数据，将原始数据转换为统一格式
        
        Args:
            raw_data: 原始K线数据
            time_frame: 时间周期，使用KLinePeriod枚举类型
            
        Returns:
            DataFrame: 清洗后的数据
        """
        func_name = "_clean_kline_data"
        logger.debug(f"[{__name__}.{func_name}] 开始清洗K线数据")
        
        if raw_data.empty:
            logger.warning(f"[{__name__}.{func_name}] 原始数据为空")
            return pd.DataFrame()
        
        # 将原始数据转换为DataFrame
        df = pd.DataFrame(raw_data, columns=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
        df = df.rename(columns={
            'date': 'timestamp',
            'open': 'open_price',
            'high': 'high_price',
            'low': 'low_price',
            'close': 'close_price',
            'volume': 'volume',
            'amount': 'turnover'
        })
        
        # 添加time_frame列
        df['time_frame'] = time_frame.value
        
        # 转换时间戳格式
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # 转换数值类型
        numeric_columns = ['open_price', 'high_price', 'low_price', 'close_price']
        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        if 'volume' in df.columns:
            df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0).astype('Int64')
        
        if 'turnover' in df.columns:
            df['turnover'] = pd.to_numeric(df['turnover'], errors='coerce')
        
        # 移除无效数据行
        df = df.dropna(subset=['timestamp'])
        
        logger.debug(f"[{__name__}.{func_name}] 数据清洗完成，共 {len(df)} 条有效记录")
        return df

    def _fetch_stock_quarterly_kline(self, stock_code: str, time_frame: KLinePeriod, quarter: str, start_date: str, end_date: str):
        """
        下载指定股票在指定季度的K线数据
        
        Args:
            stock_code: 股票代码
            time_frame: 时间周期，使用KLinePeriod枚举类型
            quarter: 季度，格式如 '2024-Q1'
            start_date: 季度开始日期
            end_date: 季度结束日期
        """
        func_name = "_fetch_stock_quarterly_kline"
        logger.debug(f"[{__name__}.{func_name}] 开始下载股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 数据")
        
        # 步骤1: 参数校验
        if not stock_code or not isinstance(stock_code, str):
            raise ValueError(f"无效的股票代码: {stock_code}")
        
        if not quarter or not isinstance(quarter, str) or '-' not in quarter:
            raise ValueError(f"无效的季度格式: {quarter}，应为 YYYY-Qn 格式")
        
        if not time_frame or not isinstance(time_frame, KLinePeriod):
            raise ValueError(f"无效的时间周期: {time_frame}")
        # 映射KLinePeriod到baostock的频率参数
        frequency = bsw.convert_kline_period_to_baostock_freq(time_frame)

        # 步骤2: 获取最小单元状态
        status = dm.get_kline_download_status(self.db_conn, stock_code, time_frame.value, quarter)
        logger.debug(f"[{__name__}.{func_name}] 股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 状态: {status}")
        
        # 如果状态为已完成，则跳过
        if status == 'completed':
            logger.info(f"[{__name__}.{func_name}] 股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 数据已存在，跳过下载")
            return
        
        # 步骤3: 下载原始数据
        logger.info(f"[{__name__}.{func_name}] 开始下载股票 {stock_code} 在 {start_date} 到 {end_date} 的 {time_frame.value} 数据")
        
        # 调用baostock_wrapper查询数据
        fields = "date,open,high,low,close,volume,amount"
        result = query_history_k_data_plus(
            code=stock_code,
            fields=fields,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            adjustflag="3"  # 默认复权方式
        )
        
        if result.error_code != '0':
            raise Exception(f"baostock查询失败，错误码: {result.error_code}，错误信息: {result.error_msg}")
        
        # 步骤4: 清洗数据
        raw_data = result.get_data()
        df = self._clean_kline_data(raw_data, time_frame)
        
        if df.empty:
            logger.warning(f"[{__name__}.{func_name}] 股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 数据为空")
            # 即使数据为空也标记为已完成
            dm.update_kline_download_progress_unified(self.db_conn, stock_code, time_frame.value, quarter, 'completed')
            return
        
        logger.info(f"[{__name__}.{func_name}] 股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 数据清洗完成，共 {len(df)} 条记录")
        
        # 步骤5: 保存数据
        save_success = dm.save_kline_data_unified(self.db_conn, stock_code, df)
        if not save_success:
            raise Exception(f"保存股票 {stock_code} 的K线数据失败")
        
        logger.info(f"[{__name__}.{func_name}] 股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 数据保存成功")
        
        # 步骤6: 保存进度
        dm.update_kline_download_progress_unified(self.db_conn, stock_code, time_frame.value, quarter, 'completed')
        logger.info(f"[{__name__}.{func_name}] 股票 {stock_code} 在季度 {quarter} 的 {time_frame.value} 下载进度已更新为完成")


def download_kline(db_conn, start_year: int, end_year: int, time_frame: KLinePeriod):
    """
    下载K线数据的对外接口
    
    Args:
        db_conn: 数据库连接句柄
        start_year: 开始年份（包含）
        end_year: 结束年份（不包含）
        time_frame: 时间周期，使用KLinePeriod枚举类型
    """
    func_name = "download_kline"
    logger.info(f"[{__name__}.{func_name}] 开始执行K线下载任务，年份范围: {start_year}-{end_year-1}，时间周期: {time_frame.value}")
    
    downloader = KLineDownloader(db_conn)
    downloader.download_kline(start_year, end_year, time_frame)
    
    logger.info(f"[{__name__}.{func_name}] K线下载任务执行完成")
