-- Verification queries for final-tick freeze migration package.

-- 1) Table exists and schema shape
SHOW CREATE TABLE `match_freeze_state`;

-- 2) Index presence
SELECT
    table_name,
    index_name,
    GROUP_CONCAT(column_name ORDER BY seq_in_index) AS indexed_columns
FROM information_schema.statistics
WHERE table_schema = DATABASE()
  AND (
      (table_name = 'odds_changes' AND index_name = 'idx_odds_changes_match_last_updated')
      OR (table_name = 'over_under_odds_changes' AND index_name = 'idx_ou_changes_match_last_updated')
      OR (table_name = 'odds_analysis_results' AND index_name = 'idx_oar_match_analyzed_at')
      OR (table_name = 'odds_analysis_results' AND index_name = 'idx_oar_match_company_analyzed_at')
      OR (table_name = 'match_freeze_state' AND index_name IN ('PRIMARY', 'idx_mfs_status_deadline', 'idx_mfs_deadline', 'idx_mfs_updated_at'))
  )
GROUP BY table_name, index_name
ORDER BY table_name, index_name;

-- 3) Freeze-state record distribution (will be empty until runtime logic writes rows)
SELECT freeze_status, COUNT(*) AS cnt
FROM match_freeze_state
GROUP BY freeze_status
ORDER BY freeze_status;

-- 4) Upcoming matches missing freeze rows (expected >0 before runtime logic rollout)
SELECT
    m.match_id,
    m.match_time,
    m.match_status
FROM matches m
LEFT JOIN match_freeze_state mfs ON mfs.match_id = m.match_id
WHERE m.match_status IN ('scheduled', 'live')
  AND m.match_time BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 2 DAY)
  AND mfs.match_id IS NULL
ORDER BY m.match_time
LIMIT 50;
