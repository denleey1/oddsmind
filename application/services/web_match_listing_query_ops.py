#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Query operations for web match-listing endpoints."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List, Sequence

from utils.timezone_utils import now

from app_database import execute_query


def _resolve_time_range(status_filter: str, monitoring_days: int):
    if status_filter == "finished":
        filter_time = now() - timedelta(days=2)
        end_date = now()
        order_direction = "DESC"
    else:
        filter_time = now() - timedelta(hours=3)
        end_date = now() + timedelta(days=monitoring_days)
        order_direction = "ASC"
    return filter_time, end_date, order_direction


def fetch_today_matches_rows(
    status_filter: str,
    monitored_leagues: Sequence[int],
    monitoring_days: int,
    monitor_all_leagues: bool,
) -> List[Dict[str, Any]]:
    filter_time, end_date, order_direction = _resolve_time_range(status_filter, monitoring_days)

    if monitor_all_leagues or not monitored_leagues:
        sql = """
            SELECT
                m.match_id,
                m.match_time,
                m.updated_at as match_updated_at,
                m.league_id,
                m.home_team_id,
                m.away_team_id,
                m.league_id,
                m.match_status,
                m.home_score,
                m.away_score,
                COALESCE(l.name_cn, l.name_en) as league_name,
                t_home.name_cn as home_team_name_cn,
                t_home.name_en as home_team_name,
                t_away.name_cn as away_team_name_cn,
                t_away.name_en as away_team_name,
                fa.recommended_outcome as recommendation,
                fa.confidence_level as recommendation_confidence,
                fa.max_score,
                fa.home_win_score,
                fa.home_confidence_level,
                fa.home_confidence_interval,
                fa.home_odds_suggestions,
                fa.draw_score,
                fa.draw_confidence_level,
                fa.draw_confidence_interval,
                fa.draw_odds_suggestions,
                fa.away_win_score,
                fa.away_confidence_level,
                fa.away_confidence_interval,
                fa.away_odds_suggestions,
                fa.pull_direction,
                fa.pull_description,
                fa.prompts_json,
                fa.absent_players_json,
                fa.briefing,
                fa.upcoming_json,
                fa.distribution_node,
                l.total_rounds,
                m.round_number,
                m.season,
                NULL as group_name,
                s_home.position as home_position,
                s_home.points as home_points,
                s_home.played as home_played,
                s_home.wins as home_wins,
                s_home.draws as home_draws,
                s_home.losses as home_losses,
                s_away.position as away_position,
                s_away.points as away_points,
                s_away.played as away_played,
                s_away.wins as away_wins,
                s_away.draws as away_draws,
                s_away.losses as away_losses,
                CASE WHEN oar_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_analysis,
                CASE WHEN oc_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_changes,
                CASE WHEN fa.match_id IS NULL THEN 0 ELSE 1 END as has_fundamental
            FROM matches m
            JOIN leagues l ON l.league_id = m.league_id
            JOIN teams t_home ON t_home.team_id = m.home_team_id
            JOIN teams t_away ON t_away.team_id = m.away_team_id
            LEFT JOIN standings s_home ON (
                s_home.team_id = m.home_team_id
                AND s_home.league_id = m.league_id
                AND s_home.standing_type = 'overall'
            )
            LEFT JOIN standings s_away ON (
                s_away.team_id = m.away_team_id
                AND s_away.league_id = m.league_id
                AND s_away.standing_type = 'overall'
            )
            LEFT JOIN fundamental_analysis fa ON fa.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_analysis_results) oar_exists
                ON oar_exists.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_changes) oc_exists
                ON oc_exists.match_id = m.match_id
            WHERE m.match_time >= %s
              AND m.match_time <= %s
              {}
            ORDER BY m.match_time {}
        """

        status_condition = ""
        if status_filter:
            status_condition = "AND m.match_status = %s"

        sql = sql.format(status_condition, order_direction)
        if status_filter:
            params = (filter_time, end_date, status_filter)
        else:
            params = (filter_time, end_date)
    else:
        sql = """
            SELECT
                m.match_id,
                m.match_time,
                m.updated_at as match_updated_at,
                m.league_id,
                m.home_team_id,
                m.away_team_id,
                m.league_id,
                m.match_status,
                m.home_score,
                m.away_score,
                COALESCE(l.name_cn, l.name_en) as league_name,
                t_home.name_cn as home_team_name_cn,
                t_home.name_en as home_team_name,
                t_away.name_cn as away_team_name_cn,
                t_away.name_en as away_team_name,
                fa.recommended_outcome as recommendation,
                fa.confidence_level as recommendation_confidence,
                fa.max_score,
                fa.home_win_score,
                fa.home_confidence_level,
                fa.home_confidence_interval,
                fa.home_odds_suggestions,
                fa.draw_score,
                fa.draw_confidence_level,
                fa.draw_confidence_interval,
                fa.draw_odds_suggestions,
                fa.away_win_score,
                fa.away_confidence_level,
                fa.away_confidence_interval,
                fa.away_odds_suggestions,
                fa.pull_direction,
                fa.pull_description,
                fa.prompts_json,
                fa.absent_players_json,
                fa.briefing,
                fa.upcoming_json,
                fa.distribution_node,
                l.total_rounds,
                m.round_number,
                m.season,
                NULL as group_name,
                s_home.position as home_position,
                s_home.points as home_points,
                s_home.played as home_played,
                s_home.wins as home_wins,
                s_home.draws as home_draws,
                s_home.losses as home_losses,
                s_away.position as away_position,
                s_away.points as away_points,
                s_away.played as away_played,
                s_away.wins as away_wins,
                s_away.draws as away_draws,
                s_away.losses as away_losses,
                CASE WHEN oar_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_analysis,
                CASE WHEN oc_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_changes,
                CASE WHEN fa.match_id IS NULL THEN 0 ELSE 1 END as has_fundamental
            FROM matches m
            JOIN leagues l ON l.league_id = m.league_id
            JOIN teams t_home ON t_home.team_id = m.home_team_id
            JOIN teams t_away ON t_away.team_id = m.away_team_id
            LEFT JOIN standings s_home ON (
                s_home.team_id = m.home_team_id
                AND s_home.league_id = m.league_id
                AND s_home.standing_type = 'overall'
            )
            LEFT JOIN standings s_away ON (
                s_away.team_id = m.away_team_id
                AND s_away.league_id = m.league_id
                AND s_away.standing_type = 'overall'
            )
            LEFT JOIN fundamental_analysis fa ON fa.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_analysis_results) oar_exists
                ON oar_exists.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_changes) oc_exists
                ON oc_exists.match_id = m.match_id
            WHERE m.league_id IN %(leagues)s
              AND m.match_time >= %(start)s
              AND m.match_time <= %(end)s
              {}
            ORDER BY m.match_time {}
        """

        status_condition = ""
        if status_filter:
            status_condition = "AND m.match_status = %(status)s"

        sql = sql.format(status_condition, order_direction)
        params = {"leagues": tuple(monitored_leagues), "start": filter_time, "end": end_date}
        if status_filter:
            params["status"] = status_filter

    return execute_query(sql, params)


