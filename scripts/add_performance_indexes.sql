-- 性能优化索引创建脚本
-- 创建日期: 2026-01-02
-- 用途: 优化matches表查询性能

-- 1. 复合索引：优化按时间和状态查询今日比赛
-- 对应接口: /api/public/matches/today
-- 查询条件: WHERE match_time >= %s AND match_time <= %s [AND match_status = %s]
CREATE INDEX IF NOT EXISTS idx_matches_time_status
ON matches(match_time, match_status);

-- 2. 复合索引：优化按联赛和时间查询
-- 对应接口: /api/public/matches/today（当MONITOR_ALL_LEAGUES=False时）
-- 查询条件: WHERE league_id IN (...) AND match_time >= %s AND match_time <= %s
CREATE INDEX IF NOT EXISTS idx_matches_league_time
ON matches(league_id, match_time);

-- 3. 索引：优化按比赛ID查询
-- 对应接口: /api/public/matches/<match_id>
-- 查询条件: WHERE match_id = %s
CREATE INDEX IF NOT EXISTS idx_matches_match_id
ON matches(match_id);

-- 4. 索引：优化按主队ID查询
-- 对应接口: 查询主队历史比赛
CREATE INDEX IF NOT EXISTS idx_matches_home_team_time
ON matches(home_team_id, match_time);

-- 5. 索引：优化按客队ID查询
-- 对应接口: 查询客队历史比赛
CREATE INDEX IF NOT EXISTS idx_matches_away_team_time
ON matches(away_team_id, match_time);

-- 6. 索引：优化按updated_at查询（用于增量更新）
CREATE INDEX IF NOT EXISTS idx_matches_updated_at
ON matches(updated_at);

-- 7. 复合索引：优化同时按主队、客队、联赛查询（避免重复比赛）
-- 对应接口: 数据去重逻辑
CREATE INDEX IF NOT EXISTS idx_matches_unique_match
ON matches(league_id, match_time, home_team_id, away_team_id);

-- 8. odds_analysis_results表索引
CREATE INDEX IF NOT EXISTS idx_odds_analysis_match_id
ON odds_analysis_results(match_id);

-- 9. odds_changes表索引
CREATE INDEX IF NOT EXISTS idx_odds_changes_match_id
ON odds_changes(match_id);

-- 10. fundamental_analysis表索引
CREATE INDEX IF NOT EXISTS idx_fundamental_analysis_match_id
ON fundamental_analysis(match_id);

-- 查看索引创建结果
SHOW INDEX FROM matches;

