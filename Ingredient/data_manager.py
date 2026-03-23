# data_manager.py
import pymysql
from pymysql.err import OperationalError
import pandas as pd
from KitchenBase.download_utils import logger, calculate_pre_close

# ================= 配置区域 =================
# 数据库连接配置，需要根据您的实际环境进行修改
DB_CONFIG = {
    'host': 'localhost',         # 数据库主机地址
    'port': 3306,                # 数据库端口号
    'user': 'root',              # 数据库用户名
    'password': 'ta225924',      # 数据库密码
    'database': 'ashare',        # 要连接的数据库名
    'charset': 'utf8mb4'         # 连接字符集，支持中文
}

class TradeDateMapManager:
    """交易日映射表管理器：仅负责trade_date_map表的入库操作"""
    def __init__(self, conn):
        self.conn = conn

    def save_trade_date_map(self, df: pd.DataFrame) -> bool:
        """
        将清洗后的交易日DataFrame批量保存到trade_date_map表
        :param df: 清洗后的交易日数据DataFrame，包含calendar_date(date)、is_trading_day(int)
        :return: 成功返回True，失败返回False
        """
        current_func = self.save_trade_date_map.__name__
        if df.empty:
            logger.warning(f"[{current_func}] 空的交易日数据，无需保存")
            return True

        # 将DataFrame转为数据库插入的元组列表
        records = []
        for _, row in df.iterrows():
            records.append((
                row['calendar_date'],
                row['is_trading_day']
            ))

        cursor = None
        try:
            cursor = self.conn.cursor()
            # 批量插入/更新（主键冲突时更新is_trading_day）
            sql = """
            INSERT INTO trade_date_map (calendar_date, is_trading_day)
            VALUES (%s, %s)
            ON DUPLICATE KEY UPDATE
                is_trading_day = VALUES(is_trading_day)
            """
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.info(f"[{current_func}] 成功保存{len(records)}条交易日数据到trade_date_map表")
            return True
        except Exception as e:
            logger.error(f"[{current_func}] 保存交易日数据失败：{e}")
            self.conn.rollback()
            return False
        finally:
            if cursor:
                cursor.close()

