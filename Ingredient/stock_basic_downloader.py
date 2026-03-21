import baostock as bs
import pandas as pd
import time
from KitchenBase.download_utils import MarketType, logger, convert_baostock_code, baostock_code_to_market
from Ingredient.data_manager import BasicStockDataManager, get_existing_stock_codes_set

# ===================== 原有工具函数（保留不动） =====================
def _fetch_stock_codes(trading_day: str, exclude_types: list = None) -> list:
    """
    从 Baostock 获取股票列表，并过滤掉不需要的类型
    返回：原始格式股票代码列表，如 sh.600000
    """
    logger.debug(f"开始调用 bs.query_all_stock 查询 {trading_day} 的股票列表...")
    rs = bs.query_all_stock(day=trading_day)
    
    if rs.error_code != '0':
        logger.error(f"获取股票列表失败: {rs.error_msg}")
        return []

    exclude_types_set = set(exclude_types) if exclude_types else set()
    filtered_code_list = []
    
    while rs.error_code == '0' and rs.next():
        row = rs.get_row_data()
        if not row[0]:
            logger.warning(f"发现空代码: {row}")
            continue

        current_code = row[0]
        current_type = baostock_code_to_market(current_code)
        
        if current_type not in exclude_types_set:
            filtered_code_list.append(current_code)

    logger.info(f"成功获取 {len(filtered_code_list)} 个有效股票代码。")
    return filtered_code_list


def _map_row_list_to_dict(row_list: list, fields_list: list) -> dict:
    if len(row_list) != len(fields_list):
        logger.warning(f"数据列表长度与字段列表长度不匹配。")
        return {}
    return dict(zip(fields_list, row_list))


def _process_code_only_record(code: str) -> tuple:
    """
    第一部分专用：只处理【股票代码】相关字段，生成入库元组
    不处理任何详情字段（行业、上市日期等留空）
    """
    try:
        # 代码格式转换
        converted_code = convert_baostock_code(code)
        pure_symbol = code.split('.')[-1]
        market_type = baostock_code_to_market(code)
        market_display = market_type.value

        # 第一部分：只填充代码相关字段，其余留空
        return (
            converted_code,       # ts_code
            "",                   # code_name  （空）
            pure_symbol,          # pure_symbol
            "",                   # industry   （空）
            market_display,       # market
            None,                 # list_date  （空）
            None,                 # delist_date（空）
            1                     # is_active 默认上市
        )
    except Exception as e:
        logger.error(f"处理代码 {code} 出错: {e}")
        return None

def _process_and_prepare_db_record(row: dict) -> tuple:
    """
    将单条 Baostock 数据字典转换为数据库插入所需的元组。
    修复：ipoDate / outDate 大写字段，确保日期正常写入
    """
    try:
        market_type = baostock_code_to_market(row.get('code', ''))
        market_display = market_type.value

        # ======================= 修复点 =======================
        # baostock 原始返回字段是：ipoDate、outDate（必须大写开头）
        list_date = row.get('ipoDate', '') or None
        delist_date = row.get('outDate', '') or None
        # ======================================================

        is_active = 1 if row.get('status', '') == '1' else 0
        converted_code = convert_baostock_code(row.get('code', ''))
        pure_symbol = row.get('code', '').split('.')[-1]

        return (
            converted_code,
            row.get('code_name', ''),
            pure_symbol,
            row.get('industry', ''),
            market_display,
            list_date,
            delist_date,
            is_active
        )
    except Exception as e:
        logger.error(f"处理股票 {row.get('code', 'UNKNOWN')} 数据时出错: {e}")
        return None

