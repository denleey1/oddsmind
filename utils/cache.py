#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Layered cache helpers: in-process L1 + Redis L2."""

from __future__ import annotations

import hashlib
import json
import logging
import socket
import threading
import time
from collections import OrderedDict
from functools import wraps
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class LRUMemoryCache:
    """Thread-safe in-memory cache with TTL and LRU eviction."""

    def __init__(self, max_size: int = 10000):
        self._cache: OrderedDict[str, tuple[Any, Optional[float]]] = OrderedDict()
        self._max_size = max_size
        self._lock = threading.RLock()
        self._cache_stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            item = self._cache.get(key)
            if item is None:
                self._cache_stats["misses"] += 1
                return None

            value, expire_time = item
            if expire_time is not None and time.time() >= expire_time:
                del self._cache[key]
                self._cache_stats["misses"] += 1
                return None

            self._cache.move_to_end(key)
            self._cache_stats["hits"] += 1
            return value

    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]

            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)
                self._cache_stats["evictions"] += 1

            expire_time = (time.time() + expire) if expire else None
            self._cache[key] = (value, expire_time)
            self._cache_stats["sets"] += 1
            return True

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        with self._lock:
            size = len(self._cache)
            self._cache.clear()
            return size

    def keys_with_prefix(self, prefix: str) -> list[str]:
        with self._lock:
            return [key for key in self._cache.keys() if key.startswith(prefix)]

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._cache_stats["hits"] + self._cache_stats["misses"]
            hit_rate = (self._cache_stats["hits"] / total * 100.0) if total else 0.0
            return {
                "hits": self._cache_stats["hits"],
                "misses": self._cache_stats["misses"],
                "sets": self._cache_stats["sets"],
                "evictions": self._cache_stats["evictions"],
                "hit_rate": round(hit_rate, 2),
                "size": len(self._cache),
                "max_size": self._max_size,
            }


MemoryCache = LRUMemoryCache


