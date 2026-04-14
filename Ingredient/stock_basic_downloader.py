# stock_basic_downloader.py
import logging
from typing import List
import pandas as pd
import baostock as bs
from KitchenBase.logger_config import get_logger
from KitchenBase.stock_enums import MarketType
from KitchenBase.download_utils import baostock_code_to_market, convert_baostock_code  # 导入工具函数
from Ingredient.DataNest import BasicStockDataManager, UnifiedDataManager  # 确保导入

# 初始化日志
logger = get_logger(__name__)

# ==================== 核心接口 ====================
def download_stock_basic(
    conn,
    market_type_list: List[MarketType] = [MarketType.SH_MAIN_BOARD, MarketType.SZ_MAIN_BOARD]
) -> bool:
    """
    下载指定市场类型的股票基础信息，并保存到stock_basic表
    
    Args:
        conn: 数据库连接对象（使用者已提前建立）
        market_type_list: 市场类型列表，元素为MarketType枚举值
    
    Returns:
        下载及保存是否成功（True/False）
    """
    func_name = "download_stock_basic"
    logger.info(f"[{func_name}] 开始执行股票基础信息下载流程 | 市场类型: {[mt.value for mt in market_type_list]}")
    
    try:
        # 步骤1: 参数检验
        _validate_params(market_type_list)
        
        # 步骤2: 下载原生数据
        raw_df = _download_raw_data(market_type_list)
        if raw_df.empty:
            logger.warning(f"[{func_name}] 未下载到任何原生股票基础数据")
            return False
        
        # 步骤3: 数据清洗
        cleaned_df = _clean_data(raw_df)
        if cleaned_df.empty:
            logger.warning(f"[{func_name}] 数据清洗后无有效数据")
            return False
        
        # 步骤4: 数据保存
        save_result = _save_data(conn, cleaned_df)

        if( not save_result):
            logger.error(f"[{func_name}] 数据保存失败")
            return False
        
        # 步骤5: 保存股票固定顺序表
        stock_codes = cleaned_df['std_stock_code'].tolist()
        seq_save_result = _save_stock_fixed_seq(conn, stock_codes)
        
        if seq_save_result:
            logger.info(f"[{func_name}] 股票基础信息下载&保存全流程完成 | 有效数据量: {len(cleaned_df)}")
            return True
        else:
            logger.warning(f"[{func_name}] 股票基础信息保存成功，但股票固定顺序表保存失败")
            return True  # 基础信息保存成功，返回 True
    
    except Exception as e:
        logger.error(f"[{func_name}] 下载流程执行失败: {str(e)}", exc_info=True)
        return False

# ==================== 内部函数 - 步骤1: 参数检验 ====================
def _validate_params(market_type_list: List[MarketType]) -> None:
    """
    校验输入参数的合法性，不合法则抛出异常
    
    Args:
        market_type_list: 市场类型列表
    
    Raises:
        ValueError: 参数不合法时抛出
    """
    func_name = "_validate_params"
    logger.debug(f"[{func_name}] 开始校验参数")
    
    # 校验市场类型列表
    if not isinstance(market_type_list, list) or len(market_type_list) == 0:
        raise ValueError(f"[{func_name}] market_type_list必须为非空列表")
    
    for mt in market_type_list:
        if not isinstance(mt, MarketType):
            raise ValueError(f"[{func_name}] 元素必须为MarketType枚举 | 非法元素: {mt}")
    
    logger.debug(f"[{func_name}] 参数校验通过")

