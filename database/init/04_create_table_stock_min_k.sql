/* ====================== 3. 股票分钟级行情表（核心回测数据） ====================== */
DROP TABLE IF EXISTS stock_min_kline;
CREATE TABLE stock_min_kline (
    -- 主键（自增，用于唯一标识每条记录）
    id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    -- 核心标识字段
    code VARCHAR(20) NOT NULL COMMENT '证券代码，格式：sh.600000 / sz.000001',
    frequency TINYINT NOT NULL COMMENT 'K线频率：5=5分钟，15=15分钟，30=30分钟，60=60分钟',
    -- 时间字段（拆分存储，方便查询）
    trade_date DATE NOT NULL COMMENT '交易日期，格式：YYYY-MM-DD',
    trade_time DATETIME NOT NULL COMMENT '完整交易时间（date+time），格式：YYYY-MM-DD HH:MM:SS',
    raw_time VARCHAR(17) NOT NULL COMMENT 'Baostock原生时间，格式：YYYYMMDDHHMMSSsss',
    -- 价格字段（精度匹配Baostock返回值：小数点后4位）
    open DECIMAL(10,4) NOT NULL COMMENT '开盘价（元）',
    high DECIMAL(10,4) NOT NULL COMMENT '最高价（元）',
    low DECIMAL(10,4) NOT NULL COMMENT '最低价（元）',
    close DECIMAL(10,4) NOT NULL COMMENT '收盘价（元）',
    -- 成交量/金额字段
    volume BIGINT UNSIGNED NOT NULL COMMENT '成交数量（股）',
    amount DECIMAL(16,4) NOT NULL COMMENT '成交金额（元）',
    -- 复权字段
    adjustflag TINYINT NOT NULL COMMENT '复权状态：1=前复权，2=后复权，3=不复权',
    -- 扩展字段（预留）
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '数据入库时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '数据更新时间',
    -- 主键约束
    PRIMARY KEY (id),
    -- 联合唯一索引：避免同一股票+同一频率+同一时间重复存储
    UNIQUE KEY uk_code_freq_time (code, frequency, trade_time),
    -- 核心查询索引：按股票+频率+日期范围查询（回测高频场景）
    KEY idx_code_freq_date (code, frequency, trade_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='A股分钟级K线数据表（5/15/30/60分钟）';