# dm_utils.py
import os
from typing import Any, List, Dict
import pymysql
from jinja2 import Template
from KitchenBase.download_utils import get_project_root
from KitchenBase.logger_config import get_logger

logger = get_logger(__name__)

def _get_sql_statements_from_file(
    sql_file_path: str,
    jinja_vars: Dict[str, Any] = None  # 模板变量（可选）
) -> List[str]:
    """
    增强升级版：支持 Jinja2 模板渲染的 SQL 文件读取器
    功能：
      1. 自动渲染 Jinja2 SQL 模板
      2. 多编码自动兼容（utf-8 / gbk / gb2312）
      3. 清洗 /* */ 多行注释、-- 行注释
      4. 按 ; 拆分 SQL 语句，过滤空语句
    :param sql_file_path: SQL 模板文件路径
    :param jinja_vars: Jinja 渲染变量（字典，可选）
    :return: 清洗后的可执行 SQL 语句列表
    """
    # 1. 检查文件是否存在
    if not os.path.exists(sql_file_path):
        logger.error(f"SQL 文件不存在：{sql_file_path}")
        return []

    # 2. 自动尝试多种编码读取文件内容
    encodings = ['utf-8', 'gbk', 'gb2312']
    sql_template_content = ""
    for encoding in encodings:
        try:
            with open(sql_file_path, 'r', encoding=encoding) as f:
                sql_template_content = f.read().strip()
            break
        except (UnicodeDecodeError, PermissionError) as e:
            logger.warning(f"编码 {encoding} 读取失败：{str(e)}")
            continue

    if not sql_template_content:
        logger.warning(f"SQL 文件内容为空/读取失败：{sql_file_path}")
        return []

    # ===================== 核心：Jinja2 模板渲染 =====================
    try:
        # 若没有传入变量，默认空字典
        render_vars = jinja_vars or {}
        
        # 方法1：直接渲染字符串（简单场景）
        sql_rendered = Template(sql_template_content).render(**render_vars)

        logger.info(f"Jinja2 模板渲染成功：{sql_file_path}")

    except Exception as e:
        logger.error(f"Jinja2 模板渲染失败：{str(e)}，文件：{sql_file_path}")
        return []
    # =================================================================

    # 3. 清洗注释
    # 移除 /* ... */ 多行注释
    import re
    sql_clean = re.sub(r'/\*[\s\S]*?\*/', '', sql_rendered)
    # 移除 -- 行注释
    sql_clean = re.sub(r'--.*?$', '', sql_clean, flags=re.MULTILINE)
    # 移除 # 行注释（MySQL 常用）
    sql_clean = re.sub(r'#.*?$', '', sql_clean, flags=re.MULTILINE)

    # 4. 按分号拆分，清洗空语句
    statements = []
    for stmt in sql_clean.split(';'):
        stmt_stripped = stmt.strip()
        if stmt_stripped:
            statements.append(stmt_stripped)

    logger.info(f"从 {sql_file_path} 解析出 {len(statements)} 条可执行 SQL")
    return statements

def _execute_sql_statements(conn, cursor, statements: List[str], action_name: str) -> bool:
    """
    批量执行 SQL 语句，自带事务提交/回滚
    :param conn: 数据库连接
    :param cursor: 游标
    :param statements: SQL 语句列表
    :param action_name: 操作名称
    :return: 执行成功 True / 失败 False
    """
    if not statements:
        return True

    try:
        for stmt in statements:
            cursor.execute(stmt)
        conn.commit()
        logger.info(f"执行 {action_name} SQL 成功，共 {len(statements)} 条语句")
        return True

    except pymysql.MySQLError as e:
        logger.error(f"执行{action_name} SQL 失败：{str(e)}")
        conn.rollback()
        return False

def get_nearest_trade_date_before(conn, date_str: str) -> str:
    func_name = "get_nearest_trade_date_before"
    cursor = None
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT calendar_date FROM trade_date_map 
            WHERE calendar_date <= %s AND is_trading_day = 1
            ORDER BY calendar_date DESC LIMIT 1
        """, (date_str,))
        res = cursor.fetchone()
        return res['calendar_date'].strftime('%Y-%m-%d') if res else date_str
    except Exception as e:
        logger.error(f"[{__name__}.{func_name}] 查询失败：{str(e)}")
        return date_str
    finally:
        if cursor:
            cursor.close()