def fetch_public_today_matches_rows(
    status_filter: str,
    monitored_leagues: Sequence[int],
    monitoring_days: int,
    monitor_all_leagues: bool,
) -> List[Dict[str, Any]]:
    filter_time, end_date, order_direction = _resolve_time_range(status_filter, monitoring_days)

    if monitor_all_leagues or not monitored_leagues:
        sql = """
            SELECT
                m.match_id,
                m.match_time,
                m.updated_at as match_updated_at,
                m.league_id,
                m.home_team_id,
                m.away_team_id,
                m.match_status,
                m.home_score,
                m.away_score,
                COALESCE(l.name_cn, l.name_en) as league_name,
                t_home.name_cn as home_team_name_cn,
                t_home.name_en as home_team_name,
                t_away.name_cn as away_team_name_cn,
                t_away.name_en as away_team_name,
                l.total_rounds,
                m.round_number,
                m.season,
                CASE WHEN oar_flag.match_id IS NOT NULL THEN 1 ELSE 0 END as has_odds_analysis,
                CASE WHEN oc_flag.match_id IS NOT NULL THEN 1 ELSE 0 END as has_odds_changes,
                CASE WHEN fa_flag.match_id IS NOT NULL THEN 1 ELSE 0 END as has_fundamental
            FROM matches m
            LEFT JOIN leagues l ON m.league_id = l.league_id
            LEFT JOIN teams t_home ON m.home_team_id = t_home.team_id
            LEFT JOIN teams t_away ON m.away_team_id = t_away.team_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_analysis_results) oar_flag ON oar_flag.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_changes) oc_flag ON oc_flag.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM fundamental_analysis) fa_flag ON fa_flag.match_id = m.match_id
            WHERE m.match_time >= %s
              AND m.match_time <= %s
              AND m.match_time IS NOT NULL
              {}
            ORDER BY m.match_time {}
        """

        status_condition = ""
        if status_filter:
            status_condition = "AND m.match_status = %s"

        sql = sql.format(status_condition, order_direction)
        if status_filter:
            params = (filter_time, end_date, status_filter)
        else:
            params = (filter_time, end_date)
    else:
        sql = """
            SELECT
                m.match_id,
                m.match_time,
                m.updated_at as match_updated_at,
                m.league_id,
                m.home_team_id,
                m.away_team_id,
                m.match_status,
                m.home_score,
                m.away_score,
                COALESCE(l.name_cn, l.name_en) as league_name,
                t_home.name_cn as home_team_name_cn,
                t_home.name_en as home_team_name,
                t_away.name_cn as away_team_name_cn,
                t_away.name_en as away_team_name,
                l.total_rounds,
                m.round_number,
                m.season,
                CASE WHEN oar_flag.match_id IS NOT NULL THEN 1 ELSE 0 END as has_odds_analysis,
                CASE WHEN oc_flag.match_id IS NOT NULL THEN 1 ELSE 0 END as has_odds_changes,
                CASE WHEN fa_flag.match_id IS NOT NULL THEN 1 ELSE 0 END as has_fundamental
            FROM matches m
            LEFT JOIN leagues l ON m.league_id = l.league_id
            LEFT JOIN teams t_home ON m.home_team_id = t_home.team_id
            LEFT JOIN teams t_away ON m.away_team_id = t_away.team_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_analysis_results) oar_flag ON oar_flag.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_changes) oc_flag ON oc_flag.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM fundamental_analysis) fa_flag ON fa_flag.match_id = m.match_id
            WHERE m.league_id IN %(leagues)s
              AND m.match_time >= %(start)s
              AND m.match_time <= %(end)s
              AND m.match_time IS NOT NULL
              {}
            ORDER BY m.match_time {}
        """

        status_condition = ""
        if status_filter:
            status_condition = "AND m.match_status = %(status)s"

        sql = sql.format(status_condition, order_direction)
        params = {"leagues": tuple(monitored_leagues), "start": filter_time, "end": end_date}
        if status_filter:
            params["status"] = status_filter

    return execute_query(sql, params)


__all__ = ["fetch_public_today_matches_rows", "fetch_today_matches_rows"]

