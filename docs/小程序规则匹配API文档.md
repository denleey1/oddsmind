# 小程序规则匹配API文档

> 更新时间: 2026-01-31
> 版本: v2.0（新增细化阈值规则）

## 概述

本文档描述了精准规则匹配系统的API接口，供小程序调用。

### 基础信息

- **基础URL**: `https://your-domain.com`（替换为实际域名）
- **请求格式**: JSON
- **响应格式**: JSON
- **数据来源**: 威廉希尔（company_id=115）

### 规则准入标准

| 联赛类型 | 准确率要求 | 样本要求 |
|----------|-----------|----------|
| 五大联赛（英超/西甲/意甲/德甲/法甲） | **100%命中** | ≥3场 |
| 普通联赛 | **90%+命中** | ≥5场 |

### 动态监测说明

⚠️ **重要**: 规则匹配结果是**动态变化**的！

```
赔率实时变化 → 特征重新计算 → 规则重新匹配
```

- 后台服务每 **60秒** 检查一次
- 赔率变化后，之前符合的比赛可能不再符合，反之亦然
- 建议在 **临近开赛时** 获取最新匹配结果

---

## 核心概念

### 1. 让球方 vs 受让方

| 概念 | 定义 | 判断方式 |
|------|------|----------|
| **让球方** | 被看好的一方（强队） | 初赔较低 |
| **受让方** | 不被看好的一方（弱队） | 初赔较高 |

示例：朗斯(1.58) vs 勒阿弗尔(7.14) → 朗斯是让球方

### 2. 盘型分类

| 盘型 | 含义 | 预测倾向 |
|------|------|----------|
| **韬光** | 赔率偏高，不看好 | 该方可能输 |
| **超韬** | 赔率极高，强烈不看好 | 该方很可能输 |
| **高开** | 开盘赔率偏高 | 有调整空间 |
| **实开** | 正常赔率 | 中性 |
| **低开** | 开盘赔率偏低 | 被看好 |
| **超实/超散/超深** | 各种偏离正常值 | 需具体分析 |

### 3. 赔率变化幅度（v2.0新增）

| 分类 | 变化幅度 | 代码标识 |
|------|----------|----------|
| **暴升** | >15% | `暴升(>15%)` |
| **大升** | 10-15% | `大升(10-15%)` |
| **小升** | 5-10% | `小升(5-10%)` |
| **微升** | 2-5% | `微升(2-5%)` |
| **稳定** | ±2% | `稳定(±2%)` |
| **微降** | 2-5% | `微降(2-5%)` |
| **小降** | 5-10% | `小降(5-10%)` |
| **大降** | 10-15% | `大降(10-15%)` |
| **暴降** | >15% | `暴降(>15%)` |

### 4. 力量差

| 分类 | 力量差值 | 含义 |
|------|----------|------|
| **强让** | >2 | 让球方明显强 |
| **微让** | 0.5-2 | 让球方略强 |
| **平手** | -0.5~0.5 | 实力接近 |
| **微受** | -2~-0.5 | 让球方略弱 |
| **强受** | <-2 | 让球方明显弱 |

---

## API接口

### 1. 获取今日规则匹配

获取今天和明天符合精准规则的比赛。

**请求**
```
GET /api/rule-alerts/today
```

**响应示例**
```json
{
  "success": true,
  "date": "2026-01-31",
  "summary": {
    "total_matches": 13,
    "handicap_win_count": 6,
    "receiver_not_lose_count": 7,
    "big5_count": 3,
    "other_count": 10
  },
  "handicap_win": [
    {
      "match_id": 2800191,
      "home_team": "朗斯",
      "away_team": "勒阿弗尔",
      "league_name": "法国甲组联赛",
      "league_id": 11,
      "is_big5": true,
      "big5_name": "法甲",
      "match_time": "2026-01-31T03:45:00",
      "match_status": "scheduled",
      "handicap_team": "朗斯",
      "receiver_team": "勒阿弗尔",
      "features": {
        "power": "强让",
        "curr_h": "超实",
        "curr_r": "韬光",
        "h_change": "小降(5-10%)",
        "r_change": "小升(5-10%)"
      },
      "rules": [
        {
          "rule_id": "HW002",
          "rule_name": "【五大】强让+让方赔率降",
          "prediction": "让方必赢",
          "bet_suggestion": "买 朗斯 赢",
          "accuracy": 1.0,
          "accuracy_pct": "100%",
          "sample": 3
        }
      ]
    }
  ],
  "receiver_not_lose": [
    {
      "match_id": 2784706,
      "home_team": "拉齐奥",
      "away_team": "热那亚",
      "league_name": "意大利甲组联赛",
      "league_id": 34,
      "is_big5": true,
      "big5_name": "意甲",
      "match_time": "2026-01-31T03:45:00",
      "features": {
        "power": "微让",
        "curr_h": "韬光",
        "curr_r": "实开",
        "h_change": "小升(5-10%)",
        "r_change": "微降(2-5%)"
      },
      "rules": [
        {
          "rule_id": "RN002",
          "rule_name": "【五大】即时让方韬光",
          "prediction": "受让方不输",
          "bet_suggestion": "买 热那亚 不输",
          "accuracy": 1.0,
          "accuracy_pct": "100%",
          "sample": 8
        },
        {
          "rule_id": "RN007",
          "rule_name": "【五大·精细】即时让方韬光+让方小升(5-10%)",
          "prediction": "受让方不输",
          "bet_suggestion": "买 热那亚 不输",
          "accuracy": 1.0,
          "accuracy_pct": "100%",
          "sample": 3
        }
      ]
    }
  ]
}
```

