# baostock_wrapper.py
import socket
from functools import wraps
from typing import Any
import baostock as bs
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

# ============================
# 核心工具：带重试+自动重登的执行器
# ============================
def _execute_with_retry_and_reauth(
    func,
    args=(),
    kwargs=None,
    timeout: int = 60,
    max_retry: int = 3  # 重试次数（可配置）
) -> Any:
    """
    带超时+重试+自动重登的函数执行器
    单次循环：设置超时 → 执行函数 → 异常则重登 → 重试
    """
    current_func = _execute_with_retry_and_reauth.__name__
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

# ============================
# 对外接口：完全兼容原生baostock接口
# 保留所有参数/返回值/异常逻辑，无感知封装
# ============================
def query_history_k_data_plus(
    code: str,
    fields: str,
    start_date: str,
    end_date: str,
    frequency: str = "d",
    adjustflag: str = "3",
    timeout: int = 60,
    max_retry: int = 3  # 新增重试参数（默认值不影响原有调用）
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
    current_func = query_history_k_data_plus.__name__
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
        logger.debug(f"[{current_func}->{inner_func}] 接口调用完成，error_code: {result.error_code}")
        return result

    try:
        # 执行带重试+重登的调用逻辑
        result = _execute_with_retry_and_reauth(
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