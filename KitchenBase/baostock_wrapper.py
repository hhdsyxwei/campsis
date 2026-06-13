import os
import socket
import time
from functools import wraps
from typing import Any
import baostock as bs
import baostock.common.contants as bs_constants
import baostock.common.context as bs_context
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import KLinePeriod

logger = get_logger(__name__)


class BaostockErrorCode:
    """Baostock 错误码常量"""
    SUCCESS = "0"                     #baostock成功码
    CONNECTION_REFUSED = "10002007"   #baostock错误消息：网络接收错误。远程主机强迫关闭了一个现有的连接。接收数据异常，请稍后再试。
    CONNECT_FAIL = "10002002"
    CONNECT_TIMEOUT = "10002003"
    IP_BLACKLIST = "10001011"        #baostock错误消息：IP被黑名单限制。

TRANSIENT_ERROR_CODES = {
    BaostockErrorCode.CONNECTION_REFUSED,
    BaostockErrorCode.CONNECT_FAIL,
    BaostockErrorCode.CONNECT_TIMEOUT,
}

class BaostockWrapper:




    """
    Baostock数据查询包装类
    提供带重试、自动重登、超时控制等功能的封装
    """

    # KLinePeriod到baostock频率映射表（静态成员）
    kline_period_to_baostock_freq = {
        KLinePeriod.MIN_1: "1",
        KLinePeriod.MIN_5: "5",
        KLinePeriod.MIN_15: "15",
        KLinePeriod.MIN_30: "30",
        KLinePeriod.MIN_60: "60",
        KLinePeriod.DAILY: "d",
        KLinePeriod.WEEKLY: "w",
        KLinePeriod.MONTHLY: "m",
        KLinePeriod.TIME_LINE: "d",  # 分时数据使用日线频率
        KLinePeriod.QUARTERLY: "m",  # 季度数据使用月线频率（近似处理）
        KLinePeriod.YEARLY: "m"      # 年度数据使用月线频率（近似处理）
    }

    def __init__(self, default_timeout: int = 60, default_max_retry: int = 3):
        """
        初始化包装器
        :param default_timeout: 默认socket超时时间（秒）
        :param default_max_retry: 默认最大重试次数
        """
        self.default_timeout = default_timeout
        self.default_max_retry = default_max_retry
        self._logged_in = False

    def _configure_baostock_endpoint(self) -> tuple:
        host = os.getenv("CAMPSIS_BAOSTOCK_HOST", bs_constants.BAOSTOCK_SERVER_IP)
        port = int(os.getenv("CAMPSIS_BAOSTOCK_PORT", str(bs_constants.BAOSTOCK_SERVER_PORT)))
        bs_constants.BAOSTOCK_SERVER_IP = host
        bs_constants.BAOSTOCK_SERVER_PORT = port
        return host, port

    def _configure_baostock_proxy(self) -> None:
        proxy_host = os.getenv("CAMPSIS_BAOSTOCK_PROXY_HOST")
        proxy_port = os.getenv("CAMPSIS_BAOSTOCK_PROXY_PORT")
        if not proxy_host or not proxy_port:
            return

        try:
            import socks
        except ImportError as e:
            raise RuntimeError("已设置 Baostock 代理环境变量，但未安装 PySocks") from e

        proxy_type_name = os.getenv("CAMPSIS_BAOSTOCK_PROXY_TYPE", "socks5").lower()
        proxy_type_map = {
            "socks5": socks.SOCKS5,
            "socks4": socks.SOCKS4,
            "http": socks.HTTP,
        }
        if proxy_type_name not in proxy_type_map:
            raise ValueError("CAMPSIS_BAOSTOCK_PROXY_TYPE 仅支持 socks5、socks4、http")

        socks.set_default_proxy(proxy_type_map[proxy_type_name], proxy_host, int(proxy_port))

        timeout = self.default_timeout

        def create_proxied_socket(*args, **kwargs):
            proxied_socket = socks.socksocket(*args, **kwargs)
            proxied_socket.settimeout(timeout)
            return proxied_socket

        socket.socket = create_proxied_socket
        logger.info(f"Baostock TCP连接将通过代理 {proxy_type_name}://{proxy_host}:{proxy_port}")

    def _check_baostock_connectivity(self, host: str, port: int, timeout: int) -> None:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return
        except socket.timeout as e:
            raise TimeoutError(f"Baostock TCP连接超时: {host}:{port}") from e
        except OSError as e:
            raise ConnectionError(f"Baostock TCP连接失败: {host}:{port} - {e}") from e

    @staticmethod
    def _clear_default_socket() -> None:
        default_socket = getattr(bs_context, "default_socket", None)
        if default_socket is not None:
            try:
                default_socket.close()
            except Exception:
                pass
        setattr(bs_context, "default_socket", None)

    def _execute_with_retry_and_reauth(
        self,
        func,
        args=(),
        kwargs=None,
        timeout: int = 300,
        max_retry: int = 3
    ) -> Any:
        """
        带超时+重试+自动重登的函数执行器
        单次循环：设置超时 → 执行函数 → 异常则重登 → 重试
        """
        if timeout is None:
            timeout = self.default_timeout
        if max_retry is None:
            max_retry = self.default_max_retry
            
        current_func = self._execute_with_retry_and_reauth.__name__
        if kwargs is None:
            kwargs = {}

        retry_count = 0
        while retry_count < max_retry:
            try:
                # 步骤1：设置全局socket超时（当前线程生效）
                socket.setdefaulttimeout(timeout)
                logger.debug(f"[{current_func}] 第 {retry_count+1}/{max_retry} 次尝试 - 设置socket全局超时为 {timeout}s")

                # 步骤2：调用目标函数（原生baostock接口）
                logger.debug(f"[{current_func}] 第 {retry_count+1}/{max_retry} 次尝试 - 执行目标函数 {func.__name__}")
                result = func(*args, **kwargs)

                # 执行成功：重置超时并返回结果
                socket.setdefaulttimeout(None)
                logger.info(f"[{current_func}] 第 {retry_count+1} 次尝试成功，函数 {func.__name__} 执行完成")
                return result
            except UnicodeDecodeError as e:
                # 捕获编码异常，封装为自定义异常抛出
                raise RuntimeError(f"Baostock数据编码异常: {str(e)}") from e
            except Exception as e:
                retry_count += 1
                logger.error(f"[{current_func}] 第 {retry_count} 次尝试失败 - 异常类型: {type(e).__name__}, 异常信息: {str(e)}")

                # 步骤3：异常时重新登录（复用已有登录，仅重登保证连接有效性）
                logger.info(f"[{current_func}] 尝试重新登录baostock以恢复连接")
                try:
                    self._clear_default_socket()
                    # 先登出（避免重复登录报错）再登录，复用已有登录态
                    bs.logout()
                    login_result = bs.login()
                    if login_result.error_code != BaostockErrorCode.SUCCESS:
                        logger.error(f"[{current_func}] 重登失败 - error_code: {login_result.error_code}, error_msg: {login_result.error_msg}")
                    else:
                        logger.info(f"[{current_func}] 重登成功 - user_id: {login_result.user_id}")
                except Exception as reauth_e:
                    logger.error(f"[{current_func}] 重登过程发生异常 - {type(reauth_e).__name__}: {str(reauth_e)}")

                # 重置超时，避免影响下一次重试
                socket.setdefaulttimeout(None)

                # 达到最大重试次数则抛出异常
                if retry_count >= max_retry:
                    logger.error(f"[{current_func}] 已达到最大重试次数({max_retry})，最终执行失败")
                    raise e

                time.sleep(min(2 ** retry_count, 8))

        # 理论上不会走到这里，防止循环异常
        raise RuntimeError(f"[{current_func}] 执行流程异常，未触发重试逻辑")

    @staticmethod
    def convert_kline_period_to_baostock_freq(kline_period: KLinePeriod) -> str:
        """
        将KLinePeriod枚举类型转换为baostock对应的时间频率字符串
        :param kline_period: KLinePeriod枚举值
        :return: baostock对应的时间频率字符串
        :raises ValueError: 当kline_period不在支持的映射范围内时抛出异常
        """
        if not isinstance(kline_period, KLinePeriod):
            raise ValueError(f"kline_period必须是KLinePeriod枚举类型，实际类型: {type(kline_period)}")
        
        freq = BaostockWrapper.kline_period_to_baostock_freq.get(kline_period)
        if freq is None:
            raise ValueError(f"不支持的KLinePeriod类型: {kline_period.value}")
        
        return freq

    def query_history_k_data_plus(
        self,
        code: str,
        fields: str,
        start_date: str,
        end_date: str,
        frequency: str = "d",
        adjustflag: str = "3",
        timeout: int = 300,
        max_retry: int = 3
    ) -> Any:
        """
        完全兼容原生baostock.query_history_k_data_plus接口
        新增特性：
        1. 多次重试（次数可配置）
        2. 异常时自动重新登录
        3. 全局socket超时保护
        4. 完整的日志追踪

        参数说明：
        - 原生参数：code/fields/start_date/end_date/frequency/adjustflag
        - 扩展参数：timeout（socket超时，默认None使用实例默认值）、max_retry（最大重试次数，默认None使用实例默认值）
        返回值：原生ResultData对象
        异常：保留原生异常类型，新增重试耗尽后的异常透传
        """
        if timeout is None:
            timeout = self.default_timeout
        if max_retry is None:
            max_retry = self.default_max_retry
            
        current_func = self.query_history_k_data_plus.__name__
        logger.debug(
            f"[{current_func}] 开始查询K线数据 "
            f"| 股票代码: {code} "
            f"| 时间范围: {start_date} - {end_date} "
            f"| 频率: {frequency} "
            f"| 复权标志: {adjustflag} "
            f"| 超时: {timeout}s "
            f"| 最大重试次数: {max_retry}"
        )

        # 定义原生baostock调用逻辑
        def _native_baostock_call():
            inner_func = _native_baostock_call.__name__
            logger.debug(f"[{current_func}->{inner_func}] 调用原生baostock.query_history_k_data_plus接口")
            result = bs.query_history_k_data_plus(
                code=code,
                fields=fields,
                start_date=start_date,
                end_date=end_date,
                frequency=frequency,
                adjustflag=adjustflag
            )
            if result and result.error_code == BaostockErrorCode.CONNECTION_REFUSED:
                raise ConnectionRefusedError(f"查询K线数据失败: {result.error_msg}")

            logger.debug(f"[{current_func}->{inner_func}] 接口调用完成，error_code: {result.error_code if result is not None else 'None'}")
            return result

        try:
            # 执行带重试+重登的调用逻辑
            result = self._execute_with_retry_and_reauth(
                func=_native_baostock_call,
                timeout=timeout,
                max_retry=max_retry
            )
            logger.info(f"[{current_func}] 股票 {code} K线数据查询最终成功")
            return result
        except TimeoutError as e:
            logger.error(f"[{current_func}] 股票 {code} 查询超时 - {str(e)}")
            raise e
        except Exception as e:
            logger.error(f"[{current_func}] 股票 {code} 查询最终失败 - {type(e).__name__}: {str(e)}")
            raise e

    def query_adjust_factor(
        self,
        code: str,
        start_date: str = "",
        end_date: str = ""
    ) -> Any:
        """
        简单封装baostock.query_adjust_factor接口
        获取复权因子信息数据，BaoStock提供的是涨跌幅复权算法复权因子
        
        参数说明：
        - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
        - start_date: 开始日期，为空时默认为2015-01-01，包含此日期
        - end_date: 结束日期，为空时默认当前日期，包含此日期
        
        返回字段：
        - code: 证券代码
        - dividOperateDate: 除权除息日期
        - foreAdjustFactor: 向前复权因子
        - backAdjustFactor: 向后复权因子
        - adjustFactor: 本次复权因子
        
        返回值：原生ResultData对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.query_adjust_factor.__name__
        logger.debug(
            f"[{current_func}] 查询复权因子 "
            f"| 股票代码: {code} "
            f"| 时间范围: {start_date or '2015-01-01'} - {end_date or '当前日期'}"
        )
        
        result = bs.query_adjust_factor(
            code=code,
            start_date=start_date,
            end_date=end_date
        )
        if result.error_code == BaostockErrorCode.CONNECTION_REFUSED:
            raise ConnectionRefusedError(f"查询复权因子失败: {result.error_code}=={result.error_msg}")
        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result

    def query_dividend_data(
        self,
        code: str,
        year: str,
        yearType: str = "report"
    ) -> Any:
        """
        简单封装baostock.query_dividend_data接口
        获取除权除息信息数据（预披露、预案、正式都已通过）
        
        参数说明：
        - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
        - year: 年份，如：2017
        - yearType: 年份类别
            - "report": 预案公告年份（默认）
            - "operate": 除权除息年份
        
        返回字段：
        - code: 证券代码
        - dividPreNoticeDate: 预案公告日期
        - dividAgmPumDate: 股东大会公告日期
        - dividPlanAnnounceDate: 预案披露日期
        - dividPlanDate: 预案日期
        - dividRegistDate: 股权登记日期
        - dividOperateDate: 除权除息日期
        - dividPayDate: 派息日期
        - dividStockMarketDate: 红股上市日期
        - dividCashPsBeforeTax: 每股股利（税前）
        - dividCashPsAfterTax: 每股股利（税后）
        - dividStocksPs: 每股送股
        - dividCashStock: 每股转增
        - dividReserveToStockPs: 每股资本公积转增
        
        返回值：原生ResultData对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.query_dividend_data.__name__
        logger.debug(
            f"[{current_func}] 查询分红送配数据 "
            f"| 股票代码: {code} "
            f"| 年份: {year} "
            f"| 年份类型: {yearType}"
        )
        
        result = bs.query_dividend_data(
            code=code,
            year=year,
            yearType=yearType
        )

        if result.error_code == BaostockErrorCode.CONNECTION_REFUSED:
            raise ConnectionRefusedError(f"查询分红送配数据失败: {result.error_msg}")

        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result

    def query_profit_data(
        self,
        code: str,
        year: int,
        quarter: int,
        timeout: int = None,
        max_retry: int = None
    ) -> Any:
        """
        简单封装baostock.query_profit_data接口
        获取季频盈利能力数据
        
        参数说明：
        - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
        - year: 统计年份
        - quarter: 统计季度（1-4）
        
        返回字段：
        - code: 证券代码
        - pubDate: 公司发布财报的日期
        - statDate: 财报统计的季度的最后一天
        - roeAvg: 净资产收益率(%)
        - npMargin: 销售净利率(%)
        - gpMargin: 销售毛利率(%)
        - netProfit: 净利润(万元)
        - epsTTM: 每股收益
        - MBRevenue: 主营营业收入(百万元)
        
        返回值：原生ResultData对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.query_profit_data.__name__
        logger.debug(
            f"[{current_func}] 查询季频盈利能力 "
            f"| 股票代码: {code} "
            f"| 年份: {year} "
            f"| 季度: {quarter}"
        )
        
        def _native_baostock_call():
            result = bs.query_profit_data(
                code=code,
                year=year,
                quarter=quarter
            )
            if result.error_code in TRANSIENT_ERROR_CODES:
                raise ConnectionError(f"查询季频盈利能力失败: {result.error_code}=={result.error_msg}")
            return result

        result = self._execute_with_retry_and_reauth(
            func=_native_baostock_call,
            timeout=timeout,
            max_retry=max_retry,
        )
        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result

    def query_trade_dates(
        self,
        start_date: str,
        end_date: str
    ) -> Any:
        """
        简单封装baostock.query_trade_dates接口
        获取交易日数据
        
        参数说明：
        - start_date: 开始日期，格式：YYYY-MM-DD
        - end_date: 结束日期，格式：YYYY-MM-DD
        
        返回字段：
        - calendar_date: 日历日期
        - is_trading_day: 是否交易日（1=是，0=否）
        
        返回值：原生ResultData对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.query_trade_dates.__name__
        logger.debug(
            f"[{current_func}] 查询交易日数据 "
            f"| 时间范围: {start_date} - {end_date}"
        )

        result = bs.query_trade_dates(
            start_date=start_date,
            end_date=end_date
        )
        
        if result.error_code == BaostockErrorCode.CONNECTION_REFUSED:
            raise ConnectionRefusedError(f"查询交易日数据失败: {result.error_msg}")

        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result

    def query_stock_industry(
        self,
        code: str = "",
        date: str = ""
    ) -> Any:
        """
        简单封装baostock.query_stock_industry接口
        获取行业分类信息数据
        
        参数说明：
        - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000，可以为空
        - date: 查询日期，格式：YYYY-MM-DD，为空时默认最新日期
        
        返回值：原生ResultData对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.query_stock_industry.__name__
        logger.debug(
            f"[{current_func}] 查询行业分类 "
            f"| 股票代码: {code or '全部'} "
            f"| 查询日期: {date or '最新日期'}"
        )
        result = bs.query_stock_industry(
            code=code,
            date=date
        )
        if result.error_code == BaostockErrorCode.CONNECTION_REFUSED:
            raise ConnectionRefusedError(f"查询行业分类失败: {result.error_msg}")

        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result

    def query_hs300_stocks(
        self,
        date: str = ""
    ) -> Any:
        """
        简单封装baostock.query_hs300_stocks接口
        获取沪深300指数成分股数据
        
        沪深300指数是由沪深两市规模最大、流动性最好的300只股票组成
        反映A股市场整体表现的核心指数
        
        参数说明：
        - date: 查询日期，格式：YYYY-MM-DD，为空时默认最新日期
                指定日期可以获取历史某一时间点的成分股构成
        
        返回字段：
        - updateDate: 更新日期
        - code: 股票代码，格式为sh.xxxxxx或sz.xxxxxx
        - code_name: 股票名称
        
        返回值：原生ResultData对象
        异常：网络连接异常时抛出ConnectionError异常
        
        注意：BaoStock的沪深300成分股数据可能不是实时更新的，
        如需最新成分股建议从交易所或中证指数公司官网获取
        """
        current_func = self.query_hs300_stocks.__name__
        logger.debug(
            f"[{current_func}] 查询沪深300成分股 "
            f"| 查询日期: {date or '最新日期'}"
        )
        
        result = bs.query_hs300_stocks(
            date=date
        )
        
        if result.error_code == BaostockErrorCode.CONNECTION_REFUSED:
            raise ConnectionRefusedError(f"查询沪深300成分股失败: {result.error_msg}")

        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result

    def query_cash_flow_data(
        self,
        code: str,
        year: int,
        quarter: int
    ) -> Any:
        """
        简单封装baostock.query_cash_flow_data接口
        获取季频现金流量数据
        
        参数说明：
        - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
        - year: 统计年份
        - quarter: 统计季度（1-4）
        
        返回字段：
        - code: 证券代码
        - pubDate: 公司发布财报的日期
        - statDate: 财报统计的季度的最后一天
        - catoAsset: 流动资产占总资产比例(%)
        - ncatoAsset: 非流动资产占总资产比例(%)
        - tangibleAssetToAsset: 有形资产占总资产比例(%)
        - ebitToInterest: 已获利息倍数(倍)
        - cfotoor: 经营活动现金流净额/营业收入(%)
        - cfotonp: 经营活动现金流净额/净利润(%)
        - cfotogr: 经营活动现金流净额/营业总收入(%)
        
        返回值：原生ResultData对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.query_cash_flow_data.__name__
        logger.debug(
            f"[{current_func}] 查询季频现金流量 "
            f"| 股票代码: {code} "
            f"| 年份: {year} "
            f"| 季度: {quarter}"
        )
        
        result = bs.query_cash_flow_data(
            code=code,
            year=year,
            quarter=quarter
        )
        if result.error_code == BaostockErrorCode.CONNECTION_REFUSED:
            raise ConnectionRefusedError(f"查询季频现金流量失败: {result.error_code}=={result.error_msg}")
        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result

    def query_balance_data(
        self,
        code: str,
        year: int,
        quarter: int
    ) -> Any:
        """
        简单封装baostock.query_balance_data接口
        获取季频偿债能力数据
        
        参数说明：
        - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
        - year: 统计年份
        - quarter: 统计季度（1-4）
        
        返回值：原生ResultData对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.query_balance_data.__name__
        logger.debug(
            f"[{current_func}] 查询季频偿债能力数据 "
            f"| 股票代码: {code} "
            f"| 年份: {year} "
            f"| 季度: {quarter}"
        )
        
        result = bs.query_balance_data(
            code=code,
            year=year,
            quarter=quarter
        )
        if result.error_code == BaostockErrorCode.CONNECTION_REFUSED:
            raise ConnectionRefusedError(f"查询偿债能力数据失败: {result.error_code}=={result.error_msg}")
        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result

    def login(self) -> Any:
        """
        简单封装baostock.login接口
        登录Baostock系统
        
        返回值：原生登录结果对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.login.__name__
        host, port = self._configure_baostock_endpoint()
        self._configure_baostock_proxy()
        logger.debug(f"[{current_func}] 登录Baostock系统 | endpoint: {host}:{port}")
        
        try:
            self._check_baostock_connectivity(host, port, timeout=min(self.default_timeout, 10))
            socket.setdefaulttimeout(self.default_timeout)
            result = bs.login()
            logger.debug(f"[{current_func}] 登录完成，error_code: {result.error_code}")
            self._logged_in = result.error_code == BaostockErrorCode.SUCCESS
            return result
        except Exception as e:
            self._clear_default_socket()
            logger.error(f"[{current_func}] 登录失败 - {type(e).__name__}: {str(e)}")
            raise ConnectionError(f"登录Baostock系统失败: {str(e)}") from e
        finally:
            socket.setdefaulttimeout(None)

    def logout(self) -> Any:
        """
        简单封装baostock.logout接口
        退出Baostock系统
        
        返回值：原生登出结果对象
        异常：网络连接异常时抛出ConnectionError异常
        """
        current_func = self.logout.__name__
        logger.debug(f"[{current_func}] 退出Baostock系统")
        
        try:
            result = bs.logout()
            error_code = result.error_code if result is not None else 'None'
            logger.debug(f"[{current_func}] 登出完成，error_code: {error_code}")
            self._logged_in = False
            return result
        except Exception as e:
            logger.error(f"[{current_func}] 登出失败 - {type(e).__name__}: {str(e)}")
            raise ConnectionError(f"退出Baostock系统失败: {str(e)}") from e

