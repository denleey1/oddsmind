-- 数据库索引优化脚本
-- 用于提升查询性能

-- 1. matches表索引优化
-- match_time是主要查询条件，需要索引
CREATE INDEX IF NOT EXISTS idx_matches_match_time ON matches(match_time);
CREATE INDEX IF NOT EXISTS idx_matches_league_id ON matches(league_id);
CREATE INDEX IF NOT EXISTS idx_matches_match_status ON matches(match_status);
-- 复合索引：league_id + match_time（用于按联赛和时间查询）
CREATE INDEX IF NOT EXISTS idx_matches_league_time ON matches(league_id, match_time);
-- 复合索引：match_status + match_time（用于按状态和时间查询）
CREATE INDEX IF NOT EXISTS idx_matches_status_time ON matches(match_status, match_time);
-- home_team_id和away_team_id用于JOIN
CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id);
CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id);

-- 2. leagues表索引（通常数据量小，但JOIN时仍需要）
CREATE INDEX IF NOT EXISTS idx_leagues_league_id ON leagues(league_id);

-- 3. teams表索引
CREATE INDEX IF NOT EXISTS idx_teams_team_id ON teams(team_id);

-- 4. standings表索引（用于LEFT JOIN）
CREATE INDEX IF NOT EXISTS idx_standings_team_league ON standings(team_id, league_id, standing_type);
CREATE INDEX IF NOT EXISTS idx_standings_league_type ON standings(league_id, standing_type);

-- 5. fundamental_analysis表索引
CREATE INDEX IF NOT EXISTS idx_fundamental_match ON fundamental_analysis(match_id);

-- 6. odds_analysis_results表索引
CREATE INDEX IF NOT EXISTS idx_odds_analysis_match ON odds_analysis_results(match_id);

-- 7. odds_changes表索引
CREATE INDEX IF NOT EXISTS idx_odds_changes_match ON odds_changes(match_id);

-- 8. 查看索引使用情况（执行后查看）
-- EXPLAIN SELECT ... FROM matches WHERE match_time >= ... AND match_time <= ...;















