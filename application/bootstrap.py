#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Application bootstrap utilities with guarded background initialisation."""

from __future__ import annotations

import os
import threading
import time
from functools import wraps
from pathlib import Path
from typing import Callable

try:  # POSIX
    import fcntl  # type: ignore
except ImportError:  # pragma: no cover - Windows fallback
    fcntl = None

try:  # Windows
    import msvcrt  # type: ignore
except ImportError:  # pragma: no cover - POSIX fallback
    msvcrt = None

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from flask import Flask

try:
    from flask_compress import Compress
except ImportError:  # pragma: no cover - optional dependency
    Compress = None

from utils.timezone_utils import now as get_now

from application.context import (
    get_logger_for,
    get_runtime,
    get_secure_configuration,
)
from application.services.analytics import analyze_existing_odds_changes, batch_analyze_fundamental
from application.services.monitoring import (
    check_and_update_completed_matches,
    initialize_daily_monitoring,
    monitor_odds_changes,
    update_match_status_periodically as _update_match_status_periodically,
    update_monitor_frequency,
)
from application.services.task_health_tracker import track_task
from app_constants import CACHE_CONTROL_HEADERS, SESSION_CONFIG
from app_database import execute_query
from services.league_status_monitor import get_league_status_monitor
from services.scheduled_data_updater import get_scheduled_updater
from services.william_odds_history_monitor import scrape_william_history_for_monitored_matches
from services.over_under_odds_monitor import scrape_over_under_for_monitored_matches

_runtime = get_runtime()
_logger = get_logger_for(__name__)
_secure_config = get_secure_configuration()
_init_lock_handle = None


def _background_services_enabled() -> bool:
    """Return whether this process should run schedulers/monitors."""
    role = (os.environ.get("ODDSMIND_ROLE") or "").strip().lower()
    if role == "web":
        return False

    flag = (os.environ.get("ODDSMIND_DISABLE_BACKGROUND") or "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return False

    return True


def _acquire_process_lock(lock_file) -> bool:
    """Acquire a non-blocking process lock for cross-process init guard."""
    if fcntl is not None:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except BlockingIOError:
            return False

    if msvcrt is not None:
        try:
            lock_file.seek(0)
            lock_file.write("0")
            lock_file.flush()
            lock_file.seek(0)
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:
            return False

    _logger.warning("No file lock backend available; continuing without process lock")
    return True


def _release_process_lock(lock_file) -> None:
    """Release process lock acquired by ``_acquire_process_lock``."""
    if fcntl is not None:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        return

    if msvcrt is not None:
        lock_file.seek(0)
        msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)


def _submit_background_task(fn: Callable, *args, **kwargs) -> bool:
    """Submit task into runtime executor while guarding shutdown races.

    Attaches a done-callback so that exceptions raised inside the task
    are always logged rather than silently swallowed.
    """

    def _log_future_exception(future):
        exc = future.exception()
        if exc is not None:
            _logger.error(
                "Background task %s raised an exception: %s",
                getattr(fn, "__name__", repr(fn)),
                exc,
                exc_info=(type(exc), exc, exc.__traceback__),
            )

    try:
        future = _runtime.executor.submit(fn, *args, **kwargs)
        future.add_done_callback(_log_future_exception)
        return True
    except RuntimeError as exc:
        _logger.warning("Skip background task submission: executor unavailable (%s)", exc)
        return False
    except Exception as exc:  # pragma: no cover - defensive
        _logger.error("Submit background task failed: %s", exc, exc_info=True)
        return False


def _run_slow_initialization() -> None:
    """Run deferred heavy tasks in background without blocking startup."""
    try:
        _logger.info("Start deferred background initialization")

        try:
            _logger.info("Initializing daily monitoring")
            init_result = initialize_daily_monitoring()
            if isinstance(init_result, dict) and init_result.get("error"):
                _logger.warning("Daily monitoring init returned error: %s", init_result.get("error"))
            else:
                _logger.info("Daily monitoring initialized")
        except Exception as exc:
            _logger.error("Daily monitoring init failed: %s", exc, exc_info=True)

        try:
            _logger.info("Analyzing existing odds changes")
            analyze_existing_odds_changes()
            _logger.info("Existing odds changes analysis completed")
        except Exception as exc:
            _logger.error("Existing odds analysis failed: %s", exc, exc_info=True)

        _logger.info("Deferred background initialization completed")
    except Exception as exc:  # pragma: no cover - defensive
        _logger.error("Deferred background initialization failed: %s", exc, exc_info=True)


def start_slow_initialization() -> bool:
    """Start deferred initialization once per process."""
    if not _background_services_enabled():
        return False

    if not _runtime.mark_slow_initialization_started():
        _logger.debug("Deferred initialization already started; skip duplicate call")
        return False

    thread = threading.Thread(target=_run_slow_initialization, daemon=True, name="SlowInitThread")
    thread.start()
    _logger.info("Deferred initialization thread started")
    return True


