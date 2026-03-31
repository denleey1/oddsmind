#!/bin/bash
# -*- coding: utf-8 -*-
# 迁移验证脚本 - 验证迁移是否成功
# 使用方法: ./migrate_verify.sh [项目目录]

set -e  # 遇到错误立即退出

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

PROJECT_DIR="${1:-/home/ubuntu/oddsmind}"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}OddsMind 迁移验证工具${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

ERRORS=0
WARNINGS=0

# 检查项目目录
echo -e "${YELLOW}检查项目目录...${NC}"
if [ ! -d "$PROJECT_DIR" ]; then
    echo -e "${RED}✗ 项目目录不存在: ${PROJECT_DIR}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ 项目目录存在${NC}"

# 检查环境配置文件
echo ""
echo -e "${YELLOW}检查环境配置...${NC}"
ENV_FILE="$PROJECT_DIR/oddsmind.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}✗ 环境配置文件不存在${NC}"
    ((ERRORS++))
else
    echo -e "${GREEN}✓ 环境配置文件存在${NC}"
    
    # 检查关键配置
    source <(grep -E '^[A-Z_]+=' "$ENV_FILE" 2>/dev/null | sed 's/^/export /' || true)
    
    if [ -z "$MYSQL_HOST" ]; then
        echo -e "${YELLOW}⚠ MYSQL_HOST 未设置${NC}"
        ((WARNINGS++))
    else
        echo -e "${GREEN}✓ MYSQL_HOST: ${MYSQL_HOST}${NC}"
    fi
    
    if [ -z "$MYSQL_DATABASE" ]; then
        echo -e "${YELLOW}⚠ MYSQL_DATABASE 未设置${NC}"
        ((WARNINGS++))
    else
        echo -e "${GREEN}✓ MYSQL_DATABASE: ${MYSQL_DATABASE}${NC}"
    fi
fi

# 检查 Python 虚拟环境
echo ""
echo -e "${YELLOW}检查 Python 环境...${NC}"
if [ ! -d "$PROJECT_DIR/venv" ]; then
    echo -e "${RED}✗ Python 虚拟环境不存在${NC}"
    ((ERRORS++))
else
    echo -e "${GREEN}✓ Python 虚拟环境存在${NC}"
    
    # 检查关键依赖
    source "$PROJECT_DIR/venv/bin/activate" 2>/dev/null || true
    if python3 -c "import flask" 2>/dev/null; then
        echo -e "${GREEN}✓ Flask 已安装${NC}"
    else
        echo -e "${RED}✗ Flask 未安装${NC}"
        ((ERRORS++))
    fi
    
    if python3 -c "import pymysql" 2>/dev/null; then
        echo -e "${GREEN}✓ PyMySQL 已安装${NC}"
    else
        echo -e "${RED}✗ PyMySQL 未安装${NC}"
        ((ERRORS++))
    fi
fi

# 检查数据库连接
echo ""
echo -e "${YELLOW}检查数据库连接...${NC}"
if [ -f "$ENV_FILE" ]; then
    source <(grep -E '^MYSQL_' "$ENV_FILE" | sed 's/^/export /')
    
    if command -v mysql &> /dev/null; then
        if mysql -h"${MYSQL_HOST}" -P"${MYSQL_PORT:-3306}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" -e "USE ${MYSQL_DATABASE}; SELECT 1;" &> /dev/null; then
            echo -e "${GREEN}✓ 数据库连接成功${NC}"
            
            # 检查关键表
            TABLES=$(mysql -h"${MYSQL_HOST}" -P"${MYSQL_PORT:-3306}" -u"${MYSQL_USER}" -p"${MYSQL_PASSWORD}" -D"${MYSQL_DATABASE}" -e "SHOW TABLES;" 2>/dev/null | wc -l)
            if [ "$TABLES" -gt 1 ]; then
                echo -e "${GREEN}✓ 数据库表已存在 (${TABLES} 个表)${NC}"
            else
                echo -e "${YELLOW}⚠ 数据库表数量异常${NC}"
                ((WARNINGS++))
            fi
        else
            echo -e "${RED}✗ 数据库连接失败${NC}"
            ((ERRORS++))
        fi
    else
        echo -e "${YELLOW}⚠ MySQL 客户端未安装，跳过数据库连接测试${NC}"
        ((WARNINGS++))
    fi
fi

# 检查关键文件
echo ""
echo -e "${YELLOW}检查关键文件...${NC}"
KEY_FILES=(
    "app.py"
    "requirements.txt"
    "config/settings.py"
)

for file in "${KEY_FILES[@]}"; do
    if [ -f "$PROJECT_DIR/$file" ]; then
        echo -e "${GREEN}✓ $file 存在${NC}"
    else
        echo -e "${RED}✗ $file 不存在${NC}"
        ((ERRORS++))
    fi
done

# 检查目录结构
echo ""
echo -e "${YELLOW}检查目录结构...${NC}"
KEY_DIRS=(
    "application"
    "config"
    "database"
    "static"
    "templates"
)

for dir in "${KEY_DIRS[@]}"; do
    if [ -d "$PROJECT_DIR/$dir" ]; then
        echo -e "${GREEN}✓ $dir/ 目录存在${NC}"
    else
        echo -e "${YELLOW}⚠ $dir/ 目录不存在${NC}"
        ((WARNINGS++))
    fi
done

# 检查 systemd 服务（如果存在）
echo ""
echo -e "${YELLOW}检查系统服务...${NC}"
if systemctl list-unit-files | grep -q "oddsmind.service"; then
    if systemctl is-active --quiet oddsmind.service; then
        echo -e "${GREEN}✓ oddsmind 服务正在运行${NC}"
    else
        echo -e "${YELLOW}⚠ oddsmind 服务未运行${NC}"
        ((WARNINGS++))
    fi
else
    echo -e "${YELLOW}⚠ oddsmind 服务未配置${NC}"
    ((WARNINGS++))
fi

# 测试应用启动（可选）
echo ""
read -p "是否测试应用启动？(y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo -e "${YELLOW}测试应用启动...${NC}"
    cd "$PROJECT_DIR"
    source venv/bin/activate
    
    # 尝试导入主模块
    if timeout 5 python3 -c "from app import app; print('App imported successfully')" 2>&1; then
        echo -e "${GREEN}✓ 应用模块导入成功${NC}"
    else
        echo -e "${RED}✗ 应用模块导入失败${NC}"
        ((ERRORS++))
    fi
fi

# 总结
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}验证完成${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过！迁移成功！${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ 有 ${WARNINGS} 个警告，但无严重错误${NC}"
    exit 0
else
    echo -e "${RED}✗ 发现 ${ERRORS} 个错误，${WARNINGS} 个警告${NC}"
    exit 1
fi




