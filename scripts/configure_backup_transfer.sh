#!/bin/bash
# -*- coding: utf-8 -*-
"""
配置备份传输目标
支持本地目录、远程服务器（SSH密钥或密码）、S3
"""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$SCRIPT_DIR/backup_config.json"

echo "=========================================="
echo "  OddsMind 备份传输配置助手"
echo "=========================================="
echo ""

# 检查配置文件是否存在
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ 配置文件不存在: $CONFIG_FILE"
    exit 1
fi

# 选择传输类型
echo "请选择传输类型:"
echo "1) 本地目录"
echo "2) 远程服务器 (SSH密钥认证 - 推荐)"
echo "3) 远程服务器 (密码认证)"
echo "4) Amazon S3"
echo ""
read -p "请输入选项 (1-4): " transfer_type_choice

case $transfer_type_choice in
    1)
        # 本地目录
        read -p "请输入本地备份目录路径 (例如: /backup/oddsmind): " local_path
        if [ -z "$local_path" ]; then
            echo "❌ 路径不能为空"
            exit 1
        fi
        
        # 创建目录（如果不存在）
        sudo mkdir -p "$local_path"
        sudo chown -R $USER:$USER "$local_path"
        
        # 更新配置
        python3 << EOF
import json
import sys

config_file = "$CONFIG_FILE"
with open(config_file, 'r', encoding='utf-8') as f:
    config = json.load(f)

config['transfer'] = {
    "enabled": True,
    "type": "local",
    "destination": "$local_path"
}

with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("✅ 配置已更新!")
EOF
        
        echo ""
        echo "✅ 本地目录传输已配置!"
        echo "   目标路径: $local_path"
        ;;
        
    2)
        # 远程服务器 - SSH密钥
        echo ""
        echo "📝 配置远程服务器传输 (SSH密钥认证)"
        echo ""
        read -p "请输入服务器IP地址: " server_ip
        read -p "请输入用户名 (默认: root): " server_user
        server_user=${server_user:-root}
        read -p "请输入目标路径 (例如: /backup/oddsmind): " remote_path
        read -p "请输入SSH端口 (默认: 22): " ssh_port
        ssh_port=${ssh_port:-22}
        
        if [ -z "$server_ip" ] || [ -z "$remote_path" ]; then
            echo "❌ 服务器IP和路径不能为空"
            exit 1
        fi
        
        # 检查SSH密钥是否存在
        if [ ! -f ~/.ssh/id_rsa ] && [ ! -f ~/.ssh/id_ed25519 ]; then
            echo ""
            echo "⚠️  未检测到SSH密钥，是否要生成新的SSH密钥？"
            read -p "输入 y 生成，n 跳过 (y/n): " generate_key
            if [ "$generate_key" = "y" ]; then
                ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -N ""
                echo "✅ SSH密钥已生成"
            fi
        fi
        
        # 尝试复制公钥到远程服务器
        if [ -f ~/.ssh/id_ed25519.pub ] || [ -f ~/.ssh/id_rsa.pub ]; then
            echo ""
            echo "📤 是否要将SSH公钥复制到远程服务器？"
            read -p "输入 y 复制，n 跳过 (y/n): " copy_key
            if [ "$copy_key" = "y" ]; then
                if [ -f ~/.ssh/id_ed25519.pub ]; then
                    ssh-copy-id -p $ssh_port -i ~/.ssh/id_ed25519.pub ${server_user}@${server_ip}
                else
                    ssh-copy-id -p $ssh_port -i ~/.ssh/id_rsa.pub ${server_user}@${server_ip}
                fi
                echo "✅ SSH公钥已复制"
            fi
        fi
        
        # 测试连接
        echo ""
        echo "🔍 测试SSH连接..."
        if ssh -p $ssh_port -o BatchMode=yes -o ConnectTimeout=5 ${server_user}@${server_ip} "echo '连接成功'" 2>/dev/null; then
            echo "✅ SSH连接测试成功!"
        else
            echo "⚠️  SSH连接测试失败，请确保:"
            echo "   1. SSH密钥已正确配置"
            echo "   2. 远程服务器允许SSH密钥认证"
            echo "   3. 网络连接正常"
            read -p "是否继续配置? (y/n): " continue_anyway
            if [ "$continue_anyway" != "y" ]; then
                exit 1
            fi
        fi
        
        # 更新配置
        destination="${server_user}@${server_ip}:${remote_path}"
        python3 << EOF
import json

config_file = "$CONFIG_FILE"
with open(config_file, 'r', encoding='utf-8') as f:
    config = json.load(f)

config['transfer'] = {
    "enabled": True,
    "type": "remote",
    "destination": "$destination",
    "ssh_port": $ssh_port
}

