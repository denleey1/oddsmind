-- Final-tick freeze state table
-- Safe to run multiple times.

CREATE TABLE IF NOT EXISTS `match_freeze_state` (
    `match_id` INT NOT NULL,
    `kickoff_time` DATETIME NOT NULL,
    `freeze_window_seconds` INT UNSIGNED NOT NULL DEFAULT 5,
    `freeze_deadline` DATETIME NOT NULL,
    `freeze_status` VARCHAR(16) NOT NULL DEFAULT 'pending',
    `freeze_attempts` INT UNSIGNED NOT NULL DEFAULT 0,
    `final_odds_captured` TINYINT(1) NOT NULL DEFAULT 0,
    `final_analysis_saved` TINYINT(1) NOT NULL DEFAULT 0,
    `final_odds_source_updated_at` DATETIME DEFAULT NULL,
    `final_analysis_analyzed_at` DATETIME DEFAULT NULL,
    `freeze_started_at` DATETIME DEFAULT NULL,
    `freeze_completed_at` DATETIME DEFAULT NULL,
    `lock_version` INT UNSIGNED NOT NULL DEFAULT 0,
    `last_error_message` VARCHAR(512) DEFAULT NULL,
    `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`match_id`),
    KEY `idx_mfs_status_deadline` (`freeze_status`, `freeze_deadline`),
    KEY `idx_mfs_deadline` (`freeze_deadline`),
    KEY `idx_mfs_updated_at` (`updated_at`),
    CONSTRAINT `fk_mfs_match_id` FOREIGN KEY (`match_id`)
        REFERENCES `matches` (`match_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Expected statuses:
-- pending | freezing | frozen | failed
