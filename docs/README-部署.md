# OddsMind 部署方案总结

## ✅ 已完成的配置

### 1. Git 仓库配置
- ✅ `.gitignore` - Git 忽略文件配置
- ✅ Git 仓库已初始化
- ✅ 部署脚本 `deploy-git.sh` 已创建

### 2. Docker 配置
- ✅ `Dockerfile` - Docker 镜像构建文件
- ✅ `docker-compose.yml` - Docker Compose 配置（包含 MySQL + Redis + 应用）
- ✅ `.dockerignore` - Docker 构建忽略文件
- ✅ 部署脚本 `deploy-docker.sh` 已创建

### 3. 文档
- ✅ `部署指南.md` - 完整部署文档
- ✅ `快速开始.md` - 快速开始指南

---

## 🚀 立即开始

### 选项 1：使用 Git 仓库（推荐用于开发）

```bash
# 1. 提交当前代码
git add .
git commit -m "Initial commit: OddsMind with security fixes"

# 2. 创建远程仓库（GitHub/GitLab/Gitee）
# 在 GitHub 创建新仓库后执行：
git remote add origin https://github.com/yourusername/oddsmind.git
git branch -M main
git push -u origin main

# 3. 在其他服务器同步
git clone https://github.com/yourusername/oddsmind.git
cd oddsmind
./deploy-git.sh
```

### 选项 2：使用 Docker（推荐用于生产）

```bash
# 1. 配置环境变量（编辑 docker-compose.yml 或创建 .env 文件）
# 设置数据库密码、Redis 配置等

# 2. 一键启动
./deploy-docker.sh

# 3. 查看服务
docker-compose ps
docker-compose logs -f oddsmind
```

---

## 📦 Docker 镜像导出/导入

### 导出镜像

```bash
# 构建镜像
docker build -t oddsmind:latest .

# 导出为文件
docker save -o oddsmind-latest.tar oddsmind:latest

# 压缩（可选）
gzip oddsmind-latest.tar
```

### 在其他服务器导入

```bash
# 导入镜像
docker load -i oddsmind-latest.tar

# 复制 docker-compose.yml 和配置文件
# 启动服务
docker-compose up -d
```

---

## 🔄 日常更新流程

### Git 方式

**开发服务器：**
```bash
git add .
git commit -m "更新描述"
git push origin main
```

**生产服务器：**
```bash
./deploy-git.sh
```

### Docker 方式

```bash
# 方式1：重新构建（推荐）
./deploy-docker.sh

# 方式2：仅重启（如果代码已挂载为卷）
git pull origin main
docker-compose restart oddsmind
```

---

## 📋 文件清单

### 核心配置文件

| 文件 | 说明 |
|------|------|
| `Dockerfile` | Docker 镜像构建配置 |
| `docker-compose.yml` | Docker Compose 服务编排 |
| `.dockerignore` | Docker 构建忽略文件 |
| `.gitignore` | Git 忽略文件 |
| `requirements.txt` | Python 依赖列表 |

### 部署脚本

| 脚本 | 说明 |
|------|------|
| `deploy-git.sh` | Git 方式部署脚本 |
| `deploy-docker.sh` | Docker 方式部署脚本 |

### 文档

| 文档 | 说明 |
|------|------|
| `部署指南.md` | 完整部署文档（详细） |
| `快速开始.md` | 快速开始指南（简洁） |
| `README-部署.md` | 本文档（总结） |

---

## 🎯 推荐使用场景

### Git 仓库方式
- ✅ 开发环境
- ✅ 测试环境
- ✅ 需要频繁更新代码
- ✅ 多开发者协作

### Docker 容器方式
- ✅ 生产环境
- ✅ 多服务器部署
- ✅ 环境一致性要求高
- ✅ 一键部署需求

---

## ⚙️ 环境变量配置

### 必需的环境变量

```bash
# 数据库配置
DB_HOST=mysql          # Docker 中使用服务名，否则使用 IP
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=oddsmind

# Redis 配置
REDIS_HOST=redis        # Docker 中使用服务名，否则使用 IP
REDIS_PORT=6379
REDIS_DB=0

# 应用配置
ODDSMIND_PORT=8889
FLASK_ENV=production

# 微信小程序（如果需要）
WECHAT_APPID=your_appid
WECHAT_APPSECRET=your_secret

# 其他
WEB_ACCESS_PASSWORD=your_web_password
SESSION_SECRET_KEY=your_session_secret
```

### 配置方式

**Git 方式：** 编辑 `oddsmind.env` 文件  
**Docker 方式：** 编辑 `docker-compose.yml` 中的 `environment` 部分，或创建 `.env` 文件

---

## 🔍 验证部署

### 检查服务状态

**Git 方式：**
```bash
systemctl status oddsmind.service
curl http://localhost:8889/health
```

**Docker 方式：**
```bash
docker-compose ps
curl http://localhost:8889/health
```

### 查看日志

**Git 方式：**
```bash
journalctl -u oddsmind.service -f
```

**Docker 方式：**
```bash
docker-compose logs -f oddsmind
```

---

## 📞 需要帮助？

1. 查看 `部署指南.md` 获取详细说明
2. 查看 `快速开始.md` 获取快速参考
3. 检查日志文件排查问题

---

**配置完成！现在可以选择 Git 或 Docker 方式开始部署了！** 🎉

