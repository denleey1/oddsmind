#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Query operations extracted from MatchDetailService."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app_database import execute_query


def get_match_basic_info(service: Any, match_id: str) -> Optional[Dict[str, Any]]:
    """获取比赛基本信息"""
    resolved_match_id = service._resolve_canonical_match_id(match_id) or match_id

    match_sql = """
    SELECT m.match_id, m.match_time, m.league_id, m.home_team_id, m.away_team_id,
           m.match_status, m.home_score, m.away_score, m.round_number,
           l.name_cn as league_name, l.total_rounds,
           ht.name_cn as home_team_name_cn, ht.name_en as home_team_name,
           at.name_cn as away_team_name_cn, at.name_en as away_team_name,
           fa.recommended_outcome as recommendation, fa.confidence_level as recommendation_confidence,
           fa.max_score, fa.home_win_score, fa.home_confidence_level, fa.home_confidence_interval,
           fa.home_odds_suggestions, fa.draw_score, fa.draw_confidence_level, fa.draw_confidence_interval,
           fa.draw_odds_suggestions, fa.away_win_score, fa.away_confidence_level, fa.away_confidence_interval,
           fa.away_odds_suggestions,
           fa.pull_direction, fa.pull_description, fa.prompts_json, fa.absent_players_json,
           fa.briefing, fa.upcoming_json,
           fa.distribution_node
    FROM matches m
    JOIN leagues l ON l.league_id = m.league_id
    LEFT JOIN teams ht ON ht.team_id = m.home_team_id
    LEFT JOIN teams at ON at.team_id = m.away_team_id
    LEFT JOIN fundamental_analysis fa ON fa.match_id = m.match_id
    WHERE m.match_id = %s
    """
    result = execute_query(match_sql, (resolved_match_id,))
    return result[0] if result else None


def resolve_canonical_match_id(service: Any, match_id: str) -> Optional[str]:
    """
    给定任意 match_id，若该比赛存在同场重复记录，返回更完整的 canonical match_id。

    选择策略：
    - 有 odds_analysis_results 优先
    - 其次有 odds_changes
    - 其次有 fundamental_analysis
    - 再按 matches.updated_at、match_id 兜底
    """
    if match_id in service._canonical_match_id_cache:
        return service._canonical_match_id_cache[match_id]

    try:
        base = execute_query(
            "SELECT league_id, match_time, home_team_id, away_team_id FROM matches WHERE match_id = %s",
            (match_id,),
        )
        if not base:
            return None
        league_id = base[0].get("league_id")
        match_time = base[0].get("match_time")
        home_team_id = base[0].get("home_team_id")
        away_team_id = base[0].get("away_team_id")

        candidates = execute_query(
            """
            SELECT
                m.match_id,
                m.updated_at as match_updated_at,
                CASE WHEN EXISTS(SELECT 1 FROM odds_analysis_results WHERE match_id = m.match_id LIMIT 1) THEN 1 ELSE 0 END as has_odds_analysis,
                CASE WHEN EXISTS(SELECT 1 FROM odds_changes WHERE match_id = m.match_id LIMIT 1) THEN 1 ELSE 0 END as has_odds_changes,
                CASE WHEN EXISTS(SELECT 1 FROM fundamental_analysis WHERE match_id = m.match_id LIMIT 1) THEN 1 ELSE 0 END as has_fundamental
            FROM matches m
            WHERE m.league_id = %s
              AND m.match_time = %s
              AND m.home_team_id = %s
              AND m.away_team_id = %s
            LIMIT 5
            """,
            (league_id, match_time, home_team_id, away_team_id),
        )
        if not candidates:
            return None

        def _score(row: Dict[str, Any]):
            return (
                int(row.get("has_odds_analysis") or 0),
                int(row.get("has_odds_changes") or 0),
                int(row.get("has_fundamental") or 0),
                row.get("match_updated_at"),
                int(row.get("match_id") or 0),
            )

        best = max(candidates, key=_score)
        best_id = str(best.get("match_id")) if best.get("match_id") is not None else None
        if best_id and best_id != str(match_id):
            service._canonical_match_id_cache[match_id] = best_id
            return best_id
        service._canonical_match_id_cache[match_id] = None
        return None
    except Exception:
        service._canonical_match_id_cache[match_id] = None
        return None


