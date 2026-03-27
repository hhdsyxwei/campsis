-- 精简版K线下载进度跟踪表 - 仅记录完成/未完成两种状态（复合主键）
CREATE TABLE `kline_block_download_status` (
  `stock_code` VARCHAR(20) NOT NULL COMMENT '股票代码',
  `time_frame` ENUM('1min', '5min', '15min', '30min', '60min', 'daily', 'weekly', 'monthly') NOT NULL DEFAULT '5min' COMMENT '时间周期',
  `quarter` VARCHAR(7) NOT NULL COMMENT '季度 YYYY-Qn格式，如2024-Q1',
  
  -- 下载状态（只有两种状态）
  `status` ENUM('not_completed', 'completed') NOT NULL DEFAULT 'not_completed' COMMENT '下载状态：not_completed-未完成，completed-已完成',
  `completed_at` TIMESTAMP NULL COMMENT '完成时间',
  
  -- 时间戳
  `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
  `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
  
  -- 复合主键
  PRIMARY KEY (`stock_code`, `time_frame`, `quarter`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='K线下载进度跟踪表 - 双状态设计，复合主键';

-- 插入测试数据
INSERT INTO `kline_block_download_status` (
    `stock_code`, `time_frame`, `quarter`, `status`
) VALUES 
('AAPL', '5min', '2024-Q1', 'not_completed'),
('MSFT', '1min', '2024-Q1', 'not_completed'),
('GOOGL', 'daily', '2024-Q1', 'completed'),
('TSLA', '5min', '2024-Q2', 'not_completed'),
('NVDA', '5min', '2024-Q1', 'not_completed');

-- 查看表结构
DESCRIBE `kline_block_download_status`;