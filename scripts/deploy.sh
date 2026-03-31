#!/bin/bash

# OddsMind 自动部署脚本
# 用于将应用部署到生产服务器
# 
# 使用方法: 
# chmod +x deploy.sh
# sudo ./deploy.sh

set -e  # 遇到错误立即退出

# =============================================================================
# 配置变量
# =============================================================================

DEPLOY_DIR="/opt/oddsmind"
SERVICE_NAME="oddsmind"
SERVICE_USER="oddsmind"
BACKUP_DIR="/backup/oddsmind"
LOG_DIR="/var/log/oddsmind"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# 工具函数
# =============================================================================

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        print_error "此脚本需要root权限运行"
        print_info "请使用: sudo $0"
        exit 1
    fi
}

check_os() {
    if [[ -f /etc/os-release ]]; then
        source /etc/os-release
        OS=$ID
        print_info "检测到操作系统: $PRETTY_NAME"
    else
        print_error "无法检测操作系统"
        exit 1
    fi
}

install_dependencies() {
    print_info "安装系统依赖..."
    
    case $OS in
        ubuntu|debian)
            apt update
            apt install -y python3 python3-pip python3-venv python3-dev
            apt install -y mysql-server mysql-client libmysqlclient-dev
            apt install -y nginx supervisor curl wget htop
            apt install -y build-essential pkg-config
            ;;
        centos|rhel|rocky|almalinux)
            yum update -y
            yum install -y python3 python3-pip python3-devel
            yum install -y mysql-server mysql mysql-devel
            yum install -y nginx supervisor curl wget htop
            yum install -y gcc gcc-c++ make pkgconfig
            ;;
        *)
            print_error "不支持的操作系统: $OS"
            exit 1
            ;;
    esac
    
    print_success "系统依赖安装完成"
}

create_user() {
    print_info "创建服务用户: $SERVICE_USER"
    
    if ! id "$SERVICE_USER" &>/dev/null; then
        useradd -r -s /bin/false -d $DEPLOY_DIR $SERVICE_USER
        print_success "用户 $SERVICE_USER 创建成功"
    else
        print_warning "用户 $SERVICE_USER 已存在"
    fi
}

create_directories() {
    print_info "创建必要目录..."
    
    mkdir -p $DEPLOY_DIR
    mkdir -p $BACKUP_DIR
    mkdir -p $LOG_DIR
    
    # 设置目录权限
    chown -R $SERVICE_USER:$SERVICE_USER $DEPLOY_DIR
    chown -R $SERVICE_USER:$SERVICE_USER $LOG_DIR
    chmod 755 $DEPLOY_DIR
    chmod 755 $LOG_DIR
    
    print_success "目录创建完成"
}

install_application() {
    print_info "安装应用文件..."
    
    # 检查当前目录是否包含应用文件
    if [[ ! -f "app.py" ]]; then
        print_error "在当前目录找不到 app.py，请确保在正确的目录运行此脚本"
        exit 1
    fi
    
    # 备份现有部署（如果存在）
    if [[ -d "$DEPLOY_DIR/app.py" ]]; then
        print_info "备份现有部署..."
        cp -r $DEPLOY_DIR $DEPLOY_DIR.backup.$(date +%Y%m%d_%H%M%S)
    fi
    
    # 复制应用文件
    print_info "复制应用文件到 $DEPLOY_DIR"
    
    # 排除不需要的文件和目录
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
        ./ $DEPLOY_DIR/
    
    # 设置文件权限
    chown -R $SERVICE_USER:$SERVICE_USER $DEPLOY_DIR
    find $DEPLOY_DIR -type f -name "*.py" -exec chmod 644 {} \;
    find $DEPLOY_DIR -type f -name "*.sh" -exec chmod 755 {} \;
    
    print_success "应用文件安装完成"
}

