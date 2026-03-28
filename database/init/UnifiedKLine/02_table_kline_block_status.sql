-- K线数据区块状态表 - 仅记录完成/未完成两种状态（复合主键）
CREATE TABLE IF NOT EXISTS `kline_block_status` (
  `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
  `time_frame` VARCHAR(20) 
    NOT NULL DEFAULT '5m' COMMENT '时间周期',
  `quarter` VARCHAR(7) NOT NULL COMMENT '季度 格式：YYYY-Qn，如2024-Q1',
  
  -- 核心状态字段：仅两种状态
  `status` ENUM('not_completed','completed') 
    NOT NULL DEFAULT 'not_completed' COMMENT '状态：not_completed-未完成，completed-已完成',
  `completed_at` TIMESTAMP NULL COMMENT '数据下载完成时间',

  -- 自动维护时间戳
  `create_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '记录创建时间',
  `update_time` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '记录更新时间',

  -- 复合主键：股票+周期+季度 唯一标识一条记录
  PRIMARY KEY (`stock_code`, `time_frame`, `quarter`)
) ENGINE=InnoDB 
DEFAULT CHARSET=utf8mb4 
COLLATE=utf8mb4_unicode_ci 
COMMENT='K线数据区块下载状态表 | 仅记录未完成/完成状态 | 复合主键唯一索引';

-- 查看表结构
DESCRIBE `kline_block_status`;