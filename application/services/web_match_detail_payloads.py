#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Payload assembly helpers extracted from web match-detail routes."""

from __future__ import annotations

from typing import Any, Dict, Optional, Set, Tuple
from utils.cache import cache_get, cache_set, get_cache_key

from application.services.analytics import get_match_detail
from application.services.web_match_detail_cache_ops import (
    build_public_match_detail_payload_ops as _build_public_match_detail_payload_ops,
    build_public_match_summary_payload_ops as _build_public_match_summary_payload_ops,
)
from application.services.web_match_detail_pagination_ops import (
    build_public_match_detail_pagination_payload_ops as _build_public_match_detail_pagination_payload_ops,
)
from app_security import ErrorHandler


def build_public_match_detail_pagination_payload(
    match_id: int,
    load_type: str,
    page: int,
    page_size: int,
    requested_fields: Optional[Set[str]],
    match_detail_service: Any,
) -> Tuple[Dict[str, Any], int]:
    return _build_public_match_detail_pagination_payload_ops(
        match_id=match_id,
        load_type=load_type,
        page=page,
        page_size=page_size,
        requested_fields=requested_fields,
        match_detail_service=match_detail_service,
        get_match_detail_fn=get_match_detail,
        error_handler=ErrorHandler,
    )


def build_public_match_detail_payload(
    match_id: int,
    no_cache: bool,
    match_detail_service: Any,
    logger: Any,
) -> Tuple[Dict[str, Any], int, Dict[str, str]]:
    return _build_public_match_detail_payload_ops(
        match_id=match_id,
        no_cache=no_cache,
        match_detail_service=match_detail_service,
        logger=logger,
        get_cache_key_fn=get_cache_key,
        cache_get_fn=cache_get,
        cache_set_fn=cache_set,
        error_handler=ErrorHandler,
    )


def build_public_match_summary_payload(match_id: int, match_detail_service: Any) -> Tuple[Dict[str, Any], Dict[str, str]]:
    return _build_public_match_summary_payload_ops(
        match_id=match_id,
        match_detail_service=match_detail_service,
        get_cache_key_fn=get_cache_key,
        cache_get_fn=cache_get,
        cache_set_fn=cache_set,
    )


__all__ = [
    "build_public_match_detail_pagination_payload",
    "build_public_match_detail_payload",
    "build_public_match_summary_payload",
]
