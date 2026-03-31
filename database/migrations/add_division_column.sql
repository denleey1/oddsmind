-- Migration: Add division column for J1 East/West divisional league support
-- Date: 2026-03-19
-- Description: 
--   日职J1联赛2026赛季起采用东/西区赛制(各10队)
--   需要在 matches 和 team_power_ratings 表中增加 division 列
--   以支持分区内排名和全局合并排名的计算

-- 1. Add division column to matches table
ALTER TABLE matches 
  ADD COLUMN division VARCHAR(20) DEFAULT NULL COMMENT '分区标识(east/west等)' AFTER season;

-- 2. Add division column to team_power_ratings table (NOT NULL with default '' for unique key)
ALTER TABLE team_power_ratings 
  ADD COLUMN division VARCHAR(20) NOT NULL DEFAULT '' COMMENT '分区标识(east/west/空=全局)' AFTER season;

-- 3. Update unique key on team_power_ratings to include division
ALTER TABLE team_power_ratings DROP INDEX uk_team_league_company;
ALTER TABLE team_power_ratings 
  ADD UNIQUE KEY uk_team_league_company_div (team_id, league_id, company_id, division);

-- 4. Add index on matches.division for filtering
CREATE INDEX idx_matches_division ON matches (division);
