#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Internal orchestration wrappers for web match-listing service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

from application.services.web_match_listing_format_ops import (
    dedupe_same_match_rows as _dedupe_same_match_rows,
    format_public_today_matches as _format_public_today_matches,
    format_today_matches as _format_today_matches,
)
from application.services.web_match_listing_query_ops import (
    fetch_public_today_matches_rows as _fetch_public_today_matches_rows,
    fetch_today_matches_rows as _fetch_today_matches_rows,
)


def dedupe_same_match_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _dedupe_same_match_rows(rows)


def fetch_today_matches(
    status_filter: str,
    monitored_leagues: Sequence[int],
    monitoring_days: int,
    monitor_all_leagues: bool,
) -> List[Dict[str, Any]]:
    matches = _fetch_today_matches_rows(
        status_filter=status_filter,
        monitored_leagues=monitored_leagues,
        monitoring_days=monitoring_days,
        monitor_all_leagues=monitor_all_leagues,
    )
    return _dedupe_same_match_rows(matches)


def format_today_matches(
    matches: List[Dict[str, Any]],
    requested_fields: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    return _format_today_matches(matches=matches, requested_fields=requested_fields)


def fetch_public_today_matches(
    status_filter: str,
    monitored_leagues: Sequence[int],
    monitoring_days: int,
    monitor_all_leagues: bool,
) -> List[Dict[str, Any]]:
    matches = _fetch_public_today_matches_rows(
        status_filter=status_filter,
        monitored_leagues=monitored_leagues,
        monitoring_days=monitoring_days,
        monitor_all_leagues=monitor_all_leagues,
    )
    return _dedupe_same_match_rows(matches)


def format_public_today_matches(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return _format_public_today_matches(matches)


__all__ = [
    "dedupe_same_match_rows",
    "fetch_public_today_matches",
    "fetch_today_matches",
    "format_public_today_matches",
    "format_today_matches",
]
