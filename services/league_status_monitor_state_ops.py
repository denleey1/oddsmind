#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""State transition/logging helpers extracted from league_status_monitor."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict


def get_status_distribution_impl(monitor) -> Dict[str, int]:
    with monitor._lock:
        distribution: Dict[str, int] = {}
        for status in monitor._status_cache.values():
            distribution[status] = distribution.get(status, 0) + 1
        return distribution


def get_monitoring_stats_impl(monitor) -> Dict[str, Any]:
    distribution = get_status_distribution_impl(monitor)
    return {
        **monitor.stats,
        "last_update": monitor._last_update.isoformat() if monitor._last_update else None,
        "status_distribution": distribution,
        "is_running": monitor.is_running,
        "cache_size": len(monitor._status_cache),
    }


def update_match_status_in_db_impl(monitor, match_id: int, new_status: str, match_data: Dict[str, Any]) -> None:
    try:
        update_sql = """
            UPDATE matches
            SET match_status = %s,
                match_time = %s,
                full_score = %s,
                half_score = %s,
                home_score = %s,
                away_score = %s,
                updated_at = NOW()
            WHERE match_id = %s
        """

        monitor.db.execute_query(
            update_sql,
            (
                new_status,
                match_data.get("match_time"),
                match_data.get("full_score", ""),
                match_data.get("half_score", ""),
                match_data.get("home_score"),
                match_data.get("away_score"),
                match_id,
            ),
        )
    except Exception as exc:
        monitor.logger.error(f"更新数据库比赛 {match_id} 状态失败: {exc}")


def notify_odds_monitor_impl(monitor, changes_count: int) -> None:
    try:
        monitor.logger.info("检测到 %s 个比赛状态变化，通知赔率监控系统", changes_count)

        if monitor.status_change_callback:
            try:
                monitor.status_change_callback(changes_count)
                monitor.logger.debug("已成功调用状态变化回调函数")
            except Exception as callback_error:
                monitor.logger.error(f"执行状态变化回调失败: {callback_error}")
        else:
            monitor.logger.debug("未设置状态变化回调函数")
    except Exception as exc:
        monitor.logger.error(f"通知赔率监控系统失败: {exc}")


def monitor_loop_impl(monitor) -> None:
    monitor.logger.info("联赛状态监控循环已启动 (自适应模式)")

    # 上次全量扫描时间戳
    last_full_scan = 0.0
    FAST_INTERVAL = 60       # 活跃联赛扫描间隔: 60秒
    FULL_SCAN_INTERVAL = 300  # 全量扫描间隔: 5分钟

    while monitor.is_running:
        loop_start = time.time()
        try:
            # ---- 自适应扫描策略 ----
            # 1. 始终优先快速扫描活跃联赛 (有live/即将开始的比赛)
            # 2. 每 FULL_SCAN_INTERVAL 做一次全量扫描
            since_full = loop_start - last_full_scan
            do_full_scan = since_full >= FULL_SCAN_INTERVAL

            if do_full_scan:
                monitor.logger.debug("开始全量联赛状态更新...")
                changes = monitor._update_league_status()
                last_full_scan = time.time()
            else:
                monitor.logger.debug("快速扫描活跃联赛...")
                changes = _fast_scan_active_leagues(monitor)

            monitor.stats["total_updates"] += 1
            monitor.stats["status_changes"] += changes
            monitor._last_update = datetime.now()

            elapsed = time.time() - loop_start
            scan_type = "全量" if do_full_scan else "快速"
            monitor.logger.info(
                "联赛状态[%s]更新完成 - 耗时: %.2fs, 变化: %s, 监控比赛: %s",
                scan_type,
                elapsed,
                changes,
                len(monitor._status_cache),
            )

            if changes > 0:
                monitor._notify_odds_monitor(changes)

        except Exception as exc:
            monitor.logger.error(f"联赛状态监控出错: {exc}", exc_info=True)
            monitor.stats["errors"] += 1

        wait_event = getattr(monitor, "_wake_event", None)
        if wait_event is not None:
            wait_event.wait(timeout=FAST_INTERVAL)
            wait_event.clear()
        else:
            time.sleep(FAST_INTERVAL)


def _fast_scan_active_leagues(monitor) -> int:
    """只扫描有 live 或即将开赛的比赛的联赛，实现快速状态检测。"""
    from .league_status_monitor_scan_ops import _get_active_league_ids

    active_ids = _get_active_league_ids(monitor)
    if not active_ids:
        return 0

    changes = 0
    for league_id in active_ids:
        try:
            league_changes = monitor._update_single_league(league_id)
            changes += league_changes
        except Exception as exc:
            monitor.logger.error("快速扫描联赛 %s 失败: %s", league_id, exc)
            monitor.stats["errors"] += 1

    return changes


__all__ = [
    "get_monitoring_stats_impl",
    "get_status_distribution_impl",
    "monitor_loop_impl",
    "notify_odds_monitor_impl",
    "update_match_status_in_db_impl",
]
