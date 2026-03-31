# 广义实力计算模块

## 文件说明

### `mysql_general_strength_calculator.py`
- **主要计算器**：适配OddsMind MySQL数据库结构的广义实力计算器
- **功能**：完全按照原版逻辑实现，支持轮次计算、档次分级
- **数据库**：自动保存结果到`team_power_ratings`表
- **使用方法**：
  ```python
  from calculation.mysql_general_strength_calculator import MySQLGeneralStrengthCalculator
  
  # 计算英超广义实力
  calculator = MySQLGeneralStrengthCalculator(league_id=36)
  results = calculator.calculate()
  ```

## 命令行使用

### 1. 单个联赛计算
```bash
# 计算英超（联赛ID=36）广义实力  
python calculation/mysql_general_strength_calculator.py --mode single --league-id 36

# 计算英超指定博彩公司（威廉希尔=115）的广义实力
python calculation/mysql_general_strength_calculator.py --mode single --league-id 36 --company-id 115

# 计算英超特定赛季的广义实力
python calculation/mysql_general_strength_calculator.py --mode single --league-id 36 --season 2024-25
```

### 2. 全部联赛全部公司计算
```bash
# 计算所有联赛所有公司的广义实力（会清空表）
python calculation/mysql_general_strength_calculator.py --mode all

# 计算所有联赛所有公司的广义实力（不清空表）
python calculation/mysql_general_strength_calculator.py --mode all --no-clear-table
```

### 3. 指定联赛全部公司计算
```bash
# 计算英超、西甲、德甲的所有公司广义实力
python calculation/mysql_general_strength_calculator.py --mode leagues --league-ids 36,31,8

# 计算五大联赛的所有公司广义实力
python calculation/mysql_general_strength_calculator.py --mode leagues --league-ids 36,31,8,34,37
```

## Python脚本调用

### 批量计算全部联赛
```python
from calculation.mysql_general_strength_calculator import BatchGeneralStrengthCalculator

# 创建批量计算器
batch_calculator = BatchGeneralStrengthCalculator()

# 计算所有联赛所有公司的广义实力
stats = batch_calculator.calculate_all_leagues_all_companies(clear_table=True)
print(f"成功计算: {stats['successful_calculations']}")
print(f"失败计算: {stats['failed_calculations']}")
```

### 批量计算指定联赛  
```python
# 计算指定联赛的所有公司广义实力
league_ids = [36, 31, 8]  # 英超、西甲、德甲
stats = batch_calculator.calculate_specific_leagues_all_companies(
    league_ids=league_ids, 
    clear_table=True
)
```

### `guangyishili_analyzer.py`
- **参考代码**：原版SQLite广义实力计算器
- **作用**：代码参考和逻辑对比
- **说明**：保留作为实现标准的参考

## 计算逻辑

1. **总场广义实力** = 主场平均不败率 + 客场平均不败率
2. **近况广义实力** = 近况主场平均不败率 + 近况客场平均不败率  
3. **综合广义实力** = 总场广义实力 × 0.2 + 近况广义实力 × 0.8
4. **相对广义实力** = 综合广义实力 - 最小综合广义实力
5. **档距** = 相对广义实力 ÷ 10.5
6. **近况轮次** = 球队最大轮次 - (联赛队伍数 - 1)

## 档次分级

- 超强1: 档距 ≥ 8.5
- 超强2: 档距 ≥ 8.0  
- 人强1: 档距 ≥ 7.5
- 人强2: 档距 ≥ 7.0
- 普强1: 档距 ≥ 6.5
- 普强2: 档距 ≥ 6.0
- 准强1: 档距 ≥ 5.5
- 准强2: 档距 ≥ 5.0
- 中强1: 档距 ≥ 4.5
- 中强2: 档距 ≥ 4.0
- 中上1: 档距 ≥ 3.5
- 中上2: 档距 ≥ 3.0
- 中游1: 档距 ≥ 2.5
- 中游2: 档距 ≥ 2.0
- 中下1: 档距 ≥ 1.5
- 中下2: 档距 ≥ 1.0
- 下游1: 档距 ≥ 0.5
- 下游2: 档距 < 0.5

## 数据库存储

计算结果自动保存到`team_power_ratings`表：

```sql
SELECT * FROM team_power_ratings 
WHERE company_id = 115 AND league_id = 36 
ORDER BY relative_power DESC;
```