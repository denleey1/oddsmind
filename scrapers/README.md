# OddsMind 爬虫命令使用指南

## 概述

OddsMind 系统提供了一套完整的足球数据爬取工具，包括联赛信息、比赛数据、积分榜和赔率数据的采集。

## 核心组件

### 1. 主程序 (main.py)
负责联赛、比赛、积分榜等基础数据的爬取。

### 2. 增量赔率更新 (incremental_odds_update.py)  
智能的赔率数据更新工具，根据比赛状态决定是否爬取赔率。

### 3. 公司信息管理
- `populate_companies.py` - 自动发现并添加新的博彩公司
- `update_companies_from_recent.py` - 从最新赔率数据中更新公司信息

## 常用命令

### 基础数据爬取

#### 1. 爬取所有联赛的比赛数据
```bash
# 爬取所有联赛
python main.py scrape-leagues --league-group all

# 爬取特定联赛组
python main.py scrape-leagues --league-group top5_european
python main.py scrape-leagues --league-group asian_leagues
```

#### 2. 爬取指定联赛
```bash
# 英超 (league_id = 36)
python main.py scrape-leagues --league-id 36

# 西甲 (league_id = 31) 
python main.py scrape-leagues --league-id 31

# 德甲 (league_id = 8)
python main.py scrape-leagues --league-id 8
```

#### 3. 爬取积分榜
```bash
# 爬取所有联赛积分榜
python main.py scrape-standings --league-group all

# 爬取指定联赛积分榜
python main.py scrape-standings --league-id 36
```

### 赔率数据爬取

#### 1. 智能增量更新（推荐）
```bash
# 爬取所有庄家公司的赔率
python incremental_odds_update.py --all-companies --max-workers 10

# 爬取指定联赛的所有庄家赔率
python incremental_odds_update.py --league-id 36 --all-companies --max-workers 10

# 爬取特定公司组的赔率
python incremental_odds_update.py --companies top3_mixed --max-workers 10
```

#### 2. 指定公司组合
```bash
# 顶级欧洲公司组合
python incremental_odds_update.py --companies big3_european

# 亚洲公司组合  
python incremental_odds_update.py --companies asian_main

# 混合公司组合
python incremental_odds_update.py --companies top3_mixed
```

#### 3. 模拟运行（测试用）
```bash
# 查看将要处理的比赛，不实际爬取
python incremental_odds_update.py --dry-run --league-id 36
```

### 完整工作流程

#### 场景1: 爬取指定公司的所有数据
```bash
# 爬取马会、澳门、易胜博、威廉希尔、韦德、必赢的全部赔率
python main.py scrape-leagues --league-group all
python incremental_odds_update.py --companies top3_mixed --max-workers 10
```

#### 场景2: 全面数据采集
```bash
# 1. 爬取所有联赛基础数据
python main.py scrape-leagues --league-group all

# 2. 爬取积分榜
python main.py scrape-standings --league-group all  

# 3. 爬取所有庄家赔率
python incremental_odds_update.py --all-companies --max-workers 10
```

#### 场景3: 日常增量更新
```bash
# 每日定时更新，只爬取新的和变化的数据
python main.py scrape-leagues --league-group all
python incremental_odds_update.py --all-companies --max-workers 10
```

## 高级参数

### 并发控制
```bash
# 设置最大并发数（默认10）
--max-workers 15

# 低并发模式（服务器负载小）
--max-workers 5
```

### 联赛组选择
- `all` - 所有联赛
- `top5_european` - 欧洲五大联赛
- `asian_leagues` - 亚洲联赛
- `americas` - 美洲联赛

### 公司组选择  
- `top3_mixed` - 马会、澳门、易胜博、威廉希尔、韦德、必赢
- `big3_european` - 威廉希尔、立博、Interwetten
- `asian_main` - 马会、澳门、皇冠等亚洲公司
- `all` - 所有公司（120+个）

## 维护命令

### 公司信息管理
```bash
# 自动发现并添加新公司
python tools/populate_companies.py

# 从最新数据更新公司信息
python update_companies_from_recent.py
```

### 数据验证
```bash
# 检查数据完整性
python tools/data_validator.py

# 查看数据统计
python tools/stats_checker.py
```

## 智能特性

### 1. 增量更新机制
- 自动跳过已处理的数据
- 根据比赛状态智能判断是否爬取赔率
- 未开始的比赛（scheduled）不爬取赔率

### 2. 错误处理
- 网络超时自动重试
- 数据解析错误跳过并记录
- 数据库连接池自动管理

### 3. 性能优化
- 并发请求提高效率
- 连接池复用减少开销
- 智能跳过重复数据

## 注意事项

1. **首次运行**需要先爬取联赛基础数据，再爬取赔率
2. **赔率爬取**会自动跳过scheduled状态的比赛
3. **公司数据**会在首次爬取赔率时自动发现和添加
4. **并发数**不宜过高，建议5-15之间
5. **网络稳定性**影响爬取成功率，建议在网络条件良好时运行

## 故障排除

### 常见错误
- `公司不存在` - 运行 `python tools/populate_companies.py`
- `联赛数据缺失` - 先运行联赛爬取命令
- `网络超时` - 降低并发数或检查网络连接
- `数据库连接失败` - 检查数据库配置和服务状态

### 日志查看
```bash
# 查看详细日志
tail -f logs/scraper.log

# 查看错误日志
grep ERROR logs/scraper.log
```