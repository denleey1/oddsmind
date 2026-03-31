-- 支付订单表
-- 创建时间: 2026-03-18
-- 用途: 存储微信支付订单，支付成功后自动生成邀请码

USE oddsmind;

CREATE TABLE IF NOT EXISTS payment_orders (
    id INT AUTO_INCREMENT PRIMARY KEY,
    order_no VARCHAR(64) NOT NULL UNIQUE COMMENT '内部订单号',
    transaction_id VARCHAR(64) NULL COMMENT '微信支付交易号',
    openid VARCHAR(128) NULL COMMENT '付款人openid（公众号或小程序）',
    plan_type ENUM('day','week','month','year') NOT NULL COMMENT '套餐类型: day=日卡, week=周卡, month=月卡, year=年卡',
    amount_cents INT NOT NULL COMMENT '金额（单位：分）',
    status ENUM('pending','paid','failed','refunded') DEFAULT 'pending' COMMENT '订单状态',
    invite_code VARCHAR(20) NULL COMMENT '支付成功后生成的邀请码',
    notify_data TEXT NULL COMMENT '微信回调原始数据（JSON）',
    paid_at DATETIME NULL COMMENT '支付完成时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '订单创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    INDEX idx_order_no (order_no),
    INDEX idx_openid (openid),
    INDEX idx_status (status),
    INDEX idx_invite_code (invite_code),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='微信支付订单表';

-- 验证表创建
SELECT 'payment_orders 表创建完成' AS status;
DESCRIBE payment_orders;
