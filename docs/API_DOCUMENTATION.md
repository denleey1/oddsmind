# OddsMind API 接口文档

## 🌐 基础信息

- **基础URL**: `https://oddsmind.top`
- **协议**: HTTPS
- **端口**: 443 (HTTPS默认端口，URL中**无需指定**)
- **API前缀**: `/api`

---

## 📋 所有API接口列表

### 一、监控相关接口（需要登录认证）

#### 1. 获取监控状态
```
GET  https://oddsmind.top/api/monitor/status
GET  https://oddsmind.top/api/v1/monitor/status
```
- **认证**: 需要登录
- **说明**: 获取当前监控服务运行状态

#### 2. 获取调度器状态
```
GET  https://oddsmind.top/api/scheduler/status
GET  https://oddsmind.top/api/v1/scheduler/status
```
- **认证**: 需要登录
- **说明**: 获取定时任务调度器状态

#### 3. 手动执行任务
```
POST https://oddsmind.top/api/scheduler/tasks/run
POST https://oddsmind.top/api/v1/scheduler/tasks/run
```
- **认证**: 需要登录
- **请求体**: `{"task_name": "leagues_update"}` 或 `"odds_update"` 或 `"strength_calculation"`
- **说明**: 手动触发定时任务执行

#### 4. 初始化监控
```
POST https://oddsmind.top/api/monitoring/initialize
POST https://oddsmind.top/api/v1/monitoring/initialize
```
- **认证**: 需要登录
- **说明**: 手动初始化监控服务

#### 5. 获取监控比赛列表
```
GET  https://oddsmind.top/api/monitoring/matches
GET  https://oddsmind.top/api/v1/monitoring/matches
```
- **认证**: 需要登录
- **说明**: 获取当前正在监控的比赛列表

---

### 二、比赛数据接口

#### 6. 获取今日比赛（需认证，包含完整分析）
```
GET  https://oddsmind.top/api/matches/today
GET  https://oddsmind.top/api/matches/today?status=scheduled
GET  https://oddsmind.top/api/matches/today?status=live
GET  https://oddsmind.top/api/matches/today?status=finished
```
- **认证**: 需要登录
- **参数**: 
  - `status` (可选): `scheduled` | `live` | `finished`
- **说明**: 返回今日比赛列表，包含完整的基本面分析数据

#### 7. 获取今日比赛（公开接口，无需认证）⭐推荐小程序使用
```
GET  https://oddsmind.top/api/public/matches/today
GET  https://oddsmind.top/api/public/matches/today?status=scheduled
GET  https://oddsmind.top/api/public/matches/today?status=live
GET  https://oddsmind.top/api/public/matches/today?status=finished
```
- **认证**: 无需认证
- **参数**: 
  - `status` (可选): `scheduled` | `live` | `finished`
- **说明**: 返回今日比赛列表（基础信息，不含分析数据）
- **适合**: 微信小程序调用

#### 8. 获取比赛详情（需认证）
```
GET  https://oddsmind.top/api/matches/<match_id>
```
- **认证**: 需要登录
- **示例**: `https://oddsmind.top/api/matches/2791718`
- **说明**: 返回比赛详细信息，包含完整分析

#### 9. 获取比赛详情（公开接口，无需认证）⭐推荐小程序使用
```
GET  https://oddsmind.top/api/public/matches/<match_id>
```
- **认证**: 无需认证
- **示例**: `https://oddsmind.top/api/public/matches/2791718`
- **说明**: 返回比赛详细信息（基础信息）
- **适合**: 微信小程序调用

#### 10. 获取比赛所有分析（需认证）
```
GET  https://oddsmind.top/api/matches/<match_id>/all_analyses
```
- **认证**: 需要登录
- **示例**: `https://oddsmind.top/api/matches/2791718/all_analyses`
- **说明**: 返回比赛的所有赔率分析结果

---

### 三、其他接口

#### 11. 健康检查（无需认证）
```
GET  https://oddsmind.top/health
```
- **认证**: 无需认证
- **说明**: 服务健康检查接口，返回服务状态信息

#### 12. 首页（需认证）
```
GET  https://oddsmind.top/
```
- **认证**: 需要登录
- **说明**: 返回HTML页面

---

## 📱 微信小程序推荐使用的API

### ✅ 公开接口（无需认证，推荐使用）

1. **获取今日比赛**
   ```
   GET https://oddsmind.top/api/public/matches/today
   GET https://oddsmind.top/api/public/matches/today?status=scheduled
   GET https://oddsmind.top/api/public/matches/today?status=live
   GET https://oddsmind.top/api/public/matches/today?status=finished
   ```

2. **获取比赛详情**
   ```
   GET https://oddsmind.top/api/public/matches/<match_id>
   ```

3. **健康检查**
   ```
   GET https://oddsmind.top/health
   ```

### ⚠️ 需要认证的接口（需要先登录）

如果需要使用需要认证的接口，需要先调用登录接口获取session，然后在请求头中携带cookie。

---

## 🔒 关于端口的重要说明

### ✅ 正确用法

```
https://oddsmind.top/api/xxx
```

**HTTPS默认端口是443，URL中无需指定端口**

### ❌ 错误用法

1. **不要指定443端口**（虽然可以工作，但不规范）
   ```
   https://oddsmind.top:443/api/xxx  ❌
   ```

2. **不要使用HTTP**（不安全，微信小程序不允许）
   ```
   http://oddsmind.top/api/xxx  ❌
   ```

3. **不要直接访问内网端口**（8889是内网端口，外网无法访问）
   ```
   https://oddsmind.top:8889/api/xxx  ❌
   ```

---

## 📝 微信小程序配置示例

```javascript
// 推荐配置
const API_BASE_URL = 'https://oddsmind.top/api';

// 获取今日比赛
wx.request({
  url: `${API_BASE_URL}/public/matches/today`,
  method: 'GET',
  success: (res) => {
    console.log(res.data);
  }
});

// 获取比赛详情
wx.request({
  url: `${API_BASE_URL}/public/matches/2791718`,
  method: 'GET',
  success: (res) => {
    console.log(res.data);
  }
});
```

---

## 🔐 认证说明

### 需要认证的接口

以下接口需要先登录获取session：
- `/api/monitor/status`
- `/api/scheduler/status`
- `/api/scheduler/tasks/run`
- `/api/monitoring/initialize`
- `/api/monitoring/matches`
- `/api/matches/today`
- `/api/matches/<match_id>`
- `/api/matches/<match_id>/all_analyses`

### 公开接口（无需认证）

以下接口可以直接调用，无需登录：
- `/api/public/matches/today`
- `/api/public/matches/<match_id>`
- `/health`

---

## 📊 响应格式

### 成功响应
```json
{
  "success": true,
  "data": { ... },
  "message": "操作成功"
}
```

### 错误响应
```json
{
  "success": false,
  "error": "错误信息",
  "message": "操作失败"
}
```

---

## 🎯 总结

- **基础URL**: `https://oddsmind.top`
- **端口**: 443（HTTPS默认，URL中无需指定）
- **微信小程序推荐**: 使用 `/api/public/` 开头的公开接口
- **所有API地址**: 见上方完整列表

