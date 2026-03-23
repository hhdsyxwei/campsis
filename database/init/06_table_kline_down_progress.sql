CREATE TABLE `kline_download_progress` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `quarter` varchar(6) NOT NULL COMMENT '季度 2024Q1',
  `data_type` varchar(10) NOT NULL DEFAULT '5min_kline' COMMENT '数据类型',
  `data_source` varchar(20) NOT NULL DEFAULT 'baostock' COMMENT '数据源',
  `last_time` datetime NOT NULL COMMENT '最后成功下载时间',
  `status` tinyint NOT NULL DEFAULT '0' COMMENT '0未开始 1下载中 2完成 3失败',
  `error_msg` varchar(500) DEFAULT NULL COMMENT '错误信息',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_stock_quarter_type` (`stock_code`,`quarter`,`data_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='5分钟K线下载进度表';