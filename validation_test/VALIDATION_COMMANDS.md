# 验证模块命令指南

## 快速开始

### 一键前置（主入口，推荐）
```bash
# 1) 更新联赛/赛程（可选）
python main.py scrape-leagues --league-group all

# 2) 采集赔率（智能跳过已有）
python main.py scrape-odds --company-filter all --max-workers 10

# 3) 计算广义实力（示例：日职联）
python main.py calculate-strength --league-ids 25 --season 2025 --max-workers 8

# 4) 赔率分析并入库（示例：日职联最近100场）
python main.py analyze-odds --league-id 25 --limit 100
```

以上完成后，可直接运行各类验证器。

### 验证所有联赛（推荐）
```bash
# 自动发现并验证数据库中所有联赛
python validation_test/optimized_multi_league_validator.py

# 指定最小赔率过滤（排除初始赔率<1.4的比赛）
python validation_test/optimized_multi_league_validator.py --min-odds 1.4

# 指定特定联赛组
python validation_test/optimized_multi_league_validator.py --leagues 15,25,36,31,8,11,23
```

## 单个联赛验证

### 基础验证命令
```bash
# 韩K联赛 (ID: 15)
python validation_test/optimized_validator_fixed.py --league-id 15

# 日职联 (ID: 25)
python validation_test/optimized_validator_fixed.py --league-id 25

# 英超 (ID: 36)
python validation_test/optimized_validator_fixed.py --league-id 36

# 西甲 (ID: 31)
python validation_test/optimized_validator_fixed.py --league-id 31

# 德甲 (ID: 8)
python validation_test/optimized_validator_fixed.py --league-id 8

# 意甲 (ID: 11)
python validation_test/optimized_validator_fixed.py --league-id 11

# 法甲 (ID: 23)
python validation_test/optimized_validator_fixed.py --league-id 23
```

### 带赔率过滤的验证
```bash
# 过滤掉赔率<1.4的比赛
python validation_test/validator_correct_filter.py --league-id 15 --min-odds 1.4

# 快速测试过滤逻辑
python validation_test/validator_correct_filter.py --test
```

## 分析工具

### 赔率区间分析
```bash
# 分析韩K联赛不同赔率区间的准确率
python validation_test/odds_range_analyzer.py --league-id 15

# 分析日职联
python validation_test/odds_range_analyzer.py --league-id 25
```

### 公司维度分析
```bash
# 分析主要公司(791, 16, 680, 649, 104)在所有联赛的表现
python validation_test/company_dimension_validator.py
```

### 胜平负专项分析
```bash
# 分析各公司的胜平负预测准确率
python validation_test/win_draw_lose_analyzer.py --league-id 15
```

### 多维度综合分析
```bash
# 全方位分析预测准确率
python validation_test/multi_dimension_analyzer.py --league-id 15
```

## 诊断工具

### 准确率计算诊断
```bash
# 诊断不同计算方法导致的准确率差异
python validation_test/accuracy_diagnosis.py
```

### 极端明显比赛分析
```bash
# 分析赔率<1.4的极端明显比赛
python validation_test/obvious_match_analyzer.py
```

## 报告生成

### 生成Markdown报告
```bash
# 生成验证报告
python validation_test/generate_md_report.py
```

---

## 日职联（J1）专项批量验证（示例）

前置已完成后，可直接批量计算与写库：
```bash
python main.py analyze-odds --league-id 25 --limit 500
```

验证报告建议：
```bash
python validation_test/optimized_validator_fixed.py --league-id 25
python validation_test/generate_md_report.py
```

### 调试验证器
```bash
# 调试模式运行
python validation_test/debug_validator.py
```

## 联赛ID对照表

| 联赛名称 | 联赛ID |
|---------|--------|
| 韩K联赛 | 15 |
| 日职联 | 25 |
| 英超 | 36 |
| 西甲 | 31 |
| 德甲 | 8 |
| 意甲 | 11 |
| 法甲 | 23 |

## 参数说明

### 通用参数
- `--league-id`: 指定联赛ID
- `--min-odds`: 最小赔率阈值（过滤低于此值的比赛）
- `--start-round`: 起始轮次（默认10）
- `--end-round`: 结束轮次（默认38）
- `--test`: 运行快速测试

### 高级参数
- `--max-workers`: 最大并发数（默认3）
- `--company-filter`: 公司过滤（tier1表示主要5家公司）
- `--force-update`: 强制更新已有数据

## 注意事项

1. **首次运行**：需要先确保验证结果表存在，如果不存在需要先运行数据采集
2. **性能考虑**：批量验证多个联赛时建议使用`optimized_multi_league_validator.py`
3. **准确率差异**：不同计算方法会导致准确率差异，建议使用`accuracy_diagnosis.py`诊断
4. **赔率过滤**：过滤极端明显比赛（赔率<1.4）可能会降低整体准确率，因为这些比赛模型表现较好

## 常见问题

### Q: 为什么准确率从58%变成了30-40%？
A: 计算方法改变导致。早期可能使用了错误的宽松匹配，现在使用更严格的规则。运行`accuracy_diagnosis.py`查看详情。

### Q: 过滤赔率<1.4的比赛后准确率为什么下降？
A: 极端明显比赛虽然赔率低，但模型在这些比赛上表现较好（60%+准确率），过滤后反而降低整体准确率。

### Q: 哪个公司预测最准？
A: 运行`company_dimension_validator.py`查看。一般公司16在多个联赛表现最佳。