setup_python_environment() {
    print_info "设置Python虚拟环境..."
    
    cd $DEPLOY_DIR
    
    # 检查虚拟环境是否已存在
    if [[ ! -d "venv" ]]; then
        print_info "创建新的虚拟环境..."
        sudo -u $SERVICE_USER python3 -m venv venv
        sudo -u $SERVICE_USER venv/bin/pip install --upgrade pip
        FORCE_INSTALL=true
    else
        print_info "虚拟环境已存在，检查依赖更新..."
        FORCE_INSTALL=false
    fi
    
    # 安装或更新依赖
    if [[ -f "requirements.txt" ]]; then
        if [[ "$FORCE_INSTALL" == "true" ]]; then
            print_info "安装Python依赖包..."
            sudo -u $SERVICE_USER venv/bin/pip install -r requirements.txt
        else
            # 检查requirements.txt是否有变化
            if [[ -f "venv/.requirements_checksum" ]] && [[ -f "requirements.txt" ]]; then
                NEW_CHECKSUM=$(md5sum requirements.txt | cut -d' ' -f1)
                OLD_CHECKSUM=$(cat venv/.requirements_checksum 2>/dev/null || echo "")
                
                if [[ "$NEW_CHECKSUM" != "$OLD_CHECKSUM" ]]; then
                    print_info "依赖文件有变化，更新Python包..."
                    sudo -u $SERVICE_USER venv/bin/pip install -r requirements.txt
                    echo "$NEW_CHECKSUM" > venv/.requirements_checksum
                    chown $SERVICE_USER:$SERVICE_USER venv/.requirements_checksum
                else
                    print_success "依赖包无变化，跳过安装"
                fi
            else
                print_info "首次部署或缺少校验文件，安装依赖包..."
                sudo -u $SERVICE_USER venv/bin/pip install -r requirements.txt
                NEW_CHECKSUM=$(md5sum requirements.txt | cut -d' ' -f1)
                echo "$NEW_CHECKSUM" > venv/.requirements_checksum
                chown $SERVICE_USER:$SERVICE_USER venv/.requirements_checksum
            fi
        fi
    else
        print_warning "未找到 requirements.txt，跳过依赖安装"
    fi
    
    print_success "Python环境设置完成"
}

configure_mysql() {
    print_info "配置MySQL..."
    
    # 启动MySQL服务
    systemctl enable mysql 2>/dev/null || systemctl enable mysqld 2>/dev/null
    systemctl start mysql 2>/dev/null || systemctl start mysqld 2>/dev/null
    
    print_info "MySQL服务已启动"
    
    # 检查是否可以连接到MySQL
    if ! mysql -e "SELECT 1;" &>/dev/null; then
        print_warning "无法连接到MySQL，请手动配置数据库"
        print_info "请执行以下步骤:"
        print_info "1. 运行: sudo mysql_secure_installation"
        print_info "2. 创建数据库: CREATE DATABASE oddsmind;"
        print_info "3. 创建用户并授权"
        return
    fi
    
    print_success "MySQL配置完成"
}

create_systemd_service() {
    print_info "创建systemd服务..."
    
    cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=OddsMind Football Odds Analysis System
After=network.target mysql.service
Requires=mysql.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$DEPLOY_DIR
Environment=PATH=$DEPLOY_DIR/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
ExecStart=$DEPLOY_DIR/venv/bin/python app.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=$SERVICE_NAME

# 环境变量文件
EnvironmentFile=-$DEPLOY_DIR/.env.production

# 安全设置
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=$LOG_DIR $DEPLOY_DIR/logs $DEPLOY_DIR/data

# 资源限制
LimitNOFILE=65536
LimitNPROC=4096

[Install]
WantedBy=multi-user.target
EOF
    
    print_success "systemd服务配置完成"
}

create_environment_file() {
    print_info "创建环境配置文件..."
    
    cat > $DEPLOY_DIR/.env.production << EOF
# 生产环境配置
FLASK_ENV=production
LOG_LEVEL=INFO

# 数据库配置（请根据实际情况修改）
DB_HOST=localhost
DB_PORT=3306
DB_USER=oddsmind
DB_PASSWORD=your_strong_password_here
DB_NAME=oddsmind

# 应用配置
APP_HOST=0.0.0.0
APP_PORT=8889
APP_DEBUG=False

# 日志配置
LOG_DIR=$LOG_DIR
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5
EOF
    
    chown $SERVICE_USER:$SERVICE_USER $DEPLOY_DIR/.env.production
    chmod 600 $DEPLOY_DIR/.env.production
    
    print_warning "请编辑 $DEPLOY_DIR/.env.production 设置正确的数据库密码"
    print_success "环境配置文件创建完成"
}

setup_nginx() {
    print_info "配置Nginx反向代理..."
    
    cat > /etc/nginx/sites-available/oddsmind << EOF
server {
    listen 80;
    server_name _;  # 替换为实际域名
    
    client_max_body_size 10M;
    
    # 静态文件
    location /static {
        alias $DEPLOY_DIR/static;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # 应用代理
    location / {
        proxy_pass http://127.0.0.1:8889;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        
        # WebSocket支持
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # 超时设置
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\\n";
        add_header Content-Type text/plain;
    }
}
EOF
    
    # 启用站点
    if [[ -d "/etc/nginx/sites-enabled" ]]; then
        ln -sf /etc/nginx/sites-available/oddsmind /etc/nginx/sites-enabled/
    fi
    
    # 测试Nginx配置
    if nginx -t; then
        print_success "Nginx配置完成"
    else
        print_error "Nginx配置测试失败"
    fi
}

setup_logrotate() {
    print_info "配置日志轮转..."
    
    cat > /etc/logrotate.d/oddsmind << EOF
$LOG_DIR/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    copytruncate
    su $SERVICE_USER $SERVICE_USER
}
EOF
    
    print_success "日志轮转配置完成"
}

