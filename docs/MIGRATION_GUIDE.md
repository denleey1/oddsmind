# OddsMind 服务器迁移指南

本文档提供将 OddsMind 应用从一台云服务器完整迁移到另一台云服务器的详细步骤，确保迁移过程中不影响当前应用的使用。

## 📋 目录

1. [迁移前准备](#迁移前准备)
2. [迁移步骤](#迁移步骤)
3. [新服务器部署](#新服务器部署)
4. [验证和测试](#验证和测试)
5. [切换和回滚](#切换和回滚)
6. [常见问题](#常见问题)

## 🚀 迁移前准备

### 1. 检查当前服务器状态

```bash
# 检查应用运行状态
systemctl status oddsmind

# 检查数据库连接
mysql -h localhost -u root -p -e "SHOW DATABASES;"

# 检查磁盘空间
df -h

# 检查 Python 环境
python3 --version
pip3 list | grep -i flask
```

### 2. 准备新服务器

确保新服务器满足以下要求：

- **操作系统**: Ubuntu 20.04+ 或类似 Linux 发行版
- **Python**: Python 3.8+
- **MySQL**: MySQL 5.7+ 或 MariaDB 10.3+
- **内存**: 建议至少 2GB RAM
- **磁盘空间**: 建议至少 20GB 可用空间
- **网络**: 能够访问互联网和数据库服务器

### 3. 在新服务器上安装基础软件

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y

# 安装 Python 和 pip
sudo apt install -y python3 python3-pip python3-venv

# 安装 MySQL 客户端（如果需要本地数据库）
sudo apt install -y mysql-client

# 安装其他可能需要的工具
sudo apt install -y git curl wget rsync
```

## 📦 迁移步骤

### 步骤 1: 在源服务器上导出所有内容

在**源服务器**上执行以下操作：

```bash
cd /home/ubuntu/oddsmind

# 1. 给脚本添加执行权限
chmod +x scripts/migrate_*.sh

# 2. 执行完整导出（这会备份数据库并打包所有文件）
./scripts/migrate_export_all.sh
```

导出完成后，会在 `migration_export/` 目录下生成：
- `oddsmind_migration_YYYYMMDD_HHMMSS.tar.gz` - 完整迁移包
- `oddsmind_migration_YYYYMMDD_HHMMSS.tar.gz.sha256` - 校验和文件
- `backups/oddsmind_db_backup_YYYYMMDD_HHMMSS.sql.gz` - 数据库备份

### 步骤 2: 传输文件到新服务器

有多种方式可以将文件传输到新服务器：

#### 方式 A: 使用 SCP（推荐）

```bash
# 在源服务器上执行
scp migration_export/oddsmind_migration_*.tar.gz \
    migration_export/oddsmind_migration_*.tar.gz.sha256 \
    user@new_server_ip:/tmp/
```

#### 方式 B: 使用 rsync

```bash
# 在源服务器上执行
rsync -avz --progress \
    migration_export/oddsmind_migration_*.tar.gz \
    migration_export/oddsmind_migration_*.tar.gz.sha256 \
    user@new_server_ip:/tmp/
```

#### 方式 C: 使用云存储（如 AWS S3, 阿里云 OSS）

```bash
# 上传到云存储
aws s3 cp migration_export/oddsmind_migration_*.tar.gz s3://your-bucket/
aws s3 cp migration_export/oddsmind_migration_*.tar.gz.sha256 s3://your-bucket/

# 在新服务器上下载
aws s3 cp s3://your-bucket/oddsmind_migration_*.tar.gz /tmp/
aws s3 cp s3://your-bucket/oddsmind_migration_*.tar.gz.sha256 /tmp/
```

## 🖥️ 新服务器部署

### 步骤 3: 在新服务器上部署

在新服务器上执行：

```bash
# 1. 将迁移脚本传输到新服务器（如果还没有）
# 或者直接从迁移包中提取

# 2. 解压迁移包（临时）
cd /tmp
tar -xzf oddsmind_migration_*.tar.gz

# 3. 给部署脚本添加执行权限
chmod +x oddsmind/scripts/migrate_deploy_new_server.sh

# 4. 执行部署脚本
./oddsmind/scripts/migrate_deploy_new_server.sh \
    /tmp/oddsmind_migration_*.tar.gz \
    /home/ubuntu/oddsmind
```

部署脚本会自动：
- ✅ 验证迁移包完整性
- ✅ 检查系统要求
- ✅ 解压项目文件
- ✅ 创建 Python 虚拟环境
- ✅ 安装依赖
- ✅ 配置环境变量
- ✅ 恢复数据库（可选）

### 步骤 4: 配置环境变量

编辑环境配置文件：

```bash
cd /home/ubuntu/oddsmind
nano oddsmind.env
```

**重要**: 更新以下配置以匹配新服务器环境：

```bash
# 数据库配置（如果数据库服务器不同）
MYSQL_HOST="新数据库服务器IP或localhost"
MYSQL_USER="数据库用户名"
MYSQL_PASSWORD="数据库密码"
MYSQL_DATABASE="oddsmind"
MYSQL_PORT="3306"

# Keycloak 配置（如果 Keycloak 服务器不同）
KEYCLOAK_BASE_URL="https://新Keycloak服务器IP/auth"

# 应用基础URL（更新为新服务器地址）
APP_BASE_URL="https://新服务器IP"
```

### 步骤 5: 恢复数据库

如果数据库服务器不同，需要在新数据库服务器上恢复数据：

```bash
cd /home/ubuntu/oddsmind

# 方法 1: 使用迁移包中的备份
gunzip < backups/oddsmind_db_backup_*.sql.gz | mysql \
    -h新数据库主机 \
    -u数据库用户 \
    -p数据库密码 \
    数据库名

# 方法 2: 从源服务器直接导出导入（如果网络允许）
# 在源服务器上：
mysqldump -h源数据库主机 -u用户 -p密码 数据库名 | \
    gzip > /tmp/db_backup.sql.gz

# 在新服务器上：
scp user@源服务器:/tmp/db_backup.sql.gz /tmp/
gunzip < /tmp/db_backup.sql.gz | mysql \
    -h新数据库主机 -u用户 -p密码 数据库名
```

### 步骤 6: 配置系统服务

如果使用 systemd 管理服务：

```bash
# 1. 复制服务配置文件（如果迁移包中有）
sudo cp /home/ubuntu/oddsmind/migration_config/systemd/oddsmind.service \
    /etc/systemd/system/oddsmind.service

# 2. 编辑服务文件，更新路径（如果需要）
sudo nano /etc/systemd/system/oddsmind.service

# 3. 重新加载 systemd
sudo systemctl daemon-reload

# 4. 启用并启动服务
sudo systemctl enable oddsmind
sudo systemctl start oddsmind

# 5. 检查服务状态
sudo systemctl status oddsmind
```

示例 systemd 服务文件 (`/etc/systemd/system/oddsmind.service`):

```ini
[Unit]
Description=OddsMind Application
After=network.target mysql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/oddsmind
Environment="PATH=/home/ubuntu/oddsmind/venv/bin"
ExecStart=/home/ubuntu/oddsmind/venv/bin/python /home/ubuntu/oddsmind/app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 步骤 7: 配置 Nginx（如果使用反向代理）

```bash
# 1. 复制 Nginx 配置（如果迁移包中有）
sudo cp /home/ubuntu/oddsmind/migration_config/nginx/oddsmind \
    /etc/nginx/sites-available/oddsmind

# 2. 编辑配置，更新服务器地址
sudo nano /etc/nginx/sites-available/oddsmind

# 3. 创建符号链接
sudo ln -s /etc/nginx/sites-available/oddsmind /etc/nginx/sites-enabled/

# 4. 测试配置
sudo nginx -t

# 5. 重新加载 Nginx
sudo systemctl reload nginx
```

## ✅ 验证和测试

### 步骤 8: 运行验证脚本

```bash
cd /home/ubuntu/oddsmind
chmod +x scripts/migrate_verify.sh
./scripts/migrate_verify.sh
```

验证脚本会检查：
- ✅ 项目目录结构
- ✅ 环境配置文件
- ✅ Python 虚拟环境和依赖
- ✅ 数据库连接
- ✅ 关键文件完整性
- ✅ 系统服务状态

### 步骤 9: 手动测试

```bash
# 1. 测试数据库连接
cd /home/ubuntu/oddsmind
source venv/bin/activate
python3 -c "
from config.settings import settings
from database.connection import get_db_connection
conn = get_db_connection()
print('数据库连接成功！')
conn.close()
"

# 2. 测试应用启动
python3 app.py
# 在另一个终端测试
curl http://localhost:8889/health

# 3. 检查日志
tail -f logs/oddsmind.log
```

## 🔄 切换和回滚

### 零停机迁移策略

为了确保迁移过程中不影响当前应用，建议采用以下策略：

#### 方案 A: 蓝绿部署（推荐）

1. **准备阶段**: 在新服务器上完成所有部署和测试
2. **切换阶段**: 
   - 更新 DNS 或负载均衡器配置，将流量指向新服务器
   - 保持旧服务器运行一段时间作为备份
3. **验证阶段**: 监控新服务器运行状态
4. **清理阶段**: 确认无误后关闭旧服务器

#### 方案 B: 数据库主从复制

如果使用独立的数据库服务器：

1. 设置数据库主从复制
2. 在新服务器上部署应用，连接到从库
3. 切换时，将从库提升为主库
4. 更新应用配置指向新主库

### 回滚计划

如果新服务器出现问题，可以快速回滚：

1. **立即回滚**: 将 DNS/负载均衡器切回旧服务器
2. **数据同步**: 如果新服务器有数据写入，需要同步回旧服务器
3. **问题排查**: 在新服务器上排查问题

## ❓ 常见问题

### Q1: 迁移过程中数据库会有新数据写入怎么办？

**A**: 建议在业务低峰期进行迁移，或者在迁移前暂停数据写入。如果必须保持运行，可以考虑：

1. 使用数据库主从复制
2. 迁移后手动同步增量数据
3. 使用数据库迁移工具（如 `pt-table-sync`）

### Q2: 迁移后应用无法启动？

**A**: 检查以下几点：

```bash
# 1. 检查日志
tail -f /home/ubuntu/oddsmind/logs/oddsmind.log
tail -f /var/log/oddsmind/health_check.log

# 2. 检查环境变量
cat /home/ubuntu/oddsmind/oddsmind.env

# 3. 检查 Python 环境
source /home/ubuntu/oddsmind/venv/bin/activate
pip list

# 4. 检查数据库连接
mysql -h数据库主机 -u用户 -p密码 -e "USE oddsmind; SHOW TABLES;"

# 5. 检查端口占用
netstat -tlnp | grep 8889
```

### Q3: 迁移后静态文件无法访问？

**A**: 检查：

1. 静态文件目录权限：`chmod -R 755 /home/ubuntu/oddsmind/static`
2. Nginx 配置中的静态文件路径
3. Flask 应用中的静态文件配置

### Q4: 迁移后定时任务不运行？

**A**: 检查：

1. cron 任务配置：`crontab -l`
2. APScheduler 配置
3. 系统时间是否正确：`date`

### Q5: 如何验证数据完整性？

**A**: 可以运行以下检查：

```bash
# 1. 检查数据库记录数
mysql -h主机 -u用户 -p密码 -D oddsmind -e "
SELECT 
    'matches' as table_name, COUNT(*) as count FROM matches
UNION ALL
SELECT 'odds', COUNT(*) FROM odds
UNION ALL
SELECT 'leagues', COUNT(*) FROM leagues;
"

# 2. 检查最近的数据
mysql -h主机 -u用户 -p密码 -D oddsmind -e "
SELECT * FROM matches ORDER BY created_at DESC LIMIT 10;
"
```

## 📝 迁移检查清单

迁移前：
- [ ] 备份源服务器数据库
- [ ] 检查源服务器磁盘空间
- [ ] 记录源服务器配置信息
- [ ] 准备新服务器环境

迁移中：
- [ ] 导出所有项目文件
- [ ] 备份数据库
- [ ] 传输文件到新服务器
- [ ] 验证文件完整性
- [ ] 部署项目文件
- [ ] 配置环境变量
- [ ] 恢复数据库
- [ ] 安装依赖

迁移后：
- [ ] 运行验证脚本
- [ ] 测试应用启动
- [ ] 测试数据库连接
- [ ] 测试关键功能
- [ ] 配置系统服务
- [ ] 配置 Nginx（如需要）
- [ ] 配置监控和日志
- [ ] 更新 DNS/负载均衡器

## 📞 获取帮助

如果遇到问题，请检查：

1. 应用日志：`/home/ubuntu/oddsmind/logs/`
2. 系统日志：`journalctl -u oddsmind -f`
3. Nginx 日志：`/var/log/nginx/error.log`

---

**最后更新**: 2025-01-XX
**文档版本**: 1.0




