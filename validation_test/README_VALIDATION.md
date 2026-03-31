# 样本外验证系统使用指南

## 概述

样本外验证（Out-of-Sample Testing）系统用于验证发现的"必杀定式"规则在新数据上的有效性，避免过拟合问题。

## 快速开始

### 1. 初始化数据库表

首先需要创建策略规则表和验证结果表：

```bash
# 方法1: 直接执行SQL脚本
mysql -u your_user -p your_database < validation_test/strategy_rules.sql

# 方法2: 通过Python自动创建（推荐）
python validation_test/strategy_rule_service.py
```

### 2. 导入黄金定式规则

```bash
python validation_test/run_validation.py import
```

这将导入以下规则：
- **完美定式**（100%胜率，样本≥5）：2条
- **高胜定式**（80-89%胜率，样本≥5）：8条

### 3. 查看所有规则

```bash
# 查看所有规则
python validation_test/run_validation.py list

# 只查看待验证的规则
python validation_test/run_validation.py list --status PENDING
```

### 4. 运行验证

```bash
# 验证所有规则
python validation_test/run_validation.py validate

# 验证指定规则
python validation_test/run_validation.py validate --rule-ids 1,2,3

# 验证指定日期范围的比赛
python validation_test/run_validation.py validate --start-date 2024-01-01 --end-date 2024-12-31
```

### 5. 生成验证报告

```bash
# 生成报告（自动保存到 reports/ 目录）
python validation_test/run_validation.py report

# 指定输出文件
python validation_test/run_validation.py report --output my_report.txt
```

## 验证结果解读

### 验证状态说明

- **✅ PASSED (验证通过)**: 胜率 ≥ 75%
  - 说明：这是真正的规律，可以放心使用
  
- **⚠️ WEAKENED (效力减弱)**: 胜率 60% - 75%
  - 说明：规则依然有效，但之前的100%有运气成分，需谨慎使用
  
- **❌ FAILED (验证失败)**: 胜率 < 60%
  - 说明：这是过拟合，之前的100%纯属巧合，建议废弃

- **⏳ NO_SAMPLE (样本不足)**: 样本数 < 3
  - 说明：新数据库中匹配的比赛太少，无法验证

### 示例输出

```
验证结果汇总
================================================================================

验证通过 (✅): 2 条
效力减弱 (⚠️): 3 条
验证失败 (❌): 1 条
样本不足 (⏳): 1 条

✅ 验证通过的规则 (2 条):
规则ID   样本数   胜率       不败率     状态
------------------------------------------------------------
1        25       82.5%      92.0%      ✅ 验证通过 (真理)
2        18       77.8%      88.9%      ✅ 验证通过 (真理)
```

## 数据库表结构

### strategy_rules (策略规则表)

存储发现的"必杀定式"规则：

- `rule_id`: 规则ID（主键）
- `home_range_cond`: 主队盘型条件（如：超实盘中水）
- `away_range_cond`: 客队盘型条件（如：韬光盘中低水）
- `draw_range_cond`: 平局盘型条件（如：平实高）
- `expected_result`: 期望结果（HOME_WIN, AWAY_WIN, DRAW）
- `training_win_rate`: 训练集胜率
- `validation_win_rate`: 验证集胜率
- `validation_status`: 验证状态

### validation_results (验证结果表)

存储每次验证的统计结果：

- `validation_id`: 验证ID（主键）
- `rule_id`: 关联的策略规则ID
- `total_matches`: 总匹配场次
- `actual_wins`: 实际主胜场次
- `win_rate`: 主胜率
- `validation_status`: 验证状态

### validation_match_details (验证匹配详情表)

存储每次验证中匹配到的具体比赛（可选，用于详细分析）。

## Python API 使用

### 导入规则

```python
from validation_test.strategy_rule_service import StrategyRuleService

service = StrategyRuleService()
service.import_golden_rules()
```

### 运行验证

```python
from validation_test.out_of_sample_validator import OutOfSampleValidator
from datetime import date

validator = OutOfSampleValidator()

# 验证单个规则
result = validator.validate_rule(
    rule_id=1,
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31)
)

# 验证所有规则
results = validator.validate_all_rules()
```

### 生成报告

```python
report = validator.get_validation_report()
print(f"验证通过: {report['summary']['passed']} 条")
```

## 注意事项

1. **数据要求**: 验证数据库必须包含 `odds_analysis_results` 表，且该表必须有 `current_home_range`, `current_away_range`, `current_draw_range` 字段

2. **比赛状态**: 只验证 `match_status = 'finished'` 的比赛

3. **样本大小**: 建议样本数 ≥ 10 才能得出可靠结论

4. **持续验证**: 建议定期（如每月）重新验证规则，因为市场环境可能变化

5. **组合使用**: 不要单独依赖一个规则，建议组合多个验证通过的规则使用

## 故障排查

### 问题：找不到匹配的比赛

**原因**: 新数据库中的盘型数据与规则不匹配

**解决**: 
- 检查 `odds_analysis_results` 表中的盘型数据是否完整
- 确认盘型命名是否一致（如：超实盘中水 vs 超实盘中水）

### 问题：验证结果全部失败

**原因**: 可能是过拟合，或者验证数据与训练数据差异太大

**解决**:
- 检查验证数据的日期范围是否合理
- 考虑使用更大的样本量
- 检查是否有数据质量问题

## 扩展功能

### 添加自定义规则

```python
from validation_test.strategy_rule_service import StrategyRuleService

service = StrategyRuleService()
service.create_rule(
    home_range_cond='超实盘中水',
    away_range_cond='韬光盘中低水',
    draw_range_cond='平实高',
    expected_result='HOME_WIN',
    rule_name='我的自定义规则',
    training_sample_size=10,
    training_win_rate=100.0,
    rating='★★★★★'
)
```

### 批量导入规则

```python
rules = [
    {
        'home_range_cond': '超实盘中水',
        'away_range_cond': '韬光盘中低水',
        'draw_range_cond': '平实高',
        'expected_result': 'HOME_WIN',
        'training_sample_size': 10,
        'training_win_rate': 100.0
    },
    # ... 更多规则
]

service.batch_create_rules(rules)
```

## 相关文件

- `strategy_rules.sql`: 数据库表结构定义
- `strategy_rule_service.py`: 策略规则管理服务
- `out_of_sample_validator.py`: 样本外验证器
- `run_validation.py`: 命令行工具

## 更新日志

- 2024-01-XX: 初始版本，支持基本的验证功能
