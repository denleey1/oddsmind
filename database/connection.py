#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""High-level database helpers backed by the shared connection pool."""
from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app_environment import get_environment_manager
from config.database_config import get_create_tables_sql
from core.exceptions import DatabaseError
from core.logger import get_logger
from database.pool import get_connection as borrow_connection

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Schema initialisation
# ---------------------------------------------------------------------------

_SCHEMA_LOCK = Lock()
_SCHEMA_INITIALISED = False


def _quote_identifier(identifier: str) -> str:
    """Quote a SQL identifier defensively while keeping legacy caller behavior."""
    return f"`{identifier.replace('`', '``')}`"


def _ensure_schema_initialised(database_name: str) -> None:
    """Create tables if they do not already exist."""
    global _SCHEMA_INITIALISED
    if _SCHEMA_INITIALISED:
        return

    with _SCHEMA_LOCK:
        if _SCHEMA_INITIALISED:
            return

        schemas = get_create_tables_sql()
        if not schemas:
            _SCHEMA_INITIALISED = True
            return

        connection = borrow_connection()
        cursor = None
        try:
            cursor = connection.cursor()
            for table_name, ddl in schemas.items():
                cursor.execute(ddl)
                logger.debug("Ensured table exists: %s", table_name)
            connection.commit()
        except Exception as exc:  # pragma: no cover - defensive guard
            connection.rollback()
            logger.error("Failed to initialise schema: %s", exc)
            raise DatabaseError(f"Failed to initialise schema: {exc}") from exc
        finally:
            if cursor is not None:
                cursor.close()
            connection.close()

        _SCHEMA_INITIALISED = True


# ---------------------------------------------------------------------------
# Database connection facade
# ---------------------------------------------------------------------------


class DatabaseConnection:
    """Facade around pooled database connections with convenience helpers."""

    def __init__(self, config_override: Optional[Dict[str, Any]] = None) -> None:
        env_manager = get_environment_manager()
        if config_override is not None:
            # Allow legacy dict-style overrides for compatibility
            self.config = config_override
            self._db_name = config_override.get("database") or config_override.get("name")
        else:
            db_cfg = env_manager.config.database
            self.config = {
                "host": db_cfg.host,
                "port": db_cfg.port,
                "user": db_cfg.user,
                "password": db_cfg.password,
                "database": db_cfg.name,
                "charset": db_cfg.charset,
            }
            self._db_name = db_cfg.name

        _ensure_schema_initialised(self._db_name)

    # ------------------------------------------------------------------
    # Context helpers
    # ------------------------------------------------------------------
    @contextmanager
    def connection_scope(self):
        """Borrow a raw connection from the pool."""
        conn = borrow_connection()
        try:
            yield conn
        except DatabaseError:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            logger.error("Database operation failed: %s", exc)
            raise DatabaseError(f"Database operation failed: {exc}") from exc
        finally:
            conn.close()

    @contextmanager
    def transaction(self):
        """Provide a cursor bound to a transaction."""
        with self.connection_scope() as conn:
            cursor = conn.cursor()
            try:
                yield cursor
                conn.commit()
            except Exception as exc:
                conn.rollback()
                if self._is_deadlock_or_lock_timeout(exc):
                    logger.warning("Transaction hit retryable deadlock/lock-timeout: %s", exc)
                else:
                    logger.error("Transaction failed: %s", exc)
                raise DatabaseError(f"Transaction failed: {exc}") from exc
            finally:
                cursor.close()

    # ------------------------------------------------------------------
    # Deadlock / lock-timeout detection helper
    # ------------------------------------------------------------------
    @staticmethod
    def _is_deadlock_or_lock_timeout(exc: BaseException) -> bool:
        """Return True when the exception indicates a MySQL deadlock (1213) or lock-wait timeout (1205)."""
        text = str(exc)
        return "1213" in text or "1205" in text

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def execute_query(
        self,
        query: str,
        params: Optional[Union[Tuple[Any, ...], Dict[str, Any], List[Any]]] = None,
        fetch: Optional[str] = None,
    ) -> Optional[Union[List[Dict[str, Any]], Dict[str, Any], int]]:
        """Execute a single query with automatic deadlock retry.

        Up to 5 attempts are made when MySQL reports a deadlock (1213) or
        lock-wait timeout (1205), using exponential backoff between 0.5 s
        and 8 s.
        """

        @retry(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
            retry=retry_if_exception(self._is_deadlock_or_lock_timeout),
            before_sleep=lambda rs: logger.warning(
                "execute_query deadlock/lock-timeout on attempt %s, retrying...",
                rs.attempt_number,
            ),
        )
        def _run():
            with self.transaction() as cursor:
                cursor.execute(query, params)
                if fetch == "one":
                    return cursor.fetchone()
                if fetch == "all":
                    return cursor.fetchall()
                return cursor.rowcount

        return _run()

    def execute_many(
        self,
        query: str,
        data: Iterable[Union[Tuple[Any, ...], Dict[str, Any]]],
        batch_size: int = 500,  # 减少批量大小，降低死锁概率
    ) -> int:
        payload = list(data)
        if not payload:
            return 0

        # 增加重试次数和等待时间，应对高并发场景
        @retry(
            stop=stop_after_attempt(8),
            wait=wait_exponential(min=1, max=30),
            retry=retry_if_exception(self._is_deadlock_or_lock_timeout),
            before_sleep=lambda rs: logger.warning(
                "execute_many deadlock/lock-timeout on attempt %s, retrying batch...",
                rs.attempt_number,
            ),
        )
        def _execute(batch: List[Union[Tuple[Any, ...], Dict[str, Any]]]) -> int:
            with self.transaction() as cursor:
                cursor.executemany(query, batch)
                return cursor.rowcount if cursor.rowcount != -1 else len(batch)

        affected = 0
        current_batch: List[Union[Tuple[Any, ...], Dict[str, Any]]] = []
        for item in payload:
            current_batch.append(item)
            if len(current_batch) == batch_size:
                affected += _execute(current_batch)
                current_batch = []
        if current_batch:
            affected += _execute(current_batch)
        return affected

    def test_connection(self) -> bool:
        try:
            result = self.execute_query("SELECT 1", fetch="one")
            return bool(result)
        except DatabaseError:
            return False

    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        query = """
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE, COLUMN_DEFAULT, COLUMN_COMMENT
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
        """
        rows = self.execute_query(query, (self._db_name, table_name), fetch="all")
        return rows or []

    def get_table_row_count(self, table_name: str) -> int:
        quoted_name = _quote_identifier(table_name)
        result = self.execute_query(f"SELECT COUNT(*) AS count FROM {quoted_name}", fetch="one")
        return int(result["count"]) if result else 0

    def close(self) -> None:
        """Compatibility shim; pooled connections are managed globally."""
        logger.debug("DatabaseConnection.close() called; pooled connections remain managed globally.")


_connection_instance: Optional[DatabaseConnection] = None
_connection_lock = Lock()


def get_connection() -> DatabaseConnection:
    global _connection_instance
    if _connection_instance is None:
        with _connection_lock:
            if _connection_instance is None:
                _connection_instance = DatabaseConnection()
    return _connection_instance


# Legacy compatibility ------------------------------------------------------

env_manager = get_environment_manager()
DB_CONFIG = env_manager.get_database_config()
