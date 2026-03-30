/* ====================== 2. 股票基础信息（核心回测数据） ====================== */
CREATE TABLE IF NOT EXISTS `stock_basic` (
  `std_stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `stock_name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `pure_symbol` varchar(10) DEFAULT NULL COMMENT '纯股票代码（不含交易所后缀）',
  `industry` varchar(50) DEFAULT NULL COMMENT '行业分类',
  `market` varchar(20) DEFAULT NULL COMMENT '市场板块',
  `list_date` date DEFAULT NULL COMMENT '上市日期',
  `delist_date` date DEFAULT NULL COMMENT '退市日期',
  `is_active` tinyint(1) DEFAULT 1 COMMENT '是否活跃（1-活跃，0-已退市）',
  `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`std_stock_code`),
  INDEX `idx_market` (`market`),
  INDEX `idx_list_date` (`list_date`),
  INDEX `idx_is_active` (`is_active`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票基础信息表';