"""
OddsMind gunicorn 生产级配置

用法:
  gunicorn -c gunicorn.conf.py app:app

优化要点:
- gthread worker: 每个worker启多个线程，数据库IO阻塞时不浪费CPU
- graceful_timeout: 收到 SIGTERM 后给予足够时间完成进行中的请求
- preload_app: 预加载应用，减少内存 + 加速启动
- max_requests: 定期回收worker，防止内存泄漏
"""

import os
import multiprocessing

# ── 绑定地址 ────────────────────────────────────────────────────
bind = os.environ.get("GUNICORN_BIND", "127.0.0.1:8889")

# ── Worker 配置 ─────────────────────────────────────────────────
# gthread: 每个 worker 进程内启多个线程处理请求
# 数据库查询阻塞时，其他线程仍可处理请求
worker_class = "gthread"

# Worker 进程数: CPU核数 (不用 2*CPU+1 因为已有线程)
workers = int(os.environ.get("GUNICORN_WORKERS", min(multiprocessing.cpu_count(), 4)))

# 每个 Worker 的线程数
threads = int(os.environ.get("GUNICORN_THREADS", 4))

# ── 超时配置 ─────────────────────────────────────────────────────
# 请求处理超时 (秒)
timeout = 60

# 优雅关闭超时: 收到 SIGTERM 后等待多久完成进行中的请求
graceful_timeout = 30

# Worker 存活检测超时
keepalive = 5

# ── 内存泄漏防护 ────────────────────────────────────────────────
# 每个 Worker 处理 N 个请求后自动重启
max_requests = 2000

# 随机 jitter 防止所有 Worker 同时重启
max_requests_jitter = 200

# ── 预加载 ──────────────────────────────────────────────────────
# 在 fork 前加载应用，共享内存 + 加速启动
# 注意: Web 模式下 ODDSMIND_DISABLE_BACKGROUND=1，不会启动后台任务
preload_app = True

# ── 日志 ────────────────────────────────────────────────────────
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# ── 安全 ────────────────────────────────────────────────────────
# 限制请求头大小 (防止攻击)
limit_request_line = 8190
limit_request_fields = 100
limit_request_field_size = 8190

# ── 文件描述符 ──────────────────────────────────────────────────
# 通过 systemd LimitNOFILE 设置，这里不重复

# ── 性能指标 ────────────────────────────────────────────────────
# 并发能力 = workers × threads = 4 × 4 = 16 (比 sync 的 4 提升 4 倍)
