-- 股票复权因子表
CREATE TABLE IF NOT EXISTS `stock_adjustment_factor` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `std_stock_code` VARCHAR(10) NOT NULL,
  `adjust_date` DATE NOT NULL,
  `fore_adjust_factor` DECIMAL(18,6) NOT NULL,
  `back_adjust_factor` DECIMAL(18,6) NOT NULL,
  `adjust_factor` DECIMAL(18,6) NOT NULL,
  `create_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `update_time` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_stock_date` (`std_stock_code`, `adjust_date`),
  INDEX `idx_adjust_date` (`adjust_date`),
  INDEX `idx_std_stock_code` (`std_stock_code`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='股票复权因子表';
