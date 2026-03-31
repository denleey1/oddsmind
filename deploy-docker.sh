#!/bin/bash
# Docker 部署脚本

set -e

echo "=========================================="
echo "OddsMind Docker 部署脚本"
echo "=========================================="

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ 错误：Docker 未安装"
    echo "请先安装 Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

# 检查 Docker Compose 是否安装
if ! command -v docker-compose &> /dev/null; then
    echo "❌ 错误：Docker Compose 未安装"
    echo "请先安装 Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi

# 检查是否在项目目录
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ 错误：未找到 docker-compose.yml 文件"
    exit 1
fi

# 拉取最新代码（如果使用 Git）
if [ -d ".git" ]; then
    echo "📥 拉取最新代码..."
    git pull origin main || git pull origin master || echo "跳过 Git 拉取"
fi

# 停止旧容器
echo "🛑 停止旧容器..."
docker-compose down

# 构建新镜像
echo "🔨 构建新镜像..."
docker-compose build --no-cache

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 检查服务状态
echo "📊 服务状态："
docker-compose ps

# 查看日志
echo ""
echo "📋 应用日志（最近 20 行）："
docker-compose logs --tail=20 oddsmind

echo ""
echo "=========================================="
echo "✅ 部署完成！"
echo "=========================================="
echo ""
echo "查看日志: docker-compose logs -f oddsmind"
echo "停止服务: docker-compose down"
echo "重启服务: docker-compose restart"