class RedisCache:
    """Redis cache backend with reconnect backoff and warning throttling."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        retry_backoff_seconds: float = 30.0,
        warning_interval_seconds: float = 30.0,
    ):
        self._host = host
        self._port = port
        self._db = db

        self._redis = None
        self._available = False
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "errors": 0,
        }

        self._retry_backoff_seconds = retry_backoff_seconds
        self._warning_interval_seconds = warning_interval_seconds
        self._next_reconnect_at = 0.0
        self._next_warning_at = 0.0

        self._init_redis()

    def _log_warning(self, message: str) -> None:
        now_ts = time.monotonic()
        if now_ts >= self._next_warning_at:
            logger.warning(message)
            self._next_warning_at = now_ts + self._warning_interval_seconds
        else:
            logger.debug(message)

    def _mark_unavailable(self, message: str) -> None:
        self._stats["errors"] += 1
        self._available = False
        self._redis = None
        self._next_reconnect_at = time.monotonic() + self._retry_backoff_seconds
        self._log_warning(message)

    def _init_redis(self) -> None:
        try:
            import redis

            try:
                with socket.create_connection((self._host, self._port), timeout=0.05):
                    pass
            except OSError as exc:
                self._mark_unavailable(f"Redis unavailable, fallback to memory cache: {exc}")
                return

            self._redis = redis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
                retry_on_timeout=False,
            )
            self._redis.ping()
            self._available = True
            self._next_reconnect_at = 0.0
            logger.info("Redis cache enabled")
        except Exception as exc:
            self._mark_unavailable(f"Redis unavailable, fallback to memory cache: {exc}")

    def _ensure_ready(self) -> bool:
        if self._available and self._redis is not None:
            return True

        if time.monotonic() < self._next_reconnect_at:
            return False

        self._init_redis()
        return self._available and self._redis is not None

    def get(self, key: str) -> Optional[Any]:
        if not self._ensure_ready():
            return None

        try:
            value = self._redis.get(key)
            if value is None:
                self._stats["misses"] += 1
                return None

            self._stats["hits"] += 1
            return json.loads(value)
        except Exception as exc:
            self._mark_unavailable(f"Redis get failed: {exc}")
            return None

    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        if not self._ensure_ready():
            return False

        try:
            encoded = json.dumps(value, ensure_ascii=False, default=str)
            if expire:
                self._redis.setex(key, expire, encoded)
            else:
                self._redis.set(key, encoded)
            self._stats["sets"] += 1
            return True
        except Exception as exc:
            self._mark_unavailable(f"Redis set failed: {exc}")
            return False

    def delete(self, key: str) -> bool:
        if not self._ensure_ready():
            return False

        try:
            return bool(self._redis.delete(key))
        except Exception as exc:
            self._mark_unavailable(f"Redis delete failed: {exc}")
            return False

    def delete_by_prefix(self, prefix: str) -> int:
        if not self._ensure_ready():
            return 0

        deleted = 0
        try:
            cursor = 0
            while True:
                cursor, keys = self._redis.scan(cursor=cursor, match=f"{prefix}*", count=200)
                if keys:
                    deleted += int(self._redis.delete(*keys))
                if cursor == 0:
                    break
        except Exception as exc:
            self._mark_unavailable(f"Redis prefix delete failed: {exc}")

        return deleted

    def clear(self) -> bool:
        if not self._ensure_ready():
            return False

        try:
            self._redis.flushdb()
            return True
        except Exception as exc:
            self._mark_unavailable(f"Redis flushdb failed: {exc}")
            return False

    def get_stats(self) -> dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100.0) if total else 0.0
        return {
            "available": self._available,
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "errors": self._stats["errors"],
            "hit_rate": round(hit_rate, 2),
        }


_memory_cache = LRUMemoryCache(max_size=10000)
_redis_cache: Optional[RedisCache] = None
_redis_cache_lock = threading.Lock()

_L1_DEFAULT_TTL = 60


def _get_redis_cache() -> RedisCache:
    global _redis_cache
    if _redis_cache is None:
        with _redis_cache_lock:
            if _redis_cache is None:
                _redis_cache = RedisCache()
    return _redis_cache


def get_cache_key(prefix: str, *args, **kwargs) -> str:
    """Build deterministic cache key from function arguments."""
    key_parts = [prefix]

    if args:
        args_hash = hashlib.md5(json.dumps(args, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:8]
        key_parts.append(args_hash)

    if kwargs:
        kwargs_hash = hashlib.md5(json.dumps(kwargs, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:8]
        key_parts.append(kwargs_hash)

    key = ":".join(key_parts)
    if len(key) > 200:
        key = f"{prefix}:{hashlib.md5(key.encode('utf-8')).hexdigest()}"
    return key


def cached(expire: int = 300, key_prefix: str = "cache"):
    """Decorator implementing L1+L2 read-through caching."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache_key = get_cache_key(key_prefix, func.__name__, *args, **kwargs)

            value = _memory_cache.get(cache_key)
            if value is not None:
                return value

            redis_cache = _get_redis_cache()
            value = redis_cache.get(cache_key)
            if value is not None:
                _memory_cache.set(cache_key, value, min(expire, _L1_DEFAULT_TTL))
                return value

            value = func(*args, **kwargs)
            redis_cache.set(cache_key, value, expire)
            _memory_cache.set(cache_key, value, min(expire, _L1_DEFAULT_TTL))
            return value

        return wrapper

    return decorator


def cache_get(key: str) -> Optional[Any]:
    """Get cached value from L1 first, then L2."""
    value = _memory_cache.get(key)
    if value is not None:
        return value

    value = _get_redis_cache().get(key)
    if value is not None:
        _memory_cache.set(key, value, _L1_DEFAULT_TTL)
    return value


def cache_set(key: str, value: Any, expire: Optional[int] = None) -> bool:
    """Set cached value into both L1 and L2 layers."""
    _get_redis_cache().set(key, value, expire)
    l1_ttl = min(expire, _L1_DEFAULT_TTL) if expire else _L1_DEFAULT_TTL
    return _memory_cache.set(key, value, l1_ttl)


def cache_delete(key: str) -> bool:
    """Delete key from both cache layers."""
    _get_redis_cache().delete(key)
    return _memory_cache.delete(key)


def cache_clear(prefix: Optional[str] = None) -> int:
    """Clear cache entries globally or by key prefix."""
    deleted = 0

    if prefix:
        memory_keys = _memory_cache.keys_with_prefix(prefix)
        for key in memory_keys:
            if _memory_cache.delete(key):
                deleted += 1

        deleted += _get_redis_cache().delete_by_prefix(prefix)
        return deleted

    deleted += _memory_cache.clear()
    _get_redis_cache().clear()
    return deleted


def get_cache_stats() -> dict[str, Any]:
    """Return combined cache metrics for L1 and L2 layers."""
    return {
        "l1_memory": _memory_cache.get_stats(),
        "l2_redis": _get_redis_cache().get_stats(),
    }
