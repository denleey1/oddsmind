# OddsMind Dockerfile
# 多阶段构建，减小镜像体积

FROM python:3.10-slim as builder

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir --user -r requirements.txt

# 生产阶段
FROM python:3.10-slim

# 设置工作目录
WORKDIR /app

# 安装运行时依赖
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python 包
COPY --from=builder /root/.local /root/.local

# 确保 Python 可以找到本地安装的包
ENV PATH=/root/.local/bin:$PATH

# 复制应用代码
COPY . .

# 创建必要的目录
RUN mkdir -p logs data backups

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV FLASK_APP=app.py

# 暴露端口（根据实际配置修改）
EXPOSE 8889

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8889/health || exit 1

# 启动命令
CMD ["python", "app.py"]


