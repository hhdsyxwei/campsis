/* ====================== 6. 股票行业分类（当前快照） ====================== */
CREATE TABLE IF NOT EXISTS `stock_industry` (
  `std_stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `stock_name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `industry` varchar(100) DEFAULT NULL COMMENT '行业名称（如：银行）',
  `industry_classification` varchar(100) DEFAULT NULL COMMENT '行业分类（如：金融业/银行业）',
  `industry_source` varchar(50) DEFAULT 'baostock' COMMENT '行业分类来源',
  `update_date` date DEFAULT NULL COMMENT '数据更新日期（每周一更新）',
  `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`std_stock_code`),
  INDEX `idx_industry` (`industry`),
  INDEX `idx_industry_classification` (`industry_classification`),
  INDEX `idx_update_date` (`update_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票行业分类表（当前快照，每周全量更新）';