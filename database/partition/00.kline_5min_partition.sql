/*
1. 新增分区（以 2025 年 Q1 为例）
-- 第一步：拆分兜底分区（先将p_default数据临时迁移到新分区）
*/
ALTER TABLE kline_5min 
REORGANIZE PARTITION p_default INTO (
    PARTITION p2025q1 VALUES LESS THAN (TO_DAYS('2025-04-01')),
    PARTITION p_default VALUES LESS THAN MAXVALUE
);

/*
2. 删除历史分区（例如清理 2023 年数据）
-- 直接删除分区（物理删除数据，速度远快于DELETE）
*/
ALTER TABLE kline_5min DROP PARTITION p2023q4;

/*
3. 分区查询验证
-- 查看表分区信息
*/
SELECT PARTITION_NAME, PARTITION_METHOD, PARTITION_DESCRIPTION 
FROM INFORMATION_SCHEMA.PARTITIONS 
WHERE TABLE_SCHEMA = '你的数据库名' AND TABLE_NAME = 'kline_5min';

/*
4. 验证分区裁剪（查询2024Q2数据，仅扫描p2024q2分区）
-- EXPLAIN PARTITIONS显示查询涉及的分区，验证是否只扫描了p
*/
EXPLAIN PARTITIONS
SELECT * FROM kline_5min 
WHERE code = 'sh.600000' AND frequency = 5 AND trade_date BETWEEN '2024-04-01' AND '2024-06-30';


/*
5. 通过存储过程自动管理分区（示例：根据传入的trade_date自动创建对应季度分区）
-- 创建存储过程：根据传入的trade_date自动创建对应季度分区（如果不存在）
-- 使用示例：CALL create_kline_partition_if_not_exists('2024-05-15', 'kline_5min');
*/
DELIMITER //
CREATE PROCEDURE create_kline_partition_if_not_exists(
    IN p_trade_date DATE,  -- 传入要插入的trade_date
    IN p_table_name VARCHAR(64) -- 表名（固定为kline_5min）
)
BEGIN
    -- 步骤1：计算该日期所属的季度、分区名称、分区结束日期
    DECLARE v_year INT;
    DECLARE v_quarter INT;
    DECLARE v_partition_name VARCHAR(20);
    DECLARE v_quarter_end DATE;
    DECLARE v_partition_exist INT DEFAULT 0;

    -- 提取年份和季度
    SET v_year = YEAR(p_trade_date);
    SET v_quarter = QUARTER(p_trade_date);

    -- 计算季度结束日期（如2024Q1 → 2024-04-01）
    SET v_quarter_end = STR_TO_DATE(CONCAT(v_year, '-', (v_quarter*3)+1, '-01'), '%Y-%m-%d');
    -- 处理第四季度（2024Q4 → 2025-01-01）
    IF v_quarter = 4 THEN
        SET v_quarter_end = STR_TO_DATE(CONCAT(v_year+1, '-01-01'), '%Y-%m-%d');
    END IF;

    -- 分区名称（如p2024q1）
    SET v_partition_name = CONCAT('p', v_year, 'q', v_quarter);

    -- 步骤2：校验分区是否已存在
    SELECT COUNT(*) INTO v_partition_exist
    FROM INFORMATION_SCHEMA.PARTITIONS
    WHERE TABLE_SCHEMA = DATABASE() 
      AND TABLE_NAME = p_table_name 
      AND PARTITION_NAME = v_partition_name;

    -- 步骤3：若分区不存在，拆分兜底分区创建新分区
    IF v_partition_exist = 0 THEN
        SET @sql = CONCAT(
            'ALTER TABLE ', p_table_name, ' REORGANIZE PARTITION p_default INTO (',
            'PARTITION ', v_partition_name, ' VALUES LESS THAN (TO_DAYS(\'', v_quarter_end, '\')),',
            'PARTITION p_default VALUES LESS THAN MAXVALUE',
            ');'
        );
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        
        -- 打印日志（可选）
        SELECT CONCAT('创建分区 ', v_partition_name, ' 成功（结束日期：', v_quarter_end, '）') AS msg;
    END IF;
END //
DELIMITER ;


/*
6. 配置事件调度器，打开事件调度器以支持自动分区管理存储过程的定时执行（例如每天检查一次是否需要创建新分区）：
*/
-- 查看调度器状态（ON 为开启，OFF 为关闭）
SHOW VARIABLES LIKE 'event_scheduler';
-- 临时开启（重启MySQL后失效）
SET GLOBAL event_scheduler = ON;
-- 永久开启（修改配置文件 my.cnf/my.ini，重启生效）
# [mysqld]
# event_scheduler = ON

/*
五、适用场景补充
若业务以「单股票 + 月度回测」为主，可将分区粒度改为按月分区（例如p202404对应 2024 年 4 月）；
若数据量超千万级 / 月，建议定期（如每 6 个月）归档历史分区到冷备库，减少主表数据量；
分区字段优先选择trade_date而非trade_time，因为trade_time包含时分秒，分区粒度太细会导致分区数量过多，反而降低性能。


六、注意事项
分区表不支持ALTER TABLE ... ADD PRIMARY KEY，因此建表时需直接定义包含分区字段的主键；
插入数据时确保trade_date字段不为空（已设置 NOT NULL），否则会插入到兜底分区；
避免跨分区的大范围查询（例如查询全年数据），尽量按分区字段筛选，发挥分区裁剪的优势。
*/