#!/bin/bash
# 查看已激活用户列表
# 使用方法: bash scripts/list_activated_users.sh

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

DB_USER="root"
DB_PASS="${DB_PASS:-${MYSQL_PASSWORD:-}}"
DB_NAME="oddsmind"

echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        👥 已激活用户列表                  ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# 选择查看方式
echo -e "${GREEN}请选择查看方式：${NC}"
echo "  1) 所有已激活用户"
echo "  2) 未过期的用户"
echo "  3) 已过期的用户"
echo "  4) 即将过期的用户（7天内）"
echo "  5) 按激活时间排序"
echo ""
read -p "请输入选项 [1-5]: " view_choice

case $view_choice in
    1)
        CONDITION="WHERE is_activated = 1"
        TITLE="所有已激活用户"
        ;;
    2)
        CONDITION="WHERE is_activated = 1 AND (expires_at IS NULL OR expires_at > NOW())"
        TITLE="未过期的用户"
        ;;
    3)
        CONDITION="WHERE is_activated = 1 AND expires_at IS NOT NULL AND expires_at < NOW()"
        TITLE="已过期的用户"
        ;;
    4)
        CONDITION="WHERE is_activated = 1 AND expires_at IS NOT NULL AND expires_at > NOW() AND expires_at < DATE_ADD(NOW(), INTERVAL 7 DAY)"
        TITLE="即将过期的用户（7天内）"
        ;;
    5)
        CONDITION="WHERE is_activated = 1 ORDER BY activated_at DESC"
        TITLE="已激活用户（按激活时间排序）"
        ;;
    *)
        CONDITION="WHERE is_activated = 1"
        TITLE="所有已激活用户"
        ;;
esac

echo ""
echo -e "${YELLOW}📊 ${TITLE}${NC}"
echo ""

# 查询用户
mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
SELECT 
    id as 'ID',
    SUBSTRING(openid, 1, 20) as 'OpenID',
    nickname as '昵称',
    invite_code_used as '激活码',
    DATE_FORMAT(activated_at, '%Y-%m-%d %H:%i') as '激活时间',
    CASE 
        WHEN expires_at IS NULL THEN '永不过期'
        WHEN expires_at > NOW() THEN CONCAT('有效(还剩', TIMESTAMPDIFF(DAY, NOW(), expires_at), '天)')
        ELSE '已过期'
    END as '状态',
    DATE_FORMAT(expires_at, '%Y-%m-%d') as '过期日期',
    DATE_FORMAT(last_login_at, '%Y-%m-%d %H:%i') as '最后登录'
FROM miniprogram_users 
$CONDITION
ORDER BY activated_at DESC
LIMIT 50;
" 2>/dev/null

# 统计信息
echo ""
echo -e "${YELLOW}📈 统计信息${NC}"
echo ""

STATS=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
SELECT 
    COUNT(*) as total,
    SUM(CASE WHEN expires_at IS NULL OR expires_at > NOW() THEN 1 ELSE 0 END) as active,
    SUM(CASE WHEN expires_at IS NOT NULL AND expires_at < NOW() THEN 1 ELSE 0 END) as expired,
    SUM(CASE WHEN expires_at IS NOT NULL AND expires_at > NOW() AND expires_at < DATE_ADD(NOW(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) as expiring_soon
FROM miniprogram_users 
WHERE is_activated = 1;
" 2>/dev/null)

TOTAL=$(echo "$STATS" | cut -f1)
ACTIVE=$(echo "$STATS" | cut -f2)
EXPIRED=$(echo "$STATS" | cut -f3)
EXPIRING_SOON=$(echo "$STATS" | cut -f4)

echo -e "  总激活用户:  ${GREEN}${TOTAL}${NC}"
echo -e "  有效用户:    ${GREEN}${ACTIVE}${NC}"
echo -e "  已过期:      ${RED}${EXPIRED}${NC}"
echo -e "  即将过期:    ${YELLOW}${EXPIRING_SOON}${NC} (7天内)"
echo ""

echo -e "${YELLOW}💡 提示：${NC}"
echo "  • 查看用户详情: bash scripts/check_user.sh <用户ID>"
echo "  • 清理过期用户: bash scripts/cleanup_expired_users.sh"
echo ""
