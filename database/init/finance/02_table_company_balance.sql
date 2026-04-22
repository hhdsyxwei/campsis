/* ====================== 公司偿债能力数据表 ====================== */
CREATE TABLE IF NOT EXISTS `company_balance` (
    `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `std_stock_code` varchar(20) NOT NULL COMMENT '股票代码',
    `pub_date` date NOT NULL COMMENT '公司发布财报的日期',
    `stat_date` date NOT NULL COMMENT '财报统计的季度的最后一天',
    `current_ratio` decimal(10,4) COMMENT '流动比率',
    `quick_ratio` decimal(10,4) COMMENT '速动比率',
    `cash_ratio` decimal(10,4) COMMENT '现金比率',
    `yoy_liability` decimal(10,4) COMMENT '总负债同比增长率(%)',
    `liability_to_asset` decimal(10,4) COMMENT '资产负债率(%)',
    `asset_to_equity` decimal(10,4) COMMENT '权益乘数',
    `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_std_stock_stat_date` (`std_stock_code`, `stat_date`),
    INDEX `idx_std_stock_code` (`std_stock_code`),
    INDEX `idx_stat_date` (`stat_date`),
    INDEX `idx_date_range` (`std_stock_code`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='公司偿债能力数据表';
