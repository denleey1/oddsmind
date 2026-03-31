-- Add freeze-related performance indexes (idempotent by metadata check).
-- Works on MySQL by generating dynamic SQL only when index is missing.

SET @schema_name := DATABASE();

-- odds_changes(match_id, last_updated)
SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'odds_changes'
              AND index_name = 'idx_odds_changes_match_last_updated'
        ),
        'SELECT ''skip idx_odds_changes_match_last_updated''',
        'CREATE INDEX idx_odds_changes_match_last_updated ON odds_changes (match_id, last_updated)'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- over_under_odds_changes(match_id, last_updated)
SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'over_under_odds_changes'
              AND index_name = 'idx_ou_changes_match_last_updated'
        ),
        'SELECT ''skip idx_ou_changes_match_last_updated''',
        'CREATE INDEX idx_ou_changes_match_last_updated ON over_under_odds_changes (match_id, last_updated)'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- odds_analysis_results(match_id, analyzed_at)
SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'odds_analysis_results'
              AND index_name = 'idx_oar_match_analyzed_at'
        ),
        'SELECT ''skip idx_oar_match_analyzed_at''',
        'CREATE INDEX idx_oar_match_analyzed_at ON odds_analysis_results (match_id, analyzed_at)'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- odds_analysis_results(match_id, company_id, analyzed_at)
SET @sql := (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'odds_analysis_results'
              AND index_name = 'idx_oar_match_company_analyzed_at'
        ),
        'SELECT ''skip idx_oar_match_company_analyzed_at''',
        'CREATE INDEX idx_oar_match_company_analyzed_at ON odds_analysis_results (match_id, company_id, analyzed_at)'
    )
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
