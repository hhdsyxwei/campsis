# stock_basic_downloader.py
import baostock as bs
import pandas as pd
import time
from KitchenBase.download_utils import MarketType, convert_baostock_code, baostock_code_to_market
from Ingredient.data_manager import BasicStockDataManager, get_existing_stock_codes_set
from Ingredient.data_manager import DataManager as dm
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

# ===================== 工具函数 =====================
def _fetch_stock_codes(trading_day: str, exclude_types: list = None) -> list:
    func_name = "_fetch_stock_codes"
    start_time = time.time()  # 开始计时
    logger.debug(f"[{__name__}.{func_name}] 开始调用 bs.query_all_stock 查询 {trading_day} 的股票列表")
    
    rs = bs.query_all_stock(day=trading_day)
    
    if rs.error_code != '0':
        logger.error(f"[{__name__}.{func_name}] 获取股票列表失败: {rs.error_msg}")
        return []

    exclude_types_set = set(exclude_types) if exclude_types else set()
    filtered_code_list = []
    
    while rs.error_code == '0' and rs.next():
        row = rs.get_row_data()
        if not row[0]:
            logger.warning(f"[{__name__}.{func_name}] 发现空代码: {row}")
            continue

        current_code = convert_baostock_code(row[0])
        current_type = baostock_code_to_market(row[0])
        
        if current_type not in exclude_types_set:
            filtered_code_list.append(current_code)

    # 统计耗时
    cost_time = time.time() - start_time
    logger.info(f"[{__name__}.{func_name}] 成功获取 {len(filtered_code_list)} 个有效股票代码，总耗时：{cost_time:.2f}s")
    return filtered_code_list


def _map_row_list_to_dict(row_list: list, fields_list: list) -> dict:
    func_name = "_map_row_list_to_dict"
    if len(row_list) != len(fields_list):
        logger.warning(f"[{__name__}.{func_name}] 数据列表长度与字段列表长度不匹配")
        return {}
    return dict(zip(fields_list, row_list))

def _process_code_only_record(code: str) -> tuple:
    func_name = "_process_code_only_record"
    try:
        converted_code = code
        pure_symbol = code.split('.')[0] if '.' in code else code
        market_type = baostock_code_to_market(code)
        market_display = market_type.value

        return (
            converted_code,
            None,    # 改为 None，语义更清晰
            pure_symbol,
            None,    # 改为 None
            market_display,
            None,
            None,
            1
        )
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] 处理代码 {code} 出错: {str(e)}")
        return None


def _process_and_prepare_db_record(row: dict) -> tuple:
    func_name = "_process_and_prepare_db_record"
    try:
        market_type = baostock_code_to_market(row.get('code', ''))
        market_display = market_type.value

        list_date = row.get('ipoDate', '') or None
        delist_date = row.get('outDate', '') or None

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
        code = row.get('code', 'UNKNOWN')
        logger.error(f"[{__name__}.{func_name}] 处理股票 {code} 数据时出错: {str(e)}")
        return None

# ===================== 核心函数 =====================
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
    func_name = "refresh_stock_code_list"
    func_start = time.time()
    logger.info(f"[{__name__}.{func_name}] ===== 开始刷新股票代码列表（全量覆盖） =====")
    basic_manager = BasicStockDataManager(conn)

    step1_start = time.time()
    valid_codes = _fetch_stock_codes(trading_day, exclude_types)
    if not valid_codes:
        logger.error(f"[{__name__}.{func_name}] 未获取到任何有效股票代码，退出")
        return
    logger.info(f"[{__name__}.{func_name}][性能] 获取股票代码耗时：{time.time() - step1_start:.2f}s")

    if valid_codes:
        dm.truncate_table_stock_fixed_seq(conn)  # 清空自增序列表，准备全量覆盖
        dm.save_stock_fixed_seq(conn, valid_codes)  # 先保存到自增序列表，后续接口调用时会关联使用

    step2_start = time.time()
    logger.info(f"[{__name__}.{func_name}] 开始转换股票代码为数据库格式")
    batch_records = []
    for code in valid_codes:
        record = _process_code_only_record(code)
        if record:
            batch_records.append(record)
    logger.info(f"[{__name__}.{func_name}][性能] 代码格式转换耗时：{time.time() - step2_start:.2f}s，总计 {len(batch_records)} 条")

    if batch_records:
        step3_start = time.time()
        logger.info(f"[{__name__}.{func_name}] 准备写入 {len(batch_records)} 条股票代码到数据库")
        success = basic_manager.batch_insert_stock_basic(batch_records)
        write_cost = time.time() - step3_start
        speed = len(batch_records) / write_cost if write_cost > 0 else 0

        if success:
            logger.info(f"[{__name__}.{func_name}] 股票代码刷新完成，共写入 {len(batch_records)} 条")
            logger.info(f"[{__name__}.{func_name}][性能] 数据库写入耗时：{write_cost:.2f}s，速度：{speed:.0f} 条/秒")
        else:
            logger.error(f"[{__name__}.{func_name}] 股票代码写入数据库失败")
    else:
        logger.warning(f"[{__name__}.{func_name}] 无有效代码可写入")

    total_cost = time.time() - func_start
    logger.info(f"[{__name__}.{func_name}][性能] 函数总耗时：{total_cost:.2f}s")
    logger.info(f"[{__name__}.{func_name}] ===== 股票代码列表刷新完成 =====")