# 创建默认实例以保持向后兼容
default_wrapper = BaostockWrapper()


def login() -> Any:
    """
    简单封装baostock.login接口
    登录Baostock系统
    
    返回值：原生登录结果对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.login()


def logout() -> Any:
    """
    简单封装baostock.logout接口
    退出Baostock系统
    
    返回值：原生登出结果对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.logout()

# 为了向后兼容，保留原有的函数接口
def query_history_k_data_plus(
    code: str,
    fields: str,
    start_date: str,
    end_date: str,
    frequency: str = "d",
    adjustflag: str = "3",
    timeout: int = 60,
    max_retry: int = 3
) -> Any:
    """
    完全兼容原生baostock.query_history_k_data_plus接口
    新增特性：
    1. 多次重试（次数可配置）
    2. 异常时自动重新登录
    3. 全局socket超时保护
    4. 完整的日志追踪
    
    参数说明：
    - 原生参数：code/fields/start_date/end_date/frequency/adjustflag
    - 扩展参数：timeout（socket超时，默认60s）、max_retry（最大重试次数，默认3次）
    返回值：原生ResultData对象
    异常：保留原生异常类型，新增重试耗尽后的异常透传
    """
    return default_wrapper.query_history_k_data_plus(
        code=code,
        fields=fields,
        start_date=start_date,
        end_date=end_date,
        frequency=frequency,
        adjustflag=adjustflag,
        timeout=timeout,
        max_retry=max_retry
    )


