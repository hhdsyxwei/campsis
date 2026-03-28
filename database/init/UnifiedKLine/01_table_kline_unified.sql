-- 统一K线数据表 - 按季度分区设计（精简版含索引及详细注释）
-- 设计目的：存储多种时间周期的K线数据，支持按季度查询和管理
-- 配合kline_download_progress表实现断点续传和防重复下载
CREATE TABLE IF NOT EXISTS `kline_unified_quarterly_extended` (
    -- 核心标识字段
    `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码，如AAPL、MSFT等',
    `time_frame` VARCHAR(20) NOT NULL COMMENT '时间周期，定义K线的时间间隔',
    `timestamp` DATETIME NOT NULL COMMENT 'K线时间戳，精确到秒，用于确定K线的时间点',
    
    -- OHLCV数据字段
    `open_price` DECIMAL(10, 4) NOT NULL COMMENT '开盘价，精确到万分位',
    `high_price` DECIMAL(10, 4) NOT NULL COMMENT '最高价，精确到万分位',
    `low_price` DECIMAL(10, 4) NOT NULL COMMENT '最低价，精确到万分位',
    `close_price` DECIMAL(10, 4) NOT NULL COMMENT '收盘价，精确到万分位',
    `volume` BIGINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '成交量，单位股',
    `turnover` DECIMAL(20, 4) NOT NULL DEFAULT 0.0000 COMMENT '成交额，单位元，精确到万分位',
    
    -- 时间戳字段
    `create_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间，自动填充',
    `update_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间，自动维护',
    
    -- 主键：股票代码+时间周期+时间戳的三元组，确保数据唯一性
    -- 此设计与kline_download_progress表配合，实现按季度单元的精确控制
    PRIMARY KEY (`stock_code`, `time_frame`, `timestamp`),
    
    -- 索引：优化常见查询模式
    INDEX `idx_timeframe_timestamp` (`time_frame`, `timestamp`) COMMENT '按时间周期和时间戳查询的复合索引',
    INDEX `idx_timestamp` (`timestamp`) COMMENT '按时间戳范围查询的索引'
) 
ENGINE=InnoDB 
DEFAULT CHARSET=utf8mb4 
COLLATE=utf8mb4_unicode_ci 
COMMENT='统一K线数据表 - 按季度分区，精简设计，支持多种时间周期，与kline_download_progress表配合实现断点续传和防重复下载'
-- 按timestamp进行范围分区，预设2024-2028年分区，便于按季度查询和管理数据生命周期
-- 分区策略：按时间戳范围划分，每个季度一个分区，与下载单元保持一致
PARTITION BY RANGE COLUMNS(`timestamp`) (
    -- 2024年季度分区
    PARTITION `p2024_q1` VALUES LESS THAN ('2024-04-01 00:00:00') COMMENT '2024年第一季度分区：1-3月数据',
    PARTITION `p2024_q2` VALUES LESS THAN ('2024-07-01 00:00:00') COMMENT '2024年第二季度分区：4-6月数据',
    PARTITION `p2024_q3` VALUES LESS THAN ('2024-10-01 00:00:00') COMMENT '2024年第三季度分区：7-9月数据',
    PARTITION `p2024_q4` VALUES LESS THAN ('2025-01-01 00:00:00') COMMENT '2024年第四季度分区：10-12月数据',
    
    -- 2025年季度分区
    PARTITION `p2025_q1` VALUES LESS THAN ('2025-04-01 00:00:00') COMMENT '2025年第一季度分区：1-3月数据',
    PARTITION `p2025_q2` VALUES LESS THAN ('2025-07-01 00:00:00') COMMENT '2025年第二季度分区：4-6月数据',
    PARTITION `p2025_q3` VALUES LESS THAN ('2025-10-01 00:00:00') COMMENT '2025年第三季度分区：7-9月数据',
    PARTITION `p2025_q4` VALUES LESS THAN ('2026-01-01 00:00:00') COMMENT '2025年第四季度分区：10-12月数据',
    
    -- 2026年季度分区
    PARTITION `p2026_q1` VALUES LESS THAN ('2026-04-01 00:00:00') COMMENT '2026年第一季度分区：1-3月数据',
    PARTITION `p2026_q2` VALUES LESS THAN ('2026-07-01 00:00:00') COMMENT '2026年第二季度分区：4-6月数据',
    PARTITION `p2026_q3` VALUES LESS THAN ('2026-10-01 00:00:00') COMMENT '2026年第三季度分区：7-9月数据',
    PARTITION `p2026_q4` VALUES LESS THAN ('2027-01-01 00:00:00') COMMENT '2026年第四季度分区：10-12月数据',
    
    -- 2027年季度分区
    PARTITION `p2027_q1` VALUES LESS THAN ('2027-04-01 00:00:00') COMMENT '2027年第一季度分区：1-3月数据',
    PARTITION `p2027_q2` VALUES LESS THAN ('2027-07-01 00:00:00') COMMENT '2027年第二季度分区：4-6月数据',
    PARTITION `p2027_q3` VALUES LESS THAN ('2027-10-01 00:00:00') COMMENT '2027年第三季度分区：7-9月数据',
    PARTITION `p2027_q4` VALUES LESS THAN ('2028-01-01 00:00:00') COMMENT '2027年第四季度分区：10-12月数据',
    
    -- 2028年季度分区
    PARTITION `p2028_q1` VALUES LESS THAN ('2028-04-01 00:00:00') COMMENT '2028年第一季度分区：1-3月数据',
    PARTITION `p2028_q2` VALUES LESS THAN ('2028-07-01 00:00:00') COMMENT '2028年第二季度分区：4-6月数据',
    PARTITION `p2028_q3` VALUES LESS THAN ('2028-10-01 00:00:00') COMMENT '2028年第三季度分区：7-9月数据',
    PARTITION `p2028_q4` VALUES LESS THAN ('2029-01-01 00:00:00') COMMENT '2028年第四季度分区：10-12月数据',
    
    -- 未来数据分区，处理超出预设范围的数据
    PARTITION `p_future` VALUES LESS THAN MAXVALUE COMMENT '未来数据分区，处理超出预设范围的数据'
);
