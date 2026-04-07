-- 股票固定顺序表 DDL
CREATE TABLE IF NOT EXISTS `stock_fixed_seq` (
  `id` INT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '固定顺序ID，下载顺序依据，永不修改',
  `std_stock_code` VARCHAR(20) NOT NULL COMMENT '标准股票代码，唯一',
  `create_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_stock_code` (`std_stock_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='股票固定顺序表 | 新股仅追加，不插入中间';