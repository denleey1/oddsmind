#!/bin/bash
# 查看所有激活码
# 使用方法: bash scripts/list_invite_codes.sh

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

DB_USER="root"
DB_PASS="${DB_PASS:-${MYSQL_PASSWORD:-}}"
DB_NAME="oddsmind"

echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║        📋 激活码列表                      ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# 选择查看方式
echo -e "${GREEN}请选择查看方式：${NC}"
echo "  1) 查看所有激活码"
echo "  2) 只看可用的激活码"
echo "  3) 只看已用完的激活码"
echo "  4) 按有效期排序"
echo ""
read -p "请输入选项 [1-4]: " view_choice

case $view_choice in
    1)
        CONDITION=""
        TITLE="所有激活码"
        ;;
    2)
        CONDITION="WHERE used_count < max_uses AND is_active = 1"
        TITLE="可用激活码"
        ;;
    3)
        CONDITION="WHERE used_count >= max_uses OR is_active = 0"
        TITLE="已用完/已禁用激活码"
        ;;
    4)
        CONDITION="ORDER BY account_expires_days DESC"
        TITLE="激活码（按有效期排序）"
        ;;
    *)
        CONDITION=""
        TITLE="所有激活码"
        ;;
esac

echo ""
echo -e "${YELLOW}📊 ${TITLE}${NC}"
echo ""

mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
SELECT 
    code as '激活码',
    CONCAT(used_count, '/', max_uses) as '使用情况',
    CONCAT(account_expires_days, '天') as '有效期',
    CASE 
        WHEN is_active = 1 THEN '✓ 启用'
        ELSE '✗ 禁用'
    END as '状态',
    notes as '备注',
    DATE_FORMAT(created_at, '%m-%d %H:%i') as '创建时间'
FROM invite_codes 
$CONDITION
ORDER BY created_at DESC
LIMIT 20;
" 2>/dev/null

echo ""
echo -e "${YELLOW}💡 提示：${NC}"
echo "  • 查看激活码详情: bash scripts/check_invite_code.sh <激活码>"
echo "  • 生成新激活码: bash scripts/create_invite_code.sh"
echo ""
