# 欧赔分析系统 (Odds Analysis System)

## 系统概述

欧赔分析系统是一个基于满水赔率计算和广义实力分析的智能推荐系统。通过分析博彩公司的即时赔率变化，结合队伍实力差异，提供比赛结果推荐。

## 核心功能

### 1. 满水赔率计算
- 将原始赔率除以返还率，得到标准化的满水赔率
- 支持初始赔率和即时赔率的双重计算
- 自动处理返还率的百分比转换

### 2. 广义实力分析
- 从 `generalized_strength` 表获取队伍实力档次
- 计算主客队实力差（档距差）
- 基于实力差选择不同的推荐策略

### 3. 理论距离查找
- 使用二分查找在标准欧赔表中找到最接近的理论值
- 支持主队和客队的独立查询
- 缓存标准赔率表以提高性能

### 4. 规则匹配系统
- 计算偏移值（理论距离 - 实际档距差）
- 根据偏移值范围匹配规则条件
- 计算规则差值并给出最终推荐

### 5. 双策略推荐
- 档距差 ≥ -1.5：使用标准推荐策略
- 档距差 < -1.5：使用弱队推荐策略

## 文件结构

```
odds_analysis/
├── __init__.py           # 模块初始化
├── analyzer.py           # 核心分析引擎
├── realtime_analyzer.py  # 实时监控服务
├── test_analysis.py      # 测试脚本
└── README.md            # 本文档
```

## 数据库表结构

### 输入表
- `european_odds`: 原始赔率数据
- `generalized_strength`: 队伍实力数据
- `standard_european_odds`: 标准欧赔参考表
- `odds_rule_conditions`: 规则条件表
- `rule_diff_outcomes`: 规则结果表

### 输出表
- `odds_analysis_results`: 分析结果存储

## 使用方法

### 1. 单场比赛分析
```python
from odds_analysis.analyzer import OddsAnalyzer

analyzer = OddsAnalyzer()
result = analyzer.analyze_match(match_id=2701856)
```

### 2. 批量分析
```python
from odds_analysis.realtime_analyzer import RealtimeOddsAnalyzer

analyzer = RealtimeOddsAnalyzer()
success_count = analyzer.analyze_batch([2701856, 2701857])
```

### 3. 实时监控模式
```bash
# 守护进程模式，每10秒检查新数据
python odds_analysis/realtime_analyzer.py --daemon --interval 10

# 批量分析指定比赛
python odds_analysis/realtime_analyzer.py --batch 2701856 2701857

# 交互模式
python odds_analysis/realtime_analyzer.py
```

### 4. 获取分析结果
```python
# 获取比赛汇总
summary = analyzer.get_match_summary(match_id)

# 获取最新结果
results = analyzer.get_latest_results(limit=10)
```

## 分析流程

1. **数据获取**
   - 从 `european_odds` 获取最新赔率
   - 从 `generalized_strength` 获取队伍实力

2. **满水计算**
   - 初始满水 = 初始赔率 / (初始返还率/100)
   - 即时满水 = 即时赔率 / (即时返还率/100)

3. **理论查找**
   - 在标准欧赔表中二分查找最接近的满水赔率
   - 获取对应的理论 distance 值

4. **偏移计算**
   - 主队偏移 = 主队理论distance - 实际档距差
   - 客队偏移 = 客队理论distance - 实际档距差

5. **规则匹配**
   - 根据偏移值范围确定规则值
   - 计算规则差 = 主队规则值 - 客队规则值

6. **结果推荐**
   - 根据规则差和档距差阈值选择推荐结果
   - 提供置信度评级（high/medium/low）

## 运行要求

- Python 3.7+
- MySQL 5.7+
- 依赖库：pymysql, numpy

## 性能优化

- 标准赔率表缓存在内存中
- 使用二分查找提高查询速度
- 支持批量分析减少数据库连接开销
- 异步分析模式支持并发处理

## 注意事项

1. 确保数据库中有足够的历史赔率数据
2. 定期更新标准欧赔表和规则表
3. 监控分析结果的准确率并调整规则
4. 注意处理数据缺失情况（如某些公司无广义实力数据）