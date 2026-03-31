# 荷乙数据缺失（重复 match_id）修复方案（含根因与长期治理）

## 现象
- 页面/接口看起来“荷乙没有数据”
- 实际数据库里 `matches`、`odds_changes`、`odds_analysis_results`、`team_power_ratings` 等表并不为空
- 但同一场比赛会出现两个不同 `match_id`，其中旧 `match_id` 往往没有赔率/分析/实力数据

## 已定位根因
### 1) 不是联赛ID重复
- `league_id=17` 一直固定，问题不来自 `leagues` 表的主键重复。

### 2) 源站同一场比赛的 `match_id` 不稳定（发生变更/替换）
- Titan007 的 `matchResult` JS 中，比赛数组第一个字段被我们当作 `match_id`（见 `scrapers/parser.py` -> `Titan007Parser._parse_single_match`）。
- 当源站在不同日期发布的 `matchResult` 数据里，对同一场比赛给出不同的 `match_id` 时：
  - 我们会把新 `match_id` 当成“新比赛”插入（因为 `matches` 以 `match_id` 为唯一主键）
  - 旧 `match_id` 仍保留，形成同场两条记录

### 3) 为什么“昨天之前正常，现在才暴露”
- 重复记录主要影响“未来赛程”。
- 当这些比赛进入前端/接口的“展示时间窗口”（如 `MONITORING_DAYS` 覆盖范围）后，去重/排序若不稳，会选到旧 `match_id`，导致显示“无赔率/无分析”，看起来就像“没有数据”。

## 修复目标
1. **立即恢复展示**：接口返回同场比赛时，稳定选择“数据更完整”的那条 match_id。
2. **让任务链路正确运行**：监控/定时任务选择比赛时也选择 canonical match_id，避免抓到旧 match_id。
3. **清理历史脏数据**：将旧 match_id 关联数据迁移/合并，并标记旧 match 记录为删除（可回滚）。
4. **长期防再发**：入库阶段识别 match_id 变更并记录，形成可追溯的重定向/合并机制。

## 已上线（代码层即时修复）
### A) 今日比赛接口去重（立即生效）
- 文件：`application/routes/web.py`
- 逻辑：对同场（`league_id + match_time + home_team_id + away_team_id`）进行去重，优先选择：
  1) `odds_analysis_results` 存在
  2) `odds_changes` 存在
  3) `fundamental_analysis` 存在
  4) `matches.updated_at` 新
  5) `match_id` 大

### B) 监控/调度选取比赛去重（避免任务抓错）
- 文件：`app_database.py` -> `get_matches_to_monitor`
- 逻辑同上，确保监控/抓取/分析链路不会选到旧 match_id。

### C) 比赛详情与AI分析入口 canonical 自动解析
- 文件：`app_services.py` -> `MatchDetailService.get_match_basic_info`
- 逻辑：若传入旧 match_id，会自动寻找同场更完整的 match_id 并切换查询。

## 数据修复（一次性脚本）
### 脚本
- 文件：`tools/dedupe_duplicate_matches.py`

### 默认策略（保守、可回滚）
1) 对每个重复组选择 canonical match_id（同上优先级）
2) 将关联表中旧 match_id 的记录迁移到 canonical（`UPDATE ... SET match_id = canonical`）
3) 将旧 match_id 在 `matches` 表标记 `is_deleted=1`（不直接删除，降低风险）

### 执行步骤
1) **先 dry-run 看影响面**

```bash
/home/ubuntu/oddsmind/venv/bin/python tools/dedupe_duplicate_matches.py --league-id 17 --dry-run
```

2) **确认无误后 apply**

```bash
/home/ubuntu/oddsmind/venv/bin/python tools/dedupe_duplicate_matches.py --league-id 17 --apply
```

### 回滚说明
- 如果仅做了 `matches.is_deleted=1`：回滚只需置回 0。
- 如果执行了关联表迁移：建议先备份（或记录迁移清单），回滚需要反向把 match_id 改回旧值。

## 长期治理（建议）
1) **引入 match_id 重定向表（推荐）**
   - 新表 `match_id_redirects(old_match_id PK, canonical_match_id, created_at, reason)`
   - 入库检测到同场 match_id 变更时写入重定向
   - API/任务统一先 resolve 到 canonical

2) **在入库阶段直接“废弃旧match_id”**
   - 发现同场已有旧 match_id 且新 match_id 出现时：
     - 标记旧 match `is_deleted=1`
     - 记录 redirect
     - 后续仅使用新 match_id

3) **补齐 scraping_logs**
   - 当前 `scraping_logs` 表为空，无法追溯哪次任务造成重复。
   - 建议在 league 更新与 odds 抓取关键路径写入 `scraping_logs`，用于未来快速定位。

4) **监控与告警**
   - 每日统计：重复组数量、每个联赛重复组数量
   - 当重复组数量突然上升时告警（可能源站结构变更或ID重排）


