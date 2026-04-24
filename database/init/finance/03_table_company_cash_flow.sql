/* ====================== 公司现金流量数据表 ====================== */
CREATE TABLE IF NOT EXISTS `company_cash_flow` (
    `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `std_stock_code` varchar(20) NOT NULL COMMENT '股票代码',
    `pub_date` date NOT NULL COMMENT '公司发布财报的日期',
    `stat_date` date NOT NULL COMMENT '财报统计的季度的最后一天',
    `cato_asset` decimal(10,4) COMMENT '流动资产占总资产比例(%)',
    `ncato_asset` decimal(10,4) COMMENT '非流动资产占总资产比例(%)',
    `tangible_asset_to_asset` decimal(10,4) COMMENT '有形资产占总资产比例(%)',
    `ebit_to_interest` decimal(10,4) COMMENT '已获利息倍数(倍)',
    `cfo_to_or` decimal(10,4) COMMENT '经营活动现金流净额/营业收入(%)',
    `cfo_to_np` decimal(10,4) COMMENT '经营活动现金流净额/净利润(%)',
    `cfo_to_gr` decimal(10,4) COMMENT '经营活动现金流净额/营业总收入(%)',
    `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_std_stock_stat_date` (`std_stock_code`, `stat_date`),
    INDEX `idx_std_stock_code` (`std_stock_code`),
    INDEX `idx_stat_date` (`stat_date`),
    INDEX `idx_date_range` (`std_stock_code`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='公司现金流量数据表';
