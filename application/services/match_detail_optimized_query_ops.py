#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Query helpers extracted from match_detail_optimized service."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app_database import execute_query
from utils.cache import cache_get, cache_set, get_cache_key


def get_match_with_standings_impl(service, match_id: str, logger) -> Optional[Dict[str, Any]]:
    cache_key = get_cache_key("match_basic_with_standings", match_id=match_id)
    cached = cache_get(cache_key)
    if cached is not None:
        logger.debug("[优化] 缓存命中: 比赛基本信息 %s", match_id)
        return cached

    sql = """
    SELECT
        m.match_id, m.match_time, m.league_id,
        m.home_team_id, m.away_team_id,
        m.match_status, m.home_score, m.away_score, m.round_number,
        l.name_cn as league_name, l.total_rounds,
        ht.name_cn as home_team_name_cn, ht.name_en as home_team_name,
        at.name_cn as away_team_name_cn, at.name_en as away_team_name,
        fa.recommended_outcome as recommendation,
        fa.confidence_level as recommendation_confidence,
        fa.max_score, fa.home_win_score, fa.home_confidence_level, fa.home_confidence_interval,
        fa.home_odds_suggestions, fa.draw_score, fa.draw_confidence_level, fa.draw_confidence_interval,
        fa.draw_odds_suggestions, fa.away_win_score, fa.away_confidence_level, fa.away_confidence_interval,
        fa.away_odds_suggestions,
        fa.distribution_node,
        sh.position as home_position, sh.points as home_points,
        sh.played as home_played, sh.wins as home_wins,
        sh.draws as home_draws, sh.losses as home_losses,
        sa.position as away_position, sa.points as away_points,
        sa.played as away_played, sa.wins as away_wins,
        sa.draws as away_draws, sa.losses as away_losses
    FROM matches m
    JOIN leagues l ON l.league_id = m.league_id
    LEFT JOIN teams ht ON ht.team_id = m.home_team_id
    LEFT JOIN teams at ON at.team_id = m.away_team_id
    LEFT JOIN fundamental_analysis fa ON fa.match_id = m.match_id
    LEFT JOIN standings sh ON sh.team_id = m.home_team_id
        AND sh.league_id = m.league_id AND sh.standing_type = 'overall'
    LEFT JOIN standings sa ON sa.team_id = m.away_team_id
        AND sa.league_id = m.league_id AND sa.standing_type = 'overall'
    WHERE m.match_id = %s
    """
    result = execute_query(sql, (match_id,))
    match_data = result[0] if result else None

    if match_data:
        cache_set(cache_key, match_data, expire=300)

    return match_data


def get_top_company_analyses_impl(service, match_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    priority_ids = [cid for cid in service.priority_company_ids if cid]

    if not priority_ids:
        sql = """
        SELECT
            oar.company_id, oar.company_name,
            oar.initial_home_range, oar.initial_home_rule_value,
            oar.initial_draw_range, oar.initial_away_range, oar.initial_away_rule_value,
            oar.initial_rule_diff, oar.initial_recommended_outcome,
            oar.current_home_range, oar.current_home_rule_value,
            oar.current_draw_range, oar.current_away_range, oar.current_away_rule_value,
            oar.current_rule_diff, oar.current_recommended_outcome,
            oar.home_power_level, oar.away_power_level, oar.analyzed_at,
            c.name_cn as company_name_cn,
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
        LIMIT %s
        """
        return execute_query(sql, (match_id, limit))

    base_sql = """
    SELECT
        oar.company_id, oar.company_name,
        oar.initial_home_range, oar.initial_home_rule_value,
        oar.initial_draw_range, oar.initial_away_range, oar.initial_away_rule_value,
        oar.initial_rule_diff, oar.initial_recommended_outcome,
        oar.current_home_range, oar.current_home_rule_value,
        oar.current_draw_range, oar.current_away_range, oar.current_away_rule_value,
        oar.current_rule_diff, oar.current_recommended_outcome,
        oar.home_power_level, oar.away_power_level, oar.analyzed_at,
        c.name_cn as company_name_cn,
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
    """

    priority_placeholders = ",".join(["%s"] * len(priority_ids))
    sql1 = base_sql + f" AND oar.company_id IN ({priority_placeholders}) LIMIT %s"
    params1 = (match_id,) + tuple(priority_ids) + (len(priority_ids) * 2,)
    priority_results = list(execute_query(sql1, params1) or [])

    priority_map = {cid: idx for idx, cid in enumerate(service.priority_company_ids)}

    def get_sort_key(row: Dict[str, Any]):
        company_id = row.get("company_id")
        if company_id is None:
            return (9999, 0)
        try:
            company_id_int = int(company_id)
        except (ValueError, TypeError):
            return (9999, 0)
        return (priority_map.get(company_id_int, 9999), company_id_int)

    priority_results.sort(key=get_sort_key)

    if len(priority_results) >= limit:
        return priority_results[:limit]

    remaining = limit - len(priority_results)
    if remaining > 0:
        sql2 = base_sql + f" AND oar.company_id NOT IN ({priority_placeholders}) LIMIT %s"
        params2 = (match_id,) + tuple(priority_ids) + (remaining,)
        other_results = list(execute_query(sql2, params2) or [])
        priority_results.extend(other_results)

    return priority_results[:limit]


def get_company_count_impl(match_id: str) -> int:
    sql = "SELECT COUNT(*) as cnt FROM odds_analysis_results WHERE match_id = %s"
    result = execute_query(sql, (match_id,))
    return result[0]["cnt"] if result else 0


__all__ = [
    "get_company_count_impl",
    "get_match_with_standings_impl",
    "get_top_company_analyses_impl",
]