with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("✅ 配置已更新!")
EOF
        
        echo ""
        echo "✅ 远程服务器传输已配置 (SSH密钥认证)!"
        echo "   服务器: ${server_user}@${server_ip}:${ssh_port}"
        echo "   目标路径: $remote_path"
        ;;
        
    3)
        # 远程服务器 - 密码认证
        echo ""
        echo "📝 配置远程服务器传输 (密码认证)"
        echo "⚠️  注意: 密码认证需要安装 sshpass，且安全性较低，建议使用SSH密钥"
        echo ""
        read -p "请输入服务器IP地址: " server_ip
        read -p "请输入用户名 (默认: root): " server_user
        server_user=${server_user:-root}
        read -p "请输入目标路径 (例如: /backup/oddsmind): " remote_path
        read -p "请输入SSH端口 (默认: 22): " ssh_port
        ssh_port=${ssh_port:-22}
        read -sp "请输入密码: " server_password
        echo ""
        
        if [ -z "$server_ip" ] || [ -z "$remote_path" ] || [ -z "$server_password" ]; then
            echo "❌ 服务器IP、路径和密码不能为空"
            exit 1
        fi
        
        # 检查sshpass是否安装
        if ! command -v sshpass &> /dev/null; then
            echo ""
            echo "⚠️  sshpass 未安装，正在安装..."
            sudo apt-get update && sudo apt-get install -y sshpass
            if [ $? -ne 0 ]; then
                echo "❌ sshpass 安装失败，请手动安装: sudo apt-get install sshpass"
                exit 1
            fi
            echo "✅ sshpass 已安装"
        fi
        
        # 测试连接
        echo ""
        echo "🔍 测试SSH连接..."
        if sshpass -p "$server_password" ssh -p $ssh_port -o StrictHostKeyChecking=no ${server_user}@${server_ip} "echo '连接成功'" 2>/dev/null; then
            echo "✅ SSH连接测试成功!"
        else
            echo "⚠️  SSH连接测试失败，请检查:"
            echo "   1. 服务器IP和端口是否正确"
            echo "   2. 用户名和密码是否正确"
            echo "   3. 远程服务器是否允许密码认证"
            read -p "是否继续配置? (y/n): " continue_anyway
            if [ "$continue_anyway" != "y" ]; then
                exit 1
            fi
        fi
        
        # 更新配置（密码存储在环境变量中更安全）
        destination="${server_user}@${server_ip}:${remote_path}"
        python3 << EOF
import json
import os

config_file = "$CONFIG_FILE"
with open(config_file, 'r', encoding='utf-8') as f:
    config = json.load(f)

config['transfer'] = {
    "enabled": True,
    "type": "remote",
    "destination": "$destination",
    "ssh_port": $ssh_port,
    "password": "$server_password"
}

with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("✅ 配置已更新!")
print("⚠️  注意: 密码已保存在配置文件中，建议使用环境变量 BACKUP_REMOTE_PASSWORD")
EOF
        
        # 提示使用环境变量
        echo ""
        echo "💡 安全提示: 建议使用环境变量存储密码:"
        echo "   export BACKUP_REMOTE_PASSWORD='$server_password'"
        echo "   然后从配置文件中删除 password 字段"
        echo ""
        echo "✅ 远程服务器传输已配置 (密码认证)!"
        echo "   服务器: ${server_user}@${server_ip}:${ssh_port}"
        echo "   目标路径: $remote_path"
        ;;
        
    4)
        # S3
        echo ""
        echo "📝 配置Amazon S3传输"
        echo ""
        read -p "请输入S3 bucket名称: " s3_bucket
        read -p "请输入S3路径前缀 (例如: oddsmind/backups，留空则直接存到bucket根目录): " s3_prefix
        read -p "请输入AWS Access Key ID: " aws_access_key
        read -sp "请输入AWS Secret Access Key: " aws_secret_key
        echo ""
        read -p "请输入AWS区域 (默认: us-east-1): " aws_region
        aws_region=${aws_region:-us-east-1}
        
        if [ -z "$s3_bucket" ] || [ -z "$aws_access_key" ] || [ -z "$aws_secret_key" ]; then
            echo "❌ S3 bucket、Access Key和Secret Key不能为空"
            exit 1
        fi
        
        # 检查boto3是否安装
        if ! python3 -c "import boto3" 2>/dev/null; then
            echo ""
            echo "⚠️  boto3 未安装，正在安装..."
            pip3 install boto3
            if [ $? -ne 0 ]; then
                echo "❌ boto3 安装失败，请手动安装: pip3 install boto3"
                exit 1
            fi
            echo "✅ boto3 已安装"
        fi
        
        # 更新配置
        if [ -n "$s3_prefix" ]; then
            s3_destination="s3://${s3_bucket}/${s3_prefix}"
        else
            s3_destination="s3://${s3_bucket}"
        fi
        
        python3 << EOF
import json

config_file = "$CONFIG_FILE"
with open(config_file, 'r', encoding='utf-8') as f:
    config = json.load(f)

config['transfer'] = {
    "enabled": True,
    "type": "s3",
    "destination": "$s3_destination",
    "aws_access_key_id": "$aws_access_key",
    "aws_secret_access_key": "$aws_secret_key",
    "aws_region": "$aws_region"
}

with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

print("✅ 配置已更新!")
EOF
        
        echo ""
        echo "💡 安全提示: 建议使用环境变量存储AWS凭证:"
        echo "   export AWS_ACCESS_KEY_ID='$aws_access_key'"
        echo "   export AWS_SECRET_ACCESS_KEY='$aws_secret_key'"
        echo "   export AWS_DEFAULT_REGION='$aws_region'"
        echo "   然后从配置文件中删除凭证字段"
        echo ""
        echo "✅ S3传输已配置!"
        echo "   目标: $s3_destination"
        ;;
        
    *)
        echo "❌ 无效的选项"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "  配置完成!"
echo "=========================================="
echo ""
echo "📝 下一步:"
echo "   1. 测试备份: python3 $SCRIPT_DIR/auto_backup.py"
echo "   2. 设置定时任务: ./$SCRIPT_DIR/setup_backup_cron.sh"
echo ""

