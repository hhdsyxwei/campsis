# baostock_wrapper.py
import socket
from functools import wraps
from typing import Any
import baostock as bs
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import KLinePeriod

logger = get_logger(__name__)


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
                    # 先登出（避免重复登录报错）再登录，复用已有登录态
                    bs.logout()
                    login_result = bs.login()
                    if login_result.error_code != '0':
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

        # 理论上不会走到这里，防止循环异常
        raise RuntimeError(f"[{current_func}] 执行流程异常，未触发重试逻辑")

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

# 创建默认实例以保持向后兼容
default_wrapper = BaostockWrapper()


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
    current_func = "query_adjust_factor"
    logger.debug(
        f"[{current_func}] 查询复权因子 "
        f"| 股票代码: {code} "
        f"| 时间范围: {start_date or '2015-01-01'} - {end_date or '当前日期'}"
    )
    
    try:
        result = bs.query_adjust_factor(
            code=code,
            start_date=start_date,
            end_date=end_date
        )
    
        logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
        return result
    except Exception as e:
        logger.error(f"[{current_func}] 查询失败 - {type(e).__name__}: {str(e)}")
        raise ConnectionError(f"查询复权因子失败: {str(e)}") from e


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
    """
    current_func = "query_dividend_data"
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
    
    logger.debug(f"[{current_func}] 查询完成，error_code: {result.error_code}")
    return result
