# dm_db_init.py
import os
import pymysql
from typing import Dict
from KitchenBase.download_utils import get_project_root
from KitchenBase.logger_config import get_logger
from .dm_utils import _get_sql_statements_from_file, _execute_sql_statements
from .dm_config import DB_CONFIG

logger = get_logger(__name__)

def create_database_if_not_exists():
    func_name = "create_database_if_not_exists"
    config_no_db = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
    try:
        conn = pymysql.connect(**config_no_db)
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} DEFAULT CHARACTER SET utf8mb4")
        conn.close()
        logger.info(f"[{__name__}.{func_name}] 数据库确认完成")
    except pymysql.OperationalError as e:
        logger.error(f"[{__name__}.{func_name}] 连接MySQL失败：{str(e)}")
        raise
    return pymysql.connect(**DB_CONFIG)

def create_all_tables_if_not_exist(conn) -> bool:
    """
    遍历内部字典（表名→路径），依次执行所有 SQL 脚本创建库表
    :param conn: 数据库连接
    :return: 全部成功返回 True
    """
    func_name = "create_all_tables_if_not_exist"

    prj_dir = get_project_root()
    database_dir = os.path.join(prj_dir, "database")

    # 采用字典类型存储 SQL 路径，以便手动添加新的表初始化脚本
    # ===================== 【字典类型】SQL 路径常量 =====================
    SQL_FILE_MAP: Dict[str, str] = {
        # 库
        # "database": "./init/00_database.sql",
        # 基础表
        "trade_date_map": f"{database_dir}/init/01_table_trade_date_map.sql.j2",
        "stock_basic": f"{database_dir}/init/02_table_stock_basic.sql.j2",
        "stock_daily": f"{database_dir}/init/03_table_stock_daily.sql.j2",
        "stock_xrxd": f"{database_dir}/init/04_table_stock_xrxd.sql.j2",
        # "kline_1min": "./init/04_table_kline_1min.sql",
        # 统一K线表
        "kline_unified": f"{database_dir}/init/UnifiedKLine/01_table_kline_unified.sql.j2",
        "kline_block_status": f"{database_dir}/init/UnifiedKLine/02_table_kline_block_status.sql.j2",
        "stock_fixed_seq": f"{database_dir}/init/UnifiedKLine/03_stock_fixed_seq.sql.j2",
        "global_dl_ctrl_block": f"{database_dir}/init/UnifiedKLine/04_global_dl_ctrl_block.sql.j2",
        "download_task_config": f"{database_dir}/init/UnifiedKLine/05_download_task_config.sql.j2",
    }

    cursor = None
    overall_success = True

    try:
        cursor = conn.cursor()
        logger.info(f"[{func_name}] 开始执行 {len(SQL_FILE_MAP)} 个库表初始化脚本")

        # 遍历字典（表名 → 路径）
        for action_name, sql_path in SQL_FILE_MAP.items():
            logger.info(f"[{func_name}] 正在初始化：{action_name}")

            # 1. 从文件获取 SQL 语句
            statements = _get_sql_statements_from_file(sql_path)
            if not statements:
                logger.error(f"[{func_name}] 获取 {action_name} SQL 语句失败，跳过该表")
                overall_success = False
                continue

            # 2. 执行 SQL 语句
            success = _execute_sql_statements(conn, cursor, statements, action_name)
            if not success:
                overall_success = False
            else:
                logger.info(f"[{func_name}] 初始化完成：{action_name}")

    except Exception as e:
        logger.error(f"[{func_name}] 整体异常：{str(e)}")
        overall_success = False
        if conn:
            conn.rollback()

    finally:
        if cursor:
            cursor.close()

    logger.info(f"[{func_name}] 全部执行完毕，结果：{'成功' if overall_success else '失败'}")
    return overall_success

def create_database_and_tables() -> bool:
    func_name = "create_database_and_tables"
    try:
        conn = create_database_if_not_exists()
        if create_all_tables_if_not_exist(conn):
            logger.info(f"[{__name__}.{func_name}] ✅ 数据库初始化全部完成")
            return conn
        else:
            conn.close()
            raise RuntimeError("数据库表初始化失败")
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] ❌ 数据库初始化失败：{str(e)}")
        raise e
