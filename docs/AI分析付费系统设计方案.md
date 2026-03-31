# AI分析付费系统设计方案（已废弃 - 改用简化版）

> ⚠️ **注意**：此方案过于复杂，需要支付系统支持。已改用**简化版方案**（基于激活码权限控制）。
> 
> 请查看：`AI分析付费系统设计方案-简化版.md`

## 一、方案概述（已废弃）

采用**积分/余额系统**，用户通过充值获得积分，每次AI分析消耗一定积分。

### 优势
- ✅ 灵活：支持多种充值方式（微信支付、支付宝、手动充值等）
- ✅ 可扩展：未来可以支持其他付费功能
- ✅ 用户友好：余额清晰可见，使用方便
- ✅ 成本可控：按次计费，成本透明

## 二、数据库设计

### 1. 扩展用户表（miniprogram_users）

添加余额字段：
```sql
ALTER TABLE miniprogram_users 
ADD COLUMN ai_balance DECIMAL(10, 2) DEFAULT 0.00 COMMENT 'AI分析余额（积分）' AFTER expires_at,
ADD COLUMN total_recharged DECIMAL(10, 2) DEFAULT 0.00 COMMENT '累计充值金额' AFTER ai_balance;
```

### 2. 创建充值记录表（ai_recharge_records）

```sql
CREATE TABLE IF NOT EXISTS ai_recharge_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    amount DECIMAL(10, 2) NOT NULL COMMENT '充值金额（元）',
    credits DECIMAL(10, 2) NOT NULL COMMENT '获得的积分',
    payment_method VARCHAR(50) DEFAULT 'manual' COMMENT '支付方式：wechat/alipay/manual',
    payment_order_id VARCHAR(100) NULL COMMENT '支付订单号',
    status ENUM('pending', 'completed', 'failed', 'refunded') DEFAULT 'pending' COMMENT '状态',
    remark TEXT NULL COMMENT '备注',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME NULL,
    
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES miniprogram_users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

### 3. 创建消费记录表（ai_consumption_records）

```sql
CREATE TABLE IF NOT EXISTS ai_consumption_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL COMMENT '用户ID',
    match_id VARCHAR(50) NOT NULL COMMENT '比赛ID',
    credits_used DECIMAL(10, 2) NOT NULL COMMENT '消耗的积分',
    analysis_id INT NULL COMMENT '关联的AI分析ID（match_ai_analysis.id）',
    status ENUM('success', 'failed', 'refunded') DEFAULT 'success' COMMENT '状态',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    INDEX idx_user_id (user_id),
    INDEX idx_match_id (match_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (user_id) REFERENCES miniprogram_users(id) ON DELETE CASCADE,
    FOREIGN KEY (analysis_id) REFERENCES match_ai_analysis(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
```

## 三、计费规则

### 默认计费标准
- **每次AI分析消耗：10积分**
- **充值比例：1元 = 10积分**（可配置）

### 可配置项（存储在system_config表）
- `ai_analysis_cost`: AI分析单次成本（积分）
- `recharge_rate`: 充值比例（1元=多少积分）
- `ai_analysis_enabled`: 是否启用AI分析付费

## 四、API接口设计

### 1. 获取用户余额
```
GET /api/miniprogram/ai-balance
```
返回：
```json
{
    "success": true,
    "data": {
        "balance": 50.00,
        "totalRecharged": 100.00,
        "costPerAnalysis": 10.00
    }
}
```

### 2. 充值接口（手动充值，管理员使用）
```
POST /api/miniprogram/ai-recharge
Body: {
    "amount": 50.00,  // 充值金额（元）
    "credits": 500.00,  // 获得的积分
    "remark": "手动充值"
}
```

### 3. 充值记录查询
```
GET /api/miniprogram/ai-recharge-records?page=1&limit=20
```

### 4. 消费记录查询
```
GET /api/miniprogram/ai-consumption-records?page=1&limit=20
```

### 5. 修改AI分析接口（添加余额检查）

在 `POST /api/matches/<match_id>/ai-analysis` 中：
1. 检查用户余额是否足够
2. 如果不足，返回错误提示
3. 如果足够，先扣除余额（预扣）
4. 调用AI分析
5. 如果成功，记录消费；如果失败，退还余额

## 五、前端展示

### 1. 余额显示
- 在用户信息页面显示余额
- 在AI分析按钮旁显示余额和单次成本

### 2. 充值入口
- 提供充值按钮
- 显示充值套餐（如：10元=100积分，50元=550积分等）

### 3. 余额不足提示
- 当余额不足时，提示用户充值
- 显示需要充值的金额

## 六、实施步骤

### 阶段一：数据库和基础功能
1. ✅ 创建数据库表
2. ✅ 扩展用户表字段
3. ✅ 创建数据库操作函数

### 阶段二：API接口
1. ✅ 余额查询接口
2. ✅ 充值接口（手动）
3. ✅ 消费记录接口
4. ✅ 修改AI分析接口（添加余额检查）

### 阶段三：前端集成
1. ✅ 余额显示
2. ✅ 充值入口
3. ✅ 余额不足提示

### 阶段四：支付集成（可选）
1. 微信支付集成
2. 支付宝支付集成

## 七、安全考虑

1. **余额检查**：使用数据库事务确保余额扣除的原子性
2. **防重复消费**：每次分析前检查是否已有分析结果
3. **退款机制**：如果AI分析失败，自动退还积分
4. **记录审计**：所有充值和消费都有完整记录

## 八、成本控制

### 管理员功能
1. **查看成本统计**：每日/每月AI分析成本
2. **调整计费标准**：根据实际成本调整积分价格
3. **用户充值管理**：手动为用户充值

## 九、未来扩展

1. **套餐优惠**：充值越多，赠送越多
2. **会员特权**：VIP用户享受折扣
3. **免费额度**：新用户赠送免费分析次数
4. **邀请奖励**：邀请好友获得积分

