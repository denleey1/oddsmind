-- 创建AI分析结果表
CREATE TABLE IF NOT EXISTS `match_ai_analysis` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `match_id` VARCHAR(50) NOT NULL COMMENT '比赛ID',
    `analysis_text` TEXT NOT NULL COMMENT 'AI分析完整文本',
    `final_judgment` VARCHAR(500) DEFAULT NULL COMMENT 'AI最终判断结果（提取的关键结论）',
    `analysis_data` JSON DEFAULT NULL COMMENT '分析时使用的原始数据（JSON格式）',
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY `uk_match_id` (`match_id`),
    KEY `idx_created_at` (`created_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='比赛AI分析结果表';

