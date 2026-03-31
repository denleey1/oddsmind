#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Odds-related models for OddsMind entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Optional

from .models_core import BaseModel


@dataclass
class CompanyModel(BaseModel):
    """Bookmaker company data model."""

    company_id: int
    name_en: str
    name_cn: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    is_asian: bool = False
    priority: int = 100
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class OddsModel(BaseModel):
    """Odds data model."""

    id: Optional[int] = None
    match_id: int = 0
    company_id: int = 0

    initial_home: Optional[float] = None
    initial_draw: Optional[float] = None
    initial_away: Optional[float] = None
    initial_home_prob: Optional[float] = None
    initial_draw_prob: Optional[float] = None
    initial_away_prob: Optional[float] = None
    initial_return_rate: Optional[float] = None

    current_home: Optional[float] = None
    current_draw: Optional[float] = None
    current_away: Optional[float] = None
    current_home_prob: Optional[float] = None
    current_draw_prob: Optional[float] = None
    current_away_prob: Optional[float] = None
    current_return_rate: Optional[float] = None

    kelly_home: Optional[float] = None
    kelly_draw: Optional[float] = None
    kelly_away: Optional[float] = None

    odds_type: str = "1x2"
    update_time: Optional[str] = None
    data_source: str = "titan007"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class OddsHistoryModel(BaseModel):
    """Odds history data model."""

    id: Optional[int] = None
    match_id: int = 0
    company_id: int = 0
    odds_type: str = "1x2"

    home_odds: Optional[float] = None
    draw_odds: Optional[float] = None
    away_odds: Optional[float] = None
    handicap_line: Optional[float] = None
    total_line: Optional[float] = None

    change_time: Optional[datetime] = None
    change_timestamp: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class OddsChangeModel(BaseModel):
    """赔率状态模型，用于分析。"""

    match_id: int
    company_id: int
    last_updated: datetime

    initial_home: Optional[Decimal] = None
    initial_draw: Optional[Decimal] = None
    initial_away: Optional[Decimal] = None
    initial_return_rate: Optional[Decimal] = None

    current_home: Optional[Decimal] = None
    current_draw: Optional[Decimal] = None
    current_away: Optional[Decimal] = None
    current_return_rate: Optional[Decimal] = None

    id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class OverUnderOddsChangeModel(BaseModel):
    """Over/under odds state for monitoring."""

    match_id: int
    company_id: int
    market_line: float
    over_open: Optional[Decimal] = None
    under_open: Optional[Decimal] = None
    over_current: Optional[Decimal] = None
    under_current: Optional[Decimal] = None
    market: str = "over_under"
    variant: Optional[str] = None
    last_updated: datetime = field(default_factory=datetime.utcnow)
    id: Optional[int] = None
    created_at: Optional[datetime] = None


@dataclass
class AsianHandicapOddsModel(BaseModel):
    """亚盘赔率数据模型（仅存初盘+即时盘）。

    handicap_line 约定（主队视角）:
      正数 = 主队受让（主弱，获得让球）
      负数 = 主队让球（主强，让出球数）
      零   = 平手盘
    """

    id: Optional[int] = None
    match_id: int = 0
    company_id: int = 80

    initial_home_odds: Optional[float] = None
    initial_handicap_line: Optional[float] = None
    initial_away_odds: Optional[float] = None

    current_home_odds: Optional[float] = None
    current_handicap_line: Optional[float] = None
    current_away_odds: Optional[float] = None

    data_source: str = "titan007"
    scraped_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


__all__ = [
    "AsianHandicapOddsModel",
    "CompanyModel",
    "OddsChangeModel",
    "OddsHistoryModel",
    "OddsModel",
    "OverUnderOddsChangeModel",
]
