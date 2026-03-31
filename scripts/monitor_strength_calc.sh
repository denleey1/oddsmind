#!/bin/bash
# 实时监控广义实力计算任务

PID_FILE="/tmp/strength_calc.pid"
LOG_FILE="/tmp/strength_calculation.log"

if [ ! -f "$PID_FILE" ]; then
    echo "错误: 任务未启动或PID文件不存在"
    exit 1
fi

PID=$(cat "$PID_FILE")

echo "=========================================="
echo "广义实力计算任务监控"
echo "=========================================="
echo "任务PID: $PID"
echo "日志文件: $LOG_FILE"
echo ""

if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "任务已完成"
    echo ""
    echo "最后日志:"
    tail -30 "$LOG_FILE" | tail -15
    exit 0
fi

echo "任务正在运行..."
echo "实时日志（按Ctrl+C退出）:"
echo "----------------------------------------"
tail -f "$LOG_FILE" 2>/dev/null














