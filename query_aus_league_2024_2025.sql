-- ============================================================
-- 查询澳超2024-2025赛季数据（仅查询，不删除）
-- ============================================================

USE oddsmind;

-- 1. 联赛记录
SELECT '=== 联赛记录 ===' AS info;
SELECT league_id, name_cn, name_en, season, is_active 
FROM leagues 
WHERE league_id = 273;

-- 2. 2024-2025赛季的比赛数据
SELECT '=== 2024-2025赛季的比赛数据 ===' AS info;
SELECT 
    match_id,
    match_time,
    match_status,
    home_team_name,
    away_team_name,
    home_score,
    away_score,
    season
FROM matches
WHERE league_id = 273 AND season = '2024-2025'
ORDER BY match_time
LIMIT 20;

-- 3. 比赛数量统计
SELECT '=== 比赛数量统计 ===' AS info;
SELECT COUNT(*) as match_count
FROM matches
WHERE league_id = 273 AND season = '2024-2025';

-- 4. 欧洲赔率数据统计
SELECT '=== 欧洲赔率数据统计 ===' AS info;
SELECT COUNT(*) as odds_count
FROM european_odds eo
INNER JOIN matches m ON eo.match_id = m.match_id
WHERE m.league_id = 273 AND m.season = '2024-2025';

-- 5. 大小球赔率数据统计
SELECT '=== 大小球赔率数据统计 ===' AS info;
SELECT COUNT(*) as ou_odds_count
FROM over_under_odds_changes ou
INNER JOIN matches m ON ou.match_id = m.match_id
WHERE m.league_id = 273 AND m.season = '2024-2025';

