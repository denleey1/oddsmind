#!/bin/bash
# 赛前30分钟自动监控脚本
# 用法:
#   ./check_30min.sh          # 手动运行，默认查看未来30分钟
#   ./check_30min.sh 60       # 手动运行，查看未来60分钟
#   ./check_30min.sh cron     # 设置定时任务（每小时:29和:59自动运行）
#   ./check_30min.sh stop     # 停止定时任务

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/check_30min.py"
LOG_DIR="$SCRIPT_DIR/logs/monitor"

case "$1" in
    cron)
        mkdir -p "$LOG_DIR"
        # 删除已有的同类cron
        crontab -l 2>/dev/null | grep -v "check_30min" > /tmp/cron_tmp
        # 每小时的:29和:59执行
        echo "29,59 * * * * /usr/bin/python3 $PY_SCRIPT -m 31 --log >> $LOG_DIR/cron.log 2>&1" >> /tmp/cron_tmp
        crontab /tmp/cron_tmp
        rm /tmp/cron_tmp
        echo "定时任务已设置: 每小时的 :29 和 :59 自动检查"
        echo "日志目录: $LOG_DIR"
        echo "  文本日志: $LOG_DIR/YYYY-MM-DD.log"
        echo "  JSON数据: $LOG_DIR/YYYY-MM-DD.json  (供回测)"
        echo "  cron输出: $LOG_DIR/cron.log"
        echo ""
        echo "查看当前cron:"
        crontab -l | grep check_30min
        ;;
    stop)
        crontab -l 2>/dev/null | grep -v "check_30min" | crontab -
        echo "定时任务已停止"
        ;;
    *)
        MINUTES="${1:-30}"
        python3 "$PY_SCRIPT" -m "$MINUTES"
        ;;
esac
