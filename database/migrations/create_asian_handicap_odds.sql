-- Migration: Create asian_handicap_odds table
-- Date: 2026-03-25
-- Description: Independent table for Asian handicap odds data (Macau only).
--   Does NOT modify any existing tables.
--   handicap_line convention (home perspective):
--     positive = home receives handicap (home is underdog)
--     negative = home gives handicap (home is favorite)

CREATE TABLE IF NOT EXISTS asian_handicap_odds (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    match_id INT NOT NULL,
    company_id INT NOT NULL DEFAULT 80,

    -- Opening line
    initial_home_odds DECIMAL(8,3),
    initial_handicap_line DECIMAL(5,2),
    initial_away_odds DECIMAL(8,3),

    -- Current/final pre-match line
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
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
