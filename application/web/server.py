#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Runtime helpers for launching the OddsMind Flask application."""

from __future__ import annotations

from flask import Flask
from waitress import serve

# 不再需要直接导入 initialize_application，改用 auto_initialize
from application.context import get_environment_manager_cached, get_logger_for

_APP_LOGGER = get_logger_for(__name__)


def get_app_logger():
    """Expose the module-level application logger."""
    return _APP_LOGGER


def run_application(app: Flask) -> None:
    """Initialise background services and start the Flask development server."""
    logger = _APP_LOGGER

    env_manager = get_environment_manager_cached()
    app_config = env_manager.get_app_config()

    logger.info("欧核数据分析应用启动中...")
    logger.info("服务器启动配置: %s:%s", app_config['host'], app_config['port'])
    logger.info("运行环境: %s", app_config['environment'])
    logger.info("调试模式: %s", app_config['debug'])
    
    # ✅ 服务启动时立即同步初始化所有核心服务（定时任务、监控等）
    # 确保 systemctl start oddsmind 后所有服务都启动，不依赖首次请求
    # 核心服务（定时任务、监控）同步初始化，耗时操作（数据抓取、分析）后台异步执行
    logger.info("开始初始化核心服务（定时任务、监控等）...")
    try:
        from application.bootstrap import auto_initialize, start_slow_initialization
        auto_initialize()
        # 防御性触发：如果核心初始化路径未触发慢初始化，这里补一次（幂等）
        start_slow_initialization()
        logger.info("✅ 核心服务初始化完成（定时任务调度器、定时数据更新服务、联赛状态监控已启动）")
    except Exception as exc:
        logger.error("❌ 核心服务初始化失败: %s", exc, exc_info=True)
        # 即使初始化失败，也继续启动Web服务，避免服务无法启动

    # 生产环境建议使用 Waitress 提供并发能力与更稳定的连接处理
    # - Flask app.run() 是开发服务器，容易在后台任务较重时导致请求排队/超时/断连
    # - debug=True 时保留原生 run() 方便调试
    if app_config.get("debug"):
        app.run(
            host=app_config["host"],
            port=app_config["port"],
            debug=True,
            # 生产环境/后台服务必须禁用 reloader，否则会出现双进程，导致调度器/线程池被重复启动并引发
            # “cannot schedule new futures after shutdown”等异常，监控任务也会表现为“时灵时不灵”。
            use_reloader=False,
            threaded=True,
        )
        return

    threads = int(app_config.get("threads") or 16)
    logger.info("使用 Waitress 启动 Web 服务: %s:%s (threads=%s)", app_config["host"], app_config["port"], threads)
    serve(app, host=app_config["host"], port=app_config["port"], threads=threads)
