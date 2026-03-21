/* ====================== 1. 交易日历（核心回测数据） ====================== */
CREATE TABLE IF NOT EXISTS `trade_date_map` (
  `calendar_date` date NOT NULL COMMENT '日历日期',
  `is_trading_day` tinyint(1) DEFAULT 0 COMMENT '是否为交易日(1-是,0-否)',
  `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`calendar_date`),
  INDEX `idx_is_trading_day` (`is_trading_day`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='交易日历映射表';