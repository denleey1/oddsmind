#!/bin/bash
# -*- coding: utf-8 -*-
# 完整迁移导出脚本 - 导出所有需要迁移的内容
# 使用方法: ./migrate_export_all.sh [导出目录]

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 获取脚本目录和项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# 设置导出目录
EXPORT_DIR="${1:-$PROJECT_ROOT/migration_export}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
EXPORT_ARCHIVE="${EXPORT_DIR}/oddsmind_migration_${TIMESTAMP}.tar.gz"

# 创建导出目录
mkdir -p "$EXPORT_DIR"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}OddsMind 完整迁移导出工具${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "项目根目录: ${YELLOW}${PROJECT_ROOT}${NC}"
echo -e "导出目录: ${YELLOW}${EXPORT_DIR}${NC}"
echo ""

# 定义需要排除的目录和文件
EXCLUDE_PATTERNS=(
    "--exclude=venv"
    "--exclude=__pycache__"
    "--exclude=*.pyc"
    "--exclude=*.pyo"
    "--exclude=*.log"
    "--exclude=logs/*"
    "--exclude=nohup.out"
    "--exclude=.git"
    "--exclude=.gitignore"
    "--exclude=*.tar.gz"
    "--exclude=*.zip"
    "--exclude=migration_export"
    "--exclude=backups"
    "--exclude=tmp"
    "--exclude=*.swp"
    "--exclude=*.swo"
    "--exclude=*~"
    "--exclude=.DS_Store"
)

echo -e "${YELLOW}步骤 1/4: 备份数据库...${NC}"
# 调用数据库备份脚本
if [ -f "$SCRIPT_DIR/migrate_backup_database.sh" ]; then
    bash "$SCRIPT_DIR/migrate_backup_database.sh" "$EXPORT_DIR/backups"
    echo -e "${GREEN}✓ 数据库备份完成${NC}"
else
    echo -e "${YELLOW}⚠ 数据库备份脚本未找到，跳过数据库备份${NC}"
fi

echo ""
echo -e "${YELLOW}步骤 2/4: 收集项目文件...${NC}"

# 创建临时目录用于打包
TEMP_DIR=$(mktemp -d)
TEMP_PROJECT_DIR="$TEMP_DIR/oddsmind"

# 复制项目文件（排除不需要的文件）
echo -e "${BLUE}正在复制项目文件...${NC}"
rsync -av \
    --exclude='venv' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='*.log' \
    --exclude='logs' \
    --exclude='nohup.out' \
    --exclude='.git' \
    --exclude='*.tar.gz' \
    --exclude='*.zip' \
    --exclude='migration_export' \
    --exclude='backups' \
    --exclude='tmp' \
    --exclude='*.swp' \
    --exclude='*.swo' \
    --exclude='*~' \
    --exclude='.DS_Store' \
    "$PROJECT_ROOT/" "$TEMP_PROJECT_DIR/"

echo -e "${GREEN}✓ 项目文件复制完成${NC}"

echo ""
echo -e "${YELLOW}步骤 3/4: 收集系统配置信息...${NC}"

# 收集系统服务配置（如果存在）
SYSTEMD_SERVICE="/etc/systemd/system/oddsmind.service"
if [ -f "$SYSTEMD_SERVICE" ]; then
    echo -e "${BLUE}发现 systemd 服务配置，正在复制...${NC}"
    mkdir -p "$TEMP_PROJECT_DIR/migration_config/systemd"
    cp "$SYSTEMD_SERVICE" "$TEMP_PROJECT_DIR/migration_config/systemd/"
    echo -e "${GREEN}✓ systemd 服务配置已复制${NC}"
else
    echo -e "${YELLOW}⚠ 未找到 systemd 服务配置${NC}"
fi

# 收集 Nginx 配置（如果存在）
NGINX_CONFIG="/etc/nginx/sites-available/oddsmind"
if [ -f "$NGINX_CONFIG" ]; then
    echo -e "${BLUE}发现 Nginx 配置，正在复制...${NC}"
    mkdir -p "$TEMP_PROJECT_DIR/migration_config/nginx"
    cp "$NGINX_CONFIG" "$TEMP_PROJECT_DIR/migration_config/nginx/"
    echo -e "${GREEN}✓ Nginx 配置已复制${NC}"
fi

# 收集 cron 任务（如果存在）
CRON_BACKUP="$TEMP_PROJECT_DIR/migration_config/crontab_backup.txt"
if crontab -l 2>/dev/null | grep -q "oddsmind"; then
    echo -e "${BLUE}发现 cron 任务，正在备份...${NC}"
    mkdir -p "$(dirname "$CRON_BACKUP")"
    crontab -l | grep "oddsmind" > "$CRON_BACKUP" || true
    echo -e "${GREEN}✓ cron 任务已备份${NC}"
fi

# 生成迁移信息文件
MIGRATION_INFO="$TEMP_PROJECT_DIR/migration_config/migration_info.txt"
cat > "$MIGRATION_INFO" << EOF
OddsMind 迁移信息
==================

导出时间: $(date)
源服务器: $(hostname)
源IP地址: $(hostname -I | awk '{print $1}')
操作系统: $(lsb_release -d 2>/dev/null | cut -f2 || uname -a)
Python版本: $(python3 --version 2>/dev/null || echo "未安装")
MySQL版本: $(mysql --version 2>/dev/null || echo "未安装")

项目路径: $PROJECT_ROOT
导出路径: $EXPORT_DIR

注意事项:
1. 请在新服务器上检查并更新 oddsmind.env 中的配置
2. 请确保新服务器已安装所有依赖（requirements.txt）
3. 请在新服务器上恢复数据库备份
4. 请根据实际情况配置 systemd 服务和 Nginx（如果使用）
EOF

echo -e "${GREEN}✓ 系统配置信息已收集${NC}"

echo ""
echo -e "${YELLOW}步骤 4/4: 创建压缩包...${NC}"

# 创建压缩包
cd "$TEMP_DIR"
tar -czf "$EXPORT_ARCHIVE" oddsmind/

# 计算文件大小
ARCHIVE_SIZE=$(du -h "$EXPORT_ARCHIVE" | cut -f1)

echo -e "${GREEN}✓ 压缩包创建完成${NC}"
echo -e "  文件: ${EXPORT_ARCHIVE}"
echo -e "  大小: ${ARCHIVE_SIZE}"

# 生成校验和
echo ""
echo -e "${YELLOW}生成文件校验和...${NC}"
sha256sum "$EXPORT_ARCHIVE" > "${EXPORT_ARCHIVE}.sha256"
echo -e "${GREEN}✓ 校验和已保存: ${EXPORT_ARCHIVE}.sha256${NC}"

# 清理临时目录
rm -rf "$TEMP_DIR"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}导出完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "导出文件位置: ${YELLOW}${EXPORT_ARCHIVE}${NC}"
echo -e "校验和文件: ${YELLOW}${EXPORT_ARCHIVE}.sha256${NC}"
echo ""
echo -e "${BLUE}下一步操作:${NC}"
echo -e "1. 将 ${EXPORT_ARCHIVE} 和 ${EXPORT_ARCHIVE}.sha256 传输到新服务器"
echo -e "2. 在新服务器上运行迁移部署脚本"
echo ""

