-- 全局下载控制块表 DDL
CREATE TABLE IF NOT EXISTS `global_dl_ctrl_block` (
  `id` TINYINT UNSIGNED NOT NULL AUTO_INCREMENT COMMENT '主键',
  `task_type` VARCHAR(20) NOT NULL COMMENT '任务类型（如：kline、xrxd、daily等）',
  `task_status` VARCHAR(32) DEFAULT NULL COMMENT '任务状态',
  `primary_pointer_name` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '主进度指示器名称（如：quarter、year、date等）',
  `primary_pointer_value` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '主进度指示器值（如：2024-Q1、2024、2024-01-01等）',
  `secondary_pointer_name` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '次级进度指示器名称（如：stock_code、code等）',
  `secondary_pointer_value` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '次级进度指示器值（如：sh.600000、000001.SZ等）',
  `tertiary_pointer_name` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '三级进度指示器名称（如：time_frame、period等）',
  `tertiary_pointer_value` VARCHAR(50) NOT NULL DEFAULT '' COMMENT '三级进度指示器值（如：5m、1h、1d等）',
  `startup_params` JSON DEFAULT NULL COMMENT '启动参数',
  `completed_blocks` INT UNSIGNED DEFAULT 0 COMMENT '已下载区块数量',
  `total_blocks` INT UNSIGNED DEFAULT 0 COMMENT '区块总数量',
  `update_time` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_task_type` (`task_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='全局下载控制块表 | 用于重启续传、单向推进';

-- 插入默认记录
INSERT INTO `global_dl_ctrl_block` (`task_type`, `task_status`, `primary_pointer_name`, `primary_pointer_value`, `secondary_pointer_name`, `secondary_pointer_value`, `tertiary_pointer_name`, `tertiary_pointer_value`)
VALUES ('kline', NULL, 'quarter', '', 'stock_code', '', 'time_frame', '5m')
ON DUPLICATE KEY UPDATE
  task_status = VALUES(task_status),
  primary_pointer_name = VALUES(primary_pointer_name),
  primary_pointer_value = VALUES(primary_pointer_value),
  secondary_pointer_name = VALUES(secondary_pointer_name),
  secondary_pointer_value = VALUES(secondary_pointer_value),
  tertiary_pointer_name = VALUES(tertiary_pointer_name),
  tertiary_pointer_value = VALUES(tertiary_pointer_value);