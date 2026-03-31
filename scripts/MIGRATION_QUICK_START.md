# OddsMind 迁移快速开始指南

## 🚀 快速迁移步骤

### 在源服务器上（当前服务器）

```bash
cd /home/ubuntu/oddsmind

# 1. 执行完整导出（包含数据库备份和项目文件）
./scripts/migrate_export_all.sh

# 2. 查看生成的迁移包
ls -lh migration_export/

# 3. 传输到新服务器（替换为新服务器的IP和用户）
scp migration_export/oddsmind_migration_*.tar.gz \
    migration_export/oddsmind_migration_*.tar.gz.sha256 \
    user@新服务器IP:/tmp/
```

### 在新服务器上

```bash
# 1. 下载迁移脚本（如果还没有）
# 或者直接从迁移包中提取临时使用

# 2. 执行部署（会自动解压、安装依赖、配置环境）
# 注意：需要先解压迁移包获取脚本，或者手动创建部署脚本
cd /tmp
tar -xzf oddsmind_migration_*.tar.gz
chmod +x oddsmind/scripts/migrate_deploy_new_server.sh
./oddsmind/scripts/migrate_deploy_new_server.sh \
    /tmp/oddsmind_migration_*.tar.gz \
    /home/ubuntu/oddsmind

# 3. 编辑环境配置文件
cd /home/ubuntu/oddsmind
nano oddsmind.env
# 更新数据库、Keycloak、应用URL等配置

# 4. 恢复数据库（如果数据库服务器不同）
gunzip < backups/oddsmind_db_backup_*.sql.gz | mysql \
    -h数据库主机 -u用户 -p密码 数据库名

# 5. 验证部署
./scripts/migrate_verify.sh

# 6. 启动应用测试
source venv/bin/activate
python app.py
```

## 📋 迁移检查清单

### 源服务器
- [ ] 执行 `migrate_export_all.sh` 导出所有内容
- [ ] 验证迁移包和校验和文件已生成
- [ ] 传输文件到新服务器

### 新服务器
- [ ] 安装 Python 3.8+、MySQL 客户端等基础软件
- [ ] 执行 `migrate_deploy_new_server.sh` 部署
- [ ] 更新 `oddsmind.env` 配置文件
- [ ] 恢复数据库
- [ ] 运行 `migrate_verify.sh` 验证
- [ ] 测试应用启动
- [ ] 配置 systemd 服务（如需要）
- [ ] 配置 Nginx（如需要）

## ⚠️ 重要提示

1. **数据库配置**: 如果新服务器使用不同的数据库，务必更新 `oddsmind.env` 中的数据库配置
2. **Keycloak 配置**: 如果 Keycloak 服务器地址不同，需要更新 `KEYCLOAK_BASE_URL`
3. **应用URL**: 更新 `APP_BASE_URL` 为新服务器的地址
4. **零停机**: 迁移过程中旧服务器继续运行，不影响当前使用
5. **验证**: 部署后务必运行验证脚本确保一切正常

## 🔧 常见问题快速解决

**问题**: 数据库连接失败
```bash
# 检查数据库配置
cat oddsmind.env | grep MYSQL
# 测试连接
mysql -h主机 -u用户 -p密码 -e "SHOW DATABASES;"
```

**问题**: Python 依赖安装失败
```bash
# 重新安装
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

**问题**: 应用无法启动
```bash
# 查看日志
tail -f logs/oddsmind.log
# 检查端口
netstat -tlnp | grep 8889
```

## 📚 详细文档

更多详细信息请参考：[MIGRATION_GUIDE.md](../MIGRATION_GUIDE.md)

