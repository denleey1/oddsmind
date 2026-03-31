#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Scanning strategy helpers extracted from league_status_monitor."""

from __future__ import annotations

import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from typing import Any, Dict, List

from config.leagues_config import LEAGUES_CONFIG
from config.monitoring_config import MONITORED_LEAGUES, MONITOR_ALL_LEAGUES


def build_league_id_map_impl(monitor) -> Dict[int, str]:
    mapping = {}
    import re

    for code, info in LEAGUES_CONFIG.items():
        match = re.search(r"s(\d+)", info.league_filename)
        if match:
            mapping[int(match.group(1))] = code

    monitor.logger.info("成功构建 League ID 到 Code 的映射, 共 %s 个联赛", len(mapping))
    return mapping


def init_status_cache_from_db_impl(monitor) -> None:
    try:
        matches = monitor.db.execute_query(
            """
            SELECT match_id, match_status
            FROM matches
            WHERE match_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)
              AND match_time <= DATE_ADD(NOW(), INTERVAL 7 DAY)
            """,
            fetch="all",
        )

        if matches:
            for match in matches:
                monitor._status_cache[match["match_id"]] = match["match_status"]
            monitor.logger.info("从数据库加载了 %s 场比赛的状态到缓存", len(matches))
        else:
            monitor.logger.warning("数据库中没有找到需要监控的比赛")
    except Exception as exc:
        monitor.logger.error(f"从数据库加载比赛状态失败: {exc}")


def _get_active_league_ids(monitor) -> set:
    """Return league IDs that have live or near-kickoff matches right now.

    These leagues will be placed at the front of the scanning queue so that
    status changes are detected within one scan cycle instead of being delayed
    behind idle leagues.

    Active criteria:
    - 比赛正在进行 (live)
    - 比赛刚结束但状态可能还未更新 (scheduled 但已过开赛时间)
    - 比赛即将开始 (scheduled，未来30分钟内)
    """
    try:
        rows = monitor.db.execute_query(
            """
            SELECT DISTINCT league_id
            FROM matches
            WHERE match_status = 'live'
               OR (match_status = 'scheduled'
                   AND match_time BETWEEN DATE_SUB(NOW(), INTERVAL 3 HOUR) AND DATE_ADD(NOW(), INTERVAL 30 MINUTE))
            """,
            fetch="all",
        )
        if rows:
            return {r["league_id"] for r in rows}
    except Exception as exc:
        monitor.logger.warning("查询活跃联赛失败，退回默认排序: %s", exc)
    return set()


def get_leagues_to_monitor_impl(monitor) -> List[int]:
    if MONITOR_ALL_LEAGUES:
        try:
            import re

            all_league_ids = []
            for _, info in LEAGUES_CONFIG.items():
                match = re.match(r"s(\d+)", info.league_filename)
                if match:
                    league_id = int(match.group(1))
                    if league_id not in all_league_ids:
                        all_league_ids.append(league_id)

            # ---- Priority sorting: leagues with live / imminent matches first ----
            active_ids = _get_active_league_ids(monitor)
            if active_ids:
                priority = sorted(lid for lid in all_league_ids if lid in active_ids)
                rest = sorted(lid for lid in all_league_ids if lid not in active_ids)
                ordered = priority + rest
                monitor.logger.info(
                    "联赛优先级排序: %s 个活跃联赛排在前面 (共 %s 个联赛)",
                    len(priority),
                    len(ordered),
                )
            else:
                ordered = sorted(all_league_ids)

            monitor.logger.info("从配置获取所有联赛ID: %s 个联赛", len(ordered))
            return ordered
        except Exception as exc:
            monitor.logger.error(f"从配置获取联赛ID失败: {exc}", exc_info=True)
            try:
                leagues = monitor.db.execute_query(
                    """
                    SELECT DISTINCT league_id
                    FROM matches
                    WHERE match_time >= DATE_SUB(NOW(), INTERVAL 1 DAY)
                      AND match_time <= DATE_ADD(NOW(), INTERVAL 7 DAY)
                    ORDER BY league_id
                    """,
                    fetch="all",
                )
                return [league["league_id"] for league in leagues]
            except Exception as db_exc:
                monitor.logger.error(f"获取活跃联赛失败: {db_exc}")
                return []

    return MONITORED_LEAGUES if MONITORED_LEAGUES else []