# ==================== 内部函数 - 步骤2: 下载原生数据 ====================
def _download_raw_data(market_type_list: List[MarketType]) -> pd.DataFrame:
    """
    通过baostock query_stock_basic接口下载全量股票基础信息
    【新版逻辑】：
    1. 下载全量数据
    2. 提取股票代码
    3. 使用 baostock_code_to_market 转换市场类型
    4. 根据 market_type_list 过滤
    5. 构造最终DF返回

    Args:
        market_type_list: 市场类型列表（枚举）

    Returns:
        原生数据DataFrame
    """
    
    func_name = "_download_raw_data"
    logger.debug(f"[{func_name}] 开始全量下载股票基础数据")

    # 1. 调用接口获取全市场数据
    rs = bs.query_stock_basic()

    if rs.error_code != '0':
        logger.error(f"[{func_name}] baostock接口调用失败 | {rs.error_code} {rs.error_msg}")
        return pd.DataFrame()

    # 2. 获取字段 & 定位 code 列（必须通过code识别市场）
    fields = rs.fields
    if "code" not in fields:
        logger.error(f"[{func_name}] baostock返回数据不包含code字段，无法识别市场")
        return pd.DataFrame()

    code_index = fields.index("code")  # 股票代码列索引（如 sh.600000）
    data_list = []

    # 3. 逐行读取 → 提取code → 识别市场 → 过滤
    while rs.next() and rs.error_code == '0':
        row = rs.get_row_data()

        # ===================== 核心新逻辑 =====================
        # 步骤A：提取股票代码（baostock格式：sh.600000）
        bs_code = row[code_index].strip() if row[code_index] else ""
        if not bs_code:
            continue  # 无代码直接跳过

        # 步骤B：调用工具函数识别市场类型
        stock_market = baostock_code_to_market(bs_code)

        # 步骤C：判断是否在目标市场列表中
        if stock_market not in market_type_list:
            continue  # 不在目标列表 → 跳过
        # ======================================================

        # 符合条件 → 加入结果集
        data_list.append(row)

    # 无数据处理
    if not data_list:
        logger.warning(f"[{func_name}] 未获取到任何符合市场条件的股票数据")
        return pd.DataFrame()

    # 构建最终DF
    raw_df = pd.DataFrame(data_list, columns=fields)
    logger.info(f"[{func_name}] 原生数据处理完成 | 最终数据量: {len(raw_df)}")

    return raw_df

