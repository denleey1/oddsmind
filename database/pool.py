"""Lazy-initialised database connection pool shared across the application."""
from __future__ import annotations

import time
from threading import Lock
from typing import Optional

import pymysql
from dbutils.pooled_db import PooledDB

from app_environment import get_environment_manager
from core.logger import get_logger

_logger = get_logger(__name__)
_pool_lock = Lock()
_pool: Optional[PooledDB] = None
_POOL_INIT_RETRY_BACKOFF_SECONDS = 30.0
_POOL_INIT_LOG_INTERVAL_SECONDS = 30.0
_pool_init_failure_at = 0.0
_pool_init_error_type = None
_pool_init_error_args: tuple = ()
_pool_init_last_log_at = 0.0


def _build_cached_pool_init_error() -> Exception:
    if _pool_init_error_type is None:
        return RuntimeError("database pool initialisation failed")
    try:
        return _pool_init_error_type(*_pool_init_error_args)
    except Exception:
        return RuntimeError(
            f"database pool initialisation failed: {_pool_init_error_type.__name__}({_pool_init_error_args})"
        )


def _record_pool_init_failure(exc: Exception) -> None:
    global _pool_init_failure_at, _pool_init_error_type, _pool_init_error_args
    _pool_init_failure_at = time.monotonic()
    _pool_init_error_type = exc.__class__
    _pool_init_error_args = getattr(exc, "args", (str(exc),))


def _clear_pool_init_failure() -> None:
    global _pool_init_failure_at, _pool_init_error_type, _pool_init_error_args
    _pool_init_failure_at = 0.0
    _pool_init_error_type = None
    _pool_init_error_args = ()


def _ensure_database_exists(host: str, port: int, user: str, password: str, charset: str, database: str) -> None:
    """Ensure the target database exists before creating a connection pool."""
    tmp_cfg = {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "charset": charset,
        "autocommit": True,
    }

    try:
        with pymysql.connect(**tmp_cfg) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"CREATE DATABASE IF NOT EXISTS `{database}` "
                    "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
    except pymysql.err.OperationalError as exc:
        error_code = exc.args[0] if exc.args else None
        # Some production users can use the schema but are not allowed to CREATE DATABASE.
        # Keep startup compatible by skipping the create check in this case.
        # 1044 = Access denied for user to database
        # 1045 = Access denied for user (wrong credentials for CREATE DB, but app user may still work)
        # 1142 = command denied to user
        # 1227 = Access denied; you need GRANT privilege
        if error_code in {1044, 1045, 1142, 1227}:
            _logger.warning(
                "No privilege to create database '%s' (code=%s); continuing with existing schema",
                database,
                error_code,
            )
            return
        _logger.error("Failed to ensure database '%s' exists: %s", database, exc)
        raise
    except Exception as exc:  # pragma: no cover - defensive guard
        _logger.error("Failed to ensure database '%s' exists: %s", database, exc)
        raise


def _initialise_pool() -> PooledDB:
    global _pool

    env_manager = get_environment_manager()
    app_config = env_manager.config
    db_cfg = app_config.database
    perf_cfg = app_config.performance

    _ensure_database_exists(
        host=db_cfg.host,
        port=db_cfg.port,
        user=db_cfg.user,
        password=db_cfg.password,
        charset=db_cfg.charset,
        database=db_cfg.name,
    )

    _logger.info(
        "Initialising database pool for %s:%s/%s (min=%s, max=%s)",
        db_cfg.host,
        db_cfg.port,
        db_cfg.name,
        db_cfg.pool.min_cached,
        db_cfg.pool.max_connections or perf_cfg.database_pool_size,
    )

    # [性能优化] 使用 init_command 在连接创建时一次性设置参数
    # 避免每次查询都执行 SET 语句
    # - time_zone: 设置为 Asia/Shanghai (+08:00)
    # - max_execution_time: 60秒查询超时（MySQL 5.7.8+）
    init_command = "SET time_zone = '+08:00'"
    
    pool = PooledDB(
        creator=pymysql,
        mincached=db_cfg.pool.min_cached,
        maxcached=db_cfg.pool.max_cached,
        maxconnections=db_cfg.pool.max_connections or perf_cfg.database_pool_size,
        blocking=db_cfg.pool.blocking,
        host=db_cfg.host,
        port=db_cfg.port,
        user=db_cfg.user,
        password=db_cfg.password,
        database=db_cfg.name,
        charset=db_cfg.charset,
        cursorclass=pymysql.cursors.DictCursor,
        ping=1,
        init_command=init_command,  # [性能优化] 连接初始化命令
    )
    return pool


def get_pool() -> PooledDB:
    """Return the shared connection pool, initialising it on first use."""
    global _pool, _pool_init_last_log_at
    if _pool is not None:
        return _pool

    with _pool_lock:
        if _pool is None:
            now = time.monotonic()
            if (
                _pool_init_error_type is not None
                and (now - _pool_init_failure_at) < _POOL_INIT_RETRY_BACKOFF_SECONDS
            ):
                remaining = _POOL_INIT_RETRY_BACKOFF_SECONDS - (now - _pool_init_failure_at)
                if (now - _pool_init_last_log_at) >= _POOL_INIT_LOG_INTERVAL_SECONDS:
                    _logger.warning(
                        "Database pool init backoff active (%.1fs remaining), skipping immediate retry",
                        remaining,
                    )
                    _pool_init_last_log_at = now
                raise _build_cached_pool_init_error()
            try:
                _pool = _initialise_pool()
                _clear_pool_init_failure()
            except Exception as exc:
                _record_pool_init_failure(exc)
                now = time.monotonic()
                if (now - _pool_init_last_log_at) >= _POOL_INIT_LOG_INTERVAL_SECONDS:
                    _logger.warning(
                        "Database pool initialisation failed; next retry in %.0fs: %s",
                        _POOL_INIT_RETRY_BACKOFF_SECONDS,
                        exc,
                    )
                    _pool_init_last_log_at = now
                raise
    return _pool


def get_connection():
    """Borrow a database connection from the shared pool."""
    return get_pool().connection()


def reset_pool() -> None:
    """Reset the shared pool (useful for testing)."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            _pool.close()
            _pool = None
