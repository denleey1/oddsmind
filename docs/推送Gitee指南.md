# 推送代码到 Gitee 指南

## 📋 当前配置

**Gitee 仓库地址：** `https://gitee.com/denleey/oddsmind.git`

## 🚀 推送步骤

### 1. 添加远程仓库（已完成）

```bash
git remote add origin https://gitee.com/denleey/oddsmind.git
```

### 2. 检查当前状态

```bash
# 查看未提交的文件
git status

# 查看远程仓库配置
git remote -v
```

### 3. 添加文件到暂存区

```bash
# 添加所有文件
git add .

# 或者选择性添加
git add Dockerfile docker-compose.yml .gitignore
git add deploy-*.sh
git add *.md
```

### 4. 提交代码

```bash
# 首次提交
git commit -m "Initial commit: OddsMind application with Docker and Git configuration"

# 后续提交
git commit -m "描述你的更改内容"
```

### 5. 推送到 Gitee

```bash
# 首次推送（设置上游分支）
git push -u origin main

# 或者如果默认分支是 master
git push -u origin master

# 后续推送
git push origin main
```

## 🔐 认证方式

### 方式一：使用 HTTPS（推荐）

首次推送时会要求输入 Gitee 用户名和密码。

**注意：** Gitee 现在需要使用**个人访问令牌（Personal Access Token）**而不是密码。

1. 在 Gitee 生成令牌：
   - 访问：https://gitee.com/profile/personal_access_tokens
   - 点击"生成新令牌"
   - 设置权限（至少需要 `projects` 权限）
   - 复制令牌

2. 推送时使用令牌作为密码：
   ```bash
   # 用户名：你的 Gitee 用户名
   # 密码：粘贴刚才生成的令牌
   git push -u origin main
   ```

### 方式二：使用 SSH（更安全）

1. 生成 SSH 密钥：
   ```bash
   ssh-keygen -t rsa -b 4096 -C "your_email@example.com"
   # 按回车使用默认路径
   # 设置密码（可选）
   ```

2. 查看公钥：
   ```bash
   cat ~/.ssh/id_rsa.pub
   ```

3. 添加到 Gitee：
   - 访问：https://gitee.com/profile/sshkeys
   - 点击"添加公钥"
   - 粘贴公钥内容
   - 保存

4. 修改远程地址为 SSH：
   ```bash
   git remote set-url origin git@gitee.com:denleey/oddsmind.git
   ```

5. 测试连接：
   ```bash
   ssh -T git@gitee.com
   ```

6. 推送：
   ```bash
   git push -u origin main
   ```

## 📝 完整推送命令（一键执行）

```bash
# 进入项目目录
cd /home/ubuntu/oddsmind

# 添加远程仓库（如果还没添加）
git remote add origin https://gitee.com/denleey/oddsmind.git

# 设置主分支名称
git branch -M main

# 添加所有文件
git add .

# 提交
git commit -m "Initial commit: OddsMind with Docker and security fixes"

# 推送（首次需要输入用户名和令牌）
git push -u origin main
```

## ⚠️ 常见问题

### 问题1：推送时提示认证失败

**解决：**
- 确认使用个人访问令牌而不是密码
- 或配置 SSH 密钥

### 问题2：提示 "remote origin already exists"

**解决：**
```bash
# 删除现有远程仓库
git remote remove origin

# 重新添加
git remote add origin https://gitee.com/denleey/oddsmind.git
```

### 问题3：推送时提示 "rejected"

**解决：**
```bash
# 如果 Gitee 仓库已有内容，需要先拉取
git pull origin main --allow-unrelated-histories

# 解决冲突后再次推送
git push -u origin main
```

### 问题4：大文件推送失败

**解决：**
- 检查 `.gitignore` 是否正确配置
- 使用 Git LFS 处理大文件：
  ```bash
  git lfs install
  git lfs track "*.log"
  git add .gitattributes
  ```

## 🔄 后续更新流程

```bash
# 1. 查看更改
git status

# 2. 添加文件
git add .

# 3. 提交
git commit -m "更新描述"

# 4. 推送
git push origin main
```

## 📦 在其他服务器拉取

```bash
# 克隆仓库
git clone https://gitee.com/denleey/oddsmind.git
cd oddsmind

# 或拉取更新
cd oddsmind
git pull origin main
```

---

**现在可以开始推送了！** 🚀