**字段说明**

| 字段 | 类型 | 说明 |
|------|------|------|
| `features.power` | string | 力量差：强让/微让/平手/微受/强受 |
| `features.curr_h` | string | 即时让方盘型 |
| `features.curr_r` | string | 即时受让方盘型 |
| `features.h_change` | string | 让方赔率变化（细化分类） |
| `features.r_change` | string | 受让方赔率变化（细化分类） |
| `rules[].accuracy` | number | 历史命中率(0-1) |
| `rules[].sample` | number | 历史样本数 |

---

### 2. 获取指定比赛的规则匹配

**请求**
```
GET /api/rule-alerts/match/{match_id}
```

**响应示例**
```json
{
  "success": true,
  "match_id": 2784706,
  "has_alert": true,
  "match_info": {
    "home_team": "拉齐奥",
    "away_team": "热那亚",
    "league_name": "意大利甲组联赛",
    "is_big5": true,
    "match_time": "2026-01-31T03:45:00"
  },
  "features": {
    "power": "微让",
    "init_h": "高开",
    "curr_h": "韬光",
    "h_change": "小升(5-10%)",
    "r_change": "微降(2-5%)"
  },
  "rules": [
    {
      "rule_id": "RN002",
      "rule_name": "【五大】即时让方韬光",
      "prediction": "受让方不输",
      "accuracy": 1.0
    }
  ]
}
```

---

### 3. 获取所有规则列表

**请求**
```
GET /api/rules
```

**响应示例**
```json
{
  "success": true,
  "total_rules": 20,
  "rules": {
    "handicap_win": [
      {
        "id": "HW001",
        "name": "强让+即时受让方超韬+受让方升",
        "prediction": "让方必赢",
        "apply_to": "all",
        "description": "力量差为强让，即时受让方超韬盘，且受让方赔率上升"
      },
      {
        "id": "HW004",
        "name": "【五大·精细】强让+让方微降(2-5%)+受让方小升(5-10%)",
        "prediction": "让方必赢",
        "apply_to": "big5_only",
        "description": "五大联赛，强让+让方赔率微降2-5%+受让方赔率小升5-10%"
      }
    ],
    "receiver_not_lose": [
      {
        "id": "RN007",
        "name": "【五大·精细】即时让方韬光+让方小升(5-10%)",
        "prediction": "受让方不输",
        "apply_to": "big5_only",
        "description": "五大联赛，即时让方韬光+让方赔率小升5-10%"
      }
    ]
  }
}
```

---

## 完整规则列表（v2.0）

### 🔴 让方必赢规则（6条）

| ID | 规则名称 | 条件 | 适用 | 命中率 |
|----|----------|------|------|--------|
| HW001 | 强让+即时受让方超韬+受让方升 | 强让 & 受让方超韬 & 受让方赔率↑ | 全部 | 100% |
| HW002 | 【五大】强让+让方赔率降 | 强让 & 让方赔率↓ | 五大 | 100% |
| HW003 | 【五大】强让+让方降+受让方升 | 强让 & 让方↓ & 受让方↑ | 五大 | 100% |
| HW004 | 【五大·精细】强让+让方微降(2-5%)+受让方小升(5-10%) | 强让 & 让方微降 & 受让方小升 | 五大 | 100% |
| HW005 | 【五大·精细】强让+即时受让方高开+受让方小升(5-10%) | 强让 & 受让方高开 & 受让方小升 | 五大 | 100% |
| HW006 | 【普通·精细】强让+让方微降(2-5%) | 强让 & 让方微降 | 普通 | 100% |

### 🟢 受让方不输规则（14条）

