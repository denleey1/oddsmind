-- 小程序登录激活安全约束补丁
-- 创建时间: 2025-11-16
-- 用途: 添加数据完整性约束，防止数据异常

USE oddsmind;

-- 1. invite_codes 表约束
ALTER TABLE invite_codes
  ADD CONSTRAINT chk_max_uses CHECK (max_uses > 0),
  ADD CONSTRAINT chk_used_count CHECK (used_count >= 0 AND used_count <= max_uses),
  ADD CONSTRAINT chk_account_expires_days CHECK (account_expires_days > 0 AND account_expires_days <= 3650);

-- 2. invite_code_usage 表唯一约束
-- 防止同一个用户多次被记录使用同一个激活码
ALTER TABLE invite_code_usage
  ADD UNIQUE KEY unique_user_code (user_id, invite_code);

-- 3. 添加索引优化性能
ALTER TABLE invite_code_usage
  ADD INDEX idx_invite_code_user (invite_code, user_id);

-- 显示约束添加结果
SELECT 
    'invite_codes约束添加完成' as status,
    COUNT(*) as record_count
FROM invite_codes;

SELECT 
    'invite_code_usage约束添加完成' as status,
    COUNT(*) as record_count
FROM invite_code_usage;