# ===================== 核心新函数：第一部分 =====================
def refresh_stock_code_list(
    conn,
    trading_day: str = "2026-03-17",
    exclude_types=[
        MarketType.INDEX,
        MarketType.ETF,
        MarketType.LOF,
        MarketType.REIT,
        MarketType.CONVERTIBLE_BOND,
        MarketType.SH_B_STOCK,
        MarketType.SZ_B_STOCK,
        MarketType.UNKNOWN
    ]
):
    """
    第一部分：刷新股票代码列表（全量覆盖，无断点续传）
    1. 获取最新股票代码列表
    2. 过滤无效类型
    3. 写入数据库 stock_basic 表（仅代码字段）
    4. 每次全量更新
    """
    logger.info("===== 开始刷新股票代码列表（全量覆盖） =====")
    basic_manager = BasicStockDataManager(conn)

    # 1. 获取最新、合法的股票代码
    valid_codes = _fetch_stock_codes(trading_day, exclude_types)
    if not valid_codes:
        logger.error("未获取到任何有效股票代码，退出")
        return

    # 2. 转换为数据库入库格式（仅代码）
    logger.info("开始转换股票代码为数据库格式...")
    batch_records = []
    for code in valid_codes:
        record = _process_code_only_record(code)
        if record:
            batch_records.append(record)

    # 3. 批量写入数据库（使用 data_manager）
    if batch_records:
        logger.info(f"准备写入 {len(batch_records)} 条股票代码到数据库...")
        success = basic_manager.batch_insert_stock_basic(batch_records)
        if success:
            logger.info(f"✅ 股票代码刷新完成，共写入 {len(batch_records)} 条")
        else:
            logger.error("❌ 股票代码写入数据库失败")
    else:
        logger.warning("无有效代码可写入")

    logger.info("===== 股票代码列表刷新完成 =====")

# ===================== 第二部分：下载股票详细信息 =====================
def download_stock_details(
    conn,
    download_groups: list[str] = ["all"]
):
    """
    第二部分：下载股票详细字段（行业、上市日期、名称等）
    严格基于第一部分已入库的股票代码，支持断点续传 + 分组下载
    """
    logger.info("===== 开始下载股票详细信息（断点续传 + 分组模式）=====")
    basic_manager = BasicStockDataManager(conn)

    # ============= 1. 从数据库读取【第一部分写入的股票白名单】=============
    # 这是最关键：只下载这里面的股票
    valid_stock_codes = basic_manager.get_existing_stock_codes_set()
    if not valid_stock_codes:
        logger.error("数据库中无股票代码，请先运行 refresh_stock_code_list！")
        return
    logger.info(f"读取到白名单股票：{len(valid_stock_codes)} 只")

    # ============= 2. 断点续传：筛选出【详情为空】的股票 =============
    need_fill_codes = basic_manager.get_need_fill_detail_codes()  # 核心修改点

    if not need_fill_codes:
        logger.info("✅ 所有股票详情已下载完成，无需操作")
        return
    logger.info(f"待补全详情股票：{len(need_fill_codes)} 只")

    # ============= 3. 分组处理逻辑（all / sh / sz / bj）=============
    target_groups = []
    if "all" in download_groups:
        target_groups = [("all", None)]
    else:
        valid_market = ["sh", "sz", "bj"]
        target_groups = [(m, m) for m in download_groups if m in valid_market]

    if not target_groups:
        logger.error("无效分组，退出")
        return

    # ============= 4. 按分组批量下载详情 =============
    for group_name, query_param in target_groups:
        logger.info(f"\n=== 处理分组：{group_name.upper()} ===")

        # 调用 baostock 批量查询
        try:
            if query_param is None:
                logger.info("查询全市场股票详情...")
                rs = bs.query_stock_basic()
            else:
                logger.info(f"查询 {group_name} 市场股票详情...")
                rs = bs.query_stock_basic(code=query_param)

            if rs.error_code != "0":
                logger.error(f"查询失败：{rs.error_msg}")
                continue
        except Exception as e:
            logger.error(f"接口异常：{e}")
            continue

        # 解析数据
        update_records = []
        while rs.next():
            row = _map_row_list_to_dict(rs.get_row_data(), rs.fields)
            raw_code = row.get("code", "")
            std_code = convert_baostock_code(raw_code)

            # 双重校验：必须在白名单 + 必须未下载详情
            if std_code not in valid_stock_codes:
                continue
            if std_code not in need_fill_codes:
                continue

            # 转换为入库格式
            record = _process_and_prepare_db_record(row)
            if record:
                update_records.append(record)

        # 批量更新数据库
        if update_records:
            logger.info(f"分组 {group_name} 准备更新 {len(update_records)} 条记录")
            basic_manager.batch_insert_stock_basic(update_records)
            logger.info(f"✅ 分组 {group_name} 处理完成")
        else:
            logger.info(f"分组 {group_name} 无需要更新的数据")

    logger.info("\n===== 🎉 股票详细信息全部下载完成 =====")