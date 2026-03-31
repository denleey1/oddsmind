-- ============================================
-- 策略规则表（Strategy Rules Table）
-- 用于存储发现的"必杀定式"规则
-- ============================================

CREATE TABLE IF NOT EXISTS strategy_rules (
    rule_id INT AUTO_INCREMENT PRIMARY KEY,
    
    -- 盘型条件（三个维度）
    home_range_cond VARCHAR(50) NOT NULL COMMENT '主队盘型条件（如：超实盘中水）',
    away_range_cond VARCHAR(50) NOT NULL COMMENT '客队盘型条件（如：韬光盘中低水）',
    draw_range_cond VARCHAR(50) NOT NULL COMMENT '平局盘型条件（如：平实高）',
    
    -- 期望结果
    expected_result VARCHAR(10) NOT NULL COMMENT '期望结果：HOME_WIN, AWAY_WIN, DRAW',
    
    -- 元数据
    rule_name VARCHAR(200) COMMENT '规则名称/描述',
    priority_order INT DEFAULT 0 COMMENT '优先级排序（数字越大优先级越高）',
    
    -- 训练数据统计（用于记录发现此规则时的数据）
    training_sample_size INT DEFAULT 0 COMMENT '训练样本数',
    training_win_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '训练集胜率（%）',
    training_unbeaten_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '训练集不败率（%）',
    
    -- 验证状态
    validation_status VARCHAR(20) DEFAULT 'PENDING' COMMENT '验证状态：PENDING, VALIDATED, FAILED, DEPRECATED',
    last_validated_at DATETIME NULL COMMENT '最后验证时间',
    
    -- 验证结果统计
    validation_sample_size INT DEFAULT 0 COMMENT '验证样本数',
    validation_win_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '验证集胜率（%）',
    validation_unbeaten_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '验证集不败率（%）',
    
    -- 评级
    rating VARCHAR(10) DEFAULT 'N/A' COMMENT '评级：★★★★★, ★★★★, ★★★, ★★, ★',
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    
    -- 唯一约束：相同的盘型组合只能有一条规则
    UNIQUE KEY uk_range_combination (home_range_cond, away_range_cond, draw_range_cond, expected_result),
    
    -- 索引
    INDEX idx_validation_status (validation_status),
    INDEX idx_priority (priority_order DESC),
    INDEX idx_rating (rating)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='策略规则表';

-- ============================================
-- 验证结果表（Validation Results Table）
-- 用于存储每次验证的详细结果
-- ============================================

CREATE TABLE IF NOT EXISTS validation_results (
    validation_id INT AUTO_INCREMENT PRIMARY KEY,
    
    rule_id INT NOT NULL COMMENT '关联的策略规则ID',
    
    -- 验证数据库信息
    validation_database VARCHAR(100) COMMENT '验证数据库名称',
    validation_table VARCHAR(100) COMMENT '验证表名称',
    
    -- 验证时间范围
    validation_start_date DATE COMMENT '验证开始日期',
    validation_end_date DATE COMMENT '验证结束日期',
    
    -- 验证结果统计
    total_matches INT DEFAULT 0 COMMENT '总匹配场次',
    actual_wins INT DEFAULT 0 COMMENT '实际主胜场次',
    actual_draws INT DEFAULT 0 COMMENT '实际平局场次',
    actual_losses INT DEFAULT 0 COMMENT '实际客胜场次',
    
    -- 胜率统计
    win_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '主胜率（%）',
    unbeaten_rate DECIMAL(5,2) DEFAULT 0.00 COMMENT '不败率（%）',
    
    -- 验证结论
    validation_status VARCHAR(20) DEFAULT 'PENDING' COMMENT '验证状态：PASSED, WEAKENED, FAILED',
    validation_comment TEXT COMMENT '验证备注',
    
    -- 时间戳
    validated_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '验证时间',
    
    -- 外键
    FOREIGN KEY (rule_id) REFERENCES strategy_rules(rule_id) ON DELETE CASCADE,
    
    -- 索引
    INDEX idx_rule_id (rule_id),
    INDEX idx_validation_status (validation_status),
    INDEX idx_validated_at (validated_at)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='验证结果表';

-- ============================================
-- 验证匹配详情表（Validation Match Details）
-- 用于存储每次验证中匹配到的具体比赛
-- ============================================

CREATE TABLE IF NOT EXISTS validation_match_details (
    detail_id INT AUTO_INCREMENT PRIMARY KEY,
    
    validation_id INT NOT NULL COMMENT '关联的验证结果ID',
    rule_id INT NOT NULL COMMENT '关联的策略规则ID',
    
    -- 比赛信息
    match_id INT NOT NULL COMMENT '比赛ID',
    match_time DATETIME COMMENT '比赛时间',
    home_team_name VARCHAR(100) COMMENT '主队名称',
    away_team_name VARCHAR(100) COMMENT '客队名称',
    league_name VARCHAR(100) COMMENT '联赛名称',
    
    -- 盘型信息
    current_home_range VARCHAR(50) COMMENT '主队盘型',
    current_away_range VARCHAR(50) COMMENT '客队盘型',
    current_draw_range VARCHAR(50) COMMENT '平局盘型',
    
    -- 比赛结果
    home_score INT COMMENT '主队得分',
    away_score INT COMMENT '客队得分',
    actual_result VARCHAR(10) COMMENT '实际结果：HOME_WIN, AWAY_WIN, DRAW',
    
    -- 是否命中
    is_correct BOOLEAN DEFAULT FALSE COMMENT '是否命中预期结果',
    
    -- 时间戳
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    
    -- 外键
    FOREIGN KEY (validation_id) REFERENCES validation_results(validation_id) ON DELETE CASCADE,
    FOREIGN KEY (rule_id) REFERENCES strategy_rules(rule_id) ON DELETE CASCADE,
    
    -- 索引
    INDEX idx_validation_id (validation_id),
    INDEX idx_rule_id (rule_id),
    INDEX idx_match_id (match_id),
    INDEX idx_is_correct (is_correct)
    
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='验证匹配详情表';
