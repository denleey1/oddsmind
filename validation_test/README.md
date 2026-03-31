# 联赛验证分析工具

## 最小化流程（建议先跑一遍）

1) 初始化/刷新联赛与赛程（必要时）：
```bash
python main.py scrape-leagues --league-group all
```

2) 采集赔率（可选：限定公司/联赛）：
```bash
python main.py scrape-odds --company-filter all --max-workers 10
```

3) 计算广义实力（示例：日职联 25）：
```bash
python main.py calculate-strength --league-ids 25 --season 2025 --max-workers 8
```

4) 赔率分析并入库（示例：日职联最近100场）：
```bash
python main.py analyze-odds --league-id 25 --limit 100
```

以上第4步会把结果写入 `odds_analysis_results`，供验证器读取。

---

## 使用方法（传统验证脚本）

### 1. 分析单个联赛

```bash
# 分析英超（默认）
python league_analyzer.py

# 分析日职联（需要广义实力数据与赔率分析结果）
python league_analyzer.py --leagues jleague

# 分析西甲，指定轮次（需要广义实力数据）
python league_analyzer.py --leagues laliga --start-round 15 --end-round 30
```

### 2. 分析多个联赛

```bash
# 分析英超和日职联
python league_analyzer.py --leagues premier jleague

# 分析五大联赛全部
python league_analyzer.py --leagues all
```

### 3. 自定义排名数量

```bash
# 显示前20名准确率，前15名一致性
python league_analyzer.py --top-accuracy 20 --top-consistency 15
```

### 4. 使用自定义表名

```bash
# 使用特定的验证结果表
python league_analyzer.py --table-suffix premier_league
# 这会使用 premier_league_validation_results 表
```

## 参数说明

| 参数 | 短参数 | 描述 | 默认值 |
|------|--------|------|--------|
| `--leagues` | `-l` | 要分析的联赛 | 英超 |
| `--start-round` | `-s` | 起始轮次 | 10 |
| `--end-round` | `-e` | 结束轮次 | 38 |
| `--top-accuracy` | `-ta` | 准确率排名显示数量 | 15 |
| `--top-consistency` | `-tc` | 一致性排名显示数量 | 10 |
| `--table-suffix` | `-t` | 自定义表名后缀 | 无 |

## 支持的联赛

| 联赛代码 | 联赛名称 | 联赛ID | 状态 | 说明 |
|----------|----------|--------|------|------|
| `premier` | 英超 | 36 | ✅ 已完成 | 第10-38轮验证完毕 |
| `laliga` | 西甲 | 31 | ⏳ 等待中 | 需要广义实力数据 |
| `bundesliga` | 德甲 | 8 | ⏳ 等待中 | 需要广义实力数据 |
| `seriea` | 意甲 | 34 | ⏳ 等待中 | 需要广义实力数据 |
| `ligue1` | 法甲 | 11 | ⏳ 等待中 | 需要广义实力数据 |
| `kleague` | 韩国K联赛 | 15 | ⏳ 等待中 | 需要广义实力数据 |
| `jleague` | 日职联 | 25 | 🔧 准备中 | 验证器已就绪，需要广义实力数据 |
| `all` | 全部联赛 | - | - | 分析所有可用联赛 |

## 输出报告

每个联赛会生成两个排名：

1. **即时盘推荐准确率排名**: 按即时盘预测准确率降序排列
2. **初盘即时盘一致性排名**: 在准确率前N名中，按一致性降序排列

## 数据表要求

分析器会自动查找对应的验证结果表：

- 单联赛: `{联赛名}_validation_results` (如: `英超_validation_results`)
- 多联赛: `multi_league_validation_results` 
- 自定义: `{table_suffix}_validation_results`

表必须包含以下字段：
- `match_id`, `company_id`, `round_number`
- `actual_home_score`, `actual_away_score`
- `initial_recommendation`, `current_recommendation`
- `initial_rule_diff`, `current_rule_diff`

## 示例输出

```
================================================================================
英超 验证结果分析报告
================================================================================
总公司数: 123
总预测数: 33995

[即时盘推荐准确率排名] (前15名)
--------------------------------------------------------------------------------
排名   公司ID     即时准确率        初盘准确率        预测总数     一致性     
--------------------------------------------------------------------------------
1    1300     0.427        0.418        239      0.310   
2    136      0.404        0.399        223      0.305   
...
```