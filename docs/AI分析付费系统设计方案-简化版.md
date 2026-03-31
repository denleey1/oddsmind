# AI分析付费系统设计方案（简化版）

## 一、方案概述

**基于激活码的权限控制**：激活码可以包含AI分析权限，用户激活时自动获得相应权限。

### 优势
- ✅ **极简**：无需充值系统，无需支付集成
- ✅ **灵活**：激活码可以设置不同的AI分析权限
- ✅ **易管理**：通过激活码统一管理
- ✅ **零成本**：不需要开发支付系统

## 二、数据库设计

### 1. 扩展激活码表（invite_codes）

添加AI分析权限字段：
```sql
ALTER TABLE invite_codes 
ADD COLUMN ai_analysis_enabled BOOLEAN DEFAULT FALSE COMMENT '是否允许AI分析',
ADD COLUMN ai_analysis_count INT DEFAULT 0 COMMENT 'AI分析次数（0=无限制，>0=限制次数）' AFTER ai_analysis_enabled;
```

### 2. 扩展用户表（miniprogram_users）

添加AI分析权限和次数：
```sql
ALTER TABLE miniprogram_users 
ADD COLUMN ai_analysis_enabled BOOLEAN DEFAULT FALSE COMMENT '是否允许AI分析',
ADD COLUMN ai_analysis_count INT DEFAULT 0 COMMENT '剩余AI分析次数（0=无限制，>0=剩余次数）' AFTER ai_analysis_enabled,
ADD COLUMN ai_analysis_used_count INT DEFAULT 0 COMMENT '已使用AI分析次数' AFTER ai_analysis_count;
```

### 3. 创建AI分析使用记录表（可选，用于统计）

```sql
CREATE TABLE IF NOT EXISTS ai_analysis_usage (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    match_id VARCHAR(50) NOT NULL COMMENT '比赛ID',
    analysis_id INT NULL COMMENT '关联的AI分析ID（match_ai_analysis.id）',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_match_id (match_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES miniprogram_users(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES match_ai_analysis(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## 三、权限模式

### 模式1：无限制（推荐）
- `ai_analysis_enabled = TRUE`
- `ai_analysis_count = 0`（0表示无限制）
- 用户可以在账号有效期内无限次使用AI分析

### 模式2：限制次数
- `ai_analysis_enabled = TRUE`
- `ai_analysis_count = 10`（例如10次）
- 用户可以使用10次AI分析，用完即止

### 模式3：不允许
- `ai_analysis_enabled = FALSE`
- `ai_analysis_count = 0`
- 用户无法使用AI分析功能

## 四、激活流程

当用户使用激活码激活账号时：

1. 读取激活码的AI分析权限设置
2. 将权限复制到用户账号：
   ```sql
   UPDATE miniprogram_users 
   SET ai_analysis_enabled = %s,
       ai_analysis_count = %s
   WHERE openid = %s
   ```

## 五、AI分析接口修改

在 `POST /api/matches/<match_id>/ai-analysis` 中：

### 1. 检查权限
```python
# 检查用户是否允许AI分析
if not user.get('ai_analysis_enabled'):
    return jsonify({
        'success': False,
        'error': '您的账号未开通AI分析功能，请联系管理员'
    }), 403

# 检查剩余次数（如果有限制）
if user.get('ai_analysis_count', 0) > 0:
    remaining = user.get('ai_analysis_count', 0)
    if remaining <= 0:
        return jsonify({
            'success': False,
            'error': f'您的AI分析次数已用完（剩余：{remaining}次），请联系管理员'
        }), 403
```

### 2. 扣除次数（如果有限制）
```python
# 如果有限制次数，先扣除
if user.get('ai_analysis_count', 0) > 0:
    new_count = user.get('ai_analysis_count', 0) - 1
    execute_update(
        "UPDATE miniprogram_users SET ai_analysis_count = %s, ai_analysis_used_count = ai_analysis_used_count + 1 WHERE openid = %s",
        (new_count, openid)
    )
```

### 3. 记录使用（可选）
```python
# 记录使用记录
execute_update(
    "INSERT INTO ai_analysis_usage (user_id, match_id) VALUES (%s, %s)",
    (user_id, match_id)
)
```

## 六、激活码管理

### 创建带AI分析权限的激活码

```bash
# 创建无限制AI分析的激活码
python tools/manage_invite_codes.py create \
    --code VIP365 \
    --account-expires-days 365 \
    --ai-analysis-enabled \
    --ai-analysis-count 0

# 创建限制10次AI分析的激活码
python tools/manage_invite_codes.py create \
    --code TRIAL10 \
    --account-expires-days 7 \
    --ai-analysis-enabled \
    --ai-analysis-count 10

# 创建不允许AI分析的激活码（默认）
python tools/manage_invite_codes.py create \
    --code BASIC \
    --account-expires-days 30
```

## 七、前端展示

### 1. 用户信息显示
- 显示AI分析权限状态
- 如果有限制次数，显示剩余次数
- 如果无限制，显示"无限制"

### 2. AI分析按钮
- 如果无权限，按钮禁用并提示
- 如果次数用完，按钮禁用并提示
- 如果正常，显示剩余次数（如果有）

## 八、API接口

### 1. 获取用户AI分析权限
```
GET /api/miniprogram/user
```
返回中增加：
```json
{
    "aiAnalysis": {
        "enabled": true,
        "remainingCount": 10,  // 0表示无限制
        "usedCount": 5
    }
}
```

## 九、实施步骤

### 阶段一：数据库扩展
1. ✅ 扩展 `invite_codes` 表
2. ✅ 扩展 `miniprogram_users` 表
3. ✅ 创建 `ai_analysis_usage` 表（可选）

### 阶段二：激活流程修改
1. ✅ 修改激活逻辑，复制AI分析权限到用户
2. ✅ 更新激活码管理工具

### 阶段三：AI分析接口修改
1. ✅ 添加权限检查
2. ✅ 添加次数扣除逻辑
3. ✅ 添加使用记录（可选）

### 阶段四：前端集成
1. ✅ 显示权限状态
2. ✅ 显示剩余次数
3. ✅ 按钮状态控制

## 十、使用场景示例

### 场景1：VIP用户（无限制）
```sql
-- 创建VIP激活码
INSERT INTO invite_codes (code, account_expires_days, ai_analysis_enabled, ai_analysis_count)
VALUES ('VIP365', 365, TRUE, 0);
```
用户激活后：365天有效期 + 无限制AI分析

### 场景2：试用用户（限制10次）
```sql
-- 创建试用激活码
INSERT INTO invite_codes (code, account_expires_days, ai_analysis_enabled, ai_analysis_count)
VALUES ('TRIAL10', 7, TRUE, 10);
```
用户激活后：7天有效期 + 10次AI分析

### 场景3：基础用户（不允许AI分析）
```sql
-- 创建基础激活码
INSERT INTO invite_codes (code, account_expires_days, ai_analysis_enabled)
VALUES ('BASIC', 30, FALSE);
```
用户激活后：30天有效期 + 不允许AI分析

## 十一、优势总结

1. **零开发成本**：不需要支付系统
2. **灵活定价**：通过激活码设置不同权限
3. **易于管理**：统一通过激活码管理
4. **简单清晰**：用户权限一目了然


