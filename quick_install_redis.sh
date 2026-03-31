#!/bin/bash
# 快速安装和配置Redis

echo "=========================================="
echo "Redis 快速安装脚本"
echo "=========================================="

# 检查是否已安装
if command -v redis-server &> /dev/null; then
    echo "✓ Redis已安装"
else
    echo "安装Redis..."
    sudo apt update
    sudo apt install redis-server -y
fi

# 检查服务状态
if systemctl is-active --quiet redis-server; then
    echo "✓ Redis服务正在运行"
else
    echo "启动Redis服务..."
    sudo systemctl start redis-server
    sudo systemctl enable redis-server
fi

# 测试连接
if redis-cli ping &> /dev/null; then
    echo "✓ Redis连接成功"
    echo ""
    echo "Redis信息:"
    redis-cli info server | grep redis_version
    redis-cli info memory | grep used_memory_human
else
    echo "✗ Redis连接失败，请检查配置"
    exit 1
fi

echo ""
echo "=========================================="
echo "安装完成！"
echo "=========================================="
echo ""
echo "下一步：重启应用使Redis生效"
echo "  sudo systemctl restart oddsmind"
