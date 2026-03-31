#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compatibility facade for split database model modules."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .models_analysis import ComprehensiveAnalysisModel, TeamPowerRatingHistoryModel
from .models_core import (
    BaseModel,
    InviteCodeModel,
    LeagueModel,
    MatchModel,
    MatchStatus,
    MiniProgramUserModel,
    ScrapingLogModel,
    StandingModel,
    StandingType,
    TeamModel,
)
from .models_odds import (
    AsianHandicapOddsModel,
    CompanyModel,
    OddsChangeModel,
    OddsHistoryModel,
    OddsModel,
    OverUnderOddsChangeModel,
)


MODEL_REGISTRY = {
    "league": LeagueModel,
    "team": TeamModel,
    "match": MatchModel,
    "company": CompanyModel,
    "odds": OddsModel,
    "odds_history": OddsHistoryModel,
    "standing": StandingModel,
    "scraping_log": ScrapingLogModel,
    "over_under_odds_change": OverUnderOddsChangeModel,
    "asian_handicap_odds": AsianHandicapOddsModel,
    "miniprogram_user": MiniProgramUserModel,
    "invite_code": InviteCodeModel,
}


def get_model_class(model_name: str) -> Optional[type]:
    """Get model class by name."""
    return MODEL_REGISTRY.get(model_name.lower())


def create_model_instance(model_name: str, data: Dict[str, Any]):
    """Create model instance from data dictionary."""
    model_class = get_model_class(model_name)
    if model_class:
        return model_class.from_dict(data)
    return None


__all__ = [
    "AsianHandicapOddsModel",
    "BaseModel",
    "CompanyModel",
    "ComprehensiveAnalysisModel",
    "InviteCodeModel",
    "LeagueModel",
    "MODEL_REGISTRY",
    "MatchModel",
    "MatchStatus",
    "MiniProgramUserModel",
    "OddsChangeModel",
    "OddsHistoryModel",
    "OddsModel",
    "OverUnderOddsChangeModel",
    "ScrapingLogModel",
    "StandingModel",
    "StandingType",
    "TeamModel",
    "TeamPowerRatingHistoryModel",
    "create_model_instance",
    "get_model_class",
]
