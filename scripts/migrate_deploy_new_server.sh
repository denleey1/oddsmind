#!/bin/bash
# -*- coding: utf-8 -*-
# 新服务器部署脚本 - 在新服务器上部署迁移的内容
# 使用方法: ./migrate_deploy_new_server.sh [迁移包路径] [目标目录]

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}OddsMind 新服务器部署工具${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# 检查参数
if [ $# -lt 1 ]; then
    echo -e "${RED}错误: 请提供迁移包路径${NC}"
    echo -e "使用方法: $0 <迁移包路径> [目标目录]"
    exit 1
fi

MIGRATION_ARCHIVE="$1"
TARGET_DIR="${2:-/home/ubuntu/oddsmind}"

# 检查迁移包是否存在
if [ ! -f "$MIGRATION_ARCHIVE" ]; then
    echo -e "${RED}错误: 迁移包不存在: ${MIGRATION_ARCHIVE}${NC}"
    exit 1
fi

# 验证校验和
echo -e "${YELLOW}步骤 1/7: 验证迁移包完整性...${NC}"
SHA256_FILE="${MIGRATION_ARCHIVE}.sha256"
if [ -f "$SHA256_FILE" ]; then
    # 计算迁移包的校验和
    CALCULATED_HASH=$(sha256sum "$MIGRATION_ARCHIVE" | cut -d' ' -f1)
    
    # 从校验和文件中读取期望的哈希值
    EXPECTED_HASH=$(cat "$SHA256_FILE" | cut -d' ' -f1)
    
    if [ "$CALCULATED_HASH" = "$EXPECTED_HASH" ]; then
        echo -e "${GREEN}✓ 迁移包完整性验证通过${NC}"
    else
        echo -e "${RED}✗ 迁移包完整性验证失败！${NC}"
        echo -e "${YELLOW}可能原因:${NC}"
        echo -e "  - 文件在传输过程中损坏"
        echo -e "  - 校验和文件不匹配"
        echo -e "${BLUE}计算值: ${CALCULATED_HASH:0:16}...${NC}"
        echo -e "${BLUE}期望值: ${EXPECTED_HASH:0:16}...${NC}"
        echo ""
        read -p "是否继续？(y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}⚠ 未找到校验和文件，跳过验证${NC}"
fi

# 检查系统要求
echo ""
echo -e "${YELLOW}步骤 2/7: 检查系统要求...${NC}"

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python3 未安装${NC}"
    exit 1
fi
PYTHON_VERSION=$(python3 --version)
echo -e "${GREEN}✓ ${PYTHON_VERSION}${NC}"

# 检查 MySQL 客户端
if ! command -v mysql &> /dev/null; then
    echo -e "${YELLOW}⚠ MySQL 客户端未安装，数据库恢复将需要手动操作${NC}"
else
    MYSQL_VERSION=$(mysql --version)
    echo -e "${GREEN}✓ ${MYSQL_VERSION}${NC}"
fi

# 检查 pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${RED}✗ pip3 未安装${NC}"
    exit 1
fi
echo -e "${GREEN}✓ pip3 已安装${NC}"

# 检查 python3-venv（通过尝试创建临时虚拟环境来测试）
echo -e "${BLUE}检查 python3-venv 包...${NC}"
TEMP_VENV_TEST=$(mktemp -d)
if python3 -m venv "$TEMP_VENV_TEST" &> /dev/null; then
    rm -rf "$TEMP_VENV_TEST"
    echo -e "${GREEN}✓ python3-venv 已安装${NC}"
else
    rm -rf "$TEMP_VENV_TEST"
    echo -e "${YELLOW}⚠ python3-venv 未安装，正在尝试安装...${NC}"
    if command -v apt-get &> /dev/null; then
        # 提取 Python 版本号（兼容不同系统）
        PYTHON_VERSION=$(python3 --version 2>&1 | sed -n 's/.*Python \([0-9]\+\.[0-9]\+\).*/\1/p' | head -1)
        if [ -z "$PYTHON_VERSION" ]; then
            PYTHON_VERSION="3"
        fi
        echo -e "${BLUE}执行: sudo apt install -y python${PYTHON_VERSION}-venv${NC}"
        if sudo apt install -y "python${PYTHON_VERSION}-venv" 2>&1 | grep -q "Setting up"; then
            echo -e "${GREEN}✓ python3-venv 安装成功${NC}"
        else
            # 尝试通用包名
            if sudo apt install -y python3-venv 2>&1 | grep -q "Setting up"; then
                echo -e "${GREEN}✓ python3-venv 安装成功${NC}"
            else
                echo -e "${YELLOW}⚠ 自动安装可能失败，将在创建虚拟环境时重试${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠ 无法自动安装 python3-venv，将在创建虚拟环境时提示${NC}"
    fi
fi

# 解压迁移包
echo ""
echo -e "${YELLOW}步骤 3/7: 解压迁移包...${NC}"
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"
tar -xzf "$MIGRATION_ARCHIVE"
echo -e "${GREEN}✓ 解压完成${NC}"

# 创建目标目录
echo ""
echo -e "${YELLOW}步骤 4/7: 部署项目文件...${NC}"
if [ -d "$TARGET_DIR" ]; then
    echo -e "${YELLOW}目标目录已存在: ${TARGET_DIR}${NC}"
    read -p "是否备份现有目录？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        BACKUP_DIR="${TARGET_DIR}_backup_$(date +%Y%m%d_%H%M%S)"
        mv "$TARGET_DIR" "$BACKUP_DIR"
        echo -e "${GREEN}✓ 已备份到: ${BACKUP_DIR}${NC}"
    else
        echo -e "${YELLOW}⚠ 将覆盖现有目录${NC}"
        rm -rf "$TARGET_DIR"
    fi
fi

mkdir -p "$(dirname "$TARGET_DIR")"
mv "$TEMP_DIR/oddsmind" "$TARGET_DIR"
echo -e "${GREEN}✓ 项目文件已部署到: ${TARGET_DIR}${NC}"

# 创建 Python 虚拟环境
echo ""
echo -e "${YELLOW}步骤 5/7: 设置 Python 环境...${NC}"
cd "$TARGET_DIR"

if [ ! -d "venv" ]; then
    echo -e "${BLUE}创建虚拟环境...${NC}"
    VENV_ERROR=$(python3 -m venv venv 2>&1)
    VENV_EXIT_CODE=$?
    
    if [ $VENV_EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}✓ 虚拟环境已创建${NC}"
    else
        echo -e "${RED}✗ 虚拟环境创建失败${NC}"
        if echo "$VENV_ERROR" | grep -q "ensurepip is not available\|python.*-venv"; then
            echo -e "${YELLOW}原因: python3-venv 包未安装${NC}"
            echo -e "${BLUE}尝试自动安装...${NC}"
            
            # 提取 Python 版本号（兼容不同系统）
            PYTHON_VERSION=$(python3 --version 2>&1 | sed -n 's/.*Python \([0-9]\+\.[0-9]\+\).*/\1/p' | head -1)
            if [ -z "$PYTHON_VERSION" ]; then
                PYTHON_VERSION="3"
            fi
            
            if command -v apt-get &> /dev/null; then
                echo -e "${BLUE}执行: sudo apt install -y python${PYTHON_VERSION}-venv${NC}"
                if sudo apt update > /dev/null 2>&1 && sudo apt install -y "python${PYTHON_VERSION}-venv" > /dev/null 2>&1; then
                    echo -e "${GREEN}✓ python3-venv 安装成功，重新创建虚拟环境...${NC}"
                    if python3 -m venv venv 2>/dev/null; then
                        echo -e "${GREEN}✓ 虚拟环境已创建${NC}"
                    else
                        # 尝试通用包名
                        if sudo apt install -y python3-venv > /dev/null 2>&1; then
                            if python3 -m venv venv 2>/dev/null; then
                                echo -e "${GREEN}✓ 虚拟环境已创建${NC}"
                            else
                                echo -e "${RED}✗ 虚拟环境创建仍然失败${NC}"
                                echo -e "${YELLOW}请手动执行: sudo apt install -y python${PYTHON_VERSION}-venv${NC}"
                                exit 1
                            fi
                        else
                            echo -e "${RED}✗ 无法安装 python3-venv${NC}"
                            echo -e "${YELLOW}请手动执行: sudo apt install -y python${PYTHON_VERSION}-venv${NC}"
                            exit 1
                        fi
                    fi
                else
                    # 尝试通用包名
                    if sudo apt install -y python3-venv > /dev/null 2>&1; then
                        echo -e "${GREEN}✓ python3-venv 安装成功，重新创建虚拟环境...${NC}"
                        if python3 -m venv venv 2>/dev/null; then
                            echo -e "${GREEN}✓ 虚拟环境已创建${NC}"
                        else
                            echo -e "${RED}✗ 虚拟环境创建仍然失败${NC}"
                            echo -e "${YELLOW}请手动执行: sudo apt install -y python3-venv${NC}"
                            exit 1
                        fi
                    else
                        echo -e "${RED}✗ 无法安装 python3-venv${NC}"
                        echo -e "${YELLOW}请手动执行以下命令安装:${NC}"
                        echo -e "  sudo apt update"
                        echo -e "  sudo apt install -y python${PYTHON_VERSION}-venv"
                        echo -e "  或: sudo apt install -y python3-venv"
                        exit 1
                    fi
                fi
            else
                echo -e "${RED}✗ 无法自动安装 python3-venv${NC}"
                echo -e "${YELLOW}请根据您的系统手动安装 python3-venv 包${NC}"
                exit 1
            fi
        else
            echo -e "${YELLOW}错误信息: ${VENV_ERROR}${NC}"
            echo -e "${RED}请检查错误信息并手动解决${NC}"
            exit 1
        fi
    fi
else
    echo -e "${YELLOW}虚拟环境已存在，跳过创建${NC}"
fi

echo -e "${BLUE}激活虚拟环境并安装依赖...${NC}"
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
echo -e "${GREEN}✓ 依赖安装完成${NC}"

# 配置环境变量
echo ""
echo -e "${YELLOW}步骤 6/7: 配置环境变量...${NC}"
ENV_FILE="$TARGET_DIR/oddsmind.env"
if [ -f "$ENV_FILE" ]; then
    echo -e "${BLUE}环境配置文件已存在: ${ENV_FILE}${NC}"
    echo -e "${YELLOW}请手动检查并更新以下配置:${NC}"
    echo -e "  - MYSQL_HOST (数据库主机)"
    echo -e "  - MYSQL_USER (数据库用户)"
    echo -e "  - MYSQL_PASSWORD (数据库密码)"
    echo -e "  - MYSQL_DATABASE (数据库名称)"
    echo -e "  - KEYCLOAK_BASE_URL (Keycloak 服务器地址)"
    echo -e "  - APP_BASE_URL (应用基础URL)"
    echo ""
    read -p "是否现在编辑环境配置文件？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} "$ENV_FILE"
    fi
else
    echo -e "${RED}✗ 环境配置文件不存在！${NC}"
    exit 1
fi

# 恢复数据库
echo ""
echo -e "${YELLOW}步骤 7/7: 恢复数据库...${NC}"
BACKUP_DIR="$TARGET_DIR/migration_config/../backups"
if [ -d "$BACKUP_DIR" ] && [ "$(ls -A $BACKUP_DIR/*.sql.gz 2>/dev/null)" ]; then
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/*.sql.gz | head -1)
    echo -e "${BLUE}找到数据库备份: ${LATEST_BACKUP}${NC}"
    
    # 加载环境变量
    source <(grep -E '^MYSQL_' "$ENV_FILE" | sed 's/^/export /')
    
    read -p "是否现在恢复数据库？(y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo -e "${BLUE}正在恢复数据库...${NC}"
        
        # 解压并恢复
        gunzip < "$LATEST_BACKUP" | mysql \
            -h"${MYSQL_HOST}" \
            -P"${MYSQL_PORT:-3306}" \
            -u"${MYSQL_USER}" \
            -p"${MYSQL_PASSWORD}" \
            "${MYSQL_DATABASE}"
        
        if [ $? -eq 0 ]; then
            echo -e "${GREEN}✓ 数据库恢复成功${NC}"
        else
            echo -e "${RED}✗ 数据库恢复失败，请手动恢复${NC}"
        fi
    else
        echo -e "${YELLOW}跳过数据库恢复，请稍后手动恢复${NC}"
    fi
else
    echo -e "${YELLOW}⚠ 未找到数据库备份文件${NC}"
fi

# 清理临时文件
rm -rf "$TEMP_DIR"

# 显示系统配置信息
echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}系统配置信息${NC}"
echo -e "${BLUE}========================================${NC}"
if [ -f "$TARGET_DIR/migration_config/migration_info.txt" ]; then
    cat "$TARGET_DIR/migration_config/migration_info.txt"
fi

# 显示后续步骤
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}部署完成！${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}后续步骤:${NC}"
echo -e "1. 检查并更新 ${ENV_FILE} 中的配置"
echo -e "2. 确保数据库已正确恢复"
echo -e "3. 配置 systemd 服务（如果使用）:"
echo -e "   sudo cp $TARGET_DIR/migration_config/systemd/oddsmind.service /etc/systemd/system/"
echo -e "   sudo systemctl daemon-reload"
echo -e "   sudo systemctl enable oddsmind"
echo -e "   sudo systemctl start oddsmind"
echo -e "4. 配置 Nginx（如果使用）:"
echo -e "   sudo cp $TARGET_DIR/migration_config/nginx/oddsmind /etc/nginx/sites-available/"
echo -e "   sudo ln -s /etc/nginx/sites-available/oddsmind /etc/nginx/sites-enabled/"
echo -e "   sudo nginx -t && sudo systemctl reload nginx"
echo -e "5. 配置 cron 任务（如果需要）:"
echo -e "   crontab -e"
echo -e "   # 参考: $TARGET_DIR/migration_config/crontab_backup.txt"
echo -e "6. 测试应用:"
echo -e "   cd $TARGET_DIR"
echo -e "   source venv/bin/activate"
echo -e "   python app.py"
echo ""

