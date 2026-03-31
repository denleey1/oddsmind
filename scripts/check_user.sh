#!/bin/bash
# 查看用户详细信息
# 使用方法: bash scripts/check_user.sh <用户ID或OpenID>

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

DB_USER="root"
DB_PASS="${DB_PASS:-${MYSQL_PASSWORD:-}}"
DB_NAME="oddsmind"

if [ -z "$1" ]; then
    echo -e "${RED}❌ 请提供用户ID或OpenID${NC}"
    echo "使用方法: bash scripts/check_user.sh <用户ID或OpenID>"
    exit 1
fi

IDENTIFIER=$1

echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        👤 用户详情查询                   ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# 判断是ID还是OpenID
if [[ "$IDENTIFIER" =~ ^[0-9]+$ ]]; then
    WHERE_CLAUSE="id = $IDENTIFIER"
    SEARCH_TYPE="用户ID"
else
    WHERE_CLAUSE="openid = '$IDENTIFIER'"
    SEARCH_TYPE="OpenID"
fi

# 检查用户是否存在
EXISTS=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
SELECT COUNT(*) FROM miniprogram_users WHERE $WHERE_CLAUSE;
" 2>/dev/null)

if [ "$EXISTS" == "0" ]; then
    echo -e "${RED}❌ 用户不存在！${NC}"
    exit 1
fi

# 显示用户基本信息
echo -e "${YELLOW}📋 基本信息${NC}"
echo ""
mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
SELECT 
    id as '用户ID',
    openid as 'OpenID',
    unionid as 'UnionID',
    nickname as '昵称',
    avatar_url as '头像URL',
    CASE 
        WHEN is_activated = 1 THEN '✓ 已激活'
        ELSE '✗ 未激活'
    END as '激活状态',
    invite_code_used as '使用的激活码',
    DATE_FORMAT(activated_at, '%Y-%m-%d %H:%i:%s') as '激活时间',
    CASE 
        WHEN expires_at IS NULL THEN '永不过期'
        ELSE DATE_FORMAT(expires_at, '%Y-%m-%d %H:%i:%s')
    END as '过期时间',
    CASE 
        WHEN expires_at IS NULL THEN '永不过期'
        WHEN expires_at > NOW() THEN CONCAT('有效(还剩', TIMESTAMPDIFF(DAY, NOW(), expires_at), '天)')
        ELSE '已过期'
    END as '账号状态',
    DATE_FORMAT(last_login_at, '%Y-%m-%d %H:%i:%s') as '最后登录',
    DATE_FORMAT(created_at, '%Y-%m-%d %H:%i:%s') as '注册时间',
    DATE_FORMAT(updated_at, '%Y-%m-%d %H:%i:%s') as '更新时间'
FROM miniprogram_users 
WHERE $WHERE_CLAUSE;
" 2>/dev/null

# 如果用户已激活，显示激活码使用记录
USER_ID=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
SELECT id FROM miniprogram_users WHERE $WHERE_CLAUSE;
" 2>/dev/null)

INVITE_CODE=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
SELECT invite_code_used FROM miniprogram_users WHERE id = $USER_ID;
" 2>/dev/null)

if [ ! -z "$INVITE_CODE" ] && [ "$INVITE_CODE" != "NULL" ]; then
    echo ""
    echo -e "${YELLOW}🎫 激活码信息${NC}"
    echo ""
    mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
    SELECT 
        code as '激活码',
        max_uses as '最大次数',
        used_count as '已使用',
        CONCAT(account_expires_days, '天') as '账号有效期',
        CASE 
            WHEN is_active = 1 THEN '✓ 启用'
            ELSE '✗ 禁用'
        END as '状态',
        notes as '备注'
    FROM invite_codes 
    WHERE code = '$INVITE_CODE';
    " 2>/dev/null
fi

echo ""
echo -e "${YELLOW}💡 可用操作：${NC}"
echo ""
echo "  • 查看所有激活用户: bash scripts/list_activated_users.sh"
echo "  • 清理用户: bash scripts/cleanup_expired_users.sh"
echo ""
