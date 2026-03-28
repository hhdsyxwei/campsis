-- 全局进度指针表 DDL
CREATE TABLE IF NOT EXISTS `kline_download_progress` (
  `id` TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '固定为1，单条记录',
  `downloading_quarter` VARCHAR(10) NOT NULL DEFAULT '' COMMENT '当前下载的季度标识，格式：YYYY-QN',
  `downloading_stock_code` VARCHAR(20) NOT NULL DEFAULT '' COMMENT '当前下载的股票ID',
  `downloading_time_frame` VARCHAR(20) NOT NULL DEFAULT '5m' COMMENT '当前下载的K线的时间周期',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全局进度指针表 | 用于重启续传、单向推进';