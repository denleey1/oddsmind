#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Monitoring and scheduling helpers extracted from the legacy app module."""

from __future__ import annotations

import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from application.context import get_logger_for, get_runtime
from application.services.task_health_tracker import get_task_tracker, track_task
from app_business import MonitorIntervalCalculator
from app_database import execute_query, get_matches_to_monitor as legacy_get_matches_to_monitor

_logger = get_logger_for(__name__)
_runtime = get_runtime()
_monitor_init_lock = threading.Lock()
_monitor_frequency_lock = threading.Lock()
_match_status_update_lock = threading.Lock()
_db_backoff_lock = threading.Lock()
_db_backoff_until = 0.0
_db_backoff_reason = ""
_DB_BACKOFF_SECONDS = 30.0


def _is_db_connectivity_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return (
        "access denied" in text
        or "operationalerror" in text
        or "can't connect" in text
        or "connection refused" in text
        or "lost connection" in text
    )


def _mark_db_backoff(exc: Exception) -> None:
    global _db_backoff_until, _db_backoff_reason
    with _db_backoff_lock:
        _db_backoff_until = time.monotonic() + _DB_BACKOFF_SECONDS
        _db_backoff_reason = str(exc)


def _current_db_backoff_message() -> Optional[str]:
    with _db_backoff_lock:
        remaining = _db_backoff_until - time.monotonic()
        if remaining <= 0:
            return None
        return f"database backoff active for {remaining:.1f}s: {_db_backoff_reason}"


def get_matches_to_monitor() -> List[Dict[str, Any]]:
    """Expose the legacy helper for compatibility."""
    return legacy_get_matches_to_monitor()


def get_monitor_interval(match_time: datetime) -> Optional[int]:
    if isinstance(match_time, str):
        match_time = datetime.fromisoformat(match_time)

    time_to_match = (match_time - datetime.now()).total_seconds() / 60
    if time_to_match <= 0:
        return None

    return MonitorIntervalCalculator.get_monitor_interval(match_time)


@track_task('daily_init', 'daily_monitor_init', expected_interval_minutes=24 * 60, max_allowed_delay_minutes=60)
def initialize_daily_monitoring() -> Dict[str, Any]:
    acquired = _monitor_init_lock.acquire(blocking=False)
    if not acquired:
        _logger.warning("Daily monitoring init already running, skipping duplicate trigger")
        return {'skipped': True}

    try:
        backoff_error = _current_db_backoff_message()
        if backoff_error:
            _logger.warning("Skipping daily monitoring init: %s", backoff_error)
            return {'error': backoff_error}

        summary = _runtime.monitoring_coordinator.initialize_monitoring()
        _runtime.monitoring_coordinator.verify_odds_sync()
        _logger.info("Daily monitoring initialisation completed: %s", summary)
        return summary
    except Exception as exc:  # pragma: no cover - compatibility
        if _is_db_connectivity_error(exc):
            _mark_db_backoff(exc)
        _logger.error("Initialise monitoring failed: %s", exc, exc_info=True)
        return {'error': str(exc)}
    finally:
        if acquired:
            _monitor_init_lock.release()


@track_task('odds_monitor', 'odds_change_monitor', expected_interval_minutes=5, max_allowed_delay_minutes=10)
def monitor_odds_changes() -> Dict[str, Any]:
    backoff_error = _current_db_backoff_message()
    if backoff_error:
        _logger.warning("Skipping odds monitor run: %s", backoff_error)
        return {'error': backoff_error}

    try:
        summary = _runtime.monitoring_coordinator.monitor_odds_changes()
        _logger.debug("Odds change monitor summary: %s", summary)

        try:
            from utils.cache_invalidation import invalidate_all_matches_cache

            updated_count = summary.get('matches_updated', summary.get('processed', 0))
            if updated_count > 0:
                invalidate_all_matches_cache()
                _logger.debug("Invalidated match cache after odds updates")
        except Exception as cache_exc:
            _logger.warning("Cache invalidation after odds monitor failed: %s", cache_exc)

        return summary
    except Exception as exc:  # pragma: no cover
        if _is_db_connectivity_error(exc):
            _mark_db_backoff(exc)
        _logger.error("Monitor odds changes failed: %s", exc, exc_info=True)
        return {'error': str(exc)}


