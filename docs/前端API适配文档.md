# 前端 API 适配文档

## 📋 概述

本次更新修复了服务端的安全问题，并对 API 响应格式进行了增强。前端需要适配以下变更：

1. **认证机制增强** - API 接口现在必须提供有效的 JWT Token
2. **错误响应格式统一** - 所有错误响应现在包含 `error_code` 字段
3. **状态信息增强** - 登录/激活接口返回更详细的用户状态信息
4. **错误码规范** - 使用标准错误码便于前端判断和处理

---

## 🔐 1. 认证机制变更

### 变更说明

**之前：** 部分 `/api/*` 接口可以在没有 Token 的情况下访问  
**现在：** 所有 `/api/*` 接口必须提供有效的 Bearer Token，否则返回 401

### 前端适配

#### 1.1 请求头设置

所有 API 请求必须包含 `Authorization` 头：

```javascript
// 正确的方式
headers: {
  'Authorization': `Bearer ${token}`,
  'Content-Type': 'application/json'
}
```

#### 1.2 401 错误处理

当收到 401 响应时，前端需要：

1. **清除本地存储的 Token**
2. **跳转到登录页面**
3. **显示错误提示**

```javascript
// 示例：axios 拦截器
axios.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      // 清除 Token
      localStorage.removeItem('token');
      // 清除用户信息
      localStorage.removeItem('user');
      // 跳转到登录页
      router.push('/login');
      // 显示错误提示
      showError('登录已过期，请重新登录');
    }
    return Promise.reject(error);
  }
);
```

#### 1.3 401 响应格式

```json
{
  "success": false,
  "error": "需要登录认证",
  "error_code": "AUTH_REQUIRED"
}
```

**常见错误码：**
- `AUTH_REQUIRED` - 缺少认证 Token
- `INVALID_TOKEN` - Token 无效或已过期
- `NOT_ACTIVATED` - 账号未激活
- `EXPIRED_TOKEN` - 账号已过期
- `USER_NOT_FOUND` - 用户不存在

---

## 📝 2. 登录接口变更

### 2.1 接口地址

```
POST /api/miniprogram/login
```

### 2.2 请求格式

```json
{
  "code": "wx.login()获取的code"
}
```

### 2.3 响应格式变更

#### 场景 1：用户未激活

**响应状态码：** `200`  
**响应体：**

```json
{
  "success": true,
  "data": {
    "openid": "xxx",
    "is_activated": false,
    "status": "NOT_ACTIVATED",
    "expires_at": null,
    "message": "需要激活账号"
  }
}
```

**前端处理：**
- 检查 `is_activated === false`
- 显示激活提示，引导用户输入激活码
- 可以显示 `message` 字段的提示信息

#### 场景 2：账号已过期

**响应状态码：** `403`  
**响应体：**

```json
{
  "success": false,
  "error": "账号已过期，请联系管理员",
  "error_code": "EXPIRED_TOKEN",
  "expires_at": "2024-11-20T10:00:00+00:00"
}
```

**前端处理：**
- 检查 `error_code === "EXPIRED_TOKEN"`
- 显示过期提示，可以显示 `expires_at` 过期时间
- 提供"重新激活"或"联系管理员"的入口
- 清除本地 Token 和用户信息

#### 场景 3：登录成功

**响应状态码：** `200`  
**响应体：**

```json
{
  "success": true,
  "data": {
    "token": "jwt_token_here",
    "user": {
      "id": 123,
      "openid": "xxx",
      "nickname": "用户昵称",
      "avatar_url": "https://...",
      "is_activated": true,
      "expires_at": "2024-12-31T23:59:59+00:00"
    }
  }
}
```

**前端处理：**
- 保存 `token` 到本地存储
- 保存 `user` 信息到本地存储
- 记录 `expires_at` 用于过期提醒
- 跳转到主页面

### 2.4 前端代码示例

```javascript
async function login(code) {
  try {
    const response = await axios.post('/api/miniprogram/login', {
      code: code
    });
    
    const { success, data } = response.data;
    
    if (!success) {
      // 处理错误（如账号过期）
      const { error, error_code, expires_at } = response.data;
      
      if (error_code === 'EXPIRED_TOKEN') {
        // 账号过期
        showExpiredDialog(expires_at);
        return;
      }
      
      showError(error);
      return;
    }
    
    // 检查是否已激活
    if (!data.is_activated) {
      // 未激活，显示激活界面
      showActivateDialog();
      return;
    }
    
    // 登录成功
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data.user));
    
    // 保存过期时间，用于提前提醒
    if (data.user.expires_at) {
      localStorage.setItem('expires_at', data.user.expires_at);
      // 可以设置定时器，在过期前提醒用户
      scheduleExpiryReminder(data.user.expires_at);
    }
    
    // 跳转到主页
    router.push('/home');
    
  } catch (error) {
    if (error.response?.status === 403) {
      // 处理 403 错误（账号过期等）
      const { error_code, expires_at } = error.response.data;
      handleExpiredAccount(error_code, expires_at);
    } else {
      showError('登录失败，请稍后重试');
    }
  }
}
```