def get_team_standings(team_id: int, league_id: int) -> Optional[Dict[str, Any]]:
    """获取球队积分榜信息（单个）"""
    standings_sql = """
        SELECT position, points, played, wins, draws, losses
        FROM standings
        WHERE team_id = %s AND league_id = %s AND standing_type = 'overall'
    """
    result = execute_query(standings_sql, (team_id, league_id))
    return result[0] if result else None


def get_team_standings_batch(team_ids: List[int], league_id: int) -> Dict[int, Dict[str, Any]]:
    """批量获取球队积分榜信息（性能优化：合并查询）"""
    if not team_ids:
        return {}

    standings_sql = """
        SELECT team_id, position, points, played, wins, draws, losses
        FROM standings
        WHERE team_id IN %s AND league_id = %s AND standing_type = 'overall'
    """
    result = execute_query(standings_sql, (tuple(team_ids), league_id))
    return {row["team_id"]: row for row in result} if result else {}


def get_odds_analyses(match_id: str) -> List[Dict[str, Any]]:
    """获取所有公司的赔率分析"""
    analysis_sql = """
    SELECT
        oar.id,
        oar.match_id,
        oar.company_id,
        oar.company_name,
        oar.initial_home_range,
        oar.initial_home_rule_value,
        oar.initial_draw_range,
        oar.initial_away_range,
        oar.initial_away_rule_value,
        oar.initial_rule_diff,
        oar.initial_recommended_outcome,
        oar.current_home_range,
        oar.current_home_rule_value,
        oar.current_draw_range,
        oar.current_away_range,
        oar.current_away_rule_value,
        oar.current_rule_diff,
        oar.current_recommended_outcome,
        oar.home_power_level,
        oar.away_power_level,
        oar.analyzed_at,
        c.name_cn as company_name,
        c.priority,
        oc.initial_home, oc.initial_draw, oc.initial_away,
        oc.current_home, oc.current_draw, oc.current_away,
        (SELECT t1.tier_level FROM team_power_ratings t1
         WHERE t1.team_id = m.home_team_id AND t1.company_id = oar.company_id AND t1.league_id = m.league_id
           AND t1.division IN (COALESCE(m.division, ''), '')
         ORDER BY CASE WHEN t1.division = COALESCE(m.division, '') THEN 0 ELSE 1 END
         LIMIT 1) AS home_tier_level,
        (SELECT t2.tier_level FROM team_power_ratings t2
         WHERE t2.team_id = m.away_team_id AND t2.company_id = oar.company_id AND t2.league_id = m.league_id
           AND t2.division IN (COALESCE(m.division, ''), '')
         ORDER BY CASE WHEN t2.division = COALESCE(m.division, '') THEN 0 ELSE 1 END
         LIMIT 1) AS away_tier_level
    FROM odds_analysis_results oar
    JOIN matches m ON m.match_id = oar.match_id
    LEFT JOIN companies c ON c.company_id = oar.company_id
    LEFT JOIN odds_changes oc ON oc.match_id = oar.match_id AND oc.company_id = oar.company_id
    WHERE oar.match_id = %s
    ORDER BY oar.analyzed_at DESC
    """
    return execute_query(analysis_sql, (match_id,))


def get_asian_handicap_odds(match_id: str) -> Optional[Dict[str, Any]]:
    """获取亚盘赔率数据（澳门主盘口）"""
    sql = """
    SELECT ah.initial_home_odds, ah.initial_handicap_line, ah.initial_away_odds,
           ah.current_home_odds, ah.current_handicap_line, ah.current_away_odds,
           ah.company_id, ah.scraped_at
    FROM asian_handicap_odds ah
    WHERE ah.match_id = %s AND ah.company_id = 80
    LIMIT 1
    """
    result = execute_query(sql, (match_id,))
    return result[0] if result else None


__all__ = [
    "get_asian_handicap_odds",
    "get_match_basic_info",
    "resolve_canonical_match_id",
    "get_team_standings",
    "get_team_standings_batch",
    "get_odds_analyses",
]