def query_adjust_factor(
    code: str,
    start_date: str = "",
    end_date: str = ""
) -> Any:
    """
    简单封装baostock.query_adjust_factor接口
    获取复权因子信息数据，BaoStock提供的是涨跌幅复权算法复权因子
    
    参数说明：
    - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
    - start_date: 开始日期，为空时默认为2015-01-01，包含此日期
    - end_date: 结束日期，为空时默认当前日期，包含此日期
    
    返回字段：
    - code: 证券代码
    - dividOperateDate: 除权除息日期
    - foreAdjustFactor: 向前复权因子
    - backAdjustFactor: 向后复权因子
    - adjustFactor: 本次复权因子
    
    返回值：原生ResultData对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.query_adjust_factor(
        code=code,
        start_date=start_date,
        end_date=end_date
    )


def query_dividend_data(
    code: str,
    year: str,
    yearType: str = "report"
) -> Any:
    """
    简单封装baostock.query_dividend_data接口
    获取除权除息信息数据（预披露、预案、正式都已通过）
    
    参数说明：
    - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
    - year: 年份，如：2017
    - yearType: 年份类别
        - "report": 预案公告年份（默认）
        - "operate": 除权除息年份
    
    返回字段：
    - code: 证券代码
    - dividPreNoticeDate: 预案公告日期
    - dividAgmPumDate: 股东大会公告日期
    - dividPlanAnnounceDate: 预案披露日期
    - dividPlanDate: 预案日期
    - dividRegistDate: 股权登记日期
    - dividOperateDate: 除权除息日期
    - dividPayDate: 派息日期
    - dividStockMarketDate: 红股上市日期
    - dividCashPsBeforeTax: 每股股利（税前）
    - dividCashPsAfterTax: 每股股利（税后）
    - dividStocksPs: 每股送股
    - dividCashStock: 每股转增
    - dividReserveToStockPs: 每股资本公积转增
    
    返回值：原生ResultData对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.query_dividend_data(
        code=code,
        year=year,
        yearType=yearType
    )


