#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Formatting and dedupe operations for web match-listing endpoints."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from utils.timezone_utils import now

from app_helpers import get_team_logo

# 联赛全称 -> 简称映射（数据库存全称，API返回简称便于小程序搜索和显示）
_LEAGUE_SHORT_NAMES: Dict[str, str] = {
    "英格兰超级联赛": "英超",
    "西班牙甲组联赛": "西甲",
    "德国甲组联赛": "德甲",
    "意大利甲组联赛": "意甲",
    "法国甲组联赛": "法甲",
    "英格兰冠军联赛": "英冠",
    "英格兰甲组联赛": "英甲",
    "英格兰乙组联赛": "英乙",
    "西班牙乙组联赛": "西乙",
    "德国乙组联赛": "德乙",
    "意大利乙组联赛": "意乙",
    "法国乙组联赛": "法乙",
    "荷兰甲组联赛": "荷甲",
    "荷兰乙组联赛": "荷乙",
    "葡萄牙超级联赛": "葡超",
    "葡萄牙甲组联赛": "葡甲",
    "苏格兰超级联赛": "苏超",
    "土耳其超级联赛": "土超",
    "俄罗斯超级联赛": "俄超",
    "波兰超级联赛": "波兰超",
    "瑞士超级联赛": "瑞士超",
    "希腊超级联赛": "希腊超",
    "乌克兰超级联赛": "乌克超",
    "捷克甲组联赛": "捷克甲",
    "比利时甲级联赛": "比甲",
    "日本职业联赛J1": "日职",
    "日本职业联赛J2": "日乙",
    "南韩K联赛": "韩K",
    "南韩K2联赛": "韩K2",
    "澳大利亚足球超级联赛": "澳超",
    "沙特阿拉伯职业联赛": "沙特联",
    "巴西甲级联赛": "巴甲",
    "巴西乙级联赛": "巴乙",
    "阿根廷甲级联赛": "阿甲",
    "阿根廷乙级联赛": "阿乙",
    "墨西哥超级联赛": "墨超",
    "美国职业大联盟": "美职",
    "中国超级联赛": "中超",
    "中国甲级联赛": "中甲",
    "瑞典超级联赛": "瑞典超",
    "挪威超级联赛": "挪超",
    "丹麦超级联赛": "丹超",
    "奥地利甲组联赛": "奥甲",
    "罗马尼亚甲组联赛": "罗甲",
    "欧洲冠军联赛": "欧冠",
    "欧罗巴联赛": "欧联杯",
    "欧协联赛": "欧协联",
}


def _short_league_name(full_name: Optional[str]) -> str:
    """Return the common short name for a league, or the original if no mapping."""
    if not full_name:
        return full_name or ""
    return _LEAGUE_SHORT_NAMES.get(full_name, full_name)


