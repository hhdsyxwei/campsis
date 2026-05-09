/* ====================== 1. 公司利润数据表（核心财务数据） ====================== */
CREATE TABLE IF NOT EXISTS `company_profit` (
    `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
    `std_stock_code` varchar(20) NOT NULL COMMENT '股票代码',
    `pub_date` date NOT NULL COMMENT '公司发布财报的日期',
    `stat_date` date NOT NULL COMMENT '财报统计的季度的最后一天',
    `roe_avg` decimal(10,4) COMMENT '净资产收益率(%)',
    `np_margin` decimal(10,4) COMMENT '销售净利率(%)',
    `gp_margin` decimal(10,4) COMMENT '销售毛利率(%)',
    `net_profit` decimal(16,2) COMMENT '净利润(万元)',
    `eps_ttm` decimal(10,4) COMMENT '每股收益',
    `mb_revenue` decimal(16,2) COMMENT '主营营业收入(百万元)',
    `total_share` decimal(20,0) COMMENT '总股本(股数)',
    `liqa_share` decimal(20,0) COMMENT '流通股本(股数)',
    `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_std_stock_stat_date` (`std_stock_code`, `stat_date`),
    INDEX `idx_std_stock_code` (`std_stock_code`),
    INDEX `idx_stat_date` (`stat_date`),
    INDEX `idx_date_range` (`std_stock_code`, `stat_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='公司利润数据表';
