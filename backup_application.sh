#!/bin/bash
# -*- coding: utf-8 -*-
# OddsMind 应用代码备份脚本
# 排除 .md 文件，只备份应用代码

set -e

# 项目根目录
PROJECT_ROOT="/home/ubuntu/oddsmind"
BACKUP_DIR="/home/ubuntu"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_NAME="oddsmind_backup_${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

echo "=========================================="
echo "OddsMind 应用代码备份工具"
echo "=========================================="
echo "备份时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "项目目录: ${PROJECT_ROOT}"
echo "备份目标: ${BACKUP_PATH}.tar.gz"
echo ""

# 创建临时备份目录
mkdir -p "${BACKUP_PATH}"

# 进入项目目录
cd "${PROJECT_ROOT}"

echo "正在收集文件..."

# 使用 rsync 或 find + tar 来排除文件
# 排除的内容：
# - *.md 文件
# - __pycache__ 目录
# - *.pyc, *.pyo 文件
# - venv 目录
# - logs 目录
# - .git 目录
# - *.log 文件
# - 备份脚本本身
# - 临时文件

# 使用 tar 命令直接打包，排除不需要的文件
tar -czf "${BACKUP_PATH}.tar.gz" \
  --exclude="*.md" \
  --exclude="*.pyc" \
  --exclude="*.pyo" \
  --exclude="*.log" \
  --exclude="*.log.*" \
  --exclude="backup_application.sh" \
  --exclude="__pycache__" \
  --exclude="venv" \
  --exclude=".git" \
  --exclude="logs" \
  --exclude="backups" \
  --exclude=".pytest_cache" \
  --exclude=".mypy_cache" \
  --exclude="node_modules" \
  --exclude=".DS_Store" \
  --exclude="*.swp" \
  --exclude="*.swo" \
  --exclude="*~" \
  --exclude="${BACKUP_NAME}*" \
  -C "${PROJECT_ROOT}" .

# 计算备份文件大小
BACKUP_SIZE=$(du -h "${BACKUP_PATH}.tar.gz" | cut -f1)

echo ""
echo "=========================================="
echo "备份完成！"
echo "=========================================="
echo "备份文件: ${BACKUP_PATH}.tar.gz"
echo "文件大小: ${BACKUP_SIZE}"
echo ""
echo "备份包含的内容："
echo "  ✓ 所有 Python 代码文件"
echo "  ✓ 配置文件"
echo "  ✓ 数据库相关文件"
echo "  ✓ 静态文件（CSS, JS, 图片等）"
echo "  ✓ 模板文件"
echo "  ✓ requirements.txt"
echo "  ✓ 其他应用相关文件"
echo ""
echo "排除的内容："
echo "  ✗ .md 文档文件"
echo "  ✗ __pycache__ 缓存目录"
echo "  ✗ venv 虚拟环境"
echo "  ✗ logs 日志文件"
echo "  ✗ .git 版本控制"
echo "  ✗ 临时文件"
echo ""
echo "恢复备份："
echo "  tar -xzf ${BACKUP_PATH}.tar.gz -C /目标目录/"
echo "=========================================="