# ===================== 下载详情 =====================
def download_stock_details(
    conn,
    download_groups: list[str] = ["all"]
):
    func_name = "download_stock_details"
    func_start = time.time()
    logger.info(f"[{__name__}.{func_name}] ===== 开始下载股票详细信息（断点续传+分组模式） =====")
    basic_manager = BasicStockDataManager(conn)

    step1_start = time.time()
    valid_stock_codes = basic_manager.get_existing_stock_codes_set()
    if not valid_stock_codes:
        logger.error(f"[{__name__}.{func_name}] 数据库中无股票代码，请先运行 refresh_stock_code_list")
        return
    logger.info(f"[{__name__}.{func_name}] 读取到白名单股票：{len(valid_stock_codes)} 只")
    logger.info(f"[{__name__}.{func_name}][性能] 读取白名单耗时：{time.time() - step1_start:.2f}s")

    step2_start = time.time()
    need_fill_codes = basic_manager.get_need_fill_detail_codes()
    if not need_fill_codes:
        logger.info(f"[{__name__}.{func_name}] 所有股票详情已下载完成，无需操作")
        return
    logger.info(f"[{__name__}.{func_name}] 待补全详情股票：{len(need_fill_codes)} 只")
    logger.info(f"[{__name__}.{func_name}][性能] 筛选待补全股票耗时：{time.time() - step2_start:.2f}s")

    target_groups = []
    if "all" in download_groups:
        target_groups = [("all", None)]
    else:
        valid_market = ["sh", "sz", "bj"]
        target_groups = [(m, m) for m in download_groups if m in valid_market]

    if not target_groups:
        logger.error(f"[{__name__}.{func_name}] 无效分组，退出")
        return

    total_update = 0
    for group_name, query_param in target_groups:
        group_start = time.time()
        logger.info(f"\n[{__name__}.{func_name}] === 处理分组：{group_name.upper()} ===")

        api_start = time.time()
        try:
            if query_param is None:
                logger.info(f"[{__name__}.{func_name}] 查询全市场股票详情")
                rs = bs.query_stock_basic()
            else:
                logger.info(f"[{__name__}.{func_name}] 查询 {group_name} 市场股票详情")
                rs = bs.query_stock_basic(code=query_param)

            if rs.error_code != "0":
                logger.error(f"[{__name__}.{func_name}] 查询失败：{rs.error_msg}")
                continue
        except Exception as e:
            logger.error(f"[{__name__}.{func_name}] 接口异常：{str(e)}")
            continue
        logger.info(f"[{__name__}.{func_name}][性能] {group_name} API 请求耗时：{time.time() - api_start:.2f}s")

        parse_start = time.time()
        update_records = []
        while rs.next():
            row = _map_row_list_to_dict(rs.get_row_data(), rs.fields)
            raw_code = row.get("code", "")
            std_code = convert_baostock_code(raw_code)

            if std_code not in valid_stock_codes:
                continue
            if std_code not in need_fill_codes:
                continue

            record = _process_and_prepare_db_record(row)
            if record:
                update_records.append(record)
        logger.info(f"[{__name__}.{func_name}][性能] {group_name} 数据解析耗时：{time.time() - parse_start:.2f}s")

        if update_records:
            db_start = time.time()
            logger.info(f"[{__name__}.{func_name}] 分组 {group_name} 准备更新 {len(update_records)} 条记录")
            basic_manager.batch_insert_stock_basic(update_records)
            db_cost = time.time() - db_start
            speed = len(update_records) / db_cost if db_cost > 0 else 0
            logger.info(f"[{__name__}.{func_name}][性能] {group_name} 数据库写入耗时：{db_cost:.2f}s，速度：{speed:.0f} 条/秒")

            total_update += len(update_records)
            logger.info(f"[{__name__}.{func_name}] 分组 {group_name} 处理完成，耗时：{time.time() - group_start:.2f}s")
        else:
            logger.info(f"[{__name__}.{func_name}] 分组 {group_name} 无需要更新的数据")

    logger.info(f"\n[{__name__}.{func_name}][性能] 本次共更新 {total_update} 条详情记录")
    logger.info(f"[{__name__}.{func_name}][性能] 函数总耗时：{time.time() - func_start:.2f}s")
    logger.info(f"\n[{__name__}.{func_name}] ===== 🎉 股票详细信息全部下载完成 =====")