# ==================== 内部函数 - 步骤3: 数据清洗 ====================
def _clean_data(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    清洗原生股票基础数据，严格匹配 stock_basic 表结构
    适配 baostock query_stock_basic 接口 + 数据库表定义
    
    数据库表字段：
    std_stock_code, stock_name, pure_symbol, industry, market,
    list_date, delist_date, is_active

    Args:
        raw_df: 原生数据DataFrame

    Returns:
        清洗后的DataFrame（可直接入库）
    """
    func_name = "_clean_data"
    logger.debug(f"[{func_name}] 开始清洗股票基础数据")

    if raw_df.empty:
        return pd.DataFrame()

    cleaned_df = raw_df.copy()

    # -------------------- 1. 字段映射（官方接口 → 数据库字段） --------------------
    field_mapping = {
        "code": "std_stock_code",    # 股票代码（主键）
        "code_name": "stock_name",   # 股票名称
        "ipoDate": "list_date",      # 上市日期
        "outDate": "delist_date",    # 退市日期
        "status": "is_active"       # 是否上市
    }

    # 安全保留存在的字段，避免 KeyError
    valid_keys = [k for k in field_mapping.keys() if k in cleaned_df.columns]
    cleaned_df = cleaned_df[valid_keys]
    cleaned_df.rename(columns=field_mapping, inplace=True)

    # -------------------- 2. 生成纯股票代码 pure_symbol --------------------
    # 从 sh.600000 → 提取 600000
    if "std_stock_code" in cleaned_df.columns:
        cleaned_df["pure_symbol"] = cleaned_df["std_stock_code"].apply(
            lambda x: x.split(".")[1] if isinstance(x, str) and "." in x else None
        )

    # -------------------- 3. 生成市场字段 market --------------------
    if "std_stock_code" in cleaned_df.columns:
        cleaned_df["market"] = cleaned_df["std_stock_code"].apply(
            lambda x: baostock_code_to_market(x).value  # 调用工具函数转换市场类型
        )
        cleaned_df["std_stock_code"] = cleaned_df["std_stock_code"].apply(convert_baostock_code) # 去除可能的空格
    # -------------------- 4. 行业字段（接口不提供，填空） --------------------
    cleaned_df["industry"] = ""

    # -------------------- 5. 日期格式化（DATE 类型） --------------------
    for col in ["list_date", "delist_date"]:
        if col in cleaned_df.columns:
            cleaned_df[col] = pd.to_datetime(
                cleaned_df[col],
                errors="coerce"
            ).dt.date  # 直接转 Python date 类型，完美匹配 MySQL date
            cleaned_df[col] = cleaned_df[col].where(cleaned_df[col].notna(), None)

    # -------------------- 6. 状态字段标准化（tinyint 1/0） --------------------
    if "is_active" in cleaned_df.columns:
        cleaned_df["is_active"] = cleaned_df["is_active"].map({
            "1": 1,   # 上市
            "0": 0    # 退市
        }).fillna(0).astype(int)

    # -------------------- 7. 去重 + 去空（主键必须非空） --------------------
    core_fields = ["std_stock_code", "stock_name", "pure_symbol", "market"]
    cleaned_df = cleaned_df.dropna(subset=core_fields)
    cleaned_df = cleaned_df.drop_duplicates(subset=["std_stock_code"], keep="last")

    # -------------------- 8. 只保留数据库表需要的字段 --------------------
    final_columns = [
        "std_stock_code",
        "stock_name",
        "pure_symbol",
        "industry",
        "market",
        "list_date",
        "delist_date",
        "is_active"
    ]
    cleaned_df = cleaned_df[final_columns]

    logger.info(f"[{func_name}] 数据清洗完成 | 清洗后数据量: {len(cleaned_df)}")
    return cleaned_df

# ==================== 内部函数 - 步骤4: 数据保存 ====================
def _save_data(conn, cleaned_df: pd.DataFrame) -> bool:
    """
    通过 data_manager 保存数据到 stock_basic 表，不直接执行 SQL
    【重构版】直接传入 DataFrame，不做数据处理，仅调用 DB 接口

    Args:
        conn: 数据库连接
        cleaned_df: 清洗后数据（已完全符合入库要求）

    Returns:
        保存结果
    """

    func_name = "_save_data"
    logger.debug(f"[{func_name}] 开始保存数据 | 待入库条数：{len(cleaned_df)}")

    # 空数据直接返回
    if cleaned_df.empty:
        logger.warning(f"[{func_name}] 数据为空，无需保存")
        return False

    try:
        # 直接创建管理器并传入 DataFrame
        data_manager = BasicStockDataManager(conn)
        return data_manager.batch_insert_stock_basic(cleaned_df)

    except Exception as e:
        logger.error(f"[{func_name}] 保存异常: {str(e)}", exc_info=True)
        return False


# ==================== 预留函数 ====================
def calculate_stock_code_purity(ts_code: str) -> str:
    logger.debug(f"预留函数调用: {ts_code}")
    return ts_code.split(".")[0] if "." in ts_code else ts_code

def convert_market_type_to_baostock_format(market_type: MarketType) -> str:
    return market_type.value

# ==================== 内部函数 - 保存股票固定顺序表 ====================
def _save_stock_fixed_seq(conn, stock_codes: List[str]) -> bool:
    """
    保存股票固定顺序表数据
    
    Args:
        conn: 数据库连接
        stock_codes: 股票代码列表，格式为 ['000001.SZ', '600000.SH', ...]
    
    Returns:
        保存是否成功
    """
    func_name = "_save_stock_fixed_seq"
    logger.debug(f"[{func_name}] 开始保存股票固定顺序表 | 股票数量: {len(stock_codes)}")
    
    try:
        # 步骤1: 清空现有表数据
        truncate_success = UnifiedDataManager.truncate_table_stock_fixed_seq(conn)
        if not truncate_success:
            logger.error(f"[{func_name}] 清空股票固定顺序表失败")
            return False
        
        # 步骤2: 准备数据格式
        # 转换为 (code,) 格式的元组列表
        stock_data = [(code,) for code in stock_codes]
        
        # 步骤3: 保存数据
        save_success = UnifiedDataManager.save_stock_fixed_seq(conn, stock_data)
        if save_success:
            logger.info(f"[{func_name}] 股票固定顺序表保存成功 | 保存数量: {len(stock_codes)}")
        else:
            logger.error(f"[{func_name}] 股票固定顺序表保存失败")
        
        return save_success
        
    except Exception as e:
        logger.error(f"[{func_name}] 保存股票固定顺序表异常: {str(e)}", exc_info=True)
        return False