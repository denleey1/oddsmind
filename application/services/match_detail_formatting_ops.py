#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Formatting operations extracted from MatchDetailService."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional


def safe_float(value: Any, default: Any = None) -> Any:
    """安全的浮点数转换"""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def sort_analyses_by_priority(analyses: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """按优先级排序分析结果，并限制返回数量"""
    from app_constants import PERSONAL_COMPANY_ORDER

    local_logger = logging.getLogger(__name__)

    def get_company_priority(company_id):
        try:
            return PERSONAL_COMPANY_ORDER.index(int(company_id))
        except (ValueError, TypeError):
            return 999

    if analyses:
        analyses.sort(key=lambda row: get_company_priority(row.get("company_id")))
        if limit is not None and limit > 0:
            limited_analyses = analyses[:limit]
            local_logger.info(
                f"公司排序完成，返回前 {len(limited_analyses)} 个公司（限制: {limit}，优先公司: {len(PERSONAL_COMPANY_ORDER)}）"
            )
            return limited_analyses
        local_logger.info(f"公司排序完成，返回全部 {len(analyses)} 个公司（无限制）")

    return analyses


def format_analysis_data(analysis: Dict[str, Any]) -> Dict[str, Any]:
    """格式化单个分析数据"""
    analyzed_at_raw = analysis.get("analyzed_at")
    if analyzed_at_raw:
        try:
            analyzed_at = analyzed_at_raw.isoformat()
        except AttributeError:
            analyzed_at = str(analyzed_at_raw)
    else:
        analyzed_at = None

    return {
        "companyId": analysis.get("company_id"),
        "companyName": analysis.get("company_name"),
        "homeTeamStrength": safe_float(analysis.get("home_team_strength")),
        "awayTeamStrength": safe_float(analysis.get("away_team_strength")),
        "homePowerLevel": safe_float(analysis.get("home_power_level")),
        "awayPowerLevel": safe_float(analysis.get("away_power_level")),
        "homeTierLevel": analysis.get("home_tier_level"),
        "awayTierLevel": analysis.get("away_tier_level"),
        "initial": {
            "homeRange": analysis.get("initial_home_range"),
            "homeRuleValue": safe_float(analysis.get("initial_home_rule_value")),
            "drawRange": analysis.get("initial_draw_range"),
            "awayRange": analysis.get("initial_away_range"),
            "awayRuleValue": safe_float(analysis.get("initial_away_rule_value")),
            "ruleDiff": safe_float(analysis.get("initial_rule_diff")),
            "recommendedOutcome": analysis.get("initial_recommended_outcome"),
            "odds": {
                "home": safe_float(analysis.get("initial_home")),
                "draw": safe_float(analysis.get("initial_draw")),
                "away": safe_float(analysis.get("initial_away")),
            },
        },
        "current": {
            "homeRange": analysis.get("current_home_range"),
            "homeRuleValue": safe_float(analysis.get("current_home_rule_value")),
            "drawRange": analysis.get("current_draw_range"),
            "awayRange": analysis.get("current_away_range"),
            "awayRuleValue": safe_float(analysis.get("current_away_rule_value")),
            "ruleDiff": safe_float(analysis.get("current_rule_diff")),
            "recommendedOutcome": analysis.get("current_recommended_outcome"),
            "odds": {
                "home": safe_float(analysis.get("current_home")),
                "draw": safe_float(analysis.get("current_draw")),
                "away": safe_float(analysis.get("current_away")),
            },
        },
        "analyzedAt": analyzed_at,
        "recommendedOutcome": analysis.get("current_recommended_outcome")
        or analysis.get("initial_recommended_outcome"),
    }


def get_top_analyses(all_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """获取顶级公司分析"""
    from app_constants import PERSONAL_COMPANY_ORDER

    top_analyses = []
    for analysis in all_analyses:
        company_id = analysis.get("companyId")
        try:
            company_id_int = int(company_id)
        except (TypeError, ValueError):
            continue
        if company_id_int in PERSONAL_COMPANY_ORDER:
            top_analyses.append(analysis)

    if not top_analyses and all_analyses:
        top_analyses = all_analyses[:10]
    return top_analyses


def build_fundamental_analysis_data(match: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """构建基本面分析数据"""
    if not match["recommendation"]:
        return None

    return {
        "recommendedOutcome": match["recommendation"],
        "confidenceLevel": match["recommendation_confidence"],
        "maxScore": float(match["max_score"]) if match["max_score"] else None,
        "homeOddsSuggestions": json.loads(match["home_odds_suggestions"])
        if match.get("home_odds_suggestions")
        else [],
        "drawOddsSuggestions": json.loads(match["draw_odds_suggestions"])
        if match.get("draw_odds_suggestions")
        else [],
        "awayOddsSuggestions": json.loads(match["away_odds_suggestions"])
        if match.get("away_odds_suggestions")
        else [],
        "homeWin": {
            "score": float(match["home_win_score"]) if match["home_win_score"] else None,
            "confidenceLevel": match["home_confidence_level"],
            "confidenceInterval": match["home_confidence_interval"],
            "oddsSuggestions": json.loads(match["home_odds_suggestions"])
            if match.get("home_odds_suggestions")
            else [],
        },
        "draw": {
            "score": float(match["draw_score"]) if match["draw_score"] else None,
            "confidenceLevel": match["draw_confidence_level"],
            "confidenceInterval": match["draw_confidence_interval"],
            "oddsSuggestions": json.loads(match["draw_odds_suggestions"])
            if match.get("draw_odds_suggestions")
            else [],
        },
        "awayWin": {
            "score": float(match["away_win_score"]) if match["away_win_score"] else None,
            "confidenceLevel": match["away_confidence_level"],
            "confidenceInterval": match["away_confidence_interval"],
            "oddsSuggestions": json.loads(match["away_odds_suggestions"])
            if match.get("away_odds_suggestions")
            else [],
        },
        "pullDirection": match.get("pull_direction"),
        "pullDescription": match.get("pull_description"),
        "prompts": json.loads(match["prompts_json"])
        if match.get("prompts_json")
        else [],
        "absentPlayers": json.loads(match["absent_players_json"])
        if match.get("absent_players_json")
        else {"home": [], "away": []},
        "briefing": match.get("briefing") or "",
        "upcoming": json.loads(match["upcoming_json"])
        if match.get("upcoming_json")
        else {"home": [], "away": []},
        "distributionNode": match.get("distribution_node") or None,
    }


__all__ = [
    "build_fundamental_analysis_data",
    "format_analysis_data",
    "get_top_analyses",
    "safe_float",
    "sort_analyses_by_priority",
]

