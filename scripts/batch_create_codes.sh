#!/bin/bash
# 批量生成激活码
# 使用方法: bash scripts/batch_create_codes.sh

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

DB_USER="root"
DB_PASS="${DB_PASS:-${MYSQL_PASSWORD:-}}"
DB_NAME="oddsmind"

echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     🎫 批量生成激活码                    ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
echo ""

# 生成随机激活码
generate_code() {
    cat /dev/urandom | tr -dc 'A-Z0-9' | fold -w 8 | head -n 1
}

# 1. 生成数量
read -p "生成数量: " QUANTITY
if ! [[ "$QUANTITY" =~ ^[0-9]+$ ]] || [ "$QUANTITY" -lt 1 ]; then
    echo -e "${RED}❌ 无效的数量！${NC}"
    exit 1
fi

# 2. 选择有效期
echo ""
echo -e "${GREEN}账号有效期：${NC}"
echo "  1) 1天   2) 7天   3) 30天"
echo "  4) 90天  5) 180天 6) 365天"
read -p "选择 [1-6]: " expire_choice

case $expire_choice in
    1) EXPIRES_DAYS=1 ;;
    2) EXPIRES_DAYS=7 ;;
    3) EXPIRES_DAYS=30 ;;
    4) EXPIRES_DAYS=90 ;;
    5) EXPIRES_DAYS=180 ;;
    6) EXPIRES_DAYS=365 ;;
    *)
        echo -e "${RED}❌ 无效的选项！${NC}"
        exit 1
        ;;
esac

# 3. 每个激活码的使用次数
echo ""
read -p "每个激活码使用次数 (默认1): " MAX_USES
MAX_USES=${MAX_USES:-1}

if ! [[ "$MAX_USES" =~ ^[0-9]+$ ]]; then
    echo -e "${RED}❌ 无效的次数！${NC}"
    exit 1
fi

# 4. 备注
echo ""
read -p "备注 (可选): " NOTES
NOTES=${NOTES:-"批量生成-${EXPIRES_DAYS}天"}

# 5. 确认
echo ""
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo -e "数量:        ${GREEN}${QUANTITY}个${NC}"
echo -e "有效期:      ${GREEN}${EXPIRES_DAYS}天${NC}"
echo -e "使用次数:    ${GREEN}${MAX_USES}次/码${NC}"
echo -e "备注:        ${GREEN}${NOTES}${NC}"
echo -e "${YELLOW}═══════════════════════════════════════${NC}"
echo ""
read -p "确认生成？ (y/n): " confirm

if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo -e "${RED}❌ 已取消${NC}"
    exit 0
fi

# 6. 批量生成
echo ""
echo -e "${BLUE}⏳ 正在生成 ${QUANTITY} 个激活码...${NC}"
echo ""

SUCCESS_COUNT=0
FAILED_COUNT=0
GENERATED_CODES=()

for i in $(seq 1 $QUANTITY); do
    CODE=$(generate_code)
    
    # 检查是否重复
    EXISTS=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
    SELECT COUNT(*) FROM invite_codes WHERE code = '$CODE';
    " 2>/dev/null)
    
    if [ "$EXISTS" != "0" ]; then
        echo -e "${YELLOW}⚠️  激活码 ${CODE} 已存在，重新生成...${NC}"
        ((i--))
        continue
    fi
    
    # 插入数据库
    RESULT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
    INSERT INTO invite_codes (code, created_by, max_uses, account_expires_days, is_active, notes, created_at)
    VALUES ('$CODE', 'admin', $MAX_USES, $EXPIRES_DAYS, TRUE, '$NOTES', NOW());
    " 2>&1)
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓${NC} ${CODE}"
        ((SUCCESS_COUNT++))
        GENERATED_CODES+=("$CODE")
    else
        echo -e "${RED}✗${NC} ${CODE} - 失败"
        ((FAILED_COUNT++))
    fi
done

# 7. 结果统计
echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           ✅ 生成完成！                   ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo -e "成功: ${GREEN}${SUCCESS_COUNT}${NC} 个"
echo -e "失败: ${RED}${FAILED_COUNT}${NC} 个"
echo ""

# 8. 保存到文件
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="/home/ubuntu/oddsmind/scripts/generated_codes_${TIMESTAMP}.txt"

echo "# 批量生成的激活码" > "$OUTPUT_FILE"
echo "# 生成时间: $(date '+%Y-%m-%d %H:%M:%S')" >> "$OUTPUT_FILE"
echo "# 数量: ${SUCCESS_COUNT}" >> "$OUTPUT_FILE"
echo "# 有效期: ${EXPIRES_DAYS}天" >> "$OUTPUT_FILE"
echo "# 使用次数: ${MAX_USES}次/码" >> "$OUTPUT_FILE"
echo "# 备注: ${NOTES}" >> "$OUTPUT_FILE"
echo "" >> "$OUTPUT_FILE"

for code in "${GENERATED_CODES[@]}"; do
    echo "$code" >> "$OUTPUT_FILE"
done

echo -e "${BLUE}📄 激活码已保存到:${NC}"
echo -e "   ${OUTPUT_FILE}"
echo ""

# 9. 显示预览
if [ ${#GENERATED_CODES[@]} -le 10 ]; then
    echo -e "${YELLOW}📋 生成的激活码：${NC}"
    echo ""
    for code in "${GENERATED_CODES[@]}"; do
        echo "   $code"
    done
    echo ""
else
    echo -e "${YELLOW}📋 激活码预览（前10个）：${NC}"
    echo ""
    for i in {0..9}; do
        if [ $i -lt ${#GENERATED_CODES[@]} ]; then
            echo "   ${GENERATED_CODES[$i]}"
        fi
    done
    echo "   ..."
    echo ""
fi

echo -e "${YELLOW}💡 提示：${NC}"
echo "  • 查看激活码列表: bash scripts/list_invite_codes.sh"
echo "  • 查看激活码文件: cat $OUTPUT_FILE"
echo ""
