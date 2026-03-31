#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OddsMind 后台任务常驻进程（worker）

用途：
- 独立运行 APScheduler / 监控 / 抓取 / 分析等后台任务
- 与 Web API 进程解耦，避免后台任务抢占 CPU 导致接口长尾慢
"""

from __future__ import annotations

import os
import signal
import sys
import threading
import time

from dotenv import load_dotenv


def main() -> None:
    # 加载环境变量
    load_dotenv("oddsmind.env")

    # 标记角色，允许 bootstrap 启动后台服务
    os.environ.setdefault("ODDSMIND_ROLE", "worker")

    from application.bootstrap import initialize_application
    from application.context import get_logger_for, get_runtime

    logger = get_logger_for(__name__)
    logger.info("OddsMind worker 启动中（后台任务进程）...")

    initialize_application()
    runtime = get_runtime()
    logger.info("OddsMind worker 已初始化完成，进入常驻循环")

    # ── Graceful Shutdown ─────────────────────────────────────────
    # 收到 SIGTERM/SIGINT 时优雅关闭，避免数据丢失
    shutdown_event = threading.Event()

    def _handle_shutdown(signum, frame):
        sig_name = signal.Signals(signum).name
        logger.info("收到 %s 信号，开始优雅关闭...", sig_name)
        shutdown_event.set()

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    # ── 定期更新服务状态到 Redis ─────────────────────────────────
    def update_worker_status():
        try:
            from application.services.task_health_tracker import update_service_status

            # 更新调度器状态
            scheduler = runtime.scheduler
            update_service_status('scheduler', {
                'running': scheduler.running if scheduler else False,
                'job_count': len(scheduler.get_jobs()) if scheduler else 0,
            })

            # 更新赔率监控器状态
            monitor = runtime.monitor
            update_service_status('odds_monitor', {
                'running': monitor.is_running if monitor else False,
                'match_count': len(monitor.match_ids) if monitor and monitor.match_ids else 0,
                'interval': monitor.monitor_interval if monitor else 0,
            })

            # 更新联赛状态监控
            league_monitor = runtime.league_status_monitor
            update_service_status('league_status_monitor', {
                'running': league_monitor.is_running if league_monitor else False,
                'stats': league_monitor.get_monitoring_stats() if league_monitor else None,
            })
        except Exception as e:
            logger.warning("更新 Worker 服务状态失败: %s", e)

    # ── 常驻循环 ─────────────────────────────────────────────────
    while not shutdown_event.is_set():
        update_worker_status()
        # 使用 Event.wait 替代 time.sleep，收到信号后可立即退出
        shutdown_event.wait(timeout=60)

    # ── 执行优雅关闭 ─────────────────────────────────────────────
    logger.info("正在关闭 Worker 所有后台服务...")
    try:
        runtime.shutdown()
        logger.info("Worker 优雅关闭完成")
    except Exception as exc:
        logger.error("Worker 关闭过程出错: %s", exc, exc_info=True)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
