#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Rate limiting and anti-replay utilities.

Priority order:
1. Redis backend (preferred in production)
2. In-memory fallback (best effort)
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import time
from functools import wraps
from typing import Optional

from flask import jsonify, request

logger = logging.getLogger(__name__)

# Lazy Redis initialization to avoid side effects during module import.
_redis_client = None
_redis_available: Optional[bool] = None
_redis_init_lock = threading.Lock()

# In-memory fallback caches.
_rate_limit_cache = {}
_code_usage_cache = {}
_cache_lock = threading.RLock()

_last_cleanup = time.time()
CLEANUP_INTERVAL = 600  # 10 minutes
WECHAT_CODE_TTL_SECONDS = 300  # 5 minutes


def _ensure_redis_initialized() -> None:
    """Initialize Redis client once on first use."""
    global _redis_client, _redis_available
    if _redis_available is not None:
        return

    with _redis_init_lock:
        if _redis_available is not None:
            return

        try:
            import redis

            redis_host = os.environ.get("REDIS_HOST", "localhost")
            redis_port = int(os.environ.get("REDIS_PORT", 6379))
            redis_db = int(os.environ.get("REDIS_DB", 0))
            redis_password = os.environ.get("REDIS_PASSWORD", None)

            # Fast network probe first to fail quickly when Redis is unreachable.
            with socket.create_connection((redis_host, redis_port), timeout=0.05):
                pass

            _redis_client = redis.Redis(
                host=redis_host,
                port=redis_port,
                db=redis_db,
                password=redis_password,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
                retry_on_timeout=False,
            )
            _redis_client.ping()
            _redis_available = True
            logger.info("Redis connected: %s:%s/%s", redis_host, redis_port, redis_db)
        except ImportError:
            logger.warning("Redis package is not installed, using in-memory fallback.")
            _redis_available = False
            _redis_client = None
        except Exception as exc:
            logger.warning("Redis unavailable, using in-memory fallback: %s", exc)
            _redis_available = False
            _redis_client = None


def _cleanup_expired_cache() -> None:
    """Cleanup expired records in fallback caches."""
    global _last_cleanup

    with _cache_lock:
        now = time.time()
        if now - _last_cleanup < CLEANUP_INTERVAL:
            return

        expired_keys = [k for k, v in _rate_limit_cache.items() if v["reset_time"] < now]
        for key in expired_keys:
            del _rate_limit_cache[key]

        expired_codes = [k for k, used_at in _code_usage_cache.items() if used_at < now - WECHAT_CODE_TTL_SECONDS]
        for key in expired_codes:
            del _code_usage_cache[key]

        _last_cleanup = now

    if expired_keys or expired_codes:
        logger.info(
            "Cache cleanup finished: rate_limit=%s, code_cache=%s",
            len(expired_keys),
            len(expired_codes),
        )


def check_rate_limit(key: str, limit: int, window: int) -> tuple[bool, Optional[dict]]:
    """Check rate limit by key.

    Returns:
        (allowed, metadata)
    """
    _ensure_redis_initialized()

    if _redis_available and _redis_client:
        try:
            redis_key = f"rate_limit:{key}"
            pipe = _redis_client.pipeline()
            pipe.incr(redis_key)
            pipe.expire(redis_key, window)
            results = pipe.execute()

            count = results[0]
            if count > limit:
                ttl = _redis_client.ttl(redis_key)
                retry_after = ttl if ttl > 0 else window
                return False, {
                    "limit": limit,
                    "remaining": 0,
                    "reset": int(time.time()) + retry_after,
                    "retry_after": retry_after,
                }

            return True, {
                "limit": limit,
                "remaining": limit - count,
                "reset": int(time.time()) + window,
            }
        except Exception as exc:
            logger.warning("Redis rate limit check failed, fallback to memory: %s", exc)

    _cleanup_expired_cache()

    now = time.time()
    with _cache_lock:
        cache = _rate_limit_cache.get(key)
        if cache is None:
            _rate_limit_cache[key] = {"count": 1, "reset_time": now + window}
            return True, None

        if now >= cache["reset_time"]:
            cache["count"] = 1
            cache["reset_time"] = now + window
            return True, None

        cache["count"] += 1
        if cache["count"] > limit:
            retry_after = int(cache["reset_time"] - now)
            return False, {
                "limit": limit,
                "remaining": 0,
                "reset": int(cache["reset_time"]),
                "retry_after": retry_after,
            }

        return True, {
            "limit": limit,
            "remaining": limit - cache["count"],
            "reset": int(cache["reset_time"]),
        }


