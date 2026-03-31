-- Rollback for final-tick freeze migration package.
-- Drops added indexes (if present) and freeze state table.

SET @schema_name := DATABASE();

-- Drop idx_odds_changes_match_last_updated if exists
SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'odds_changes'
              AND index_name = 'idx_odds_changes_match_last_updated'
        ),
        'DROP INDEX idx_odds_changes_match_last_updated ON odds_changes',
        'SELECT ''skip drop idx_odds_changes_match_last_updated'''
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Drop idx_ou_changes_match_last_updated if exists
SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'over_under_odds_changes'
              AND index_name = 'idx_ou_changes_match_last_updated'
        ),
        'DROP INDEX idx_ou_changes_match_last_updated ON over_under_odds_changes',
        'SELECT ''skip drop idx_ou_changes_match_last_updated'''
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Drop idx_oar_match_analyzed_at if exists
SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'odds_analysis_results'
              AND index_name = 'idx_oar_match_analyzed_at'
        ),
        'DROP INDEX idx_oar_match_analyzed_at ON odds_analysis_results',
        'SELECT ''skip drop idx_oar_match_analyzed_at'''
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Drop idx_oar_match_company_analyzed_at if exists
SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'odds_analysis_results'
              AND index_name = 'idx_oar_match_company_analyzed_at'
        ),
        'DROP INDEX idx_oar_match_company_analyzed_at ON odds_analysis_results',
        'SELECT ''skip drop idx_oar_match_company_analyzed_at'''
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Drop freeze state table
DROP TABLE IF EXISTS `match_freeze_state`;
