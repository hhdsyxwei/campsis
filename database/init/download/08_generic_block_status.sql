/* ====================== 8. 通用区块状态管理表 ====================== */
CREATE TABLE IF NOT EXISTS `generic_block_status` (
  -- 区块标识字段（最多3个，支持联合主键）
  `block_key_1` VARCHAR(50) NOT NULL COMMENT '区块主键字段1（如：股票代码、任务类型等）',
  `block_key_2` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '区块主键字段2（如：时间周期、年份等）',
  `block_key_3` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '区块主键字段3（如：季度、日期等）',
  
  -- 区块元信息
  `block_name` VARCHAR(100) DEFAULT NULL COMMENT '区块名称（可读性描述）',
  `task_type` VARCHAR(50) NOT NULL COMMENT '任务类型（如：kline、industry、xrxd、daily等）',
  
  -- 核心状态字段（4种状态）
  `status` ENUM('not_completed', 'skipped', 'completed', 'error') 
    NOT NULL DEFAULT 'not_completed' 
    COMMENT '状态：not_completed-未完成，skipped-已跳过，completed-已完成，error-下载异常',
  
  -- 统计信息
  `total_items` INT UNSIGNED DEFAULT 0 COMMENT '区块内总项目数',
  `success_count` INT UNSIGNED DEFAULT 0 COMMENT '成功处理数量',
  `fail_count` INT UNSIGNED DEFAULT 0 COMMENT '失败处理数量',
  
  -- 时间戳
  `completed_at` TIMESTAMP NULL COMMENT '完成时间',
  `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  -- 错误信息
  `error_message` TEXT DEFAULT NULL COMMENT '错误信息（status=error时记录）',
  `retry_count` TINYINT UNSIGNED DEFAULT 0 COMMENT '重试次数',
  
  -- 扩展字段
  `extra_data` JSON DEFAULT NULL COMMENT '扩展数据（不同区块类型可存储不同信息）',
  
  -- 联合主键：支持1-3个字段
  PRIMARY KEY (`block_key_1`, `block_key_2`, `block_key_3`, `task_type`),
  
  -- 索引
  INDEX `idx_status` (`status`),
  INDEX `idx_task_type` (`task_type`),
  INDEX `idx_status_type` (`status`, `task_type`),
  INDEX `idx_updated_at` (`updated_at`)
  
) ENGINE=InnoDB 
DEFAULT CHARSET=utf8mb4 
COLLATE=utf8mb4_unicode_ci 
COMMENT='通用区块状态管理表 | 支持最多3字段联合主键 | 4种状态：not_completed/skipped/completed/error';