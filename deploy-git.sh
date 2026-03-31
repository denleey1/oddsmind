#!/bin/bash
# Git 部署脚本

set -e

echo "=========================================="
echo "OddsMind Git 部署脚本"
echo "=========================================="

# 检查是否在项目目录
if [ ! -f "app.py" ]; then
    echo "错误：请在项目根目录运行此脚本"
    exit 1
fi

# 拉取最新代码
echo "📥 拉取最新代码..."
git pull origin main || git pull origin master

# 检查虚拟环境
if [ ! -d "venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "🔧 激活虚拟环境..."
source venv/bin/activate

# 更新依赖
echo "📚 更新依赖..."
pip install -r requirements.txt

# 检查环境变量文件
if [ ! -f "oddsmind.env" ]; then
    echo "⚠️  警告：未找到 oddsmind.env 文件"
    echo "请创建并配置环境变量文件"
fi

# 重启服务（如果使用 systemd）
if systemctl is-active --quiet oddsmind.service; then
    echo "🔄 重启服务..."
    systemctl restart oddsmind.service
    sleep 3
    systemctl status oddsmind.service --no-pager | head -10
else
    echo "ℹ️  systemd 服务未运行，请手动启动应用"
fi

echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="