def update_single_league_impl(monitor, league_id: int) -> int:
    changes_count = 0

    try:
        league_code = monitor._league_id_to_code_map.get(league_id)
        if not league_code:
            monitor.logger.warning("无法为 League ID %s 找到对应的 League Code，跳过爬取", league_id)
            return 0

        monitor.logger.debug("爬取联赛 %s (Code: %s) 的最新数据...", league_id, league_code)
        result = monitor.scraper.scrape(league_codes=[league_code], force_refresh=True)
        if not result.success or not result.data:
            monitor.logger.warning("联赛 %s 数据爬取失败", league_id)
            return 0

        league_result = result.data.get(league_code)
        if not league_result:
            monitor.logger.warning("联赛 %s (%s) 返回数据为空", league_id, league_code)
            return 0

        league_data = league_result.data if hasattr(league_result, "data") else league_result
        if not isinstance(league_data, dict):
            monitor.logger.warning("联赛 %s 数据格式异常: %s", league_id, type(league_data))
            return 0

        matches_data = league_data.get("matches", {})
        current_matches: Dict[int, Any] = {}

        for _, round_matches in matches_data.items():
            if isinstance(round_matches, list):
                for match in round_matches:
                    match_id = match.get("match_id")
                    match_status = match.get("match_status", "unknown")
                    if match_id:
                        current_matches[match_id] = (match_status, match)

        changed_rows: List[tuple[int, str, Dict[str, Any], Any]] = []
        with monitor._lock:
            for match_id, (new_status, match_data) in current_matches.items():
                old_status = monitor._status_cache.get(match_id)
                if old_status != new_status:
                    monitor._status_cache[match_id] = new_status
                    changes_count += 1
                    changed_rows.append((match_id, new_status, match_data, old_status))

            monitor.stats["matches_tracked"] = len(monitor._status_cache)

        # Keep DB writes out of lock scope to avoid long lock holds under IO latency.
        for match_id, new_status, match_data, old_status in changed_rows:
            monitor.logger.info("比赛 %s 状态变化: %s → %s", match_id, old_status, new_status)
            monitor._update_match_status_in_db(match_id, new_status, match_data)

    except Exception as exc:
        monitor.logger.error(f"更新联赛 {league_id} 状态失败: {exc}", exc_info=True)

    return changes_count


def update_league_status_impl(monitor) -> int:
    changes_count = 0

    leagues_to_monitor = monitor._get_leagues_to_monitor()
    if not leagues_to_monitor:
        monitor.logger.warning("没有找到需要监控的联赛")
        return 0

    monitor.stats["leagues_monitored"] = len(leagues_to_monitor)

    # 8线程并发扫描，确保所有联赛(尤其活跃联赛)在一个周期内完成
    executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="league-status")
    future_to_league = {
        executor.submit(monitor._update_single_league, league_id): league_id
        for league_id in leagues_to_monitor
    }
    pending = set(future_to_league.keys())
    completed = 0
    # [修复] 给足时间: 每联赛15s(含可能的超时重试), 8线程并发, 加60s缓冲
    overall_timeout = max(120.0, min(600.0, len(leagues_to_monitor) * 15.0 / 8 + 60))
    deadline = time.monotonic() + overall_timeout

    try:
        while pending:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            done, pending = wait(
                pending,
                timeout=min(5.0, remaining),
                return_when=FIRST_COMPLETED,
            )
            for future in done:
                league_id = future_to_league[future]
                try:
                    league_changes = future.result()
                    changes_count += league_changes
                    completed += 1
                    monitor.logger.debug("联赛 %s 状态变化: %s", league_id, league_changes)
                except Exception as exc:
                    monitor.logger.error(f"更新联赛 {league_id} 状态失败: {exc}")
                    monitor.stats["errors"] += 1

        if pending:
            for future in pending:
                future.cancel()
            monitor.stats["errors"] += len(pending)
            monitor.logger.warning(
                "联赛状态更新超时，已完成 %s/%s 个联赛，取消 %s 个未完成任务",
                completed,
                len(future_to_league),
                len(pending),
            )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    return changes_count


__all__ = [
    "build_league_id_map_impl",
    "get_leagues_to_monitor_impl",
    "init_status_cache_from_db_impl",
    "update_league_status_impl",
    "update_single_league_impl",
]
