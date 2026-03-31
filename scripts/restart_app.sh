#!/bin/bash
# 应用重启脚本 - 应用性能优化后需要重启

echo "========================================"
echo "Oddsmind 应用重启脚本"
echo "========================================"
echo ""

# 停止gunicorn进程
echo "停止当前运行的gunicorn进程..."
pkill -f "gunicorn.*app:app"
sleep 2

# 等待进程完全停止
echo "等待进程完全停止..."
sleep 3

# 检查是否还有残留进程
REMAINING=$(ps aux | grep -E "gunicorn.*app:app" | grep -v grep | wc -l)
if [ $REMAINING -gt 0 ]; then
    echo "发现残留进程，强制停止..."
    pkill -9 -f "gunicorn.*app:app"
    sleep 2
fi

# 重启应用
echo "启动应用..."
cd /home/ubuntu/oddsmind
nohup python3 app.py > logs/app_startup.log 2>&1 &

# 等待应用启动
echo "等待应用启动..."
sleep 5

# 检查应用是否启动成功
echo "检查应用状态..."
if curl -s http://localhost:8889/health > /dev/null 2>&1; then
    echo "✅ 应用启动成功！"
else
    echo "❌ 应用启动失败，请检查日志"
    echo "启动日志："
    tail -20 logs/app_startup.log
    exit 1
fi

echo ""
echo "========================================"
echo "应用重启完成"
echo "========================================"

