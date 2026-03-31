#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Core data models for OddsMind entities."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional


class MatchStatus(Enum):
    """Match status enumeration."""

    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class StandingType(Enum):
    """Standing type enumeration."""

    OVERALL = "overall"
    HOME = "home"
    AWAY = "away"


@dataclass
class BaseModel:
    """Base model with common functionality."""

    def to_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary."""
        return asdict(self)

    def to_db_dict(self) -> Dict[str, Any]:
        """Convert model to dictionary suitable for database operations."""
        data = self.to_dict()

        for key, value in data.items():
            if isinstance(value, Enum):
                data[key] = value.value
            elif isinstance(value, datetime):
                data[key] = value.isoformat()

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BaseModel":
        """Create model instance from dictionary."""
        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {key: value for key, value in data.items() if key in valid_keys}
        return cls(**filtered_data)


@dataclass
class LeagueModel(BaseModel):
    """League data model."""

    league_id: int
    name_cn: str
    name_tw: Optional[str] = None
    name_en: Optional[str] = None
    season: Optional[str] = None
    color: Optional[str] = None
    logo: Optional[str] = None
    total_rounds: int = 38
    current_round: int = 1
    description: Optional[str] = None
    country: Optional[str] = None
    level: int = 1
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LeagueModel":
        if "id" in data and "league_id" not in data:
            data["league_id"] = data["id"]

        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {key: value for key, value in data.items() if key in valid_keys}
        return cls(**filtered_data)


@dataclass
class TeamModel(BaseModel):
    """Team data model."""

    team_id: int
    name_cn: str
    name_tw: Optional[str] = None
    name_en: Optional[str] = None
    short_name: Optional[str] = None
    logo: Optional[str] = None
    country: Optional[str] = None
    founded_year: Optional[int] = None
    stadium: Optional[str] = None
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TeamModel":
        if "id" in data and "team_id" not in data:
            data["team_id"] = data["id"]

        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {key: value for key, value in data.items() if key in valid_keys}
        return cls(**filtered_data)


@dataclass
class MatchModel(BaseModel):
    """Match data model."""

    match_id: int
    league_id: int
    season: Optional[str] = None
    division: Optional[str] = None  # 分区标识: 'east', 'west' 等
    round_number: Optional[int] = None
    match_time: Optional[datetime] = None
    timezone: str = "UTC"

    home_team_id: int = 0
    away_team_id: int = 0
    home_team_name: Optional[str] = None
    away_team_name: Optional[str] = None

    home_score: Optional[int] = None
    away_score: Optional[int] = None
    home_ht_score: Optional[int] = None
    away_ht_score: Optional[int] = None
    full_score: Optional[str] = None
    half_score: Optional[str] = None

    home_rank: Optional[str] = None
    away_rank: Optional[str] = None
    home_recent_form: Optional[str] = None
    away_recent_form: Optional[str] = None

    handicap: Optional[float] = None
    total_goals: Optional[float] = None

    match_status: MatchStatus = MatchStatus.SCHEDULED
    round_status: Optional[int] = None
    minute_played: Optional[int] = None

    referee: Optional[str] = None
    stadium: Optional[str] = None
    attendance: Optional[int] = None
    weather: Optional[str] = None

    is_deleted: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatchModel":
        if "id" in data and "match_id" not in data:
            data["match_id"] = data["id"]

        if "match_status" in data and isinstance(data["match_status"], str):
            try:
                data["match_status"] = MatchStatus(data["match_status"])
            except ValueError:
                data["match_status"] = MatchStatus.SCHEDULED

        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {key: value for key, value in data.items() if key in valid_keys}
        return cls(**filtered_data)


@dataclass
class StandingModel(BaseModel):
    """League standing data model."""

    id: Optional[int] = None
    league_id: int = 0
    season: Optional[str] = None
    team_id: int = 0

    standing_type: StandingType = StandingType.OVERALL
    position: int = 0
    played: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    goals_for: int = 0
    goals_against: int = 0
    goal_difference: int = 0
    points: int = 0

    recent_form: Optional[str] = None
    current_streak: Optional[str] = None
    home_wins: int = 0
    home_draws: int = 0
    home_losses: int = 0
    away_wins: int = 0
    away_draws: int = 0
    away_losses: int = 0

    clean_sheets: int = 0
    failed_to_score: int = 0

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StandingModel":
        if "id" in data and "team_id" not in data:
            data["team_id"] = data["id"]

        if "standing_type" in data and isinstance(data["standing_type"], str):
            try:
                data["standing_type"] = StandingType(data["standing_type"])
            except ValueError:
                data["standing_type"] = StandingType.OVERALL

        if "recent_form" in data and isinstance(data["recent_form"], list):
            form_chars = []
            for result in data["recent_form"]:
                if result == 0:
                    form_chars.append("L")
                elif result == 1:
                    form_chars.append("D")
                elif result == 2:
                    form_chars.append("W")
            data["recent_form"] = "".join(form_chars)

        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {key: value for key, value in data.items() if key in valid_keys}
        return cls(**filtered_data)


@dataclass
class ScrapingLogModel(BaseModel):
    """Scraping operation log model."""

    id: Optional[int] = None
    scraper_name: str = ""
    target_type: str = ""
    target_id: str = ""

    status: str = ""
    items_processed: int = 0
    items_success: int = 0
    items_failed: int = 0

    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    memory_usage_mb: Optional[float] = None

    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: Optional[datetime] = None


@dataclass
class MiniProgramUserModel(BaseModel):
    """小程序用户数据模型"""

    id: Optional[int] = None
    openid: str = ""
    unionid: Optional[str] = None
    nickname: Optional[str] = None
    avatar_url: Optional[str] = None
    is_activated: bool = False
    activated_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    invite_code_used: Optional[str] = None
    last_login_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class InviteCodeModel(BaseModel):
    """邀请码数据模型"""

    id: Optional[int] = None
    code: str = ""
    created_by: Optional[str] = None
    max_uses: int = 1
    used_count: int = 0
    expires_at: Optional[datetime] = None
    is_active: bool = True
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


__all__ = [
    "BaseModel",
    "InviteCodeModel",
    "LeagueModel",
    "MatchModel",
    "MatchStatus",
    "MiniProgramUserModel",
    "ScrapingLogModel",
    "StandingModel",
    "StandingType",
    "TeamModel",
]
