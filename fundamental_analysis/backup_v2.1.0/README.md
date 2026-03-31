# 基本面分析模块

## 功能说明
提供足球比赛基本面数据的获取、解析和分析功能。

## 模块结构
```
fundamental_analysis/
├── __init__.py         # 模块初始化
├── calculator.py       # 基本面评分计算器
├── scraper.py         # 数据爬取和解析
├── league_manager.py   # 联赛管理器
└── example.py         # 使用示例
```

## 核心功能

### 1. 数据获取 (scraper.py)
- `FundamentalDataFetcher`: 一站式数据获取器
- `FundamentalScraper`: 网页爬取
- `FundamentalParser`: 数据解析

### 2. 评分计算 (calculator.py)
- `FundamentalCalculator`: 基本面评分计算
- 支持近期表现、主客场表现、历史交锋三维度分析
- 权重分配：近期30%、主客场40%、交锋30%

### 3. 联赛管理 (league_manager.py)
- `LeagueManager`: 联赛信息管理
- `get_league_name`: 动态联赛检测

## 快速使用

### 完整流程
```python
from fundamental_analysis import FundamentalDataFetcher, FundamentalCalculator

# 1. 获取数据
fetcher = FundamentalDataFetcher()
data = fetcher.fetch_and_parse("2702235")  # 比赛ID

# 2. 计算评分
calculator = FundamentalCalculator()
result = calculator.calculate_analysis_scores(data)

# 3. 查看结果
scores = result['final_scores']
print(f"主胜: {scores['home_win']:.1f}")
print(f"平局: {scores['draw']:.1f}")
print(f"客胜: {scores['away_win']:.1f}")
```

### 仅计算（已有数据）
```python
from fundamental_analysis import FundamentalCalculator

calculator = FundamentalCalculator()
result = calculator.calculate_analysis_scores(parsed_data)
```

## 数据格式

### 输入数据格式 (parsed_data)
```python
{
    'match_id': '2702235',
    'basic_info': {
        'home_team': '主队名',
        'away_team': '客队名',
        'league': '联赛名'
    },
    'analysis_data': {
        'history': [...],         # 历史交锋记录
        'home_team_history': [...], # 主队近期战绩
        'away_team_history': [...] # 客队近期战绩
    }
}
```

### 输出结果格式
```python
{
    'final_scores': {
        'home_win': 6.7,  # 主胜评分
        'draw': 6.6,      # 平局评分
        'away_win': 5.1   # 客胜评分
    },
    'confidence_level': '信心充足',
    'recommended_outcome': 'home_win',
    'weights': {...},
    'odds_patterns': [...]
}
```

## 运行示例
```bash
# 运行完整示例
python fundamental_analysis/example.py

# 测试爬虫功能
python fundamental_analysis/scraper.py
```

## 注意事项
1. 需要网络连接才能爬取数据
2. 联赛名称会自动检测，未识别时使用全部数据
3. 评分范围：0-10分，越高越有可能