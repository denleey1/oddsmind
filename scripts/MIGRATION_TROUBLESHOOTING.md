# 迁移问题排查指南

## 常见问题及解决方案

### 1. python3-venv 未安装错误

**错误信息:**
```
The virtual environment was not created successfully because ensurepip is not available.
On Debian/Ubuntu systems, you need to install the python3-venv package
```

**解决方案:**

```bash
# 方法 1: 安装对应 Python 版本的 venv 包
PYTHON_VERSION=$(python3 --version | sed -n 's/.*Python \([0-9]\+\.[0-9]\+\).*/\1/p')
sudo apt update
sudo apt install -y python${PYTHON_VERSION}-venv

# 方法 2: 如果方法1失败，尝试通用包名
sudo apt install -y python3-venv

# 安装完成后，重新运行部署脚本
```

**快速修复命令（一键执行）:**
```bash
sudo apt update && sudo apt install -y python3.10-venv
# 或者
sudo apt update && sudo apt install -y python3-venv
```

### 2. 迁移包完整性验证失败

**可能原因:**
- 文件在传输过程中损坏
- 校验和文件路径不匹配

**解决方案:**

```bash
# 方法 1: 重新传输文件
# 在源服务器上重新生成迁移包
cd /home/ubuntu/oddsmind
./scripts/migrate_export_all.sh

# 重新传输到新服务器
scp migration_export/oddsmind_migration_*.tar.gz \
    migration_export/oddsmind_migration_*.tar.gz.sha256 \
    user@新服务器IP:/tmp/

# 方法 2: 手动验证
# 在新服务器上
cd /tmp
sha256sum oddsmind_migration_*.tar.gz
# 与校验和文件中的值对比

# 方法 3: 如果确定文件完整，可以跳过验证继续部署
# 在部署脚本提示时选择 'y' 继续
```

### 3. 数据库连接失败

**检查步骤:**
```bash
# 1. 检查环境配置文件
cat /home/ubuntu/oddsmind/oddsmind.env | grep MYSQL

# 2. 测试数据库连接
mysql -h数据库主机 -P端口 -u用户 -p密码 -e "SHOW DATABASES;"

# 3. 检查数据库服务是否运行
sudo systemctl status mysql
# 或
sudo systemctl status mariadb

# 4. 检查防火墙
sudo ufw status
# 如果需要，开放 MySQL 端口
sudo ufw allow 3306
```

### 4. 依赖安装失败

**解决方案:**
```bash
cd /home/ubuntu/oddsmind
source venv/bin/activate

# 升级 pip
pip install --upgrade pip

# 使用国内镜像源（如果网络慢）
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或者逐个安装
pip install Flask[async]==3.0.0
pip install Flask-Cors==4.0.1
# ... 其他依赖
```

### 5. 应用无法启动

**排查步骤:**
```bash
# 1. 检查日志
tail -f /home/ubuntu/oddsmind/logs/oddsmind.log

# 2. 检查端口占用
netstat -tlnp | grep 8889
# 或
lsof -i :8889

# 3. 检查环境变量
cd /home/ubuntu/oddsmind
source venv/bin/activate
python3 -c "from app import app; print('OK')"

# 4. 手动启动测试
python3 app.py
```

### 6. 权限问题

**解决方案:**
```bash
# 确保项目目录权限正确
sudo chown -R ubuntu:ubuntu /home/ubuntu/oddsmind
chmod +x /home/ubuntu/oddsmind/scripts/*.sh

# 确保日志目录可写
mkdir -p /home/ubuntu/oddsmind/logs
chmod 755 /home/ubuntu/oddsmind/logs
```

### 7. systemd 服务无法启动

**排查步骤:**
```bash
# 1. 检查服务文件
sudo cat /etc/systemd/system/oddsmind.service

# 2. 检查服务状态
sudo systemctl status oddsmind

# 3. 查看详细日志
sudo journalctl -u oddsmind -f

# 4. 重新加载配置
sudo systemctl daemon-reload
sudo systemctl restart oddsmind
```

## 快速修复脚本

如果遇到 python3-venv 问题，可以运行以下快速修复：

```bash
#!/bin/bash
# 快速修复 python3-venv 问题

echo "正在安装 python3-venv..."
sudo apt update
sudo apt install -y python3-venv || sudo apt install -y python3.10-venv

if [ $? -eq 0 ]; then
    echo "✓ python3-venv 安装成功"
    echo "现在可以重新运行部署脚本"
else
    echo "✗ 安装失败，请手动检查"
fi
```

## 获取帮助

如果以上方法都无法解决问题，请：

1. 收集错误信息：
   ```bash
   # 保存错误日志
   ./scripts/migrate_deploy_new_server.sh 2>&1 | tee migration_error.log
   ```

2. 检查系统信息：
   ```bash
   python3 --version
   uname -a
   cat /etc/os-release
   ```

3. 查看详细日志：
   ```bash
   tail -100 /home/ubuntu/oddsmind/logs/oddsmind.log
   ```