setup_monitoring() {
    print_info "设置监控脚本..."
    
    cat > $DEPLOY_DIR/health_check.sh << 'EOF'
#!/bin/bash

SERVICE_NAME="oddsmind"
LOG_FILE="/var/log/oddsmind/health_check.log"
ALERT_EMAIL=""  # 设置告警邮箱

log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> $LOG_FILE
}

# 检查服务状态
if ! systemctl is-active --quiet $SERVICE_NAME; then
    log_message "ERROR: Service $SERVICE_NAME is down, attempting restart..."
    systemctl restart $SERVICE_NAME
    sleep 10
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        log_message "INFO: Service $SERVICE_NAME restarted successfully"
    else
        log_message "ERROR: Failed to restart $SERVICE_NAME"
        # 发送告警邮件
        if [[ -n "$ALERT_EMAIL" ]]; then
            echo "OddsMind service failed to restart on $(hostname)" | mail -s "OddsMind Alert" $ALERT_EMAIL
        fi
    fi
fi

# 检查Web服务响应
if ! curl -s --max-time 10 http://localhost:8889/health > /dev/null; then
    log_message "WARNING: Web service not responding"
fi

# 检查数据库连接
# 这里可以添加数据库连接检查

# 检查磁盘空间
DISK_USAGE=$(df /opt | tail -1 | awk '{print $5}' | sed 's/%//')
if [[ $DISK_USAGE -gt 80 ]]; then
    log_message "WARNING: Disk usage is ${DISK_USAGE}%"
fi

# 检查内存使用
MEMORY_USAGE=$(free | grep Mem | awk '{printf "%.2f", ($3/$2) * 100.0}' | cut -d. -f1)
if [[ $MEMORY_USAGE -gt 80 ]]; then
    log_message "WARNING: Memory usage is ${MEMORY_USAGE}%"
fi
EOF
    
    chmod +x $DEPLOY_DIR/health_check.sh
    chown $SERVICE_USER:$SERVICE_USER $DEPLOY_DIR/health_check.sh
    
    # 添加到crontab
    (crontab -u root -l 2>/dev/null; echo "*/5 * * * * $DEPLOY_DIR/health_check.sh") | crontab -u root -
    
    print_success "监控脚本设置完成"
}

start_services() {
    print_info "启动服务..."
    
    # 重新加载systemd配置
    systemctl daemon-reload
    
    # 启用并启动OddsMind服务
    systemctl enable $SERVICE_NAME
    systemctl start $SERVICE_NAME
    
    # 启用并启动Nginx
    systemctl enable nginx
    systemctl restart nginx
    
    # 检查服务状态
    sleep 5
    
    if systemctl is-active --quiet $SERVICE_NAME; then
        print_success "OddsMind服务启动成功"
    else
        print_error "OddsMind服务启动失败"
        print_info "查看日志: journalctl -u $SERVICE_NAME -f"
    fi
    
    if systemctl is-active --quiet nginx; then
        print_success "Nginx服务启动成功"
    else
        print_error "Nginx服务启动失败"
    fi
}

test_deployment() {
    print_info "测试部署..."
    
    # 测试Web服务
    sleep 10
    if curl -s --max-time 10 http://localhost:8889 > /dev/null; then
        print_success "Web服务响应正常"
    else
        print_warning "Web服务无响应，请检查日志"
    fi
    
    # 显示服务状态
    print_info "服务状态:"
    systemctl status $SERVICE_NAME --no-pager -l
}

# =============================================================================
# 主部署流程
# =============================================================================

main() {
    print_info "开始 OddsMind 部署流程..."
    echo "=============================================="
    
    # 检查环境
    check_root
    check_os
    
    # 部署步骤
    install_dependencies
    create_user
    create_directories
    install_application
    setup_python_environment
    configure_mysql
    create_systemd_service
    create_environment_file
    setup_nginx
    setup_logrotate
    setup_monitoring
    start_services
    test_deployment
    
    echo "=============================================="
    print_success "OddsMind 部署完成！"
    echo ""
    print_info "接下来的步骤:"
    print_info "1. 编辑数据库配置: $DEPLOY_DIR/.env.production"
    print_info "2. 导入数据库: mysql -u user -p database < backup.sql"
    print_info "3. 重启服务: systemctl restart $SERVICE_NAME"
    print_info "4. 检查状态: systemctl status $SERVICE_NAME"
    print_info "5. 查看日志: journalctl -u $SERVICE_NAME -f"
    print_info "6. 访问应用: http://服务器IP:80"
    echo ""
    print_info "有用的命令:"
    print_info "- 重启服务: systemctl restart $SERVICE_NAME"
    print_info "- 查看日志: journalctl -u $SERVICE_NAME -f"
    print_info "- 检查状态: systemctl status $SERVICE_NAME"
    print_info "- 更新代码: 重新运行此脚本"
}

# 执行主函数
main "$@"