@track_task('frequency_updater', 'monitor_frequency_updater', expected_interval_minutes=1, max_allowed_delay_minutes=5)
def update_monitor_frequency() -> None:
    acquired = _monitor_frequency_lock.acquire(blocking=False)
    if not acquired:
        _logger.warning("Monitor frequency update already running, skipping duplicate trigger")
        return

    try:
        backoff_error = _current_db_backoff_message()
        if backoff_error:
            _logger.warning("Skipping monitor frequency update: %s", backoff_error)
            return

        monitor = _runtime.monitor
        monitored_match_ids = tuple(dict.fromkeys(monitor.match_ids or [])) if monitor else ()

        if not monitor or not monitor.is_running or not monitored_match_ids:
            _logger.info("Monitor not running or empty, attempting re-initialisation")
            try:
                summary = _runtime.monitoring_coordinator.initialize_monitoring(force=True)
                _logger.info("Monitor re-initialised: %s", summary)
            except Exception as init_exc:
                if _is_db_connectivity_error(init_exc):
                    _mark_db_backoff(init_exc)
                _logger.error("Monitor re-initialisation failed: %s", init_exc, exc_info=True)
            return

        current_matches = get_matches_to_monitor()
        current_match_ids = {m['match_id'] for m in current_matches}
        monitored_match_ids_set = set(monitored_match_ids)

        new_matches = current_match_ids - monitored_match_ids_set
        removed_matches = monitored_match_ids_set - current_match_ids

        if new_matches or removed_matches:
            _logger.info(
                "Monitor target set changed, reinitialising (new=%s removed=%s)",
                len(new_matches),
                len(removed_matches),
            )
            try:
                summary = _runtime.monitoring_coordinator.initialize_monitoring(force=True)
                _logger.info("Monitor target refresh completed: %s", summary)
            except Exception as refresh_exc:
                if _is_db_connectivity_error(refresh_exc):
                    _mark_db_backoff(refresh_exc)
                _logger.error("Monitor target refresh failed: %s", refresh_exc, exc_info=True)
            return

        result: List[Dict[str, Any]] = []
        chunk_size = 200
        for offset in range(0, len(monitored_match_ids), chunk_size):
            chunk = monitored_match_ids[offset : offset + chunk_size]
            placeholders = ','.join(['%s'] * len(chunk))
            sql = f"""
                SELECT match_id, match_time, match_status
                FROM matches
                WHERE match_id IN ({placeholders})
            """
            result.extend(execute_query(sql, tuple(chunk)))

        if not result:
            return

        live_matches = [m for m in result if m.get('match_status') == 'live']
        finished_matches = [m for m in result if m.get('match_status') == 'finished']
        scheduled_matches = [m for m in result if m.get('match_status') == 'scheduled']

        if live_matches:
            new_interval = 3 * 60
        elif finished_matches:
            new_interval = 5 * 60
        elif scheduled_matches:
            earliest_time = min(m['match_time'] for m in scheduled_matches)
            new_interval = get_monitor_interval(earliest_time)
        else:
            new_interval = 30 * 60

        if new_interval and new_interval != monitor.monitor_interval:
            monitor.update_monitor_interval(new_interval)
            _logger.info("Updated monitor interval to %s minutes", new_interval // 60)
    except Exception as exc:  # pragma: no cover
        if _is_db_connectivity_error(exc):
            _mark_db_backoff(exc)
        _logger.error("Update monitor frequency failed: %s", exc, exc_info=True)
    finally:
        if acquired:
            _monitor_frequency_lock.release()


@track_task('match_completion_check', 'completed_match_processing', expected_interval_minutes=30, max_allowed_delay_minutes=15)
def check_and_update_completed_matches() -> Dict[str, Any]:
    backoff_error = _current_db_backoff_message()
    if backoff_error:
        _logger.warning("Skipping completed-match processing: %s", backoff_error)
        return {'error': backoff_error}

    try:
        summary = _runtime.monitoring_coordinator.process_completed_matches()
        _logger.info("Completed-match processing summary: %s", summary)
        return summary
    except Exception as exc:  # pragma: no cover
        if _is_db_connectivity_error(exc):
            _mark_db_backoff(exc)
            # 重置 coordinator 以便下次重试时重新创建连接
            try:
                _runtime._monitoring_coordinator = None
            except Exception:
                pass
        _logger.error("Process completed matches failed: %s", exc, exc_info=True)
        return {'error': str(exc)}


def update_finished_matches_odds() -> int:
    result = _runtime.monitoring_coordinator.process_completed_matches()
    return result.get('final_odds_saved', 0)


@track_task('match_status_updater', 'periodic_match_status_update', expected_interval_minutes=60, max_allowed_delay_minutes=30)
def update_match_status_periodically() -> Dict[str, Any]:
    acquired = _match_status_update_lock.acquire(blocking=False)
    if not acquired:
        _logger.warning("Match-status periodic update already running, skipping duplicate trigger")
        return {'skipped': True}

    try:
        backoff_error = _current_db_backoff_message()
        if backoff_error:
            _logger.warning("Skipping match-status periodic update: %s", backoff_error)
            return {'error': backoff_error}

        result = _runtime.monitoring_coordinator.update_match_statuses()
        _logger.info("Match status updater periodic result: %s", result)
        return result
    except Exception as exc:  # pragma: no cover
        if _is_db_connectivity_error(exc):
            _mark_db_backoff(exc)
            # 重置 coordinator 以便下次重试时重新创建连接
            try:
                _runtime._monitoring_coordinator = None
            except Exception:
                pass
        _logger.error("Periodic match status update failed: %s", exc, exc_info=True)
        return {'error': str(exc)}
    finally:
        if acquired:
            _match_status_update_lock.release()


__all__ = [
    'get_matches_to_monitor',
    'get_monitor_interval',
    'initialize_daily_monitoring',
    'monitor_odds_changes',
    'update_monitor_frequency',
    'check_and_update_completed_matches',
    'update_finished_matches_odds',
    'update_match_status_periodically',
    'get_task_tracker',
]