---

## 🔑 3. 激活接口变更

### 3.1 接口地址

```
POST /api/miniprogram/activate
```

### 3.2 请求格式

```json
{
  "code": "wx.login()获取的code",
  "invite_code": "INVITE123"
}
```

### 3.3 响应格式变更

#### 场景 1：激活成功

**响应状态码：** `200`  
**响应体：**

```json
{
  "success": true,
  "data": {
    "token": "jwt_token_here",
    "user": {
      "id": 123,
      "openid": "xxx",
      "nickname": "用户昵称",
      "avatar_url": "https://...",
      "is_activated": true,
      "expires_at": "2024-12-31T23:59:59+00:00"
    }
  }
}
```

#### 场景 2：账号已激活

**响应状态码：** `400`  
**响应体：**

```json
{
  "success": false,
  "error": "账号已激活，请直接登录",
  "error_code": "ALREADY_ACTIVATED",
  "expires_at": "2024-12-31T23:59:59+00:00"
}
```

**前端处理：**
- 检查 `error_code === "ALREADY_ACTIVATED"`
- 提示用户账号已激活，引导直接登录
- 可以显示 `expires_at` 信息

#### 场景 3：激活码无效

**响应状态码：** `400`  
**响应体：**

```json
{
  "success": false,
  "error": "激活码无效或已失效",
  "error_code": "INVALID_INVITE_CODE"
}
```

**前端处理：**
- 检查 `error_code === "INVALID_INVITE_CODE"`
- 显示错误提示
- 允许用户重新输入激活码

### 3.4 前端代码示例

```javascript
async function activate(code, inviteCode) {
  try {
    const response = await axios.post('/api/miniprogram/activate', {
      code: code,
      invite_code: inviteCode
    });
    
    const { success, data } = response.data;
    
    if (!success) {
      const { error, error_code, expires_at } = response.data;
      
      if (error_code === 'ALREADY_ACTIVATED') {
        // 账号已激活，引导登录
        showMessage('账号已激活，请直接登录');
        // 可以显示过期时间
        if (expires_at) {
          showMessage(`账号有效期至：${formatDate(expires_at)}`);
        }
        return;
      }
      
      if (error_code === 'INVALID_INVITE_CODE') {
        // 激活码无效
        showError('激活码无效或已失效，请检查后重试');
        return;
      }
      
      showError(error);
      return;
    }
    
    // 激活成功
    localStorage.setItem('token', data.token);
    localStorage.setItem('user', JSON.stringify(data.user));
    
    if (data.user.expires_at) {
      localStorage.setItem('expires_at', data.user.expires_at);
      scheduleExpiryReminder(data.user.expires_at);
    }
    
    showSuccess('激活成功！');
    router.push('/home');
    
  } catch (error) {
    if (error.response?.status === 400) {
      const { error_code } = error.response.data;
      handleActivateError(error_code);
    } else {
      showError('激活失败，请稍后重试');
    }
  }
}
```

---

## 🚫 4. API 错误处理规范

### 4.1 错误响应格式

所有错误响应统一格式：

```json
{
  "success": false,
  "error": "错误描述信息",
  "error_code": "ERROR_CODE"
}
```

### 4.2 标准错误码列表

| 错误码 | HTTP 状态码 | 说明 | 前端处理建议 |
|--------|------------|------|------------|
| `AUTH_REQUIRED` | 401 | 需要登录认证 | 清除 Token，跳转登录页 |
| `INVALID_TOKEN` | 401 | Token 无效或已过期 | 清除 Token，跳转登录页 |
| `NOT_ACTIVATED` | 200 | 账号未激活 | 显示激活界面 |
| `EXPIRED_TOKEN` | 401/403 | 账号已过期 | 显示过期提示，提供重新激活入口 |
| `USER_NOT_FOUND` | 401 | 用户不存在 | 清除 Token，跳转登录页 |
| `ALREADY_ACTIVATED` | 400 | 账号已激活 | 提示已激活，引导登录 |
| `INVALID_INVITE_CODE` | 400 | 激活码无效 | 显示错误，允许重试 |