class DailyDataManager:
    """日线数据管理器，封装对 stock_daily 表的读写操作"""

    def __init__(self, connection):
        self.conn = connection

    def save_daily_data(self, ts_code: str, baostock_rs) -> bool:
        """
        将 baostock 查询结果保存到数据库。
        Args:
            ts_code (str): 股票代码，例如 '000001.SZ'
            baostock_rs: baostock 的 ResultData 对象
        Returns:
            bool: 保存成功返回 True，否则返回 False
        """
        current_func = self.save_daily_data.__name__
        if baostock_rs is None or baostock_rs.error_code != '0':
            # ✅ 修复：增加错误日志
            logger.error(f"[{current_func}] 股票 {ts_code} baostock 查询失败，错误码：{baostock_rs.error_code if baostock_rs else 'None'}")
            return False

        data_list = []
        while baostock_rs.next():
            data_list.append(baostock_rs.get_row_data())

        logger.info(f"[{current_func}] 股票 {ts_code} 从 baostock 获取到 {len(data_list)} 条日线数据。")

        if not data_list:
            return True  # 无数据也算成功，只是没有记录要插入

        df = pd.DataFrame(data_list, columns=baostock_rs.fields)
        records = []

        for _, row in df.iterrows():
            try:
                trade_date = row['date']
                pre_close_val = calculate_pre_close(row['close'], row['pctChg'])
                records.append((
                    ts_code, trade_date,
                    float(row['open']) if row['open'] else None,
                    float(row['high']) if row['high'] else None,
                    float(row['low']) if row['low'] else None,
                    float(row['close']) if row['close'] else None,
                    pre_close_val,
                    float(row['pctChg']) if row['pctChg'] else None,
                    float(row['volume']) if row['volume'] else None,
                    float(row['amount']) if row['amount'] else None,
                    float(row['turn']) if row['turn'] else None,
                    float(row['peTTM']) if row['peTTM'] else None,
                    float(row['pbMRQ']) if row['pbMRQ'] else None,
                ))
            except ValueError as e:
                logger.warning(f"[{current_func}] 数据转换错误 {ts_code} {row['date']}: {e}")
                continue  # 跳过有问题的行

        if not records:
            return True

        cursor = self.conn.cursor()
        sql = """
        INSERT INTO stock_daily 
        (ts_code, trade_date, open, high, low, close, pre_close, change_rate, volume, amount, turnover_rate, pe, pb)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            open = VALUES(open), high = VALUES(high), low = VALUES(low), close = VALUES(close),
            pre_close = VALUES(pre_close), change_rate = VALUES(change_rate), volume = VALUES(volume),
            amount = VALUES(amount), turnover_rate = VALUES(turnover_rate), pe = VALUES(pe), pb = VALUES(pb)
        """
        try:
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.debug(f"[{current_func}] 股票 {ts_code} 插入成功，共 {len(records)} 条记录。")
            return True
        except Exception as e:
            logger.error(f"[{current_func}] 股票 {ts_code} 入库失败: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()

    def check_date_range_exists(self, ts_code: str, start_date: str = None, end_date: str = None) -> bool:
        """
        简化版校验逻辑：仅检查指定股票是否有任意一条数据，有则认为已下载。
        :param ts_code: 股票代码（如000001.SZ）
        :param start_date: 兼容原有参数（无实际作用）
        :param end_date: 兼容原有参数（无实际作用）
        :return: 存在数据返回True，否则False
        """
        current_func = self.check_date_range_exists.__name__
        cursor = None
        try:
            cursor = self.conn.cursor()
            # 仅查询该股票是否有任意一条数据
            sql = "SELECT 1 FROM stock_daily WHERE ts_code = %s LIMIT 1"
            cursor.execute(sql, (ts_code,))
            result = cursor.fetchone()

            if result:
                logger.info(f"[{current_func}] 股票 {ts_code} 数据库中已存在数据，无需重复下载")
                return True
            else:
                logger.info(f"[{current_func}] 股票 {ts_code} 数据库中无数据，需要下载")
                return False

        except Exception as e:
            logger.error(f"[{current_func}] 校验股票 {ts_code} 数据是否存在失败：{e}")
            return False  # 异常时默认认为未下载（避免漏下载）
        finally:
            if cursor:
                cursor.close()
            
    def get_active_stocks(self) -> list:
        """
        从数据库中查询所有仍在上市交易的股票代码列表
        """
        current_func = self.get_active_stocks.__name__
        cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute("""
                 SELECT ts_code FROM stock_basic 
                 WHERE market IN ('主板(深A)', '主板(沪A)', '科创板', '创业板', '北交所') 
                 AND is_active = 1
             """)
            stocks = cursor.fetchall()
            return [stock['ts_code'] for stock in stocks]
        finally:
            cursor.close()
            
    def get_stock_listing_date(self, ts_code: str) -> str:
        """
        获取指定股票的上市日期
        """
        current_func = self.get_stock_listing_date.__name__
        cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        try:
            cursor.execute("SELECT list_date FROM stock_basic WHERE ts_code = %s", (ts_code,))
            result = cursor.fetchone()
            if result and result['list_date']:
                return result['list_date'].strftime('%Y-%m-%d')
            return None
        finally:
            cursor.close()
            
    def get_latest_tradedate_for_stock(self, ts_code: str) -> str:
        """
        从数据库中查询指定股票的最新交易日期。
        如果没有找到任何数据，则返回 None。
        """
        current_func = self.get_latest_tradedate_for_stock.__name__
        cursor = self.conn.cursor(pymysql.cursors.DictCursor)
        try:
            sql = "SELECT MAX(trade_date) AS latest_date FROM stock_daily WHERE ts_code = %s"
            cursor.execute(sql, (ts_code,))
            result = cursor.fetchone()
            latest_date = result['latest_date']
            return latest_date.strftime('%Y-%m-%d') if latest_date else None
        except Exception as e:
            logger.error(f"[{current_func}] 查询股票 {ts_code} 的最新交易日期时出错: {e}")
            return None
        finally:
            cursor.close()


class BasicStockDataManager:
    """股票基础信息数据管理器，封装对 stock_basic 表的操作"""
    
    def __init__(self, connection):
        self.conn = connection
    
    # 原有方法保留，新增以下函数
    def get_need_fill_detail_codes(self) -> set:
        """
        获取需要补充详情的股票代码集合（code_name为空的股票）
        返回：ts_code 集合（如 {'600000.SH', '000001.SZ'}）
        """
        need_fill_codes = set()
        cursor = None
        try:
            cursor = self.conn.cursor()
            # ✅ 修复：按日期是否为空判断，而不是按名称是否为空判断
            cursor.execute("""
                SELECT ts_code FROM stock_basic
                WHERE list_date IS NULL OR list_date IS NULL
            """)
            # 提取结果为集合
            need_fill_codes = {row[0] for row in cursor.fetchall()}
            logger.info(f"查询到需要补充详情的股票数量：{len(need_fill_codes)}")
        except Exception as e:
            logger.error(f"获取需要补充详情的股票代码失败：{e}")
        finally:
            if cursor:
                cursor.close()
        return need_fill_codes

    def get_existing_stock_codes_set(self) -> set:
        """
        从数据库的 stock_basic 表中查询所有已存在的股票代码，返回一个集合。
        用于断点续传时快速判断哪些股票已经下载过。
        """
        current_func = self.get_existing_stock_codes_set.__name__
        cursor = self.conn.cursor(pymysql.cursors.SSCursor)  # 使用流式游标，防止数据量大时装入内存
        try:
            sql = "SELECT DISTINCT ts_code FROM stock_basic"
            cursor.execute(sql)
            existing_codes = {row[0] for row in cursor.fetchall()}
            logger.debug(f"[{current_func}] 从数据库中加载了 {len(existing_codes)} 个已存在的股票代码。")
            return existing_codes
        except Exception as e:
            logger.error(f"[{current_func}] 查询数据库中已存在的股票代码时出错: {e}")
            return set()
        finally:
            cursor.close()

    def batch_insert_stock_basic(self, records: list) -> bool:
        """
        批量插入股票基础信息到数据库
        Args:
            records: 元组列表，每个元组对应一条stock_basic记录
        Returns:
            bool: 插入成功返回True，失败返回False
        """
        current_func = self.batch_insert_stock_basic.__name__
        if not records:
            logger.warning(f"[{current_func}] 空的记录列表，无需插入")
            return True

        cursor = self.conn.cursor()
        sql = """
        INSERT INTO stock_basic 
        (ts_code, code_name, pure_symbol, industry, market, list_date, delist_date, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            code_name = VALUES(code_name),
            industry = VALUES(industry),
            market = VALUES(market),
            list_date = VALUES(list_date),
            delist_date = VALUES(delist_date),
            is_active = VALUES(is_active)
        """
        try:
            cursor.executemany(sql, records)
            self.conn.commit()
            logger.info(f"[{current_func}] 成功插入/更新 {len(records)} 条股票基础信息")
            return True
        except Exception as e:
            logger.error(f"[{current_func}] 批量插入股票基础信息失败: {e}")
            self.conn.rollback()
            return False
        finally:
            cursor.close()


def get_existing_stock_codes_set(conn) -> set:
    """兼容原有调用方式的封装函数"""
    current_func = get_existing_stock_codes_set.__name__
    logger.debug(f"[{current_func}] 调用BasicStockDataManager获取已存在的股票代码")
    return BasicStockDataManager(conn).get_existing_stock_codes_set()


def get_nearest_trade_date_before(conn, date_str: str) -> str:
    current_func = get_nearest_trade_date_before.__name__
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    try:
        # ✅ 修复：使用交易日历表，不依赖股票数据
        cursor.execute("""
            SELECT calendar_date FROM trade_date_map 
            WHERE calendar_date <= %s AND is_trading_day = 1
            ORDER BY calendar_date DESC LIMIT 1
        """, (date_str,))
        result = cursor.fetchone()
        
        if result and result['calendar_date']:
            return result['calendar_date'].strftime('%Y-%m-%d')
        else:
            logger.warning(f"[{current_func}] 无法找到 {date_str} 之前的交易日")
            return date_str
    finally:
        cursor.close()

def create_tables_if_not_exist(conn):
    """
    初始化数据库表结构
    :param conn: 数据库连接对象
    :return: 成功返回True，失败返回False
    """
    current_func = create_tables_if_not_exist.__name__
    db_name = DB_CONFIG['database']
    cursor = None
    try:
        # 选择数据库
        conn.select_db(db_name)
        
        cursor = conn.cursor()
        
        # 创建 stock_basic 表
        stock_basic_sql = """
        CREATE TABLE IF NOT EXISTS `stock_basic` (
          `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
          `code_name` varchar(100) DEFAULT NULL COMMENT '股票名称',
          `pure_symbol` varchar(10) DEFAULT NULL COMMENT '纯股票代码（不含交易所后缀）',
          `industry` varchar(50) DEFAULT NULL COMMENT '行业分类',
          `market` varchar(20) DEFAULT NULL COMMENT '市场板块',
          `list_date` date DEFAULT NULL COMMENT '上市日期',
          `delist_date` date DEFAULT NULL COMMENT '退市日期',
          `is_active` tinyint(1) DEFAULT 1 COMMENT '是否活跃（1-活跃，0-已退市）',
          `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
          `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
          PRIMARY KEY (`ts_code`),
          INDEX `idx_market` (`market`),
          INDEX `idx_list_date` (`list_date`),
          INDEX `idx_is_active` (`is_active`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票基础信息表';
        """
        
        # 创建 stock_daily 表
        stock_daily_sql = """
        CREATE TABLE IF NOT EXISTS `stock_daily` (
          `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
          `ts_code` varchar(20) NOT NULL COMMENT '股票代码',
          `trade_date` date NOT NULL COMMENT '交易日期',
          `open` decimal(10,3) DEFAULT NULL COMMENT '开盘价',
          `high` decimal(10,3) DEFAULT NULL COMMENT '最高价',
          `low` decimal(10,3) DEFAULT NULL COMMENT '最低价',
          `close` decimal(10,3) DEFAULT NULL COMMENT '收盘价',
          `pre_close` decimal(10,3) DEFAULT NULL COMMENT '前收盘价',
          `change_rate` decimal(10,4) DEFAULT NULL COMMENT '涨跌幅(%)',
          `volume` bigint(20) DEFAULT NULL COMMENT '成交量(手)',
          `amount` decimal(15,2) DEFAULT NULL COMMENT '成交额(千元)',
          `turnover_rate` decimal(10,4) DEFAULT NULL COMMENT '换手率(%)',
          `pe` decimal(12,2) DEFAULT NULL COMMENT '市盈率(TTM)',
          `pb` decimal(10,2) DEFAULT NULL COMMENT '市净率',
          `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
          `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
          PRIMARY KEY (`id`),
          UNIQUE KEY `uk_tscode_date` (`ts_code`,`trade_date`),
          INDEX `idx_ts_code` (`ts_code`),
          INDEX `idx_trade_date` (`trade_date`),
          INDEX `idx_date_range` (`ts_code`, `trade_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票日线数据表';
        """
        
        # 创建 trade_date_map 表
        trade_date_map_sql = """
        CREATE TABLE IF NOT EXISTS `trade_date_map` (
          `calendar_date` date NOT NULL COMMENT '日历日期',
          `is_trading_day` tinyint(1) DEFAULT 0 COMMENT '是否为交易日(1-是,0-否)',
          `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
          `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
          PRIMARY KEY (`calendar_date`),
          INDEX `idx_is_trading_day` (`is_trading_day`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='交易日历映射表';
        """
        
        # 执行建表语句
        cursor.execute(stock_basic_sql)
        logger.debug(f"[{current_func}] 执行stock_basic表创建SQL语句")
        
        cursor.execute(stock_daily_sql)
        logger.debug(f"[{current_func}] 执行stock_daily表创建SQL语句")
        
        cursor.execute(trade_date_map_sql)
        logger.debug(f"[{current_func}] 执行trade_date_map表创建SQL语句")
        
        conn.commit()
        logger.info(f"[{current_func}] 数据库 '{db_name}' 表结构初始化完成")
        return True
        
    except Exception as e:
        logger.error(f"[{current_func}] 初始化数据库表结构时出错: {e}")
        conn.rollback()
        return False
    finally:
        if cursor:
            cursor.close()


def create_database_if_not_exists():
    """
    自动创建 ashare 数据库（如果不存在），然后返回数据库连接
    全程使用你现有的 DB_CONFIG，无需修改配置
    """
    current_func = create_database_if_not_exists.__name__
    
    # ---------------------- 第一步：先连接 MySQL 服务，不指定库 ----------------------
    # 复制配置并临时去掉 database，避免"找不到库"报错
    config_no_db = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
    
    try:
        logger.debug(f"[{current_func}] 尝试连接MySQL服务（不指定数据库）")
        conn = pymysql.connect(**config_no_db)
        with conn.cursor() as cursor:
            logger.debug(f"[{current_func}] 创建数据库 '{DB_CONFIG['database']}'（如果不存在）")
            cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']} DEFAULT CHARACTER SET utf8mb4")
        conn.close()
        logger.debug(f"[{current_func}] 数据库连接已关闭")

    except OperationalError as e:
        logger.error(f"[{current_func}] 连接 MySQL 服务失败：{e}")
        raise

    # ---------------------- 第二步：使用完整配置连接 ashare 库 ----------------------
    try:
        logger.debug(f"[{current_func}] 尝试连接到 '{DB_CONFIG['database']}' 数据库")
        db_conn = pymysql.connect(**DB_CONFIG)
        logger.info(f"[{current_func}] 成功连接到 {DB_CONFIG['database']} 数据库")
        return db_conn

    except OperationalError as e:
        logger.error(f"[{current_func}] 连接 {DB_CONFIG['database']} 失败：{e}")
        raise

def create_database_and_tables():
    """
    创建数据库和表结构的综合函数，返回数据库连接对象
    """
    current_func = create_database_and_tables.__name__
    
    try:
        logger.info(f"[{current_func}] 开始创建数据库和表结构")
        conn = create_database_if_not_exists()
        logger.debug(f"[{current_func}] 数据库创建完成，开始创建表结构")
        
        if create_tables_if_not_exist(conn):
            logger.info(f"[{current_func}] 数据库和表结构创建成功")
            return conn
        else:
            logger.error(f"[{current_func}] 数据库表结构初始化失败")
            conn.close()
            raise Exception("数据库表结构初始化失败")
            
    except Exception as e:
        logger.error(f"[{current_func}] 创建数据库和表结构时出错: {e}")
        raise

# Ingredient/data_manager.py
# 在DataManager类中新增以下方法
def save_kline_5min_data(self, df, stock_code):
    """
    保存5分钟K线数据到数据库/文件
    
    Args:
        df (pd.DataFrame): 5分钟K线数据
        stock_code (str): 股票代码
    """
    # 1. 保存到CSV文件（可选）
    # csv_path = f"./data/kline_5min/{stock_code.replace('.', '_')}_{datetime.now().strftime('%Y%m%d')}.csv"
    # self._ensure_dir(csv_path)
    # df.to_csv(csv_path, index=False, encoding="utf-8")
    
    # 2. 保存到数据库（根据实际数据库架构实现）
    # 示例：使用SQLAlchemy保存到PostgreSQL/MySQL
    if self.db_engine:
        table_name = f"kline_5min_{stock_code.replace('.', '_')}"
        df.to_sql(
            name=table_name,
            con=self.db_engine,
            if_exists="append",
            index=False,
            chunksize=1000
        )
    print(f"[{stock_code}] 5分钟K线数据已保存")