-- 下载任务配置表 DDL
CREATE TABLE IF NOT EXISTS `download_task_config` (
  `id` int NOT NULL AUTO_INCREMENT COMMENT '自增ID',
  `time_frame` VARCHAR(20) COLLATE utf8mb4_unicode_ci NOT NULL COMMENT '时间周期：1min/5min/daily等',
  `start_year` int NOT NULL COMMENT '起始年份',
  `end_year` int NOT NULL COMMENT '结束年份',
  `is_enabled` tinyint(1) DEFAULT '1' COMMENT '是否启用：1-是 0-否',
  `create_time` datetime DEFAULT CURRENT_TIMESTAMP,
  `update_time` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_time_frame` (`time_frame`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='下载任务配置表'