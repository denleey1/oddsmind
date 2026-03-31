#!/bin/bash
# 等待广义实力计算完成，然后重启应用

PID_FILE="/tmp/strength_calc.pid"
LOG_FILE="/tmp/strength_calculation.log"
MAX_WAIT=3600  # 最多等待1小时

echo "=========================================="
echo "等待广义实力计算任务完成..."
echo "PID文件: $PID_FILE"
echo "日志文件: $LOG_FILE"
echo "最大等待时间: ${MAX_WAIT}秒（1小时）"
echo "=========================================="
echo ""

if [ ! -f "$PID_FILE" ]; then
    echo "错误: PID文件不存在，任务可能未启动"
    exit 1
fi

PID=$(cat "$PID_FILE")
echo "任务PID: $PID"
echo ""

# 检查进程是否存在
if ! ps -p "$PID" > /dev/null 2>&1; then
    echo "任务已完成或未运行"
    echo ""
    echo "最后日志:"
    tail -20 "$LOG_FILE"
    echo ""
    echo "检查退出码..."
    wait "$PID" 2>/dev/null
    EXIT_CODE=$?
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ 任务成功完成！"
    else
        echo "⚠️  任务退出码: $EXIT_CODE"
    fi
else
    echo "任务正在运行，等待完成..."
    echo ""
    
    START_TIME=$(date +%s)
    CHECK_COUNT=0
    
    while ps -p "$PID" > /dev/null 2>&1; do
        ELAPSED=$(($(date +%s) - START_TIME))
        
        if [ $ELAPSED -gt $MAX_WAIT ]; then
            echo ""
            echo "⚠️  等待超时（超过${MAX_WAIT}秒），停止等待"
            break
        fi
        
        CHECK_COUNT=$((CHECK_COUNT + 1))
        if [ $((CHECK_COUNT % 6)) -eq 0 ]; then
            echo "[$(date '+%H:%M:%S')] 已等待 ${ELAPSED}秒，任务仍在运行..."
            # 显示最后几行日志
            tail -3 "$LOG_FILE" 2>/dev/null | sed 's/^/  /' || echo "  等待中..."
        fi
        
        sleep 10
    done
    
    # 等待进程完全退出
    wait "$PID" 2>/dev/null
    EXIT_CODE=$?
    
    echo ""
    echo "=========================================="
    echo "任务已完成！"
    echo "总耗时: ${ELAPSED}秒"
    echo "退出码: $EXIT_CODE"
    echo ""
    echo "最后日志:"
    tail -30 "$LOG_FILE" | tail -15
    echo ""
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ 任务成功完成！"
    else
        echo "⚠️  任务退出码: $EXIT_CODE（可能有问题）"
    fi
fi

echo ""
echo "=========================================="
echo "准备重启应用..."
echo "=========================================="

# 重启应用
sudo systemctl restart oddsmind

echo ""
echo "应用已重启"
echo "检查状态..."
sleep 3
sudo systemctl status oddsmind --no-pager | head -15

echo ""
echo "=========================================="
echo "完成！"














