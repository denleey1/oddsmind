#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Formatting helpers extracted from match_detail_optimized service."""

from __future__ import annotations

import json
from typing import Any, Dict, List


def safe_float_impl(value: Any, default: Any = None) -> Any:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def format_analysis_impl(service, analysis: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "companyId": analysis.get("company_id"),
        "companyName": analysis.get("company_name_cn") or analysis.get("company_name"),
        "homePowerLevel": safe_float_impl(analysis.get("home_power_level")),
        "awayPowerLevel": safe_float_impl(analysis.get("away_power_level")),
        "homeTierLevel": analysis.get("home_tier_level"),
        "awayTierLevel": analysis.get("away_tier_level"),
        "initial": {
            "homeRange": analysis.get("initial_home_range"),
            "homeRuleValue": safe_float_impl(analysis.get("initial_home_rule_value")),
            "drawRange": analysis.get("initial_draw_range"),
            "awayRange": analysis.get("initial_away_range"),
            "awayRuleValue": safe_float_impl(analysis.get("initial_away_rule_value")),
            "ruleDiff": safe_float_impl(analysis.get("initial_rule_diff")),
            "recommendedOutcome": analysis.get("initial_recommended_outcome"),
            "odds": {
                "home": safe_float_impl(analysis.get("initial_home")),
                "draw": safe_float_impl(analysis.get("initial_draw")),
                "away": safe_float_impl(analysis.get("initial_away")),
            },
        },
        "current": {
            "homeRange": analysis.get("current_home_range"),
            "homeRuleValue": safe_float_impl(analysis.get("current_home_rule_value")),
            "drawRange": analysis.get("current_draw_range"),
            "awayRange": analysis.get("current_away_range"),
            "awayRuleValue": safe_float_impl(analysis.get("current_away_rule_value")),
            "ruleDiff": safe_float_impl(analysis.get("current_rule_diff")),
            "recommendedOutcome": analysis.get("current_recommended_outcome"),
            "odds": {
                "home": safe_float_impl(analysis.get("current_home")),
                "draw": safe_float_impl(analysis.get("current_draw")),
                "away": safe_float_impl(analysis.get("current_away")),
            },
        },
        "analyzedAt": (
            analysis.get("analyzed_at").isoformat()
            if hasattr(analysis.get("analyzed_at"), "isoformat")
            else (str(analysis.get("analyzed_at")) if analysis.get("analyzed_at") else None)
        ),
        "recommendedOutcome": analysis.get("current_recommended_outcome")
        or analysis.get("initial_recommended_outcome"),
    }


def build_response_impl(
    service,
    match: Dict[str, Any],
    analyses: List[Dict[str, Any]],
    total_company_count: int,
) -> Dict[str, Any]:
    standings = {
        "home": {
            "position": match.get("home_position"),
            "points": match.get("home_points"),
            "played": match.get("home_played"),
            "wins": match.get("home_wins"),
            "draws": match.get("home_draws"),
            "losses": match.get("home_losses"),
        }
        if match.get("home_position") is not None
        else None,
        "away": {
            "position": match.get("away_position"),
            "points": match.get("away_points"),
            "played": match.get("away_played"),
            "wins": match.get("away_wins"),
            "draws": match.get("away_draws"),
            "losses": match.get("away_losses"),
        }
        if match.get("away_position") is not None
        else None,
    }

    fundamental = None
    if match.get("recommendation"):
        fundamental = {
            "recommendedOutcome": match["recommendation"],
            "confidenceLevel": match["recommendation_confidence"],
            "maxScore": safe_float_impl(match["max_score"]),
            "homeOddsSuggestions": json.loads(match["home_odds_suggestions"]) if match.get("home_odds_suggestions") else [],
            "drawOddsSuggestions": json.loads(match["draw_odds_suggestions"]) if match.get("draw_odds_suggestions") else [],
            "awayOddsSuggestions": json.loads(match["away_odds_suggestions"]) if match.get("away_odds_suggestions") else [],
            "homeWin": {
                "score": safe_float_impl(match["home_win_score"]),
                "confidenceLevel": match["home_confidence_level"],
                "confidenceInterval": match["home_confidence_interval"],
            }
            if match.get("home_win_score")
            else None,
            "draw": {
                "score": safe_float_impl(match["draw_score"]),
                "confidenceLevel": match["draw_confidence_level"],
                "confidenceInterval": match["draw_confidence_interval"],
            }
            if match.get("draw_score")
            else None,
            "awayWin": {
                "score": safe_float_impl(match["away_win_score"]),
                "confidenceLevel": match["away_confidence_level"],
                "confidenceInterval": match["away_confidence_interval"],
            }
            if match.get("away_win_score")
            else None,
            "distributionNode": match.get("distribution_node") or None,
        }

    from application.services.web_match_listing_format_ops import _short_league_name

    return {
        "matchId": match["match_id"],
        "leagueName": _short_league_name(match["league_name"]),
        "roundNumber": match.get("round_number"),
        "totalRounds": match.get("total_rounds"),
        "matchTime": (
            match.get("match_time").isoformat()
            if hasattr(match.get("match_time"), "isoformat")
            else (str(match.get("match_time")) if match.get("match_time") else None)
        ),
        "homeTeam": match["home_team_name_cn"] or match["home_team_name"],
        "awayTeam": match["away_team_name_cn"] or match["away_team_name"],
        "homeTeamLogo": service.get_team_logo(match["home_team_name_cn"] or match["home_team_name"]),
        "awayTeamLogo": service.get_team_logo(match["away_team_name_cn"] or match["away_team_name"]),
        "matchStatus": match["match_status"],
        "homeScore": match["home_score"],
        "awayScore": match["away_score"],
        "standings": standings,
        "fundamentalAnalysis": fundamental,
        "oddsAnalysis": analyses[0] if analyses else None,
        "companyAnalyses": analyses,
        "totalCompanyCount": total_company_count,
    }


__all__ = ["build_response_impl", "format_analysis_impl", "safe_float_impl"]