def query_profit_data(
    code: str,
    year: int,
    quarter: int,
    timeout: int = None,
    max_retry: int = None
) -> Any:
    """
    简单封装baostock.query_profit_data接口
    获取季频盈利能力数据
    
    参数说明：
    - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
    - year: 统计年份
    - quarter: 统计季度（1-4）
    
    返回字段：
    - code: 证券代码
    - pubDate: 公司发布财报的日期
    - statDate: 财报统计的季度的最后一天
    - roeAvg: 净资产收益率(%)
    - npMargin: 销售净利率(%)
    - gpMargin: 销售毛利率(%)
    - netProfit: 净利润(万元)
    - epsTTM: 每股收益
    - MBRevenue: 主营营业收入(百万元)
    - totalShare: 总股本(股数)
    - liqaShare: 流通股本(股数)
    
    返回值：原生ResultData对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.query_profit_data(
        code=code,
        year=year,
        quarter=quarter,
        timeout=timeout,
        max_retry=max_retry,
    )


def query_trade_dates(
    start_date: str,
    end_date: str
) -> Any:
    """
    简单封装baostock.query_trade_dates接口
    获取交易日数据
    
    参数说明：
    - start_date: 开始日期，格式：YYYY-MM-DD
    - end_date: 结束日期，格式：YYYY-MM-DD
    
    返回字段：
    - calendar_date: 日历日期
    - is_trading_day: 是否交易日（1=是，0=否）
    
    返回值：原生ResultData对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.query_trade_dates(
        start_date=start_date,
        end_date=end_date
    )


