#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""League write helpers extracted from EnhancedDatabaseManager."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict

from core.exceptions import DatabaseError
from .models import LeagueModel, MatchModel, TeamModel

if TYPE_CHECKING:
    from .enhanced_manager import EnhancedDatabaseManager


def store_league_data_impl(manager: "EnhancedDatabaseManager", league_data: Dict[str, Any]) -> Dict[str, int]:
    try:
        counts = {
            "leagues": 0,
            "teams": 0,
            "matches": 0,
            "standings": 0,
        }

        if "league" in league_data and league_data["league"]:
            league_model = LeagueModel.from_dict(league_data["league"])
            manager.leagues.upsert(league_model, ["league_id"])
            counts["leagues"] = 1

        if "teams" in league_data and league_data["teams"]:
            team_models = [TeamModel.from_dict(team_data) for team_data in league_data["teams"] if isinstance(team_data, dict)]
            for team in team_models:
                manager.teams.upsert(team, ["team_id"])
            counts["teams"] = len(team_models)

        if "matches" in league_data and league_data["matches"]:
            match_models = []
            for _, round_matches in league_data["matches"].items():
                for match_data in round_matches:
                    if isinstance(match_data, dict):
                        normalized = normalize_match_data_impl(match_data)
                        match_models.append(MatchModel.from_dict(normalized))

            for match in match_models:
                manager.matches.upsert(match, ["match_id"])
            counts["matches"] = len(match_models)

        return counts

    except Exception as exc:
        manager.logger.error(f"Error storing league data: {exc}")
        raise DatabaseError(f"Failed to store league data: {str(exc)}")


def normalize_match_data_impl(match_data: Dict[str, Any]) -> Dict[str, Any]:
    normalized = match_data.copy()

    if "round_status" in normalized:
        round_status = normalized["round_status"]
        if round_status == -1:
            normalized["match_status"] = "finished"
        elif round_status == 0:
            normalized["match_status"] = "scheduled"
        else:
            normalized["match_status"] = "live"

    return normalized


__all__ = ["normalize_match_data_impl", "store_league_data_impl"]
