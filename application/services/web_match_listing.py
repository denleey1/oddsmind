#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Match listing query and formatting helpers for web routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set

from application.services.web_match_listing_ops import (
    dedupe_same_match_rows as _dedupe_same_match_rows,
    fetch_public_today_matches as _fetch_public_today_matches,
    fetch_today_matches as _fetch_today_matches,
    format_public_today_matches as _format_public_today_matches,
    format_today_matches as _format_today_matches,
)


ALLOWED_MATCH_STATUSES = {"", "live", "scheduled", "finished", "pending", "postponed", "cancelled"}


def validate_match_status(status: str, logger: Any) -> str:
    """Normalize and validate ``match_status`` values used by route filters."""
    if not status:
        return ""
    status_lower = status.lower().strip()
    if status_lower in ALLOWED_MATCH_STATUSES:
        return status_lower
    logger.warning("Invalid match_status parameter ignored: %s", status)
    return ""


def dedupe_same_match_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Compatibility wrapper for dedupe logic."""
    return _dedupe_same_match_rows(rows)


def fetch_today_matches(
    status_filter: str,
    monitored_leagues: Sequence[int],
    monitoring_days: int,
    monitor_all_leagues: bool,
) -> List[Dict[str, Any]]:
    """Fetch route payload rows for authenticated today-matches endpoint."""
    return _fetch_today_matches(
        status_filter=status_filter,
        monitored_leagues=monitored_leagues,
        monitoring_days=monitoring_days,
        monitor_all_leagues=monitor_all_leagues,
    )


def format_today_matches(
    matches: List[Dict[str, Any]],
    requested_fields: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """Format authenticated today-matches response payload."""
    return _format_today_matches(matches=matches, requested_fields=requested_fields)


def fetch_public_today_matches(
    status_filter: str,
    monitored_leagues: Sequence[int],
    monitoring_days: int,
    monitor_all_leagues: bool,
) -> List[Dict[str, Any]]:
    """Fetch route payload rows for public today-matches endpoint."""
    return _fetch_public_today_matches(
        status_filter=status_filter,
        monitored_leagues=monitored_leagues,
        monitoring_days=monitoring_days,
        monitor_all_leagues=monitor_all_leagues,
    )


def format_public_today_matches(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Format public today-matches response payload."""
    return _format_public_today_matches(matches)


__all__ = [
    "ALLOWED_MATCH_STATUSES",
    "dedupe_same_match_rows",
    "fetch_public_today_matches",
    "fetch_today_matches",
    "format_public_today_matches",
    "format_today_matches",
    "validate_match_status",
]
