#!/bin/bash
# 清理过期用户（谨慎使用！）
# 使用方法: bash scripts/cleanup_expired_users.sh

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

DB_USER="root"
DB_PASS="${DB_PASS:-${MYSQL_PASSWORD:-}}"
DB_NAME="oddsmind"

echo -e "${RED}╔═══════════════════════════════════════════╗${NC}"
echo -e "${RED}║     ⚠️  用户清理工具（谨慎使用！）        ║${NC}"
echo -e "${RED}╚═══════════════════════════════════════════╝${NC}"
echo ""
echo -e "${YELLOW}⚠️  警告：此操作不可逆！请谨慎操作！${NC}"
echo ""

# 1. 选择清理类型
echo -e "${GREEN}请选择清理类型：${NC}"
echo "  1) 查看将要清理的用户（不实际删除）"
echo "  2) 清理已过期用户（过期时间 < 当前时间）"
echo "  3) 清理长期未登录用户（30天未登录）"
echo "  4) 清理测试用户（openid 包含 'test'）"
echo "  5) 清理特定用户（按用户ID）"
echo -e "  ${RED}6) 清理所有用户（危险！）${NC}"
echo "  7) 取消"
echo ""
read -p "请输入选项 [1-7]: " cleanup_choice

case $cleanup_choice in
    1)
        # 预览模式
        echo ""
        echo -e "${YELLOW}📋 预览：将要清理的用户${NC}"
        echo ""
        
        # 显示所有用户统计
        TOTAL_COUNT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users;
        " 2>/dev/null)
        
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}0. 所有用户统计：${NC}"
        echo -e "  总用户数: ${GREEN}${TOTAL_COUNT}${NC}"
        echo ""
        
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}1. 已过期用户：${NC}"
        mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
        SELECT 
            id,
            SUBSTRING(openid, 1, 20) as openid,
            invite_code_used,
            DATE_FORMAT(expires_at, '%Y-%m-%d') as expired_date,
            TIMESTAMPDIFF(DAY, expires_at, NOW()) as days_expired
        FROM miniprogram_users 
        WHERE is_activated = 1 
          AND expires_at IS NOT NULL 
          AND expires_at < NOW()
        ORDER BY expires_at DESC
        LIMIT 20;
        " 2>/dev/null
        
        COUNT1=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users 
        WHERE is_activated = 1 AND expires_at IS NOT NULL AND expires_at < NOW();
        " 2>/dev/null)
        
        echo ""
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}2. 长期未登录用户（30天）：${NC}"
        mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
        SELECT 
            id,
            SUBSTRING(openid, 1, 20) as openid,
            invite_code_used,
            DATE_FORMAT(last_login_at, '%Y-%m-%d') as last_login,
            TIMESTAMPDIFF(DAY, last_login_at, NOW()) as days_ago
        FROM miniprogram_users 
        WHERE is_activated = 1 
          AND last_login_at IS NOT NULL
          AND last_login_at < DATE_SUB(NOW(), INTERVAL 30 DAY)
        ORDER BY last_login_at ASC
        LIMIT 20;
        " 2>/dev/null
        
        COUNT2=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users 
        WHERE is_activated = 1 
          AND last_login_at IS NOT NULL
          AND last_login_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
        " 2>/dev/null)
        
        echo ""
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}3. 测试用户：${NC}"
        mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
        SELECT 
            id,
            openid,
            invite_code_used,
            DATE_FORMAT(created_at, '%Y-%m-%d') as created
        FROM miniprogram_users 
        WHERE openid LIKE '%test%' OR openid LIKE '%Test%'
        LIMIT 20;
        " 2>/dev/null
        
        COUNT3=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users 
        WHERE openid LIKE '%test%' OR openid LIKE '%Test%';
        " 2>/dev/null)
        
        echo ""
        echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${YELLOW}4. 所有用户（前20个）：${NC}"
        mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -t -e "
        SELECT 
            id,
            SUBSTRING(openid, 1, 20) as openid,
            CASE 
                WHEN is_activated = 1 THEN '✓ 已激活'
                ELSE '✗ 未激活'
            END as status,
            invite_code_used,
            DATE_FORMAT(created_at, '%Y-%m-%d') as created
        FROM miniprogram_users 
        ORDER BY created_at DESC
        LIMIT 20;
        " 2>/dev/null
        
        echo ""
        echo -e "${YELLOW}📊 统计：${NC}"
        echo -e "  总用户数:        ${GREEN}${TOTAL_COUNT}${NC}"
        echo -e "  已过期用户:      ${RED}${COUNT1}${NC}"
        echo -e "  长期未登录:      ${YELLOW}${COUNT2}${NC}"
        echo -e "  测试用户:        ${BLUE}${COUNT3}${NC}"
        echo ""
        echo -e "${GREEN}✅ 预览完成，未执行删除操作${NC}"
        exit 0
        ;;
    2)
        # 清理已过期用户
        echo ""
        echo -e "${YELLOW}📋 将要清理：已过期用户${NC}"
        
        COUNT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users 
        WHERE is_activated = 1 
          AND expires_at IS NOT NULL 
          AND expires_at < NOW();
        " 2>/dev/null)
        
        if [ "$COUNT" == "0" ]; then
            echo -e "${GREEN}✅ 没有已过期的用户${NC}"
            exit 0
        fi
        
        echo -e "${RED}⚠️  将删除 ${COUNT} 个已过期用户${NC}"
        echo ""
        read -p "确认删除？输入 'DELETE' 确认: " confirm
        
        if [ "$confirm" != "DELETE" ]; then
            echo -e "${YELLOW}❌ 已取消${NC}"
            exit 0
        fi
        
        # 备份（可选）
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="/home/ubuntu/oddsmind/scripts/backup_expired_users_${TIMESTAMP}.sql"
        
        echo ""
        echo -e "${BLUE}📦 正在备份...${NC}"
        mysqldump -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" miniprogram_users \
            --where="is_activated = 1 AND expires_at IS NOT NULL AND expires_at < NOW()" \
            > "$BACKUP_FILE" 2>/dev/null
        
        echo -e "${GREEN}✅ 备份已保存: ${BACKUP_FILE}${NC}"
        echo ""
        
        # 执行删除
        echo -e "${RED}🗑️  正在删除...${NC}"
        DELETED=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        DELETE FROM miniprogram_users 
        WHERE is_activated = 1 
          AND expires_at IS NOT NULL 
          AND expires_at < NOW();
        SELECT ROW_COUNT();
        " 2>/dev/null)
        
        echo -e "${GREEN}✅ 已删除 ${DELETED} 个已过期用户${NC}"
        ;;
    3)
        # 清理长期未登录用户
        echo ""
        echo -e "${YELLOW}📋 将要清理：30天未登录用户${NC}"
        
        COUNT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users 
        WHERE is_activated = 1 
          AND last_login_at IS NOT NULL
          AND last_login_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
        " 2>/dev/null)
        
        if [ "$COUNT" == "0" ]; then
            echo -e "${GREEN}✅ 没有长期未登录的用户${NC}"
            exit 0
        fi
        
        echo -e "${RED}⚠️  将删除 ${COUNT} 个长期未登录用户${NC}"
        echo ""
        read -p "确认删除？输入 'DELETE' 确认: " confirm
        
        if [ "$confirm" != "DELETE" ]; then
            echo -e "${YELLOW}❌ 已取消${NC}"
            exit 0
        fi
        
        # 执行删除
        DELETED=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        DELETE FROM miniprogram_users 
        WHERE is_activated = 1 
          AND last_login_at IS NOT NULL
          AND last_login_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
        SELECT ROW_COUNT();
        " 2>/dev/null)
        
        echo -e "${GREEN}✅ 已删除 ${DELETED} 个长期未登录用户${NC}"
        ;;
    4)
        # 清理测试用户
        echo ""
        echo -e "${YELLOW}📋 将要清理：测试用户${NC}"
        
        COUNT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users 
        WHERE openid LIKE '%test%' OR openid LIKE '%Test%';
        " 2>/dev/null)
        
        if [ "$COUNT" == "0" ]; then
            echo -e "${GREEN}✅ 没有测试用户${NC}"
            exit 0
        fi
        
        echo -e "${RED}⚠️  将删除 ${COUNT} 个测试用户${NC}"
        echo ""
        read -p "确认删除？输入 'DELETE' 确认: " confirm
        
        if [ "$confirm" != "DELETE" ]; then
            echo -e "${YELLOW}❌ 已取消${NC}"
            exit 0
        fi
        
        # 执行删除
        DELETED=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        DELETE FROM miniprogram_users 
        WHERE openid LIKE '%test%' OR openid LIKE '%Test%';
        SELECT ROW_COUNT();
        " 2>/dev/null)
        
        echo -e "${GREEN}✅ 已删除 ${DELETED} 个测试用户${NC}"
        ;;
    5)
        # 清理特定用户
        echo ""
        read -p "请输入要删除的用户ID: " user_id
        
        if ! [[ "$user_id" =~ ^[0-9]+$ ]]; then
            echo -e "${RED}❌ 无效的用户ID！${NC}"
            exit 1
        fi
        
        # 显示用户信息
        USER_INFO=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT CONCAT(id, '|', openid, '|', IFNULL(nickname, 'NULL'), '|', invite_code_used)
        FROM miniprogram_users 
        WHERE id = $user_id;
        " 2>/dev/null)
        
        if [ -z "$USER_INFO" ]; then
            echo -e "${RED}❌ 用户不存在！${NC}"
            exit 1
        fi
        
        echo ""
        echo -e "${YELLOW}用户信息：${NC}"
        echo "$USER_INFO" | awk -F'|' '{print "  ID: " $1 "\n  OpenID: " $2 "\n  昵称: " $3 "\n  激活码: " $4}'
        echo ""
        read -p "确认删除此用户？输入 'DELETE' 确认: " confirm
        
        if [ "$confirm" != "DELETE" ]; then
            echo -e "${YELLOW}❌ 已取消${NC}"
            exit 0
        fi
        
        # 执行删除
        DELETED=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        DELETE FROM miniprogram_users WHERE id = $user_id;
        SELECT ROW_COUNT();
        " 2>/dev/null)
        
        if [ "$DELETED" == "1" ]; then
            echo -e "${GREEN}✅ 用户已删除${NC}"
        else
            echo -e "${RED}❌ 删除失败${NC}"
        fi
        ;;
    6)
        # 清理所有用户（极度危险！）
        echo ""
        echo -e "${RED}╔═══════════════════════════════════════════╗${NC}"
        echo -e "${RED}║     ⚠️⚠️⚠️  极度危险操作！⚠️⚠️⚠️            ║${NC}"
        echo -e "${RED}╚═══════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${RED}⚠️  警告：此操作将删除所有用户数据！${NC}"
        echo -e "${RED}⚠️  包括已激活和未激活的所有用户！${NC}"
        echo -e "${RED}⚠️  此操作不可逆！${NC}"
        echo ""
        
        # 统计用户数量
        TOTAL_COUNT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users;
        " 2>/dev/null)
        
        ACTIVATED_COUNT=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        SELECT COUNT(*) FROM miniprogram_users WHERE is_activated = 1;
        " 2>/dev/null)
        
        echo -e "${YELLOW}📊 当前用户统计：${NC}"
        echo -e "  总用户数:      ${RED}${TOTAL_COUNT}${NC}"
        echo -e "  已激活用户:   ${RED}${ACTIVATED_COUNT}${NC}"
        echo -e "  未激活用户:   ${RED}$((TOTAL_COUNT - ACTIVATED_COUNT))${NC}"
        echo ""
        
        if [ "$TOTAL_COUNT" == "0" ]; then
            echo -e "${GREEN}✅ 没有用户需要清理${NC}"
            exit 0
        fi
        
        # 第一层确认
        echo -e "${RED}⚠️  确认要删除所有 ${TOTAL_COUNT} 个用户吗？${NC}"
        read -p "输入 'YES' 继续: " confirm1
        
        if [ "$confirm1" != "YES" ]; then
            echo -e "${YELLOW}❌ 已取消${NC}"
            exit 0
        fi
        
        # 第二层确认
        echo ""
        echo -e "${RED}⚠️  最后确认：此操作将永久删除所有用户数据！${NC}"
        read -p "再次输入 'DELETE ALL' 确认: " confirm2
        
        if [ "$confirm2" != "DELETE ALL" ]; then
            echo -e "${YELLOW}❌ 已取消${NC}"
            exit 0
        fi
        
        # 备份
        TIMESTAMP=$(date +%Y%m%d_%H%M%S)
        BACKUP_FILE="/home/ubuntu/oddsmind/scripts/backup_all_users_${TIMESTAMP}.sql"
        
        echo ""
        echo -e "${BLUE}📦 正在备份所有用户数据...${NC}"
        mysqldump -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" miniprogram_users \
            > "$BACKUP_FILE" 2>/dev/null
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✅ 备份已保存: ${BACKUP_FILE}${NC}"
        else
            echo -e "${RED}❌ 备份失败！操作已取消！${NC}"
            exit 1
        fi
        
        # 第三层确认（备份成功后）
        echo ""
        echo -e "${YELLOW}备份已完成，最后确认：${NC}"
        read -p "输入 'CONFIRM DELETE' 执行删除: " confirm3
        
        if [ "$confirm3" != "CONFIRM DELETE" ]; then
            echo -e "${YELLOW}❌ 已取消${NC}"
            echo -e "${BLUE}💡 备份文件已保存: ${BACKUP_FILE}${NC}"
            exit 0
        fi
        
        # 执行删除
        echo ""
        echo -e "${RED}🗑️  正在删除所有用户...${NC}"
        DELETED=$(mysql -u"$DB_USER" -p"$DB_PASS" "$DB_NAME" -se "
        DELETE FROM miniprogram_users;
        SELECT ROW_COUNT();
        " 2>/dev/null)
        
        if [ "$DELETED" == "$TOTAL_COUNT" ]; then
            echo -e "${GREEN}✅ 已删除 ${DELETED} 个用户${NC}"
            echo -e "${YELLOW}💡 备份文件: ${BACKUP_FILE}${NC}"
        else
            echo -e "${RED}⚠️  删除数量不匹配！预期: ${TOTAL_COUNT}, 实际: ${DELETED}${NC}"
            echo -e "${YELLOW}💡 备份文件: ${BACKUP_FILE}${NC}"
        fi
        ;;
    7)
        echo -e "${YELLOW}❌ 已取消${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}❌ 无效的选项！${NC}"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}✅ 清理完成！${NC}"
echo ""