def dedupe_same_match_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate records representing the same fixture under different source match IDs.

    Preference order:
    1) has odds analysis
    2) has odds changes
    3) has fundamental analysis
    4) newest update timestamp
    5) larger match_id
    """
    if not rows:
        return []

    def key(row: Dict[str, Any]):
        return (row.get("league_id"), row.get("match_time"), row.get("home_team_id"), row.get("away_team_id"))

    def score(row: Dict[str, Any]):
        has_odds_analysis = int(row.get("has_odds_analysis") or 0)
        has_odds_changes = int(row.get("has_odds_changes") or 0)
        has_fundamental = int(row.get("has_fundamental") or 0)
        updated_at = row.get("match_updated_at")
        return (has_odds_analysis, has_odds_changes, has_fundamental, updated_at, int(row.get("match_id") or 0))

    best_by_key: Dict[Any, Dict[str, Any]] = {}
    for row in rows:
        row_key = key(row)
        if row_key not in best_by_key or score(row) > score(best_by_key[row_key]):
            best_by_key[row_key] = row

    result = list(best_by_key.values())
    if len(rows) > 1:
        first_time = rows[0].get("match_time")
        last_time = rows[-1].get("match_time")
        if first_time and last_time:
            is_desc = first_time > last_time
            result.sort(key=lambda item: item.get("match_time") or now(), reverse=is_desc)
        else:
            result.sort(key=lambda item: item.get("match_time") or now(), reverse=True)
    else:
        result.sort(key=lambda item: item.get("match_time") or now(), reverse=True)
    return result


def _safe_float(value: Any) -> Any:
    try:
        return float(value) if value is not None else None
    except (ValueError, TypeError):
        return None


def _safe_json_list(value: Any) -> list:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        import json
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return []


def _safe_json_obj(value: Any, default: Any = None) -> Any:
    if not value:
        return default or {}
    if isinstance(value, dict):
        return value
    try:
        import json
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else (default or {})
    except Exception:
        return default or {}


def _format_match_time(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if value:
        return str(value)
    return None


def format_today_matches(
    matches: List[Dict[str, Any]],
    requested_fields: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    formatted_matches: List[Dict[str, Any]] = []
    for match in matches:
        standings_data = {
            "home": {
                "position": match["home_position"],
                "points": match["home_points"],
                "played": match["home_played"],
                "wins": match["home_wins"],
                "draws": match["home_draws"],
                "losses": match["home_losses"],
            },
            "away": {
                "position": match["away_position"],
                "points": match["away_points"],
                "played": match["away_played"],
                "wins": match["away_wins"],
                "draws": match["away_draws"],
                "losses": match["away_losses"],
            },
        }

        formatted = {
            "matchId": match["match_id"],
            "leagueId": match["league_id"],
            "leagueName": _short_league_name(match["league_name"]),
            "matchTime": _format_match_time(match["match_time"]),
            "homeTeamId": match["home_team_id"],
            "awayTeamId": match["away_team_id"],
            "homeTeam": match["home_team_name_cn"] or match["home_team_name"],
            "awayTeam": match["away_team_name_cn"] or match["away_team_name"],
            "homeTeamLogo": get_team_logo(match["home_team_name_cn"] or match["home_team_name"]),
            "awayTeamLogo": get_team_logo(match["away_team_name_cn"] or match["away_team_name"]),
            "matchStatus": match["match_status"],
            "homeScore": match["home_score"],
            "awayScore": match["away_score"],
            "roundNumber": match["round_number"],
            "totalRounds": match["total_rounds"],
            "season": match["season"],
            "groupName": match["group_name"],
            "standings": standings_data,
            "fundamentalAnalysis": {
                "recommendedOutcome": match["recommendation"],
                "confidenceLevel": match["recommendation_confidence"],
                "maxScore": _safe_float(match["max_score"]),
                "homeWin": {
                    "score": _safe_float(match["home_win_score"]),
                    "confidenceLevel": match["home_confidence_level"],
                    "confidenceInterval": match["home_confidence_interval"],
                    "oddsSuggestions": match["home_odds_suggestions"],
                }
                if match["home_win_score"] is not None
                else None,
                "draw": {
                    "score": _safe_float(match["draw_score"]),
                    "confidenceLevel": match["draw_confidence_level"],
                    "confidenceInterval": match["draw_confidence_interval"],
                    "oddsSuggestions": match["draw_odds_suggestions"],
                }
                if match["draw_score"] is not None
                else None,
                "awayWin": {
                    "score": _safe_float(match["away_win_score"]),
                    "confidenceLevel": match["away_confidence_level"],
                    "confidenceInterval": match["away_confidence_interval"],
                    "oddsSuggestions": match["away_odds_suggestions"],
                }
                if match["away_win_score"] is not None
                else None,
                "pullDirection": match.get("pull_direction"),
                "pullDescription": match.get("pull_description"),
                "prompts": _safe_json_list(match.get("prompts_json")),
                "absentPlayers": _safe_json_obj(match.get("absent_players_json"), {"home": [], "away": []}),
                "briefing": match.get("briefing") or "",
                "upcoming": _safe_json_obj(match.get("upcoming_json"), {"home": [], "away": []}),
                "distributionNode": match.get("distribution_node") or None,
            },
        }

        if requested_fields:
            filtered_formatted: Dict[str, Any] = {}
            for field in requested_fields:
                if field in formatted:
                    filtered_formatted[field] = formatted[field]
            formatted_matches.append(filtered_formatted)
        else:
            formatted_matches.append(formatted)
    return formatted_matches


def format_public_today_matches(matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted_matches: List[Dict[str, Any]] = []
    for match in matches:
        formatted_matches.append(
            {
                "matchId": match["match_id"],
                "leagueId": match["league_id"],
                "leagueName": _short_league_name(match["league_name"]),
                "matchTime": _format_match_time(match["match_time"]),
                "homeTeamId": match["home_team_id"],
                "awayTeamId": match["away_team_id"],
                "homeTeam": match["home_team_name_cn"] or match["home_team_name"],
                "awayTeam": match["away_team_name_cn"] or match["away_team_name"],
                "homeTeamLogo": get_team_logo(match["home_team_name_cn"] or match["home_team_name"]),
                "awayTeamLogo": get_team_logo(match["away_team_name_cn"] or match["away_team_name"]),
                "matchStatus": match["match_status"],
                "homeScore": match["home_score"],
                "awayScore": match["away_score"],
                "roundNumber": match["round_number"],
                "totalRounds": match["total_rounds"],
                "season": match["season"],
                "groupName": None,
            }
        )
    return formatted_matches


__all__ = ["dedupe_same_match_rows", "format_public_today_matches", "format_today_matches"]