### 4.3 前端错误处理工具函数

```javascript
// 错误处理工具函数
function handleApiError(error) {
  if (!error.response) {
    // 网络错误
    return {
      message: '网络错误，请检查网络连接',
      code: 'NETWORK_ERROR'
    };
  }
  
  const { status, data } = error.response;
  const { error: errorMessage, error_code } = data || {};
  
  // 401 错误统一处理
  if (status === 401) {
    // 清除认证信息
    clearAuth();
    // 跳转登录
    router.push('/login');
    
    return {
      message: errorMessage || '登录已过期，请重新登录',
      code: error_code || 'AUTH_REQUIRED',
      action: 'redirect_to_login'
    };
  }
  
  // 403 错误（账号过期等）
  if (status === 403) {
    if (error_code === 'EXPIRED_TOKEN') {
      return {
        message: errorMessage || '账号已过期',
        code: error_code,
        expires_at: data.expires_at,
        action: 'show_expired_dialog'
      };
    }
  }
  
  // 其他错误
  return {
    message: errorMessage || '操作失败，请稍后重试',
    code: error_code || 'UNKNOWN_ERROR'
  };
}

// 清除认证信息
function clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  localStorage.removeItem('expires_at');
}
```

---

## ⏰ 5. 账号过期处理

### 5.1 过期时间字段

所有用户信息响应都包含 `expires_at` 字段：

```json
{
  "expires_at": "2024-12-31T23:59:59+00:00"  // ISO 8601 格式，UTC 时间
}
```

### 5.2 前端过期检查

```javascript
// 检查账号是否过期
function checkAccountExpiry(expiresAt) {
  if (!expiresAt) {
    return { expired: false, message: '永久有效' };
  }
  
  const expiryDate = new Date(expiresAt);
  const now = new Date();
  
  if (expiryDate < now) {
    return {
      expired: true,
      message: '账号已过期',
      daysRemaining: 0
    };
  }
  
  const daysRemaining = Math.ceil((expiryDate - now) / (1000 * 60 * 60 * 24));
  
  return {
    expired: false,
    message: `账号有效期至 ${formatDate(expiresAt)}`,
    daysRemaining: daysRemaining
  };
}

// 定时检查过期
function scheduleExpiryReminder(expiresAt) {
  if (!expiresAt) return;
  
  const expiryDate = new Date(expiresAt);
  const now = new Date();
  const daysUntilExpiry = Math.ceil((expiryDate - now) / (1000 * 60 * 60 * 24));
  
  // 提前 7 天提醒
  if (daysUntilExpiry <= 7 && daysUntilExpiry > 0) {
    showWarning(`您的账号将在 ${daysUntilExpiry} 天后过期，请及时续费`);
  }
  
  // 已过期
  if (expiryDate < now) {
    showExpiredDialog(expiresAt);
  }
}
```

### 5.3 过期提示 UI

```javascript
// 显示过期对话框
function showExpiredDialog(expiresAt) {
  // 显示模态框
  Modal.confirm({
    title: '账号已过期',
    content: `您的账号已于 ${formatDate(expiresAt)} 过期，请联系管理员续费或使用新的激活码重新激活`,
    okText: '重新激活',
    cancelText: '联系管理员',
    onOk: () => {
      // 跳转到激活页面
      router.push('/activate');
    },
    onCancel: () => {
      // 显示联系方式
      showContactInfo();
    }
  });
}
```

---

## 🔄 6. 请求拦截器配置

### 6.1 Axios 拦截器完整示例

```javascript
import axios from 'axios';
import router from './router';

// 创建 axios 实例
const api = axios.create({
  baseURL: process.env.VUE_APP_API_BASE_URL || '',
  timeout: 10000
});

// 请求拦截器 - 添加 Token
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => {
    return Promise.reject(error);
  }
);

// 响应拦截器 - 统一错误处理
api.interceptors.response.use(
  response => {
    // 检查响应中的错误码
    const { success, error_code } = response.data;
    
    // 如果 success 为 false，但状态码是 200，也需要处理
    if (success === false) {
      if (error_code === 'EXPIRED_TOKEN') {
        handleExpiredToken(response.data);
        return Promise.reject(response.data);
      }
    }
    
    return response;
  },
  error => {
    const errorInfo = handleApiError(error);
    
    // 根据错误类型执行不同操作
    if (errorInfo.action === 'redirect_to_login') {
      // 已在 handleApiError 中处理
    } else if (errorInfo.action === 'show_expired_dialog') {
      showExpiredDialog(errorInfo.expires_at);
    } else {
      // 显示错误提示
      showError(errorInfo.message);
    }
    
    return Promise.reject(error);
  }
);

export default api;
```

