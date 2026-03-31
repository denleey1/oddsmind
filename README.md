# OddsMind - 足球赔率数据采集与分析系统

## 功能特点

- ✅ **符合PEP 8规范**：代码规范，类型提示完整
- ✅ **配置文件驱动**：使用YAML配置文件，灵活配置数据源
- ✅ **SQLite数据库存储**：结构化存储，方便查询分析
- ✅ **自动清理**：自动清理临时JS和JSON文件
- ✅ **完整日志**：详细的日志记录，便于调试
- ✅ **错误处理**：完善的异常处理和重试机制

## 快速开始

### 1. 安装依赖
```bash
pip install -r requirements.txt
```

### 2. 配置文件
编辑 `config.yaml` 设置数据源URL和其他参数

### 3. 运行爬虫
```bash
python titan007_parser.py
```

## 项目结构
```
OddsMind/
├── config.yaml          # 配置文件
├── titan007_parser.py   # 主程序
├── requirements.txt     # 依赖包
├── README.md           # 说明文档
├── docs/               # 文档文件夹（所有.md文档文件）
└── data/               # 数据目录（自动创建）
    └── titan007_football.db  # SQLite数据库
```

**注意**：所有项目文档（.md文件）都存放在 `docs/` 文件夹中，请查看 `docs/README.md` 获取文档索引。

## 数据库结构

### 1. leagues表（联赛信息）
- `league_id`: 联赛ID（主键）
- `name_cn/tw/en`: 联赛名称（中文/繁体/英文）
- `season`: 赛季
- `total_rounds`: 总轮次
- `current_round`: 当前轮次

### 2. teams表（球队信息）
- `team_id`: 球队ID（主键）
- `name_cn/tw/en`: 球队名称
- `logo`: 队徽图片路径

### 3. matches表（比赛数据）
- `match_id`: 比赛ID（主键）
- `league_id`: 联赛ID（外键）
- `round_number`: 轮次
- `match_time`: 比赛时间
- `home_team_id/away_team_id`: 主客队ID（外键）
- `full_score/half_score`: 全场/半场比分
- `handicap`: 让球盘
- `total_goals`: 大小球盘
- `match_status`: 比赛状态

### 4. standings表（积分榜）
- `team_id`: 球队ID（外键）
- `standing_type`: 积分榜类型（total/home/away）
- `rank`: 排名
- `played/wins/draws/losses`: 场次/胜/平/负
- `goals_for/against`: 进球/失球
- `points`: 积分

## 配置说明

### 数据源配置
```yaml
data_sources:
  epl_2025_2026:
    url: "https://zq.titan007.com/..."
    league_id: 36
    season: "2025-2026"
```

### 数据库配置
```yaml
database:
  path: "data/titan007_football.db"  # 数据库路径
  rebuild: false                      # 是否重建数据库
```

### 临时文件配置
```yaml
temp_files:
  keep_temp: false  # 是否保留临时文件
  temp_dir: "temp"  # 临时文件目录
```

## 使用示例

### 查询数据库
```python
import sqlite3

conn = sqlite3.connect('data/titan007_football.db')
cursor = conn.cursor()

# 查询所有比赛
cursor.execute("SELECT * FROM matches WHERE match_status='已结束'")
matches = cursor.fetchall()

# 查询积分榜
cursor.execute("SELECT * FROM standings WHERE standing_type='total' ORDER BY rank")
standings = cursor.fetchall()

conn.close()
```

## 注意事项

1. 首次运行会自动创建 `data` 目录和数据库
2. 临时JS和JSON文件会自动清理
3. 可通过配置文件切换不同联赛数据源
4. 数据仅供学习研究使用

## License

仅供学习研究使用，请遵守相关网站的使用条款。