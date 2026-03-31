#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helpers for deriving live Poisson parameters from over/under odds."""

from __future__ import annotations

import math
from datetime import datetime
from decimal import Decimal
from typing import Optional, Tuple


def poisson_pmf(mu: float, k: int) -> float:
    return math.exp(-mu) * mu ** k / math.factorial(k)


def poisson_cdf(mu: float, k: int) -> float:
    return sum(poisson_pmf(mu, i) for i in range(k + 1))


def parse_line_str(value: Optional[str]) -> Optional[float]:
    """Convert Asian total string into float midpoint."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if '/' in text:
        try:
            a_str, b_str = text.split('/', 1)
            return (float(a_str) + float(b_str)) / 2.0
        except (ValueError, TypeError):
            return None
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


def to_decimal_odds(value: Optional[str]) -> Optional[float]:
    """Convert stored odds (water or decimal) to decimal odds."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        num = float(text)
    except (ValueError, TypeError):
        return None
    if num <= 0:
        return None
    if num < 1.2:
        return 1.0 + num
    return num


def no_vig_over_prob(over_dec: float, under_dec: float) -> float:
    p_over_star = 1.0 / over_dec
    p_under_star = 1.0 / under_dec
    s = p_over_star + p_under_star
    return p_over_star / s


def ev_components_over(mu: float, line: float) -> Tuple[float, float]:
    base = int(math.floor(line))
    frac = line - base
    ge = lambda n: 1.0 - poisson_cdf(mu, n - 1)
    le = lambda n: poisson_cdf(mu, n)
    if abs(frac) < 1e-12:
        win = ge(base + 1)
        lose = le(base - 1)
    elif abs(frac - 0.5) < 1e-12:
        win = ge(base + 1)
        lose = le(base)
    elif abs(frac - 0.25) < 1e-12:
        win = ge(base + 1)
        lose = le(base - 1) + 0.5 * poisson_pmf(mu, base)
    elif abs(frac - 0.75) < 1e-12:
        win = ge(base + 2) + 0.5 * poisson_pmf(mu, base + 1)
        lose = le(base)
    else:
        win = ge(math.floor(line) + 1)
        lose = le(math.floor(line))
    return win, lose


def implied_mu_from_line(line_mid: float, over_dec: float, under_dec: float) -> Tuple[float, float]:
    """Solve EV_over(mu) = 0 for the implied total goals mean."""
    if line_mid is None or over_dec is None or under_dec is None:
        raise ValueError("Missing inputs for implied mu calculation")

    p_over = no_vig_over_prob(over_dec, under_dec)
    if not (0.0 < p_over < 1.0):
        raise ValueError("Invalid implied probability for over market")

    fair_odds = 1.0 / p_over

    def objective(mu: float) -> float:
        win, lose = ev_components_over(mu, line_mid)
        return (fair_odds - 1.0) * win - lose

    lo, hi = 0.01, 10.0
    f_lo, f_hi = objective(lo), objective(hi)
    expansion = 0
    while f_lo * f_hi > 0 and expansion < 12:
        hi *= 1.5
        f_hi = objective(hi)
        expansion += 1

    for _ in range(120):
        mid = 0.5 * (lo + hi)
        f_mid = objective(mid)
        if abs(f_mid) < 1e-12:
            return mid, p_over
        if f_lo * f_mid <= 0:
            hi = mid
            f_hi = f_mid
        else:
            lo = mid
            f_lo = f_mid

    return 0.5 * (lo + hi), p_over


def to_decimal(value: Optional[float]) -> Optional[Decimal]:
    if value is None:
        return None
    return Decimal(str(round(value, 6)))


def parse_timestamp(value: Optional[str]) -> Optional[datetime]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    patterns = (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%dT%H:%M:%S",
    )
    for fmt in patterns:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None
