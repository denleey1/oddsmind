#!/bin/bash
# -*- coding: utf-8 -*-
"""
设置自动备份定时任务
每天凌晨4点执行备份
"""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BACKUP_SCRIPT="$SCRIPT_DIR/auto_backup.py"
PYTHON_PATH="$(which python3)"

# 检查Python路径
if [ -z "$PYTHON_PATH" ]; then
    echo "❌ 错误: 未找到python3，请确保Python已安装"
    exit 1
fi

# 检查备份脚本是否存在
if [ ! -f "$BACKUP_SCRIPT" ]; then
    echo "❌ 错误: 备份脚本不存在: $BACKUP_SCRIPT"
    exit 1
fi

# 确保备份脚本可执行
chmod +x "$BACKUP_SCRIPT"

# 创建日志目录
LOG_DIR="$PROJECT_ROOT/backups/logs"
mkdir -p "$LOG_DIR"

# Cron任务（每天凌晨4点执行）
CRON_TIME="0 4 * * *"
CRON_JOB="$CRON_TIME cd $PROJECT_ROOT && $PYTHON_PATH $BACKUP_SCRIPT >> $LOG_DIR/backup_cron.log 2>&1"

# 检查是否已存在相同的cron任务
EXISTING_CRON=$(crontab -l 2>/dev/null | grep -F "$BACKUP_SCRIPT")

if [ -n "$EXISTING_CRON" ]; then
    echo "⚠️  检测到已存在的备份定时任务:"
    echo "$EXISTING_CRON"
    echo ""
    read -p "是否要替换现有任务? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # 删除旧任务
        crontab -l 2>/dev/null | grep -v "$BACKUP_SCRIPT" | crontab -
        echo "✅ 已删除旧任务"
    else
        echo "❌ 操作已取消"
        exit 0
    fi
fi

# 添加新的cron任务
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ 定时备份任务已设置!"
echo ""
echo "📋 任务详情:"
echo "   执行时间: 每天凌晨 4:00"
echo "   备份脚本: $BACKUP_SCRIPT"
echo "   日志文件: $LOG_DIR/backup_cron.log"
echo ""
echo "📝 查看当前cron任务:"
echo "   crontab -l"
echo ""
echo "📝 编辑cron任务:"
echo "   crontab -e"
echo ""
echo "📝 删除备份定时任务:"
echo "   crontab -l | grep -v '$BACKUP_SCRIPT' | crontab -"
echo ""
echo "📝 手动执行备份:"
echo "   cd $PROJECT_ROOT && $PYTHON_PATH $BACKUP_SCRIPT"

