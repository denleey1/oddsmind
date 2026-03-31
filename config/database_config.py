#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database configuration and schema definitions.
Modern MySQL-first database configuration with comprehensive table schemas.
"""

from typing import Dict, List, Any
from dataclasses import dataclass


@dataclass
class DatabaseConfig:
    """Database configuration with connection pooling and schema definitions."""
    
    # Connection settings
    HOST: str = "localhost"
    PORT: int = 3306
    USER: str = "root"
    PASSWORD: str = "your_password"  # Change this!
    DATABASE: str = "oddsmind"
    CHARSET: str = "utf8mb4"
    
    # Connection pool settings
    POOL_SIZE: int = 20
    MAX_OVERFLOW: int = 30
    POOL_RECYCLE: int = 3600
    POOL_PRE_PING: bool = True
    
    # SQLAlchemy settings
    ECHO: bool = False
    ECHO_POOL: bool = False


# Database table schemas
DATABASE_SCHEMAS = {
    
    # Leagues table
    'leagues': """
        CREATE TABLE IF NOT EXISTS leagues (
            league_id INT PRIMARY KEY,
            name_cn VARCHAR(100) NOT NULL,
            name_tw VARCHAR(100),
            name_en VARCHAR(100),
            season VARCHAR(50),
            color VARCHAR(20),
            logo TEXT,
            total_rounds INT DEFAULT 38,
            current_round INT DEFAULT 1,
            description TEXT,
            country VARCHAR(50),
            level INT DEFAULT 1,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_league_country (country),
            INDEX idx_league_level (level),
            INDEX idx_league_active (is_active)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    # Teams table
    'teams': """
        CREATE TABLE IF NOT EXISTS teams (
            team_id INT PRIMARY KEY,
            name_cn VARCHAR(100) NOT NULL,
            name_tw VARCHAR(100),
            name_en VARCHAR(100),
            short_name VARCHAR(20),
            logo TEXT,
            country VARCHAR(50),
            founded_year INT,
            stadium VARCHAR(100),
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_team_country (country),
            INDEX idx_team_active (is_active),
            INDEX idx_team_name_cn (name_cn)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    # Matches table with comprehensive match information
    'matches': """
        CREATE TABLE IF NOT EXISTS matches (
            match_id INT PRIMARY KEY,
            league_id INT NOT NULL,
            season VARCHAR(50),
            round_number INT,
            match_time DATETIME,
            timezone VARCHAR(10) DEFAULT 'UTC',
            
            home_team_id INT NOT NULL,
            away_team_id INT NOT NULL,
            home_team_name VARCHAR(100),
            away_team_name VARCHAR(100),
            
            -- Scores
            home_score INT,
            away_score INT,
            home_ht_score INT,  -- half time
            away_ht_score INT,
            full_score VARCHAR(20),
            half_score VARCHAR(20),
            
            -- Rankings and form
            home_rank VARCHAR(10),
            away_rank VARCHAR(10),
            home_recent_form VARCHAR(20),  -- Last 5 games: WWLDL
            away_recent_form VARCHAR(20),
            
            -- Betting lines
            handicap DECIMAL(4,2),
            total_goals DECIMAL(4,2),
            
            -- Match status
            match_status ENUM('scheduled', 'live', 'finished', 'postponed', 'cancelled') DEFAULT 'scheduled',
            round_status INT,  -- -1: finished, 0: not started, other: live
            minute_played INT,
            
            -- Additional info
            referee VARCHAR(100),
            stadium VARCHAR(100),
            attendance INT,
            weather VARCHAR(100),
            
            -- Metadata
            is_deleted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            FOREIGN KEY (league_id) REFERENCES leagues (league_id) ON DELETE RESTRICT,
            FOREIGN KEY (home_team_id) REFERENCES teams (team_id) ON DELETE RESTRICT,
            FOREIGN KEY (away_team_id) REFERENCES teams (team_id) ON DELETE RESTRICT,
            
            INDEX idx_match_time (match_time),
            INDEX idx_match_league (league_id),
            INDEX idx_match_season (season),
            INDEX idx_match_teams (home_team_id, away_team_id),
            INDEX idx_match_status (match_status),
            INDEX idx_match_round (league_id, round_number)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    # Bookmaker companies
    'companies': """
        CREATE TABLE IF NOT EXISTS `companies` (
            `company_id` INT PRIMARY KEY,
            `name_en` VARCHAR(255),
            `name_cn` VARCHAR(255),
            `country` VARCHAR(255),
            `website` VARCHAR(255),
            `is_asian` BOOLEAN DEFAULT FALSE,
            `priority` INT DEFAULT 100,
            `is_active` BOOLEAN DEFAULT TRUE,
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
    
    # European odds - current/final odds
    'european_odds': """
        CREATE TABLE IF NOT EXISTS european_odds (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            match_id INT NOT NULL,
            company_id INT NOT NULL,
            
            -- Initial odds
            initial_home DECIMAL(8,3),
            initial_draw DECIMAL(8,3),
            initial_away DECIMAL(8,3),
            initial_home_prob DECIMAL(6,3),
            initial_draw_prob DECIMAL(6,3),
            initial_away_prob DECIMAL(6,3),
            initial_return_rate DECIMAL(6,3),
            
            -- Current/final odds
            current_home DECIMAL(8,3),
            current_draw DECIMAL(8,3),
            current_away DECIMAL(8,3),
            current_home_prob DECIMAL(6,3),
            current_draw_prob DECIMAL(6,3),
            current_away_prob DECIMAL(6,3),
            current_return_rate DECIMAL(6,3),
            
            -- Kelly index
            kelly_home DECIMAL(6,3),
            kelly_draw DECIMAL(6,3),
            kelly_away DECIMAL(6,3),
            
            -- Metadata
            odds_type ENUM('1x2', 'asian_handicap', 'over_under') DEFAULT '1x2',
            update_time VARCHAR(50),
            data_source VARCHAR(50) DEFAULT 'titan007',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_match_company_type (match_id, company_id, odds_type),
            FOREIGN KEY (match_id) REFERENCES matches (match_id) ON DELETE CASCADE,
            FOREIGN KEY (company_id) REFERENCES companies (company_id) ON DELETE CASCADE,
            
            INDEX idx_odds_match (match_id),
            INDEX idx_odds_company (company_id),
            INDEX idx_odds_type (odds_type),
            INDEX idx_odds_update_time (update_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    'over_under_odds_changes': """
        CREATE TABLE IF NOT EXISTS over_under_odds_changes (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            match_id INT NOT NULL,
            company_id INT NOT NULL,
            market_line DECIMAL(5,2) NOT NULL,
            over_open DECIMAL(8,3),
            under_open DECIMAL(8,3),
            over_current DECIMAL(8,3),
            under_current DECIMAL(8,3),
            market VARCHAR(32) DEFAULT 'over_under',
            variant VARCHAR(32) DEFAULT '',
            last_updated DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY uk_match_company_variant (match_id, company_id, market_line, variant),
            INDEX idx_ou_match (match_id),
            INDEX idx_ou_company (company_id),
            INDEX idx_ou_updated (last_updated),
            FOREIGN KEY (match_id) REFERENCES matches (match_id) ON DELETE CASCADE,
            FOREIGN KEY (company_id) REFERENCES companies (company_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # Asian handicap odds (independent table, does not affect existing data)
    'asian_handicap_odds': """
        CREATE TABLE IF NOT EXISTS asian_handicap_odds (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            match_id INT NOT NULL,
            company_id INT NOT NULL DEFAULT 80,

            -- 初盘
            initial_home_odds DECIMAL(8,3),
            initial_handicap_line DECIMAL(5,2),
            initial_away_odds DECIMAL(8,3),

            -- 即时盘（未开赛=当前盘; 已开赛=赛前最后盘）
            current_home_odds DECIMAL(8,3),
            current_handicap_line DECIMAL(5,2),
            current_away_odds DECIMAL(8,3),

            data_source VARCHAR(50) DEFAULT 'titan007',
            scraped_at DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

            UNIQUE KEY uk_ah_match_company (match_id, company_id),
            INDEX idx_ah_match (match_id),
            INDEX idx_ah_scraped (scraped_at),
            FOREIGN KEY (match_id) REFERENCES matches (match_id) ON DELETE CASCADE,
            FOREIGN KEY (company_id) REFERENCES companies (company_id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # League standings
    'standings': """
        CREATE TABLE IF NOT EXISTS standings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            league_id INT NOT NULL,
            season VARCHAR(50),
            team_id INT NOT NULL,
            
            standing_type ENUM('overall', 'home', 'away') DEFAULT 'overall',
            position INT NOT NULL,
            played INT DEFAULT 0,
            wins INT DEFAULT 0,
            draws INT DEFAULT 0,
            losses INT DEFAULT 0,
            goals_for INT DEFAULT 0,
            goals_against INT DEFAULT 0,
            goal_difference INT DEFAULT 0,
            points INT DEFAULT 0,
            
            -- Form and streaks
            recent_form VARCHAR(20),  -- Last 5-10 games
            current_streak VARCHAR(10),  -- W3, L2, D1, etc.
            home_wins INT DEFAULT 0,
            home_draws INT DEFAULT 0,
            home_losses INT DEFAULT 0,
            away_wins INT DEFAULT 0,
            away_draws INT DEFAULT 0,
            away_losses INT DEFAULT 0,
            
            -- Additional stats
            clean_sheets INT DEFAULT 0,
            failed_to_score INT DEFAULT 0,
            
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_league_team_type (league_id, team_id, standing_type, season),
            FOREIGN KEY (league_id) REFERENCES leagues (league_id) ON DELETE CASCADE,
            FOREIGN KEY (team_id) REFERENCES teams (team_id) ON DELETE CASCADE,
            
            INDEX idx_standings_league (league_id),
            INDEX idx_standings_position (position),
            INDEX idx_standings_season (season)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    # Scraping logs and status
    'scraping_logs': """
        CREATE TABLE IF NOT EXISTS scraping_logs (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            scraper_name VARCHAR(50) NOT NULL,
            target_type ENUM('league', 'match', 'odds') NOT NULL,
            target_id VARCHAR(50) NOT NULL,
            
            status ENUM('started', 'success', 'failed', 'skipped') NOT NULL,
            items_processed INT DEFAULT 0,
            items_success INT DEFAULT 0,
            items_failed INT DEFAULT 0,
            
            error_message TEXT,
            execution_time_ms INT,
            memory_usage_mb DECIMAL(8,2),
            
            start_time DATETIME,
            end_time DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            INDEX idx_logs_scraper (scraper_name),
            INDEX idx_logs_target (target_type, target_id),
            INDEX idx_logs_status (status),
            INDEX idx_logs_time (start_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    # System configuration
    'system_config': """
        CREATE TABLE IF NOT EXISTS system_config (
            id INT AUTO_INCREMENT PRIMARY KEY,
            config_key VARCHAR(100) NOT NULL UNIQUE,
            config_value TEXT,
            config_type ENUM('string', 'integer', 'float', 'boolean', 'json') DEFAULT 'string',
            description TEXT,
            is_system BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_config_key (config_key)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    # MiniProgram users table
    'miniprogram_users': """
        CREATE TABLE IF NOT EXISTS miniprogram_users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            openid VARCHAR(128) NOT NULL UNIQUE COMMENT '微信OpenID',
            unionid VARCHAR(128) NULL COMMENT '微信UnionID（可选）',
            nickname VARCHAR(100) NULL COMMENT '用户昵称',
            avatar_url TEXT NULL COMMENT '头像URL',
            is_activated BOOLEAN DEFAULT FALSE COMMENT '是否已激活',
            activated_at DATETIME NULL COMMENT '激活时间',
            expires_at DATETIME NULL COMMENT '账号过期时间',
            invite_code_used VARCHAR(50) NULL COMMENT '使用的邀请码',
            last_login_at DATETIME NULL COMMENT '最后登录时间',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_openid (openid),
            INDEX idx_activated (is_activated),
            INDEX idx_expires_at (expires_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    # Invite codes table
    'invite_codes': """
        CREATE TABLE IF NOT EXISTS invite_codes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            code VARCHAR(50) NOT NULL UNIQUE COMMENT '邀请码',
            created_by VARCHAR(100) NULL COMMENT '创建者（管理员）',
            max_uses INT DEFAULT 1 COMMENT '最大使用次数',
            used_count INT DEFAULT 0 COMMENT '已使用次数',
            expires_at DATETIME NULL COMMENT '邀请码过期时间',
            account_expires_days INT DEFAULT 365 COMMENT '账号有效期（天数），1=1天，7=1周，30=1个月，365=1年',
            is_active BOOLEAN DEFAULT TRUE COMMENT '是否激活',
            notes TEXT NULL COMMENT '备注',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_code (code),
            INDEX idx_active (is_active),
            INDEX idx_expires_at (expires_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
    
    # Invite code usage records table
    'invite_code_usage': """
        CREATE TABLE IF NOT EXISTS invite_code_usage (
            id INT AUTO_INCREMENT PRIMARY KEY,
            invite_code_id INT NOT NULL COMMENT '邀请码ID',
            invite_code VARCHAR(50) NOT NULL COMMENT '邀请码',
            user_id INT NOT NULL COMMENT '用户ID',
            openid VARCHAR(128) NOT NULL COMMENT '微信OpenID',
            account_expires_at DATETIME NOT NULL COMMENT '账号过期时间',
            used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '使用时间',
            
            INDEX idx_invite_code (invite_code),
            INDEX idx_user_id (user_id),
            INDEX idx_openid (openid),
            INDEX idx_used_at (used_at),
            FOREIGN KEY (invite_code_id) REFERENCES invite_codes(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """
}


# Initial data for companies  
COMPANIES_INIT_DATA = [
    (4, "Nordicbet", "Nordic", "Finland", "https://nordicbet.com", False, 1, True),
    (80, "Macau", "澳门", "Macau", "", False, 2, True),
    (81, "Weide", "伟德", "Isle of Man", "https://weide.com", False, 3, True),
    (90, "Easybets", "易胜博", "Philippines", "https://easybets.com", True, 4, True),
    (115, "William Hill", "威廉希尔", "United Kingdom", "https://williamhill.com", False, 5, True),
    (181, "Unibet", "优利", "Malta", "https://unibet.com", False, 6, True),
    (188, "bet365", "bet365", "United Kingdom", "https://bet365.com", False, 7, True),
    (190, "Interwetten", "InterWetten", "Malta", "https://interwetten.com", False, 8, True),
    (255, "BWIN", "BWIN", "Austria", "https://bwin.com", False, 9, True),
    (281, "Ladbrokes", "立博", "United Kingdom", "https://ladbrokes.com", False, 10, True),
    (432, "HKJC", "香港马会", "Hong Kong", "https://bet.hkjc.com", True, 11, True),
    (474, "SB", "利记", "Philippines", "", False, 12, True),
    (657, "Pinnacle", "平博", "Curacao", "https://pinnacle.com", False, 13, True),
    (937, "Marathonbet", "明陞", "Curacao", "https://marathonbet.com", False, 14, True),
    (976, "18Bet", "18bet", "Curacao", "", False, 15, True),
]


def get_create_tables_sql() -> Dict[str, str]:
    """Get all table creation SQL statements."""
    return DATABASE_SCHEMAS


def get_companies_init_data() -> List[tuple]:
    """Get initial data for companies table."""
    return COMPANIES_INIT_DATA
