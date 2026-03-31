#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Utilities for fusing historical Poisson parameters with market-implied totals."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from config.companies_config import COMPANIES_CONFIG
from calculation.poisson_live import implied_mu_from_line


_COMPANY_BY_ID = {info.company_id: info for info in COMPANIES_CONFIG.values()}


def _record_weight(line: float, company_id: int) -> float:
    base = 1.0
    company = _COMPANY_BY_ID.get(company_id)
    if company:
        if company.priority <= 5:
            base += 0.4
        elif company.priority <= 10:
            base += 0.25
        elif company.priority <= 20:
            base += 0.1
        if company.is_asian:
            base += 0.05
    distance = abs(line - 2.5)
    line_weight = max(0.2, 1.0 - distance)
    return base * line_weight


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def fuse_expected_goals(
    hist_home: float,
    hist_away: float,
    records: List[Dict[str, Any]],
    match_time: Optional[datetime] = None,
) -> Dict[str, Any]:
    """Fuse historical expected goals with market-implied totals."""
    if not records:
        return {'applied': False}

    weighted_mu = 0.0
    total_weight = 0.0
    latest_update: Optional[datetime] = None
    company_ids = set()

    for record in records:
        line_mid = record.get('market_line')
        over_dec = record.get('over_current') or record.get('over_open')
        under_dec = record.get('under_current') or record.get('under_open')
        company_id = record.get('company_id')
        if line_mid is None or over_dec is None or under_dec is None or not company_id:
            continue
        try:
            mu, _ = implied_mu_from_line(float(line_mid), float(over_dec), float(under_dec))
        except Exception:
            continue
        weight = _record_weight(float(line_mid), int(company_id))
        weighted_mu += mu * weight
        total_weight += weight
        company_ids.add(int(company_id))
        last_updated = record.get('last_updated')
        if isinstance(last_updated, datetime):
            if latest_update is None or last_updated > latest_update:
                latest_update = last_updated

    if total_weight <= 0:
        return {'applied': False}

    mu_live = weighted_mu / total_weight

    total_hist = hist_home + hist_away
    if total_hist <= 0:
        home_share = away_share = 0.5
    else:
        home_share = hist_home / total_hist
        away_share = hist_away / total_hist

    home_live = mu_live * home_share
    away_live = mu_live * away_share

    hours_to_match = None
    if match_time:
        hours_to_match = max(0.0, (match_time - datetime.utcnow()).total_seconds() / 3600)

    base_weight = 0.5
    if hours_to_match is not None:
        if hours_to_match <= 12:
            base_weight += 0.15
        elif hours_to_match <= 24:
            base_weight += 0.1
        elif hours_to_match <= 48:
            base_weight += 0.05

    company_count = len(company_ids)
    if company_count >= 6:
        base_weight += 0.15
    elif company_count >= 4:
        base_weight += 0.1
    elif company_count >= 2:
        base_weight += 0.05

    if latest_update and match_time:
        minutes_gap = (match_time - latest_update).total_seconds() / 60
        if minutes_gap < 180:
            base_weight += 0.05
        elif minutes_gap < 720:
            base_weight += 0.02

    weight = _clamp(base_weight, 0.35, 0.8)

    home_final = weight * home_live + (1 - weight) * hist_home
    away_final = weight * away_live + (1 - weight) * hist_away

    return {
        'applied': True,
        'weight': weight,
        'mu_live_total': mu_live,
        'home_live': home_live,
        'away_live': away_live,
        'home_final': home_final,
        'away_final': away_final,
        'company_count': company_count,
        'latest_market_update': latest_update,
        'hours_to_match': hours_to_match,
    }
