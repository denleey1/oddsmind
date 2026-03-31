# Keycloak 用户授权配置指南

## 概述

本系统通过 Keycloak 实现用户认证，并支持**自动化创建带有效期的用户**。

用户购买授权后，只需执行一条命令，即可自动创建30天有效期的账号。

---

## 一、一次性配置（首次使用需完成）

### 1.1 配置管理员密码

编辑 `oddsmind.env` 文件，填写 Keycloak 管理员密码：

```bash
# 找到这两行，填写你的 Keycloak admin 账号密码
KEYCLOAK_ADMIN_USERNAME="admin"
KEYCLOAK_ADMIN_PASSWORD="你的admin密码"  # 【必填】
```

### 1.2 配置 Keycloak 用户属性映射

**目的**：让应用能够读取用户的过期时间

**操作步骤**：

1. **登录 Keycloak 管理控制台**
   ```
   地址：https://119.29.112.18/auth/admin
   账号：admin
   密码：你的密码
   ```

2. **选择 Realm**
   - 左上角切换到 `oddsmind` Realm

3. **配置 Client Scopes**
   - 左侧菜单：`Client Scopes`
   - 点击 `profile`
   - 点击 `Mappers` 标签页
   - 点击 `Add mapper` → `By configuration` → 选择 `User Attribute`

4. **添加映射器配置**
   ```
   Name:                account_expiry_date
   User Attribute:      account_expiry_date
   Token Claim Name:    account_expiry_date
   Claim JSON Type:     String
   Add to ID token:     ON  ✅
   Add to access token: ON  ✅
   Add to userinfo:     ON  ✅
   Multivalued:         OFF
   ```

5. **点击 Save 保存**

**✅ 完成！** 这个配置只需要做一次，以后就不用管了。

---

## 二、日常使用：创建用户

### 2.1 基本用法（推荐：自动生成）

当有客户购买授权时，执行以下命令：

```bash
python create_user.py --auto
```

**自动生成特点**：
- ✅ 用户名：`user` + 8位随机数字（如 `user12345678`）
- ✅ 密码：12位高强度随机密码（含大小写字母、数字、特殊字符）
- ✅ 安全性高，避免弱密码

**示例**：
```bash
python create_user.py --auto
```

**输出**：
```
🎲 自动生成模式
   用户名前缀：user
   密码强度：  高强度12位（含大小写字母、数字、特殊字符）

🔄 正在创建用户 user87654321...

============================================================
✅ 用户创建成功！
------------------------------------------------------------
用户名：    user87654321
密码：      Xk9@mP2nQ5w!

⚠️  重要提示：
   - 请立即复制保存上述账号信息！
   - 密码为随机生成，丢失后需要重置！

邮箱：      user87654321@oddsmind.local
有效期至：  2025-11-14
登录地址：  http://119.29.112.18/login
============================================================

💡 提示：请将上述信息发送给用户
💡 用户账号将在 2025-11-14 后自动过期
```

### 2.2 高级用法

**自定义有效期**（如60天）：
```bash
python create_user.py --auto --days 60
```

**自定义用户名前缀**：
```bash
python create_user.py --auto --prefix vip
# 生成类似：vip12345678
```

**手动指定用户名和密码**（不推荐）：
```bash
python create_user.py --username zhangsan --password abc123456
```

### 2.3 参数说明

| 参数 | 简写 | 说明 | 必填 | 默认值 |
|------|------|------|------|--------|
| `--auto` | `-a` | 自动生成用户名和密码 | 🟢 推荐 | - |
| `--username` | `-u` | 手动指定用户名 | ❌ | - |
| `--password` | `-p` | 手动指定密码（需与--username配合） | ❌ | - |
| `--email` | `-e` | 邮箱 | ❌ | `username@oddsmind.local` |
| `--days` | `-d` | 有效期天数 | ❌ | 30 |
| `--prefix` | | 自动生成用户名的前缀 | ❌ | `user` |

---