def configure_app(app: Flask) -> None:
    """Apply common Flask configuration options."""
    app.config.update(_secure_config["flask"])
    app.config.update(SESSION_CONFIG)

    if Compress is not None:
        Compress(app)
        app.config["COMPRESS_MIN_SIZE"] = 500
        app.config["COMPRESS_LEVEL"] = 1
        app.config["COMPRESS_DEFER"] = True
    else:
        _logger.warning("flask_compress not installed; response compression disabled")


def register_after_request(app: Flask) -> None:
    """Attach default ``after_request`` security/cache headers."""

    @app.after_request
    def _after_request(response):
        for header, value in CACHE_CONTROL_HEADERS.items():
            response.headers[header] = value
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


def ensure_initialized(func: Callable) -> Callable:
    """Decorator to lazily initialize background services on first request."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not _background_services_enabled():
            if not _runtime.is_initialised:
                _runtime.is_initialised = True
            return func(*args, **kwargs)

        if not _runtime.is_initialised:
            _logger.info("First request detected; triggering initialization")
            try:
                initialize_application()
            except Exception as exc:
                _logger.error("Request-time initialization failed: %s", exc, exc_info=True)

        return func(*args, **kwargs)

    return wrapper


def auto_initialize() -> None:
    """Initialize background services at process start, guarded by file lock."""
    if not _background_services_enabled():
        _logger.info("Web-only mode detected; skip background service initialization")
        _runtime.is_initialised = True
        return

    if _runtime.is_initialised:
        _logger.debug("Background services already initialized")
        return

    lock_file_path = Path(__file__).resolve().parent.parent / ".init_lock"
    lock_file = None
    lock_acquired = False

    global _init_lock_handle

    try:
        lock_file = open(lock_file_path, "a+", encoding="utf-8")
        lock_acquired = _acquire_process_lock(lock_file)

        if lock_acquired:
            _logger.info("Process %d acquired init lock; starting initialization", os.getpid())
            try:
                initialize_application()
                _logger.info("Application initialization completed")
                _init_lock_handle = lock_file
                lock_file = None
            except Exception:
                _release_process_lock(lock_file)
                raise
        else:
            _logger.info("Process %d skipped init; lock already held by another process", os.getpid())
            time.sleep(0.5)
            _runtime.is_initialised = True
    except Exception as exc:
        _logger.error("Auto initialization failed: %s", exc, exc_info=True)
        if not _runtime.is_initialised:
            try:
                initialize_application()
                _logger.info("Application initialization completed without process lock")
            except Exception as fallback_exc:
                _logger.error("Fallback initialization failed: %s", fallback_exc, exc_info=True)
    finally:
        if lock_file is not None:
            try:
                lock_file.close()
            except Exception:
                pass


def initialize_application() -> None:
    """Ensure background services and schedulers are initialized exactly once."""
    if not _background_services_enabled():
        _runtime.is_initialised = True
        return

    def _initialise() -> None:
        _logger.info("Starting fast application initialization")

        init_scheduler()
        updater_started = start_scheduled_data_updater()
        monitor_started = start_league_status_monitoring()

        if updater_started and monitor_started:
            _logger.info("Fast initialization complete; starting deferred tasks")
        else:
            _logger.warning(
                "Fast initialization finished with degraded services (updater=%s, league_monitor=%s)",
                updater_started,
                monitor_started,
            )

        start_slow_initialization()

    _runtime.ensure_initialised(_initialise)


def init_scheduler() -> None:
    """Register and start APScheduler jobs."""
    scheduler = _runtime.scheduler

    scheduler.add_job(
        initialize_daily_monitoring,
        CronTrigger(hour=10, minute=0),
        id="daily_init",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 60,
    )

    scheduler.add_job(
        monitor_odds_changes,
        IntervalTrigger(minutes=5),
        id="odds_monitor",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 30,
    )

    scheduler.add_job(
        update_monitor_frequency,
        IntervalTrigger(minutes=1),
        id="frequency_updater",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 15,
    )

    scheduler.add_job(
        check_and_update_completed_matches,
        IntervalTrigger(minutes=30),
        id="match_completion_check",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 60,
    )

    scheduler.add_job(
        batch_analyze_new_matches,
        IntervalTrigger(hours=1),
        id="batch_fundamental_analysis",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 60,
    )

    # 威廉欧赔历史爬取: 每 30 分钟为待监控比赛爬取完整变化时间线
    scheduler.add_job(
        scrape_william_history_for_monitored_matches,
        IntervalTrigger(minutes=30),
        id="william_odds_history_scraper",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 30,
    )

    # 大小球赔率爬取: 每 30 分钟为待监控比赛重爬开盘/即时大小球赔率
    scheduler.add_job(
        scrape_over_under_for_monitored_matches,
        IntervalTrigger(minutes=30),
        id="over_under_odds_scraper",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 30,
    )

    # 比赛状态更新: 每1小时定期全量同步（之前是3小时，太慢）
    scheduler.add_job(
        update_match_status_periodically,
        IntervalTrigger(hours=1),
        id="match_status_updater",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 60 * 2,
    )

    # 关键时段补充触发 — 覆盖欧洲/亚洲/美洲主赛期
    for job_hour, job_id_suffix in [
        (6, "early_morning"),    # 06:00 亚洲/澳洲赛事收尾
        (9, "morning"),          # 09:00 亚洲白天赛事
        (15, "eu_afternoon"),    # 15:00 欧洲下午赛事开始 (英超等)
        (19, "eu_evening"),      # 19:00 欧洲晚间赛事密集期
        (22, "eu_night"),        # 22:00 欧洲晚间赛事 + 美洲赛事开始
        (1, "am_wrapup"),        # 01:00 美洲赛事 + 欧洲收尾
    ]:
        scheduler.add_job(
            update_match_status_periodically,
            CronTrigger(hour=job_hour, minute=0),
            id=f"match_status_{job_id_suffix}",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=60 * 60 * 2,
        )

    # 启动时立即执行一次
    scheduler.add_job(
        update_match_status_periodically,
        "date",
        run_date=get_now(),
        id="initial_match_status_update",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=60 * 60 * 2,
    )

    if not scheduler.running:
        scheduler.start()
        _logger.info("Scheduler started with %d jobs", len(scheduler.get_jobs()))
    else:
        _logger.info("Scheduler already running; skipped start")


def start_league_status_monitoring() -> bool:
    """Start league status monitor service and return availability."""
    try:
        monitor = _runtime.league_status_monitor
        if monitor is None or not monitor.is_running:
            _logger.info("Starting league status monitor")
            monitor = get_league_status_monitor(
                update_interval=300,
                status_change_callback=on_league_status_change,
                runtime=_runtime,
            )
            _runtime.league_status_monitor = monitor
            monitor.start()
            _logger.info("League status monitor started")
            return True

        _logger.info("League status monitor already running")
        return True
    except Exception as exc:
        _logger.error("Failed to start league status monitor: %s", exc, exc_info=True)
        return False


def start_scheduled_data_updater() -> bool:
    """Start scheduled data updater service and return availability."""
    try:
        updater = _runtime.scheduled_data_updater
        if updater is None or not updater.is_running:
            _logger.info("Starting scheduled data updater")
            updater = get_scheduled_updater(runtime=_runtime)
            updater.start()
            _runtime.scheduled_data_updater = updater
            _logger.info("Scheduled data updater started")
            return True

        _logger.info("Scheduled data updater already running")
        return True
    except Exception as exc:
        _logger.error("Failed to start scheduled data updater: %s", exc, exc_info=True)
        return False


def on_league_status_change(changes_count: int) -> None:
    """Adjust monitor interval after league status changes."""
    try:
        _logger.info("League status changed for %d leagues; refreshing monitor interval", changes_count)
        update_monitor_frequency()
    except Exception as exc:
        _logger.error("Failed handling league status change callback: %s", exc, exc_info=True)


@track_task(
    "batch_fundamental_analysis",
    "Batch fundamental analysis",
    expected_interval_minutes=60,
    max_allowed_delay_minutes=30,
)
def batch_analyze_new_matches() -> None:
    """Discover new scheduled matches and trigger batch fundamental analysis."""
    try:
        sql = """
            SELECT DISTINCT m.match_id
            FROM matches m
            WHERE m.match_time >= NOW()
              AND m.match_time < DATE_ADD(NOW(), INTERVAL 10 DAY)
              AND m.match_status = 'scheduled'
              AND NOT EXISTS (
                  SELECT 1 FROM fundamental_analysis fa
                  WHERE fa.match_id = m.match_id
              )
            LIMIT 50
        """
        matches = execute_query(sql)
        if not matches:
            return

        match_ids = [row["match_id"] for row in matches]
        _logger.info("Found %d new matches for fundamental analysis", len(match_ids))
        _submit_background_task(batch_analyze_fundamental, match_ids)
    except Exception as exc:
        _logger.error("Batch fundamental analysis scheduling failed: %s", exc, exc_info=True)


def update_match_status_periodically() -> None:
    """Wrapper around monitoring service with error boundary for scheduler."""
    try:
        _update_match_status_periodically()
    except Exception as exc:
        _logger.error("Periodic match status update failed: %s", exc, exc_info=True)


__all__ = [
    "initialize_application",
    "ensure_initialized",
    "auto_initialize",
    "start_slow_initialization",
    "configure_app",
    "register_after_request",
]
