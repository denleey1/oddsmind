#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Redis operations extracted from task_health_tracker."""

from __future__ import annotations

import json
import socket
import time
from datetime import datetime
from threading import Lock
from typing import Any, Dict, List, Optional

_REDIS_RETRY_BACKOFF_SECONDS = 30.0
_REDIS_WARNING_INTERVAL_SECONDS = 30.0
_redis_state_lock = Lock()
_redis_retry_after = 0.0
_redis_last_warning_at = 0.0


def _log_redis_warning(logger, message: str) -> None:
    global _redis_last_warning_at
    now = time.monotonic()
    with _redis_state_lock:
        if now - _redis_last_warning_at >= _REDIS_WARNING_INTERVAL_SECONDS:
            logger.warning(message)
            _redis_last_warning_at = now
        else:
            logger.debug(message)


def _mark_redis_unavailable(logger, message: str) -> None:
    global _redis_retry_after
    with _redis_state_lock:
        _redis_retry_after = time.monotonic() + _REDIS_RETRY_BACKOFF_SECONDS
    _log_redis_warning(logger, message)


def get_redis_client(logger):
    """Get Redis client with fast-fail connection checks and retry backoff."""
    global _redis_retry_after
    with _redis_state_lock:
        if time.monotonic() < _redis_retry_after:
            return None

    try:
        import redis

        try:
            with socket.create_connection(("localhost", 6379), timeout=0.05):
                pass
        except OSError as exc:
            _mark_redis_unavailable(logger, f"鏃犳硶杩炴帴 Redis: {exc}")
            return None

        client = redis.Redis(
            host="localhost",
            port=6379,
            db=0,
            decode_responses=True,
            socket_connect_timeout=0.5,
            socket_timeout=0.5,
            retry_on_timeout=False,
        )
        client.ping()
        with _redis_state_lock:
            _redis_retry_after = 0.0
        return client
    except Exception as exc:
        _mark_redis_unavailable(logger, f"鏃犳硶杩炴帴 Redis: {exc}")
        return None


def update_service_status_impl(
    redis_client,
    service_name: str,
    status: Dict[str, Any],
    service_key_prefix: str,
    now_func,
    logger,
) -> None:
    if not redis_client:
        return
    try:
        key = f"{service_key_prefix}:{service_name}"
        payload = status.copy()
        payload["updated_at"] = now_func().isoformat()
        redis_client.setex(key, 300, json.dumps(payload))
    except Exception as exc:
        _log_redis_warning(logger, f"鏇存柊鏈嶅姟鐘舵€佸け璐? {exc}")


def get_service_status_impl(redis_client, service_name: str, service_key_prefix: str, logger) -> Optional[Dict[str, Any]]:
    if not redis_client:
        return None
    try:
        key = f"{service_key_prefix}:{service_name}"
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as exc:
        _log_redis_warning(logger, f"鑾峰彇鏈嶅姟鐘舵€佸け璐? {exc}")
    return None


def save_task_to_redis_impl(redis_client, task, key_prefix: str, ttl: int, logger) -> None:
    if not redis_client:
        return
    try:
        key = f"{key_prefix}{task.task_id}"
        data = {
            "task_id": task.task_id,
            "task_name": task.task_name,
            "last_run_time": task.last_run_time.isoformat() if task.last_run_time else None,
            "last_success_time": task.last_success_time.isoformat() if task.last_success_time else None,
            "last_error_time": task.last_error_time.isoformat() if task.last_error_time else None,
            "last_error_message": task.last_error_message,
            "last_duration_seconds": task.last_duration_seconds,
            "run_count": task.run_count,
            "success_count": task.success_count,
            "error_count": task.error_count,
            "expected_interval_minutes": task.expected_interval_minutes,
            "max_allowed_delay_minutes": task.max_allowed_delay_minutes,
            "is_running": task.is_running,
        }
        redis_client.setex(key, ttl, json.dumps(data))
    except Exception as exc:
        _log_redis_warning(logger, f"淇濆瓨浠诲姟鐘舵€佸埌 Redis 澶辫触: {exc}")


def load_task_from_redis_impl(redis_client, task_id: str, key_prefix: str, task_cls, logger):
    if not redis_client:
        return None
    try:
        key = f"{key_prefix}{task_id}"
        data = redis_client.get(key)
        if not data:
            return None

        payload = json.loads(data)
        task = task_cls(
            task_id=payload["task_id"],
            task_name=payload["task_name"],
            expected_interval_minutes=payload.get("expected_interval_minutes", 60),
            max_allowed_delay_minutes=payload.get("max_allowed_delay_minutes", 30),
        )
        task.last_run_time = datetime.fromisoformat(payload["last_run_time"]) if payload.get("last_run_time") else None
        task.last_success_time = (
            datetime.fromisoformat(payload["last_success_time"]) if payload.get("last_success_time") else None
        )
        task.last_error_time = datetime.fromisoformat(payload["last_error_time"]) if payload.get("last_error_time") else None
        task.last_error_message = payload.get("last_error_message")
        task.last_duration_seconds = payload.get("last_duration_seconds")
        task.run_count = payload.get("run_count", 0)
        task.success_count = payload.get("success_count", 0)
        task.error_count = payload.get("error_count", 0)
        task.is_running = payload.get("is_running", False)
        return task
    except Exception as exc:
        _log_redis_warning(logger, f"浠?Redis 鍔犺浇浠诲姟鐘舵€佸け璐? {exc}")
        return None


def get_all_task_ids_from_redis_impl(redis_client, key_prefix: str, logger) -> List[str]:
    if not redis_client:
        return []
    try:
        keys = redis_client.keys(f"{key_prefix}*")
        return [key.replace(key_prefix, "") for key in keys]
    except Exception as exc:
        _log_redis_warning(logger, f"浠?Redis 鑾峰彇浠诲姟鍒楄〃澶辫触: {exc}")
        return []


__all__ = [
    "get_all_task_ids_from_redis_impl",
    "get_redis_client",
    "get_service_status_impl",
    "load_task_from_redis_impl",
    "save_task_to_redis_impl",
    "update_service_status_impl",
]
