#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analysis-related models for OddsMind entities."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .models_core import BaseModel


@dataclass
class ComprehensiveAnalysisModel(BaseModel):
    """Comprehensive analysis result model."""

    id: Optional[int] = None
    match_id: int = 0
    analysis_time: Optional[datetime] = None

    home_team_power_level: Optional[float] = None
    away_team_power_level: Optional[float] = None
    power_level_diff: Optional[float] = None

    fundamental_home_score: Optional[float] = None
    fundamental_draw_score: Optional[float] = None
    fundamental_away_score: Optional[float] = None
    fundamental_confidence: Optional[str] = None
    fundamental_recommendation: Optional[str] = None

    odds_confidence: Optional[float] = None
    odds_recommendation: Optional[str] = None

    final_recommendation: Optional[str] = None
    final_confidence: Optional[float] = None
    risk_level: Optional[str] = None

    is_reasonable: Optional[bool] = None

    created_at: Optional[datetime] = field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = field(default_factory=datetime.utcnow)


@dataclass
class TeamPowerRatingHistoryModel(BaseModel):
    """Team power rating history data model."""

    id: Optional[int] = None
    team_id: int = 0
    league_id: int = 0
    company_id: int = 0
    season: Optional[str] = None
    round_number: int = 0
    calculation_date: Optional[datetime] = field(default_factory=datetime.utcnow)

    start_round: int = 1
    target_round: int = 1

    total_power: float = 0.0
    recent_power: float = 0.0
    relative_power: float = 0.0
    power_level: float = 0.0
    tier_distance: float = 0.0
    tier_level: str = ""

    team_name: str = ""
    company_name: str = ""


__all__ = ["ComprehensiveAnalysisModel", "TeamPowerRatingHistoryModel"]
