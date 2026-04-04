# trade_date_map_downloader.py
from KitchenBase.logger_config import get_logger
import baostock as bs
import pandas as pd
from datetime import datetime
from typing import Optional
from Ingredient.DataNest import TradeDateMapManager

logger = get_logger(__name__)


def _validate_date_range(start_date: str, end_date: str) -> bool:
    """
    校验日期范围合法性（格式+逻辑）
    :param start_date: 起始日期（YYYY-MM-DD）
    :param end_date: 结束日期（YYYY-MM-DD）
    :return: 合法返回True，否则False
    """
    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
        if start_dt > end_dt:
            logger.warning(f"日期范围异常：start_date({start_date}) > end_date({end_date})")
            return False
        return True
    except ValueError as e:
        logger.error(f"日期格式错误（需YYYY-MM-DD）：{e}")
        return False

def _download_raw_trade_dates(start_date: str, end_date: str) -> Optional[pd.DataFrame]:
    """
    从Baostock下载原始交易日数据，返回DataFrame
    :param start_date: 起始日期
    :param end_date: 结束日期
    :return: 原始数据DataFrame，失败返回None
    """
    # 避免重复登录（若已登录则复用）
    try:
        # 先尝试获取登录状态（Baostock无直接获取状态接口，用查询兜底）
        test_rs = bs.query_trade_dates(start_date=start_date, end_date=start_date)
        if test_rs.error_code == '0':
            logger.debug("Baostock已登录，复用现有连接")
        else:
            lg = bs.login()
            if lg.error_code != '0':
                logger.error(f"Baostock登录失败：{lg.error_msg}")
                return None
    except:
        # 首次登录
        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"Baostock登录失败：{lg.error_msg}")
            return None

    try:
        # 调用接口获取原始数据
        rs = bs.query_trade_dates(start_date=start_date, end_date=end_date)
        if rs.error_code != '0':
            logger.error(f"下载交易日数据失败：{rs.error_msg}")
            return None

        # 将返回结果转为DataFrame（适配接口格式变化）
        data_list = []
        while (rs.error_code == '0') and rs.next():  # 修复&为and，提升可读性
            data_list.append(rs.get_row_data())
        
        if not data_list:
            logger.warning(f"{start_date}~{end_date}范围内无交易日数据")
            return None

        # 构建DataFrame，字段与Baostock返回一致
        df = pd.DataFrame(data_list, columns=rs.fields)
        logger.info(f"成功下载{len(df)}条原始交易日数据")
        return df
    except Exception as e:
        logger.error(f"下载原始交易日数据异常：{e}", exc_info=True)  # 输出完整异常栈
        return None

def _clean_trade_dates_data(raw_df: pd.DataFrame) -> Optional[pd.DataFrame]:
    """
    清洗交易日数据：格式转换、空值处理、数据校验
    :param raw_df: 原始数据DataFrame
    :return: 清洗后的DataFrame，失败返回None
    """
    try:
        # 复制数据避免修改原数据
        df = raw_df.copy()

        # 1. 字段重命名（兼容Baostock字段名可能的变更）
        # 先检查字段是否存在，避免KeyError
        rename_map = {}
        if 'calendar_date' in df.columns:
            rename_map['calendar_date'] = 'calendar_date'
        if 'is_trading_day' in df.columns:
            rename_map['is_trading_day'] = 'is_trading_day'
        df.rename(columns=rename_map, inplace=True)

        # 2. 格式转换：calendar_date转为date类型，is_trading_day转为int
        # 处理空值/异常值
        df['calendar_date'] = pd.to_datetime(df['calendar_date'], errors='coerce').dt.date
        df['is_trading_day'] = pd.to_numeric(df['is_trading_day'], errors='coerce').fillna(0).astype(int)

        # 3. 空值处理：删除calendar_date为空的行
        df = df.dropna(subset=['calendar_date'])

        # 4. 数据校验：is_trading_day仅保留0/1
        df = df[df['is_trading_day'].isin([0, 1])]

        # 去重（按calendar_date）
        df = df.drop_duplicates(subset=['calendar_date'], keep='last')

        logger.info(f"数据清洗完成，有效数据{len(df)}条（去重后）")
        return df
    except Exception as e:
        logger.error(f"清洗交易日数据异常：{e}", exc_info=True)
        return None

def download_trade_date_map(
    conn, 
    start_year: int = 2015, 
    end_year: Optional[int] = None
) -> bool:
    """
    对外暴露的核心函数：按年下载交易日数据并保存到数据库
    规则：包含 start_year 全年，不包含 end_year
    :param conn: 数据库连接对象
    :param start_year: 起始年份（默认2015）
    :param end_year: 结束年份（默认当前年份）
    :return: 成功返回True，失败返回False
    """
    # 处理默认结束年份：默认使用当前年份
    current_year = datetime.now().year
    if end_year is None:
        end_year = current_year
        logger.info(f"未指定结束年份，默认使用当前年份：{end_year}")

    # 年份合法性校验
    if not isinstance(start_year, int) or not isinstance(end_year, int):
        logger.error("年份必须为整数类型")
        return False
    if start_year <= 0 or end_year <= 0:
        logger.error("年份必须为正整数")
        return False
    if start_year >= end_year:
        logger.error(f"年份范围异常：start_year({start_year}) >= end_year({end_year})")
        return False

    # 生成日期范围：包含 start_year 全年，不包含 end_year
    # 开始日期：start_year-01-01
    start_date = f"{start_year}-01-01"
    # 结束日期：end_year - 1 年的 12月31日
    end_date = f"{end_year - 1}-12-31"

    logger.info(f"交易日数据按年下载范围：{start_year} ~ {end_year-1} 年（{start_date} ~ {end_date}）")

    # 1. 校验日期范围
    if not _validate_date_range(start_date, end_date):
        return False

    # 2. 下载原始数据
    raw_df = _download_raw_trade_dates(start_date, end_date)
    if raw_df is None:
        logger.error("原始交易日数据下载失败，终止流程")
        return False

    # 3. 清洗数据
    clean_df = _clean_trade_dates_data(raw_df)
    if clean_df is None or len(clean_df) == 0:
        logger.error("交易日数据清洗后无有效数据，终止流程")
        return False

    # 4. 调用data_manager保存数据（数据入库逻辑完全交给data_manager）
    try:
        trade_date_manager = TradeDateMapManager(conn)
        save_result = trade_date_manager.save_trade_date_map(clean_df)
        if save_result:
            logger.info("交易日数据成功保存到数据库")
            return True
        else:
            logger.error("交易日数据保存到数据库失败")
            return False
    except Exception as e:
        logger.error(f"初始化TradeDateMapManager或保存数据异常：{e}", exc_info=True)
        return False

# 测试代码（可选，单独运行该模块时执行）
if __name__ == "__main__":
    import pymysql

    # 配置数据库连接
    DB_CONFIG = {
        "host": "localhost",
        "user": "root",
        "password": "ta225924",
        "database": "ashare",
        "charset": "utf8mb4"
    }

    # 创建连接
    conn = pymysql.connect(**DB_CONFIG)
    try:
        # 示例：下载 2015 ~ 2016 年全年数据（不包含2017）
        result = download_trade_date_map(conn, start_year=2015, end_year=2016)
        print(f"下载结果：{'成功' if result else '失败'}")
    finally:
        conn.close()