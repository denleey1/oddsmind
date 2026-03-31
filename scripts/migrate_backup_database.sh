#!/bin/bash
# -*- coding: utf-8 -*-
# 数据库备份脚本 - 用于迁移前的数据备份
# 使用方法: ./migrate_backup_database.sh [备份文件路径]

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 加载环境变量
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/oddsmind.env"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}错误: 找不到环境配置文件 $ENV_FILE${NC}"
    exit 1
fi

# 从环境文件读取数据库配置
source <(grep -E '^MYSQL_' "$ENV_FILE" | sed 's/^/export /')

# 设置默认备份路径
BACKUP_DIR="${1:-$PROJECT_ROOT/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/oddsmind_db_backup_${TIMESTAMP}.sql"
BACKUP_FILE_COMPRESSED="${BACKUP_FILE}.gz"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}OddsMind 数据库备份工具${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "数据库主机: ${YELLOW}${MYSQL_HOST}${NC}"
echo -e "数据库名称: ${YELLOW}${MYSQL_DATABASE}${NC}"
echo -e "备份文件: ${YELLOW}${BACKUP_FILE_COMPRESSED}${NC}"
echo ""

# 检查 mysqldump 是否可用
if ! command -v mysqldump &> /dev/null; then
    echo -e "${RED}错误: 未找到 mysqldump 命令，请先安装 MySQL 客户端${NC}"
    exit 1
fi

# 执行备份
echo -e "${YELLOW}开始备份数据库...${NC}"
mysqldump \
    -h"${MYSQL_HOST}" \
    -P"${MYSQL_PORT:-3306}" \
    -u"${MYSQL_USER}" \
    -p"${MYSQL_PASSWORD}" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --add-drop-database \
    --databases "${MYSQL_DATABASE}" \
    | gzip > "$BACKUP_FILE_COMPRESSED"

if [ $? -eq 0 ]; then
    BACKUP_SIZE=$(du -h "$BACKUP_FILE_COMPRESSED" | cut -f1)
    echo -e "${GREEN}✓ 数据库备份成功！${NC}"
    echo -e "  备份文件: ${BACKUP_FILE_COMPRESSED}"
    echo -e "  文件大小: ${BACKUP_SIZE}"
    echo ""
    echo -e "${GREEN}备份完成时间: $(date)${NC}"
    
    # 生成校验和
    echo -e "${YELLOW}生成文件校验和...${NC}"
    sha256sum "$BACKUP_FILE_COMPRESSED" > "${BACKUP_FILE_COMPRESSED}.sha256"
    echo -e "${GREEN}✓ 校验和已保存: ${BACKUP_FILE_COMPRESSED}.sha256${NC}"
else
    echo -e "${RED}✗ 数据库备份失败！${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}备份完成！${NC}"
echo -e "${GREEN}========================================${NC}"




