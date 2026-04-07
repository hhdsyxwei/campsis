/* ====================== 3. 股票日线行情表（核心回测数据） ====================== */
CREATE TABLE IF NOT EXISTS `stock_daily` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `std_stock_code` varchar(20) NOT NULL COMMENT '股票代码',
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
  UNIQUE KEY `uk_std_stock_date` (`std_stock_code`,`trade_date`),
  INDEX `idx_std_stock_code` (`std_stock_code`),
  INDEX `idx_trade_date` (`trade_date`),
  INDEX `idx_date_range` (`std_stock_code`, `trade_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票日线数据表';