#!/bin/bash
# 监控优化相关的日志
# 用于验证性能优化是否正常工作

LOG_FILE="/home/ubuntu/oddsmind/logs/oddsmind.log"
CHECK_INTERVAL=10
TOTAL_CHECKS=60  # 10分钟，每10秒检查一次

echo "开始监控优化相关日志..."
echo "监控文件: $LOG_FILE"
echo "检查间隔: ${CHECK_INTERVAL}秒"
echo "总检查次数: ${TOTAL_CHECKS}次"
echo "=========================================="

for i in $(seq 1 $TOTAL_CHECKS); do
    echo ""
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] 检查 #$i/$TOTAL_CHECKS"
    echo "----------------------------------------"
    
    # 1. BatchWriter 相关
    echo "1. BatchWriter 状态:"
    tail -100 "$LOG_FILE" | grep -i "BatchWriter" | tail -3 || echo "  未找到 BatchWriter 日志"
    
    # 2. 联赛状态监控
    echo "2. 联赛状态监控:"
    tail -100 "$LOG_FILE" | grep -i "LeagueStatusMonitor\|联赛状态" | tail -3 || echo "  未找到联赛状态监控日志"
    
    # 3. 404错误快速失败
    echo "3. 404错误处理:"
    tail -100 "$LOG_FILE" | grep -i "404\|fast_fail\|cached invalid" | tail -3 || echo "  未找到404相关日志"
    
    # 4. 速率限制重试
    echo "4. 速率限制:"
    tail -100 "$LOG_FILE" | grep -i "Rate limit.*retrying\|速率限制" | tail -3 || echo "  未找到速率限制重试日志"
    
    # 5. 分批处理
    echo "5. 分批处理:"
    tail -100 "$LOG_FILE" | grep -i "分批处理\|batch.*处理\|并发数" | tail -3 || echo "  未找到分批处理日志"
    
    # 6. 性能优化标记
    echo "6. 性能优化标记:"
    tail -100 "$LOG_FILE" | grep -i "性能优化" | tail -3 || echo "  未找到性能优化标记"
    
    # 7. 错误和异常
    echo "7. 最近错误:"
    tail -50 "$LOG_FILE" | grep -i "ERROR\|Exception\|Traceback" | tail -2 || echo "  无错误"
    
    sleep $CHECK_INTERVAL
done

echo ""
echo "=========================================="
echo "监控完成！"














