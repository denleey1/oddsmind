#!/bin/bash
# 快速检查优化状态

LOG_FILE="/home/ubuntu/oddsmind/logs/oddsmind.log"

echo "=========================================="
echo "优化状态检查 - $(date)"
echo "=========================================="
echo ""

echo "1. BatchWriter 状态:"
if grep -q "BatchWriter.*started\|BatchWriter.*initialized" "$LOG_FILE" 2>/dev/null; then
    echo "  ✅ BatchWriter 已启动"
    tail -20 "$LOG_FILE" | grep -i "BatchWriter" | tail -3
else
    echo "  ⚠️  未找到 BatchWriter 启动日志"
fi
echo ""

echo "2. 联赛状态监控优化:"
if grep -q "分批处理\|并发数.*10" "$LOG_FILE" 2>/dev/null; then
    echo "  ✅ 发现分批处理/并发优化日志"
    tail -50 "$LOG_FILE" | grep -i "分批处理\|并发数\|LeagueStatusMonitor.*批" | tail -3
else
    echo "  ⚠️  未找到分批处理日志"
fi
echo ""

echo "3. 404错误快速失败:"
if grep -q "404.*fast_fail\|404.*cached invalid\|404.*marking as invalid" "$LOG_FILE" 2>/dev/null; then
    echo "  ✅ 发现404快速失败日志"
    tail -50 "$LOG_FILE" | grep -i "404.*fast_fail\|404.*cached\|404.*marking" | tail -3
else
    echo "  ⚠️  未找到404快速失败日志（可能还没有404错误）"
    echo "  检查404错误总数:"
    tail -200 "$LOG_FILE" | grep -i "404" | wc -l | xargs echo "  404错误数量:"
fi
echo ""

echo "4. 速率限制重试:"
if grep -q "Rate limit.*retrying\|速率限制.*重试" "$LOG_FILE" 2>/dev/null; then
    echo "  ✅ 发现速率限制重试日志"
    tail -50 "$LOG_FILE" | grep -i "Rate limit.*retrying" | tail -3
else
    echo "  ⚠️  未找到速率限制重试日志（可能没有速率限制超时）"
fi
echo ""

echo "5. 联赛状态监控耗时:"
if grep -q "联赛状态更新完成" "$LOG_FILE" 2>/dev/null; then
    echo "  最近的耗时记录:"
    tail -100 "$LOG_FILE" | grep -i "联赛状态更新完成" | tail -3 | sed 's/^/  /'
else
    echo "  ⚠️  未找到联赛状态更新完成日志"
fi
echo ""

echo "6. 最近的关键错误:"
tail -100 "$LOG_FILE" | grep -i "ERROR.*BatchWriter\|ERROR.*LeagueStatusMonitor\|ERROR.*性能优化" | tail -3 || echo "  无相关错误"
echo ""

echo "=========================================="














