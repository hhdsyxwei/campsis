/* ====================== 8. 沪深300成分股表 ====================== */
CREATE TABLE IF NOT EXISTS `index_csi300_component` (
  `id` bigint(20) unsigned NOT NULL AUTO_INCREMENT COMMENT '主键ID',
  `std_stock_code` varchar(20) NOT NULL COMMENT '股票代码',
  `stock_name` varchar(100) DEFAULT NULL COMMENT '股票名称',
  `update_date` date DEFAULT NULL COMMENT '数据更新日期',
  `create_time` timestamp DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `update_time` timestamp DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_stock_code` (`std_stock_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='沪深300成分股表';
