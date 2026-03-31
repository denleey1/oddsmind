#!/bin/bash
# 交互式激活码生成脚本
# 使用方法: bash scripts/create_invite_code.sh

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目路径
PROJECT_DIR="/home/ubuntu/oddsmind"
cd "$PROJECT_DIR"

# 数据库配置
DB_USER="root"
DB_PASS="${DB_PASS:-${MYSQL_PASSWORD:-}}"
DB_NAME="oddsmind"

echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     🎫 激活码生成工具 v2.0              ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# 函数：生成随机激活码
generate_code() {
    # 生成8位随机字符串（大写字母+数字）
    cat /dev/urandom | tr -dc 'A-Z0-9' | fold -w 8 | head -n 1
}

# 函数：验证数字输入
validate_number() {
    re='^[0-9]+$'
    if ! [[ $1 =~ $re ]] ; then
        return 1
    fi
    return 0
}

# 1. 选择有效期
echo -e "${GREEN}📅 请选择账号有效期：${NC}"
echo "  1) 1天   (测试用)"
echo "  2) 7天   (体验用)"
echo "  3) 30天  (月卡)"
echo "  4) 90天  (季卡)"
echo "  5) 180天 (半年卡)"
echo "  6) 365天 (年卡)"
echo "  7) 自定义天数"
echo ""
read -p "请输入选项 [1-7]: " expire_choice

case $expire_choice in
    1)
        EXPIRES_DAYS=1
        EXPIRE_NAME="1天测试"
        ;;
    2)
        EXPIRES_DAYS=7
        EXPIRE_NAME="7天体验"
        ;;
    3)
        EXPIRES_DAYS=30
        EXPIRE_NAME="30天月卡"
        ;;
    4)
        EXPIRES_DAYS=90
        EXPIRE_NAME="90天季卡"
        ;;
    5)
        EXPIRES_DAYS=180
        EXPIRE_NAME="180天半年卡"
        ;;
    6)
        EXPIRES_DAYS=365
        EXPIRE_NAME="365天年卡"
        ;;
    7)
        read -p "请输入天数: " EXPIRES_DAYS
        if ! validate_number "$EXPIRES_DAYS"; then
            echo -e "${RED}❌ 无效的天数！${NC}"
            exit 1
        fi
        EXPIRE_NAME="${EXPIRES_DAYS}天"
        ;;
    *)
        echo -e "${RED}❌ 无效的选项！${NC}"
        exit 1
        ;;
esac

echo ""

# 2. 选择使用次数
echo -e "${GREEN}🔢 请选择激活码使用次数：${NC}"
echo "  1) 1次   (单人使用)"
echo "  2) 5次   (小团队)"
echo "  3) 10次  (团队使用)"
echo "  4) 50次  (批量使用)"
echo "  5) 100次 (大批量)"
echo "  6) 自定义次数"
echo ""
read -p "请输入选项 [1-6]: " uses_choice

case $uses_choice in
    1)
        MAX_USES=1
        ;;
    2)
        MAX_USES=5
        ;;
    3)
        MAX_USES=10
        ;;
    4)
        MAX_USES=50
        ;;
    5)
        MAX_USES=100
        ;;
    6)
        read -p "请输入次数: " MAX_USES
        if ! validate_number "$MAX_USES"; then
            echo -e "${RED}❌ 无效的次数！${NC}"
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}❌ 无效的选项！${NC}"
        exit 1
        ;;
esac

echo ""

# 3. 选择激活码类型
echo -e "${GREEN}🎯 请选择激活码类型：${NC}"
echo "  1) 自动生成 (推荐)"
echo "  2) 自定义激活码"
echo ""
read -p "请输入选项 [1-2]: " code_type

if [ "$code_type" == "2" ]; then
    read -p "请输入激活码: " INVITE_CODE
    INVITE_CODE=$(echo "$INVITE_CODE" | tr '[:lower:]' '[:upper:]')
