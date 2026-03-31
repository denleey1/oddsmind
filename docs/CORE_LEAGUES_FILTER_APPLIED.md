# 核心联赛过滤已应用

## ✅ 已完成的修改

### 1. 更新监控配置
**文件**: `config/monitoring_config.py`

**修改内容**:
- ✅ 定义了核心联赛ID列表（19个）
- ✅ 将 `MONITORED_LEAGUES` 设置为只包含核心联赛
- ✅ 将 `MONITOR_ALL_LEAGUES` 设置为 `False`

**核心联赛ID列表**:
```python
CORE_LEAGUE_IDS = [5, 8, 9, 10, 11, 12, 16, 17, 23, 30, 31, 33, 34, 36, 37, 40, 273, 292, 745]
```

**核心联赛详情**:
1. 5 - 比利时甲组联赛（比甲）
2. 8 - 德国甲组联赛（德甲）
3. 9 - 德国乙组联赛（德乙）
4. 10 - 俄罗斯超级联赛（俄超）
5. 11 - 法国甲组联赛（法甲）
6. 12 - 法国乙组联赛（法乙）
7. 16 - 荷兰甲组联赛（荷甲）
8. 17 - 荷兰乙组联赛（荷乙）
9. 23 - 葡萄牙超级联赛（葡超）
10. 30 - 土耳其超级联赛（土超）
11. 31 - 西班牙甲组联赛（西甲）
12. 33 - 西班牙乙组联赛（西乙）
13. 34 - 意大利甲组联赛（意甲）
14. 36 - 英格兰超级联赛（英超）
15. 37 - 英格兰冠军联赛（英冠）
16. 40 - 意大利乙组联赛（意乙）
17. 273 - 澳大利亚足球超级联赛（澳超）
18. 292 - 沙特阿拉伯职业联赛（沙特超）
19. 745 - 沙特阿拉伯甲级联赛（沙特甲）

---

## 📋 自动应用核心联赛过滤的位置

以下代码位置已经自动使用 `MONITORED_LEAGUES` 配置，无需额外修改：

### 1. API接口
- ✅ `application/routes/web.py`
  - `get_today_matches()` - 今日比赛接口
  - `get_public_today_matches()` - 公共今日比赛接口
  - 自动使用 `MONITORED_LEAGUES` 过滤

### 2. 数据库查询
- ✅ `app_database.py`
  - `get_matches_to_monitor()` - 获取监控比赛
  - 自动使用 `MONITORED_LEAGUES` 过滤

### 3. 监控服务
- ✅ `services/league_status_monitor.py`
  - 联赛状态监控
  - 自动使用 `MONITORED_LEAGUES` 过滤

- ✅ `services/match_status_updater.py`
  - 比赛状态更新
  - 自动使用 `MONITORED_LEAGUES` 过滤

---

## 🔍 验证方法

### 1. 检查配置
```bash
cd /home/ubuntu/oddsmind
python3 -c "from config.monitoring_config import MONITORED_LEAGUES, MONITOR_ALL_LEAGUES; print(f'监控联赛数: {len(MONITORED_LEAGUES)}'); print(f'监控所有联赛: {MONITOR_ALL_LEAGUES}'); print(f'核心联赛ID: {MONITORED_LEAGUES}')"
```

**预期输出**:
```
监控联赛数: 19
监控所有联赛: False
核心联赛ID: [5, 8, 9, 10, 11, 12, 16, 17, 23, 30, 31, 33, 34, 36, 37, 40, 273, 292, 745]
```

### 2. 测试API接口
```bash
# 测试今日比赛接口（应该只返回核心联赛的比赛）
curl "http://127.0.0.1:8889/api/public/matches/today" | python3 -c "import sys, json; d=json.load(sys.stdin); leagues = set(m.get('leagueName', '') for m in d.get('data', [])); print(f'返回的联赛数: {len(leagues)}'); print(f'联赛列表: {sorted(leagues)}')"
```

**预期**: 只返回核心联赛的比赛

### 3. 检查数据库查询
```bash
# 检查监控的比赛是否只来自核心联赛
cd /home/ubuntu/oddsmind
python3 << 'EOF'
from app_database import get_matches_to_monitor
from config.monitoring_config import MONITORED_LEAGUES
matches = get_matches_to_monitor()
league_ids = set(m.get('league_id') for m in matches)
print(f"监控的比赛数: {len(matches)}")
print(f"涉及的联赛ID: {sorted(league_ids)}")
print(f"是否都在核心联赛中: {all(lid in MONITORED_LEAGUES for lid in league_ids)}")
EOF
```

---

## 📊 影响范围

### 自动过滤的功能
以下功能现在**只显示核心联赛**的数据：

1. ✅ **今日比赛接口** (`/api/matches/today`, `/api/public/matches/today`)
   - 只返回核心联赛的比赛

2. ✅ **比赛监控服务**
   - 只监控核心联赛的比赛

3. ✅ **联赛状态监控**
   - 只监控核心联赛的状态

4. ✅ **比赛状态更新**
   - 只更新核心联赛的比赛状态

### 不受影响的功能
- 比赛详情接口（通过match_id查询，不受联赛限制）
- 历史数据（已存在的数据不受影响）

---

## ⚠️ 注意事项

1. **需要重启服务**才能应用新配置
   ```bash
   kill -HUP 713527  # 优雅重启
   # 或
   systemctl restart oddsmind.service
   ```

2. **数据清理**（可选）
   - 如果需要清理非核心联赛的历史数据，需要单独执行清理脚本
   - 当前配置只影响新查询，不删除历史数据

3. **监控范围**
   - 只监控核心联赛（19个）
   - 其他联赛的数据不会被查询或显示

---

## 🎯 总结

✅ **配置已更新**: 只监控核心联赛（19个）  
✅ **自动应用**: 所有相关功能自动使用新配置  
✅ **保持干净**: 只显示核心联赛的数据  

**下一步**: 重启服务以应用新配置

---

**更新日期**: 2025-12-29  
**核心联赛数**: 19个  
**配置状态**: ✅ 已应用













