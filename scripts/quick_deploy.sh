#!/bin/bash

# OddsMind 快速部署脚本
# 仅更新代码和重启服务，不重装依赖

set -e

# 配置变量
DEPLOY_DIR="/opt/oddsmind"
SERVICE_NAME="oddsmind"
SERVICE_USER="oddsmind"

# 颜色输出
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# 检查是否已经部署过
if [[ ! -d "$DEPLOY_DIR" ]]; then
    print_warning "应用尚未部署，请先运行完整部署脚本 deploy.sh"
    exit 1
fi

# 检查当前目录
if [[ ! -f "app.py" ]]; then
    print_warning "请在项目根目录运行此脚本"
    exit 1
fi

print_info "开始快速部署更新..."

# 1. 停止服务
print_info "停止服务..."
systemctl stop $SERVICE_NAME

# 2. 备份当前版本（简单备份）
print_info "创建备份..."
cp -r $DEPLOY_DIR $DEPLOY_DIR.backup.$(date +%H%M%S)

# 3. 更新代码文件
print_info "更新代码文件..."
rsync -av --progress \
    --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='*.pyo' \
    --exclude='.pytest_cache' \
    --exclude='logs/*.log' \
    --exclude='.env*' \
    --exclude='backups/' \
    --exclude='*.sql' \
    --exclude='venv/' \
    ./ $DEPLOY_DIR/

# 4. 检查依赖变化
cd $DEPLOY_DIR
if [[ -f "requirements.txt" && -f "venv/.requirements_checksum" ]]; then
    NEW_CHECKSUM=$(md5sum requirements.txt | cut -d' ' -f1)
    OLD_CHECKSUM=$(cat venv/.requirements_checksum 2>/dev/null || echo "")
    
    if [[ "$NEW_CHECKSUM" != "$OLD_CHECKSUM" ]]; then
        print_info "依赖有变化，更新Python包..."
        sudo -u $SERVICE_USER venv/bin/pip install -r requirements.txt
        echo "$NEW_CHECKSUM" > venv/.requirements_checksum
        chown $SERVICE_USER:$SERVICE_USER venv/.requirements_checksum
    else
        print_success "依赖无变化，跳过包安装"
    fi
fi

# 5. 设置权限
chown -R $SERVICE_USER:$SERVICE_USER $DEPLOY_DIR
find $DEPLOY_DIR -type f -name "*.py" -exec chmod 644 {} \;

# 6. 启动服务
print_info "启动服务..."
systemctl start $SERVICE_NAME

# 7. 检查状态
sleep 3
if systemctl is-active --quiet $SERVICE_NAME; then
    print_success "服务启动成功"
    
    # 测试Web服务
    sleep 5
    if curl -s --max-time 10 http://localhost:8889 > /dev/null; then
        print_success "Web服务响应正常"
    else
        print_warning "Web服务无响应，请检查日志"
    fi
else
    print_warning "服务启动失败，请查看日志: journalctl -u $SERVICE_NAME -f"
fi

print_success "快速部署完成！"
print_info "查看状态: systemctl status $SERVICE_NAME"
print_info "查看日志: journalctl -u $SERVICE_NAME -f"