else
    INVITE_CODE=$(generate_code)
fi

echo ""

# 4. 添加备注（可选）
read -p "备注信息 (可选，直接回车跳过): " NOTES
if [ -z "$NOTES" ]; then
    NOTES="${EXPIRE_NAME}-${MAX_USES}次使用"
fi

echo ""

# 5. 确认信息
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "${YELLOW}📋 请确认以下信息：${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "激活码:      ${GREEN}${INVITE_CODE}${NC}"
echo -e "有效期:      ${GREEN}${EXPIRES_DAYS}天${NC}"
echo -e "使用次数:    ${GREEN}${MAX_USES}次${NC}"
echo -e "备注:        ${GREEN}${NOTES}${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo ""
read -p "确认生成？ (y/n): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo -e "${RED}❌ 已取消${NC}"
    exit 0
fi

echo ""
echo -e "${BLUE}⏳ 正在生成激活码...${NC}"

# 6. 生成激活码（插入数据库）
RESULT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
INSERT INTO invite_codes (code, created_by, max_uses, account_expires_days, is_active, notes, created_at)
VALUES ('$INVITE_CODE', 'admin', $MAX_USES, $EXPIRES_DAYS, TRUE, '$NOTES', NOW());
SELECT ROW_COUNT();
" 2>&1)

# 检查是否成功
if echo "$RESULT" | grep -q "ERROR"; then
    echo -e "${RED}❌ 生成失败！${NC}"
    echo -e "${RED}错误信息: $RESULT${NC}"
    
    # 检查是否是重复激活码
    if echo "$RESULT" | grep -q "Duplicate entry"; then
        echo ""
        echo -e "${YELLOW}提示: 激活码 ${INVITE_CODE} 已存在，请重新运行脚本${NC}"
    fi
    exit 1
fi

# 7. 成功提示
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✅ 激活码生成成功！             ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}🎫 激活码信息${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "  激活码:      ${GREEN}${INVITE_CODE}${NC}"
echo -e "  有效期:      ${GREEN}${EXPIRES_DAYS}天${NC}"
echo -e "  使用次数:    ${GREEN}0/${MAX_USES}${NC}"
echo -e "  状态:        ${GREEN}启用${NC}"
echo -e "  备注:        ${BLUE}${NOTES}${NC}"
echo ""
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# 8. 查看激活码（带表格）
echo -e "${YELLOW}📊 激活码详情：${NC}"
echo ""
mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -e "
SELECT 
    code as '激活码',
    max_uses as '最大次数',
    used_count as '已使用',
    CONCAT(account_expires_days, '天') as '账号有效期',
    CASE 
        WHEN is_active = 1 THEN '✓ 启用'
        ELSE '✗ 禁用'
    END as '状态',
    notes as '备注',
    DATE_FORMAT(created_at, '%Y-%m-%d %H:%i') as '创建时间'
FROM invite_codes 
WHERE code = '$INVITE_CODE';
" 2>/dev/null

echo ""

# 9. 提示操作
echo -e "${YELLOW}💡 接下来可以：${NC}"
echo ""
echo "  1. 复制激活码发送给用户: ${GREEN}${INVITE_CODE}${NC}"
echo "  2. 查看所有激活码: ${BLUE}bash scripts/list_invite_codes.sh${NC}"
echo "  3. 查看激活码详情: ${BLUE}bash scripts/check_invite_code.sh ${INVITE_CODE}${NC}"
echo "  4. 继续生成激活码: ${BLUE}bash scripts/create_invite_code.sh${NC}"
echo ""

# 10. 是否继续生成
echo ""
read -p "是否继续生成激活码？ (y/n): " continue_create

if [ "$continue_create" == "y" ] || [ "$continue_create" == "Y" ]; then
    echo ""
    exec bash "$0"
fi

echo ""
echo -e "${GREEN}✅ 完成！${NC}"