| ID | 规则名称 | 条件 | 适用 | 命中率 |
|----|----------|------|------|--------|
| RN001 | 初让方高开→即时韬光 | 初盘高开 → 即时韬光 | 全部 | 100% |
| RN002 | 【五大】即时让方韬光 | 即时让方韬光 | 五大 | 100% |
| RN003 | 【五大】即时让方韬光+让方赔率升 | 韬光 & 让方↑ | 五大 | 100% |
| RN004 | 【五大】即时让方韬光+受让方赔率降 | 韬光 & 受让方↓ | 五大 | 100% |
| RN005 | 【五大】即时让方超韬 | 即时让方超韬 | 五大 | 100% |
| RN006 | 【五大·精细】即时让方韬光+让方暴升(>15%) | 韬光 & 让方暴升 | 五大 | 100% |
| RN007 | 【五大·精细】即时让方韬光+让方小升(5-10%) | 韬光 & 让方小升 | 五大 | 100% |
| RN008 | 【五大·精细】即时让方超韬+让方暴升(>15%) | 超韬 & 让方暴升 | 五大 | 100% |
| RN009 | 【五大】微让+即时让方韬光 | 微让 & 韬光 | 五大 | 100% |
| RN010 | 【普通·精细】即时让方高开+让方暴升(>15%) | 高开 & 让方暴升 | 普通 | 100% |
| RN011 | 【普通·精细】即时让方韬光+受让方大降(10-15%) | 韬光 & 受让方大降 | 普通 | 100% |
| RN012 | 【普通·精细】即时让方高开+受让方暴降(>15%) | 高开 & 受让方暴降 | 普通 | 100% |
| RN013 | 【普通·精细】初让方低开→即时高开+让方暴升(>15%) | 低开→高开 & 让方暴升 | 普通 | 100% |
| RN014 | 微让+即时让方韬光 | 微让 & 韬光 | 全部 | 90.9% |

---

## 小程序前端展示建议

### 1. 列表页展示

```html
<!-- 比赛卡片 -->
<view class="match-card" wx:for="{{matches}}" wx:key="match_id">
  <!-- 联赛标签 -->
  <view class="league-tag {{item.is_big5 ? 'big5' : ''}}">
    {{item.is_big5 ? item.big5_name : item.league_name}}
  </view>
  
  <!-- 比赛信息 -->
  <view class="teams">{{item.home_team}} vs {{item.away_team}}</view>
  <view class="time">{{item.match_time}}</view>
  
  <!-- 规则标签 -->
  <view class="rule-tags">
    <view class="tag {{rule.prediction == '让方必赢' ? 'red' : 'green'}}" 
          wx:for="{{item.rules}}" wx:for-item="rule" wx:key="rule_id">
      {{rule.prediction}} {{rule.accuracy_pct}}
    </view>
  </view>
  
  <!-- 投注建议 -->
  <view class="suggestion">
    👉 {{item.rules[0].bet_suggestion}}
  </view>
</view>
```

### 2. 颜色编码

```css
/* 让方必赢 - 红色系 */
.tag.red {
  background: linear-gradient(135deg, #ff6b6b, #ee5a5a);
  color: white;
}

/* 受让方不输 - 绿色系 */
.tag.green {
  background: linear-gradient(135deg, #52c41a, #389e0d);
  color: white;
}

/* 五大联赛标识 */
.league-tag.big5 {
  background: #ffd700;
  color: #333;
  font-weight: bold;
}

/* 精细规则特殊标识 */
.rule-name:contains('精细') {
  border: 1px solid #1890ff;
}
```

### 3. 特征展示组件

```html
<!-- 赔率变化展示 -->
<view class="feature-row">
  <text class="label">让方变化:</text>
  <text class="value {{getChangeClass(features.h_change)}}">
    {{features.h_change}}
  </text>
</view>

<view class="feature-row">
  <text class="label">受让方变化:</text>
  <text class="value {{getChangeClass(features.r_change)}}">
    {{features.r_change}}
  </text>
</view>
```

```javascript
// 获取变化样式类
getChangeClass(change) {
  if (change.includes('升')) return 'up';
  if (change.includes('降')) return 'down';
  return 'stable';
}
```

```css
.value.up { color: #f5222d; }   /* 上升-红色 */
.value.down { color: #52c41a; } /* 下降-绿色 */
.value.stable { color: #999; }  /* 稳定-灰色 */
```

### 4. 实时刷新建议

```javascript
Page({
  data: {
    alerts: [],
    lastUpdate: null
  },
  
  onLoad() {
    this.loadAlerts();
    // 每2分钟刷新一次
    this.refreshTimer = setInterval(() => {
      this.loadAlerts();
    }, 120000);
  },
  
  onUnload() {
    clearInterval(this.refreshTimer);
  },
  
  async loadAlerts() {
    const res = await wx.request({
      url: 'https://your-domain.com/api/rule-alerts/today'
    });
    
    if (res.data.success) {
      this.setData({
        alerts: res.data,
        lastUpdate: new Date().toLocaleTimeString()
      });
    }
  },
  
  // 下拉刷新
  onPullDownRefresh() {
    this.loadAlerts().then(() => {
      wx.stopPullDownRefresh();
    });
  }
});
```

---

## 注意事项

1. **规则是动态的** - 赔率变化后规则匹配结果会变，建议定时刷新
2. **关注精细规则** - 带【精细】标识的规则条件更严格，信号更强
3. **五大联赛优先** - 五大联赛规则100%命中，普通联赛90%+
4. **投注建议仅供参考** - 任何投注都有风险

---

## 更新日志

### v2.0 (2026-01-31)
- 新增细化阈值规则（微降/小降/大降/暴降等）
- 新增6条五大联赛精细规则
- 新增4条普通联赛精细规则
- 优化API响应结构，添加features字段

### v1.0 (2026-01-30)
- 初始版本，包含10条基础规则