def rate_limit(limit: int = 60, window: int = 60, key_func=None):
    """Flask decorator for endpoint-level rate limiting."""

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            key = key_func() if key_func else (request.remote_addr or "unknown")
            rate_key = f"rate_limit:{f.__name__}:{key}"

            allowed, info = check_rate_limit(rate_key, limit, window)
            if not allowed:
                logger.warning("Rate limit triggered: %s, limit=%s, window=%s", rate_key, limit, window)
                return jsonify(
                    {
                        "success": False,
                        "error": f"请求过于频繁，请在 {info['retry_after']} 秒后重试",
                        "rate_limit": info,
                    }
                ), 429

            response = f(*args, **kwargs)
            response_obj = response[0] if isinstance(response, tuple) else response

            if info and hasattr(response_obj, "headers"):
                response_obj.headers["X-RateLimit-Limit"] = str(info["limit"])
                response_obj.headers["X-RateLimit-Remaining"] = str(info["remaining"])
                response_obj.headers["X-RateLimit-Reset"] = str(info["reset"])

            return response

        return decorated_function

    return decorator


def check_and_mark_wechat_code_used(code: str) -> bool:
    """Check and mark WeChat login code as used.

    Returns:
        True if this is the first use; False if repeated within TTL.
    """
    _ensure_redis_initialized()

    if _redis_available and _redis_client:
        try:
            redis_key = f"wechat_code:{code}"
            result = _redis_client.set(redis_key, "1", ex=WECHAT_CODE_TTL_SECONDS, nx=True)
            if result:
                return True

            logger.warning("Detected duplicated WeChat code usage: %s...", code[:10])
            return False
        except Exception as exc:
            logger.warning("Redis code check failed, fallback to memory: %s", exc)

    _cleanup_expired_cache()

    cache_key = f"wechat_code:{code}"
    now = time.time()
    with _cache_lock:
        used_at = _code_usage_cache.get(cache_key)
        if used_at is not None:
            # Keep TTL behavior even if periodic cleanup has not happened yet.
            if now - used_at < WECHAT_CODE_TTL_SECONDS:
                logger.warning("Detected duplicated WeChat code usage: %s...", code[:10])
                return False
            del _code_usage_cache[cache_key]

        _code_usage_cache[cache_key] = now
        return True


def get_rate_limit_status(key: str) -> Optional[dict]:
    """Get current rate limit status."""
    _ensure_redis_initialized()

    if _redis_available and _redis_client:
        try:
            redis_key = f"rate_limit:{key}"
            count = _redis_client.get(redis_key)
            if count is None:
                return None

            ttl = _redis_client.ttl(redis_key)
            if ttl <= 0:
                return None

            return {
                "count": int(count),
                "reset_time": int(time.time()) + ttl,
                "remaining_time": ttl,
            }
        except Exception as exc:
            logger.warning("Redis status query failed, fallback to memory: %s", exc)

    with _cache_lock:
        cache = _rate_limit_cache.get(key)
        if cache is None:
            return None

        now = time.time()
        if now >= cache["reset_time"]:
            del _rate_limit_cache[key]
            return None

        return {
            "count": cache["count"],
            "reset_time": cache["reset_time"],
            "remaining_time": int(cache["reset_time"] - now),
        }


class RedisRateLimiter:
    """Standalone Redis-backed helper for direct usage."""

    def __init__(self, redis_client):
        self.redis = redis_client
        self.logger = logging.getLogger(__name__)

    def check_rate_limit(self, key: str, limit: int, window: int) -> tuple[bool, Optional[dict]]:
        """Check rate limit using Redis only."""
        try:
            pipe = self.redis.pipeline()
            pipe.incr(key)
            pipe.expire(key, window)
            results = pipe.execute()

            count = results[0]
            if count > limit:
                ttl = self.redis.ttl(key)
                return False, {
                    "limit": limit,
                    "remaining": 0,
                    "reset": int(time.time()) + ttl,
                    "retry_after": ttl,
                }

            return True, {
                "limit": limit,
                "remaining": limit - count,
                "reset": int(time.time()) + window,
            }
        except Exception as exc:
            self.logger.error("Redis rate limit check failed: %s", exc)
            # Fail-open to avoid blocking core APIs when Redis has incidents.
            return True, None

    def check_and_mark_wechat_code_used(self, code: str) -> bool:
        """Check and mark WeChat code usage using Redis only."""
        try:
            key = f"wechat_code:{code}"
            result = self.redis.set(key, "1", ex=WECHAT_CODE_TTL_SECONDS, nx=True)
            if result:
                return True

            self.logger.warning("Detected duplicated WeChat code usage: %s...", code[:10])
            return False
        except Exception as exc:
            self.logger.error("Redis code check failed: %s", exc)
            # Fail-open for compatibility with historical behavior.
            return True


__all__ = [
    "rate_limit",
    "check_rate_limit",
    "check_and_mark_wechat_code_used",
    "get_rate_limit_status",
    "RedisRateLimiter",
]