def query_stock_industry(
    code: str = "",
    date: str = ""
) -> Any:
    """
    简单封装baostock.query_stock_industry接口
    获取行业分类信息数据
    
    参数说明：
    - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000，可以为空
    - date: 查询日期，格式：YYYY-MM-DD，为空时默认最新日期
    
    返回值：原生ResultData对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.query_stock_industry(
        code=code,
        date=date
    )


def query_hs300_stocks(
    date: str = ""
) -> Any:
    """
    简单封装baostock.query_hs300_stocks接口
    获取沪深300指数成分股数据
    
    沪深300指数是由沪深两市规模最大、流动性最好的300只股票组成
    反映A股市场整体表现的核心指数
    
    参数说明：
    - date: 查询日期，格式：YYYY-MM-DD，为空时默认最新日期
            指定日期可以获取历史某一时间点的成分股构成
    
    返回字段：
    - updateDate: 更新日期
    - code: 股票代码，格式为sh.xxxxxx或sz.xxxxxx
    - code_name: 股票名称
    
    返回值：原生ResultData对象
    异常：网络连接异常时抛出ConnectionError异常
    
    使用示例：
    >>> import KitchenBase.baostock_wrapper as bs
    >>> result = bs.query_hs300_stocks()
    >>> result_data = result.get_data()
    >>> print(result_data)
    
    注意：BaoStock的沪深300成分股数据可能不是实时更新的，
    如需最新成分股建议从交易所或中证指数公司官网获取
    """
    return default_wrapper.query_hs300_stocks(
        date=date
    )


def query_cash_flow_data(
    code: str,
    year: int,
    quarter: int
) -> Any:
    """
    简单封装baostock.query_cash_flow_data接口
    获取季频现金流量数据
    
    参数说明：
    - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
    - year: 统计年份
    - quarter: 统计季度（1-4）
    
    返回字段：
    - code: 证券代码
    - pubDate: 公司发布财报的日期
    - statDate: 财报统计的季度的最后一天
    - catoAsset: 流动资产占总资产比例(%)
    - ncatoAsset: 非流动资产占总资产比例(%)
    - tangibleAssetToAsset: 有形资产占总资产比例(%)
    - ebitToInterest: 已获利息倍数(倍)
    - cfotoor: 经营活动现金流净额/营业收入(%)
    - cfotonp: 经营活动现金流净额/净利润(%)
    - cfotogr: 经营活动现金流净额/营业总收入(%)
    
    返回值：原生ResultData对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.query_cash_flow_data(
        code=code,
        year=year,
        quarter=quarter
    )


def query_balance_data(
    code: str,
    year: int,
    quarter: int,
    timeout: int = 60,
    max_retry: int = 3
) -> Any:
    """
    简单封装baostock.query_balance_data接口
    获取季频偿债能力数据
    
    参数说明：
    - code: 股票代码，sh或sz.+6位数字代码，如：sh.600000
    - year: 统计年份
    - quarter: 统计季度（1-4）
    - timeout: socket超时时间（秒），默认60s
    - max_retry: 最大重试次数，默认3次
    
    返回值：原生ResultData对象
    异常：网络连接异常时抛出ConnectionError异常
    """
    return default_wrapper.query_balance_data(
        code=code,
        year=year,
        quarter=quarter
    )
