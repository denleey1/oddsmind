-- 信心值引擎 v3.0 — 临场基本面分析新增列
-- 执行前请确认 fundamental_analysis 表已存在

ALTER TABLE fundamental_analysis
  ADD COLUMN IF NOT EXISTS pull_direction VARCHAR(20) DEFAULT NULL
    COMMENT '拉力方向: home/away/draw/balanced',
  ADD COLUMN IF NOT EXISTS pull_description VARCHAR(100) DEFAULT NULL
    COMMENT '拉力描述文字',
  ADD COLUMN IF NOT EXISTS prompts_json TEXT DEFAULT NULL
    COMMENT '人工提示标签JSON数组(缺阵/赛程/题材等)',
  ADD COLUMN IF NOT EXISTS absent_players_json TEXT DEFAULT NULL
    COMMENT '缺阵球员JSON {home:[...], away:[...]}';
