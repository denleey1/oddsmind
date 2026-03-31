#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Cache and retry payload operations for public match-detail endpoints."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Tuple

from core.exceptions import DatabaseError


def build_public_match_detail_payload_ops(
    match_id: int,
    no_cache: bool,
    match_detail_service: Any,
    logger: Any,
    get_cache_key_fn: Callable[..., str],
    cache_get_fn: Callable[..., Any],
    cache_set_fn: Callable[..., None],
    error_handler: Any,
) -> Tuple[Dict[str, Any], int, Dict[str, str]]:
    cache_key = get_cache_key_fn("match_detail_full", match_id=match_id)
    if not no_cache:
        cached_result = cache_get_fn(cache_key)
        if cached_result is not None:
            logger.debug("缓存命中: 比赛详情 %s", match_id)
            return cached_result, 200, {"X-Cache": "HIT", "X-Response-Time": "0ms (cached)"}

    start_time = time.time()
    last_exc = None
    result: Dict[str, Any] = {}

    for attempt in range(3):
        try:
            result = match_detail_service.get_complete_match_detail(str(match_id), include_poisson=True)
            last_exc = None
            break
        except DatabaseError as exc:
            last_exc = exc
            msg = str(exc)
            if ("1213" in msg or "1205" in msg) and attempt < 2:
                time.sleep(0.15 * (2**attempt))
                continue
            raise

    if last_exc is not None:
        raise last_exc

    elapsed_ms = (time.time() - start_time) * 1000
    if elapsed_ms > 2000:
        logger.warning(
            "⚠️ 慢请求: 比赛详情 %s 耗时 %.0fms (完整版接口，含泊松+态度总结)",
            match_id,
            elapsed_ms,
        )

    if result and result.get("success"):
        cache_set_fn(cache_key, result, expire=60)
        return result, 200, {"X-Cache": "MISS", "X-Response-Time": f"{elapsed_ms:.0f}ms"}

    return error_handler.handle_not_found_error("比赛"), 404, {}


def build_public_match_summary_payload_ops(
    match_id: int,
    match_detail_service: Any,
    get_cache_key_fn: Callable[..., str],
    cache_get_fn: Callable[..., Any],
    cache_set_fn: Callable[..., None],
) -> Tuple[Dict[str, Any], Dict[str, str]]:
    cache_key = get_cache_key_fn("match_summary", match_id=match_id)
    cached_result = cache_get_fn(cache_key)
    if cached_result is not None:
        return {"success": True, "data": cached_result}, {"X-Cache": "HIT"}

    all_analyses_raw = match_detail_service.get_odds_analyses(str(match_id)) or []
    if not all_analyses_raw:
        return {"success": True, "data": {}}, {}

    summary = match_detail_service.summary_calculator.calculate_company_summary(all_analyses_raw)
    cache_set_fn(cache_key, summary, expire=60)
    return {"success": True, "data": summary}, {"X-Cache": "MISS"}


__all__ = [
    "build_public_match_detail_payload_ops",
    "build_public_match_summary_payload_ops",
]

