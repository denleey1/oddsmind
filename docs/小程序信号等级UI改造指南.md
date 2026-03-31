# 小程序信号等级 UI 改造指南

## 一、背景

API 已升级到 v3.2，新增信号分级：**重仓 / 强烈 / 参考**。  
30天验证数据：重仓 91.2%、强烈 84.4%、参考 76.4%。  
小程序需要在 UI 上体现这个分级，让用户一眼区分推荐价值。

---

## 二、API 无需改动

接口地址不变：`GET /api/rule-alerts/today`

返回格式完全向后兼容，**原有字段全部保留**，新增以下字段：

### 2.1 每场比赛新增字段

| 字段 | 类型 | 值 | 说明 |
|------|------|------|------|
| `signal_level` | string | `"重仓"` / `"强烈"` / `"参考"` | 信号等级 |
| `signal_icon` | string | `"🔴"` / `"🟠"` / `"🟡"` | 信号图标 |
| `cross_confirm` | bool | true/false | 是否跨体系确认 |
| `grade_summary` | string | `"2S+0A"` | S/A级规则数汇总 |

### 2.2 summary 新增字段

```json
{
  "heavy_bet_count": 4,       // 重仓场次
  "strong_signal_count": 2,   // 强烈场次  
  "reference_count": 4        // 参考场次
}
```

### 2.3 新增分组数组

| 数组 | 说明 |
|------|------|
| `heavy_bets` | 重仓比赛列表 |
| `strong_signals` | 强烈比赛列表 |
| `reference_signals` | 参考比赛列表 |

> 原有的 `handicap_not_lose` 和 `receiver_not_lose` 数组不变，仍包含所有信号。

---

## 三、小程序 UI 改动点

### 3.1 比赛卡片 — 加信号标签

在每张比赛卡片的左上角或顶部，根据 `signal_level` 显示一个彩色标签：

```
┌─────────────────────────────────────┐
│ 🔴 重仓                    英超      │
│ 西汉姆联 vs 曼彻斯特联               │
│ 02-12 04:15                         │
│ 让方不输 → 买曼彻斯特联不输           │
│ 规则: WL-H16(S) + V1-HN01(S)       │
└─────────────────────────────────────┘
```

**样式映射：**

```javascript
// 信号等级配置
const SIGNAL_CONFIG = {
  '重仓': {
    color: '#FF3B30',      // 红色
    bgColor: '#FFF0F0',    // 浅红背景
    icon: '🔴',
    label: '重仓',
    desc: '高置信度推荐'
  },
  '强烈': {
    color: '#FF9500',      // 橙色
    bgColor: '#FFF8F0',    // 浅橙背景
    icon: '🟠',
    label: '强烈',
    desc: '较高置信度'
  },
  '参考': {
    color: '#999999',      // 灰色
    bgColor: '#F5F5F5',    // 浅灰背景
    icon: '🟡',
    label: '参考',
    desc: '仅供参考'
  }
};
```

### 3.2 读取方式

数据在原有的 `handicap_not_lose` 数组里，每个 item 已经带了 `signal_level`：

```javascript
// 原有代码大概是这样遍历的：
const matches = res.data.handicap_not_lose;

matches.forEach(match => {
  // 新增：读取信号等级
  const level = match.signal_level;  // "重仓" / "强烈" / "参考"
  const icon = match.signal_icon;    // "🔴" / "🟠" / "🟡"
  
  // 根据 level 设置样式
  const config = SIGNAL_CONFIG[level] || SIGNAL_CONFIG['参考'];
});
```

### 3.3 列表页 — 顶部统计栏

在列表顶部显示今日信号汇总：

```
┌──────────────────────────────────┐
│  🔴 重仓 4场  🟠 强烈 2场  🟡 参考 4场  │
└──────────────────────────────────┘
```

读取 summary 字段：

```javascript
const summary = res.data.summary;
const heavyCount = summary.heavy_bet_count;
const strongCount = summary.strong_signal_count;
const refCount = summary.reference_count;
```

### 3.4 排序与分组

建议按信号等级排序，重仓在最前面：

```javascript
const ORDER = { '重仓': 0, '强烈': 1, '参考': 2 };

matches.sort((a, b) => {
  const oa = ORDER[a.signal_level] ?? 9;
  const ob = ORDER[b.signal_level] ?? 9;
  if (oa !== ob) return oa - ob;
  // 同等级按比赛时间排
  return (a.match_time || '').localeCompare(b.match_time || '');
});
```

或者直接用新的分组数组分区展示：

```javascript
const heavyBets = res.data.heavy_bets;         // 重仓列表
const strongSignals = res.data.strong_signals;  // 强烈列表
const refSignals = res.data.reference_signals;  // 参考列表
```

### 3.5 参考信号弱化展示（可选）

参考信号可以视觉弱化，比如：
- 透明度降低（opacity: 0.6）
- 卡片加虚线边框
- 默认折叠，点击展开
- 或直接不展示（只展示重仓+强烈）

---

## 四、信号等级说明（可放在小程序"关于"页）

| 等级 | 含义 | 历史命中率 | 建议 |
|------|------|-----------|------|
| 🔴 重仓 | 2-4条S级规则同时触发 | 91.2% | 推荐跟进 |
| 🟠 强烈 | 多条规则触发或S+A混合 | 84.4% | 可以考虑 |
| 🟡 参考 | 单条规则触发 | 76.4% | 仅供参考 |

---

## 五、改动量评估

| 改动 | 工作量 | 必要性 |
|------|--------|--------|
| 卡片加 signal_level 标签 | 小（读字段+加样式） | **必须** |
| 顶部统计栏 | 小 | 推荐 |
| 按等级排序/分组 | 小 | 推荐 |
| 参考信号弱化 | 小 | 可选 |

总计：约 1-2 小时前端工作量，不需要改任何请求逻辑。
