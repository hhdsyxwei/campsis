/* ====================== 7. 股票行业分类历史 ====================== */
CREATE TABLE IF NOT EXISTS `stock_industry_history` (
  `std_stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `stock_name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `industry` varchar(100) DEFAULT NULL COMMENT '行业名称',
  `industry_classification` varchar(100) DEFAULT NULL COMMENT '行业分类',
  `industry_source` varchar(50) DEFAULT 'baostock' COMMENT '行业分类来源',
  `update_date` date NOT NULL COMMENT '数据更新日期（来自Baostock的updateDate）',
  `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`std_stock_code`, `update_date`),  -- 联合主键
  INDEX `idx_industry` (`industry`),
  INDEX `idx_industry_classification` (`industry_classification`),
  INDEX `idx_update_date` (`update_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票行业分类历史表（记录Baostock返回的updateDate）';