## 三、工作原理

### 3.1 创建流程

```
执行脚本
   ↓
连接 Keycloak Admin API
   ↓
创建用户（自动设置过期时间属性）
   ↓
设置密码
   ↓
返回账号信息
```

### 3.2 过期检查

```
用户登录
   ↓
Keycloak 验证账号密码
   ↓
应用获取用户信息（包含过期时间）
   ↓
检查是否过期
   ↓
   ├─ 未过期 → 正常登录
   └─ 已过期 → 拒绝登录，显示过期提示页面
```

---

## 四、常见问题

### Q1: 提示 "未配置 KEYCLOAK_ADMIN_PASSWORD"

**解决**：编辑 `oddsmind.env`，填写管理员密码：
```bash
KEYCLOAK_ADMIN_PASSWORD="你的admin密码"
```

### Q2: 提示 "用户已存在"

**原因**：该用户名已经被创建过

**解决**：
- 换一个用户名
- 或在 Keycloak 中删除旧用户后重新创建

### Q3: 提示 "获取管理员令牌失败"

**原因**：管理员账号或密码错误

**解决**：
1. 检查 `KEYCLOAK_ADMIN_USERNAME` 是否正确（默认是 admin）
2. 检查 `KEYCLOAK_ADMIN_PASSWORD` 是否正确
3. 尝试手动登录 Keycloak 管理控制台验证密码

### Q4: 用户过期后如何续期？

**方法1**：在 Keycloak 管理控制台手动修改
- `Users` → 找到用户 → `Attributes` 标签页
- 修改 `account_expiry_date` 的值（如改为 `2025-12-14`）

**方法2**：等待后续的延期脚本（即将开发）

### Q5: 如何查看所有用户？

**方法1**：Keycloak 管理控制台
- `Users` → `View all users`

**方法2**：等待后续的查询脚本（即将开发）

---

## 五、安全建议

1. **妥善保管管理员密码**
   - 不要将 `oddsmind.env` 文件上传到公开仓库
   - 建议定期更换管理员密码

2. **密码强度要求**
   - 脚本要求密码至少6位
   - 建议使用字母+数字组合
   - 示例：`user2024abc`

3. **备份用户数据**
   - Keycloak 用户数据存储在数据库中
   - 建议定期备份 Keycloak 数据库

---

## 六、技术细节

### 6.1 用户属性

系统使用 Keycloak 的 `User Attributes` 功能存储过期时间：

```
属性名：account_expiry_date
格式：  YYYY-MM-DD (如 2025-11-14)
```

### 6.2 过期检查逻辑

在 `auth.py` 的 `callback()` 函数中：

```python
# 获取用户信息中的过期时间
expiry_date_str = user_info.get('account_expiry_date')

# 如果过期时间存在
if expiry_date_str:
    expiry_date = datetime.strptime(expiry_date_str, '%Y-%m-%d')
    
    # 检查是否过期
    if datetime.now() > expiry_date:
        # 拒绝登录，显示过期页面
        return "账号已过期", 403
```

### 6.3 依赖库

脚本使用的 Python 库：
- `requests` - HTTP 请求
- `python-dotenv` - 读取环境变量

确保已安装：
```bash
pip install requests python-dotenv
```

---

## 七、快速开始

### 第一次使用

```bash
# 1. 配置管理员密码
vim oddsmind.env
# 填写 KEYCLOAK_ADMIN_PASSWORD

# 2. 在 Keycloak 中配置用户属性映射（见 1.2 节）

# 3. 创建第一个测试用户
python create_user.py --username testuser --password test123456

# 4. 测试登录
# 访问 http://119.29.112.18/login
# 使用 testuser / test123456 登录
```

---

## 八、后续功能规划

- [ ] 查询用户列表脚本
- [ ] 用户延期脚本
- [ ] 删除用户脚本
- [ ] 批量创建用户
- [ ] 自动发送账号信息邮件

---

**如有问题，请联系技术支持。**

