#!/bin/bash
# 查看激活码详细信息和使用记录
# 使用方法: bash scripts/check_invite_code.sh <激活码>

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

DB_USER="root"
DB_PASS="${DB_PASS:-${MYSQL_PASSWORD:-}}"
DB_NAME="oddsmind"

if [ -z "$1" ]; then
    echo -e "${RED}❌ 请提供激活码${NC}"
    echo "使用方法: bash scripts/check_invite_code.sh <激活码>"
    exit 1
fi

CODE=$1

echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║      🔍 激活码详情: ${CODE}          ${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# 1. 检查激活码是否存在
EXISTS=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
SELECT COUNT(*) FROM invite_codes WHERE code = '$CODE';
" 2>/dev/null)

if [ "$EXISTS" == "0" ]; then
    echo -e "${RED}❌ 激活码不存在！${NC}"
    exit 1
fi

# 2. 显示激活码基本信息
echo -e "${YELLOW}📋 基本信息${NC}"
echo ""
mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
SELECT 
    code as '激活码',
    max_uses as '最大使用次数',
    used_count as '已使用次数',
    CONCAT(max_uses - used_count, ' 次') as '剩余次数',
    CONCAT(account_expires_days, '天') as '账号有效期',
    CASE 
        WHEN is_active = 1 THEN '✓ 启用'
        ELSE '✗ 禁用'
    END as '状态',
    notes as '备注',
    created_by as '创建者',
    DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as '创建时间'
FROM invite_codes 
WHERE code = '$CODE';
" 2>/dev/null

echo ""

# 3. 显示使用记录
echo -e "${YELLOW}📊 使用记录${NC}"
echo ""

USAGE_COUNT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
SELECT COUNT(*) FROM invite_code_usage WHERE invite_code = '$CODE';
" 2>/dev/null)

if [ "$USAGE_COUNT" == "0" ]; then
    echo -e "${BLUE}  暂无使用记录${NC}"
else
    mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
    SELECT 
        u.user_id as '用户ID',
        SUBSTRING(u.openid, 1, 15) as 'OpenID',
        mu.nickname as '昵称',
        CASE 
            WHEN mu.is_activated = 1 THEN '✓ 已激活'
            ELSE '✗ 未激活'
        END as '状态',
        DATE_FORMAT(u.account_expires_at, '%Y-%m-%d') as '账号过期日',
        DATE_FORMAT(u.used_at, '%Y-%m-%d %H:%i') as '使用时间'
    FROM invite_code_usage u
    LEFT JOIN miniprogram_users mu ON u.user_id = mu.id
    WHERE u.invite_code = '$CODE'
    ORDER BY u.used_at DESC;
    " 2>/dev/null
fi

echo ""

# 4. 统计信息
echo -e "${YELLOW}📈 统计信息${NC}"
echo ""

STATS=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
SELECT 
    ic.used_count,
    ic.max_uses,
    ic.account_expires_days,
    COUNT(u.id) as actual_usage,
    SUM(CASE WHEN mu.is_activated = 1 THEN 1 ELSE 0 END) as active_users
FROM invite_codes ic
LEFT JOIN invite_code_usage u ON ic.code = u.invite_code
LEFT JOIN miniprogram_users mu ON u.user_id = mu.id
WHERE ic.code = '$CODE'
GROUP BY ic.code;
" 2>/dev/null)

USED_COUNT=$(echo "$STATS" | cut -f1)
MAX_USES=$(echo "$STATS" | cut -f2)
EXPIRES_DAYS=$(echo "$STATS" | cut -f3)
ACTUAL_USAGE=$(echo "$STATS" | cut -f4)
ACTIVE_USERS=$(echo "$STATS" | cut -f5)

REMAINING=$((MAX_USES - USED_COUNT))
USAGE_PERCENT=$(awk "BEGIN {printf \"%.1f\", ($USED_COUNT/$MAX_USES)*100}")

echo -e "  使用率:      ${GREEN}${USAGE_PERCENT}%${NC} (${USED_COUNT}/${MAX_USES})"
echo -e "  剩余次数:    ${YELLOW}${REMAINING}次${NC}"
echo -e "  实际激活:    ${GREEN}${ACTIVE_USERS}人${NC}"
echo -e "  账号有效期:  ${BLUE}${EXPIRES_DAYS}天${NC}"

if [ "$REMAINING" == "0" ]; then
    echo -e "  状态:        ${RED}已用完${NC}"
else
    echo -e "  状态:        ${GREEN}可用${NC}"
fi

echo ""

# 5. 操作建议
echo -e "${YELLOW}💡 可用操作：${NC}"
echo ""
if [ "$REMAINING" -gt "0" ]; then
    echo "  • 复制激活码发送给用户: ${GREEN}${CODE}${NC}"
else
    echo "  • 激活码已用完，生成新的: ${BLUE}bash scripts/create_invite_code.sh${NC}"
fi
echo "  • 查看所有激活码: ${BLUE}bash scripts/list_invite_codes.sh${NC}"
echo ""