---

## 📱 7. 小程序特定处理

### 7.1 微信登录流程

```javascript
// 小程序登录
async function wxLogin() {
  try {
    // 1. 获取微信 code
    const loginRes = await wx.login();
    const code = loginRes.code;
    
    // 2. 调用登录接口
    const response = await api.post('/api/miniprogram/login', { code });
    const { success, data } = response.data;
    
    if (!success) {
      // 处理错误
      const { error_code } = response.data;
      if (error_code === 'EXPIRED_TOKEN') {
        wx.showModal({
          title: '账号已过期',
          content: '您的账号已过期，请使用激活码重新激活',
          showCancel: true,
          confirmText: '去激活',
          success: (res) => {
            if (res.confirm) {
              wx.navigateTo({ url: '/pages/activate/activate' });
            }
          }
        });
      }
      return;
    }
    
    // 3. 检查激活状态
    if (!data.is_activated) {
      // 未激活，跳转到激活页面
      wx.navigateTo({ url: '/pages/activate/activate' });
      return;
    }
    
    // 4. 保存 Token 和用户信息
    wx.setStorageSync('token', data.token);
    wx.setStorageSync('user', data.user);
    
    if (data.user.expires_at) {
      wx.setStorageSync('expires_at', data.user.expires_at);
      checkExpiryReminder(data.user.expires_at);
    }
    
    // 5. 跳转到主页
    wx.switchTab({ url: '/pages/home/home' });
    
  } catch (error) {
    wx.showToast({
      title: '登录失败',
      icon: 'none'
    });
  }
}
```

### 7.2 激活流程

```javascript
// 小程序激活
async function activate(inviteCode) {
  try {
    // 1. 获取微信 code
    const loginRes = await wx.login();
    const code = loginRes.code;
    
    // 2. 调用激活接口
    const response = await api.post('/api/miniprogram/activate', {
      code: code,
      invite_code: inviteCode
    });
    
    const { success, data } = response.data;
    
    if (!success) {
      const { error_code } = response.data;
      
      if (error_code === 'ALREADY_ACTIVATED') {
        wx.showModal({
          title: '提示',
          content: '您的账号已激活，请直接登录',
          showCancel: false,
          success: () => {
            wx.navigateTo({ url: '/pages/login/login' });
          }
        });
        return;
      }
      
      if (error_code === 'INVALID_INVITE_CODE') {
        wx.showToast({
          title: '激活码无效或已失效',
          icon: 'none'
        });
        return;
      }
      
      wx.showToast({
        title: response.data.error || '激活失败',
        icon: 'none'
      });
      return;
    }
    
    // 3. 激活成功
    wx.setStorageSync('token', data.token);
    wx.setStorageSync('user', data.user);
    
    if (data.user.expires_at) {
      wx.setStorageSync('expires_at', data.user.expires_at);
    }
    
    wx.showToast({
      title: '激活成功',
      icon: 'success'
    });
    
    // 跳转到主页
    setTimeout(() => {
      wx.switchTab({ url: '/pages/home/home' });
    }, 1500);
    
  } catch (error) {
    wx.showToast({
      title: '激活失败，请稍后重试',
      icon: 'none'
    });
  }
}
```

---

## ✅ 8. 前端适配检查清单

### 8.1 必须完成的适配

- [ ] **所有 API 请求添加 Authorization 头**
  ```javascript
  headers: { 'Authorization': `Bearer ${token}` }
  ```

- [ ] **实现 401 错误统一处理**
  - 清除本地 Token
  - 跳转到登录页
  - 显示错误提示

- [ ] **适配登录接口响应格式**
  - 处理 `is_activated: false` 情况
  - 处理 `EXPIRED_TOKEN` 错误码
  - 保存 `expires_at` 字段

- [ ] **适配激活接口响应格式**
  - 处理 `ALREADY_ACTIVATED` 错误码
  - 处理 `INVALID_INVITE_CODE` 错误码
  - 保存激活后的用户信息

- [ ] **实现账号过期检查**
  - 解析 `expires_at` 字段
  - 实现过期提醒功能
  - 实现过期后的处理流程

### 8.2 建议完成的优化

- [ ] **错误码统一处理**
  - 创建错误码映射表
  - 实现统一的错误处理函数

- [ ] **Token 自动刷新机制**
  - 检测 Token 即将过期
  - 自动调用登录接口刷新

- [ ] **用户体验优化**
  - 过期前 7 天提醒
  - 过期后引导重新激活
  - 显示账号有效期信息

---

## 🔗 9. API 接口列表

### 9.1 需要认证的接口

以下接口现在**必须**提供有效的 Bearer Token：

- `GET /api/matches/today` - 获取今日比赛
- `GET /api/matches/:matchId` - 获取比赛详情
- `GET /api/matches/:matchId/all_analyses` - 获取比赛分析
- `GET /api/miniprogram/user` - 获取用户信息

**所有接口在缺少 Token 或 Token 无效时返回 401**

### 9.2 公共接口（无需认证）

- `GET /api/public/matches/today` - 公共今日比赛接口
- `GET /api/public/matches/:matchId` - 公共比赛详情接口
- `GET /health` - 健康检查接口

---

## 📞 10. 技术支持

如有问题，请联系后端开发团队。

**文档版本：** v1.0  
**更新日期：** 2025-11-20  
**适用版本：** 服务端安全修复版本

---

## 📝 附录：完整代码示例

### A. 完整的 API 工具类

```javascript
// api.js
import axios from 'axios';
import router from './router';

const api = axios.create({
  baseURL: process.env.VUE_APP_API_BASE_URL || '',
  timeout: 10000
});

// 请求拦截器
api.interceptors.request.use(
  config => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  error => Promise.reject(error)
);

// 响应拦截器
api.interceptors.response.use(
  response => {
    // 检查业务错误
    if (response.data.success === false) {
      const { error_code } = response.data;
      if (error_code === 'EXPIRED_TOKEN') {
        handleExpiredToken(response.data);
        return Promise.reject(response.data);
      }
    }
    return response;
  },
  error => {
    if (error.response?.status === 401) {
      clearAuth();
      router.push('/login');
      return Promise.reject({
        message: '登录已过期，请重新登录',
        code: 'AUTH_REQUIRED'
      });
    }
    return Promise.reject(error);
  }
);

function clearAuth() {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
  localStorage.removeItem('expires_at');
}

function handleExpiredToken(data) {
  clearAuth();
  // 显示过期对话框
  showExpiredDialog(data.expires_at);
}

export default api;
```

### B. 登录服务

```javascript
// authService.js
import api from './api';
import router from './router';

export const authService = {
  async login(code) {
    try {
      const response = await api.post('/api/miniprogram/login', { code });
      const { success, data } = response.data;
      
      if (!success) {
        throw new Error(data.error || '登录失败');
      }
      
      if (!data.is_activated) {
        return {
          needActivate: true,
          openid: data.openid
        };
      }
      
      // 保存认证信息
      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
      
      if (data.user.expires_at) {
        localStorage.setItem('expires_at', data.user.expires_at);
        this.scheduleExpiryReminder(data.user.expires_at);
      }
      
      return {
        success: true,
        user: data.user
      };
      
    } catch (error) {
      if (error.response?.data?.error_code === 'EXPIRED_TOKEN') {
        throw {
          code: 'EXPIRED_TOKEN',
          message: error.response.data.error,
          expires_at: error.response.data.expires_at
        };
      }
      throw error;
    }
  },
  
  async activate(code, inviteCode) {
    try {
      const response = await api.post('/api/miniprogram/activate', {
        code,
        invite_code: inviteCode
      });
      
      const { success, data } = response.data;
      
      if (!success) {
        const { error_code } = response.data;
        throw {
          code: error_code,
          message: response.data.error
        };
      }
      
      // 保存认证信息
      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
      
      if (data.user.expires_at) {
        localStorage.setItem('expires_at', data.user.expires_at);
        this.scheduleExpiryReminder(data.user.expires_at);
      }
      
      return {
        success: true,
        user: data.user
      };
      
    } catch (error) {
      throw error;
    }
  },
  
  scheduleExpiryReminder(expiresAt) {
    if (!expiresAt) return;
    
    const expiryDate = new Date(expiresAt);
    const now = new Date();
    const daysUntilExpiry = Math.ceil((expiryDate - now) / (1000 * 60 * 60 * 24));
    
    if (daysUntilExpiry <= 7 && daysUntilExpiry > 0) {
      // 提前 7 天提醒
      console.warn(`账号将在 ${daysUntilExpiry} 天后过期`);
      // 可以显示提示框
    }
  },
  
  checkExpiry() {
    const expiresAt = localStorage.getItem('expires_at');
    if (!expiresAt) return { expired: false };
    
    const expiryDate = new Date(expiresAt);
    const now = new Date();
    
    return {
      expired: expiryDate < now,
      daysRemaining: Math.ceil((expiryDate - now) / (1000 * 60 * 60 * 24))
    };
  }
};
```

---

**文档结束**


