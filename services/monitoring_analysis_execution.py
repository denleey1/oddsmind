#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Execution helpers extracted from MonitoringCoordinator analysis internals."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def find_completed_rounds(execute_query_fn, logger) -> List[Dict[str, Any]]:
    sql = """
    SELECT DISTINCT 
        m.league_id,
        m.round_number,
        l.name_cn AS league_name,
        COUNT(DISTINCT m.match_id) AS match_count
    FROM matches m
    JOIN leagues l ON l.league_id = m.league_id
    WHERE m.match_status = 'finished'
      AND m.updated_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
      AND NOT EXISTS (
          SELECT 1 FROM team_power_ratings tpr
          WHERE tpr.league_id = m.league_id
            AND tpr.round_number = m.round_number
            AND tpr.season = m.season
      )
    GROUP BY m.league_id, m.round_number, l.name_cn
    """
    _ = logger
    return execute_query_fn(sql)


def calculate_strength(
    execute_query_fn,
    logger,
    league_id: int,
    round_number: int,
) -> Tuple[bool, Optional[str]]:
    season_sql = """
    SELECT DISTINCT season
    FROM matches
    WHERE league_id = %s AND round_number = %s
    LIMIT 1
    """

    result = execute_query_fn(season_sql, (league_id, round_number))
    if not result:
        logger.error("Cannot determine season for league %s round %s", league_id, round_number)
        return False, None

    season = result[0]['season']
    from calculation.mysql_general_strength_calculator import MySQLGeneralStrengthCalculator

    calculator = MySQLGeneralStrengthCalculator(league_id=league_id, season=season)
    try:
        summary = calculator.calculate()
        status = summary.get('status', 'ok') if isinstance(summary, dict) else 'ok'

        if status == 'ok':
            logger.info(
                "Strength calculation successful for league %s season %s round %s",
                league_id,
                season,
                round_number,
            )
            return True, season

        logger.error(
            "Strength calculation incomplete for league %s season %s round %s: status=%s, details=%s",
            league_id,
            season,
            round_number,
            status,
            summary.get('errors') if isinstance(summary, dict) else None,
        )
        return False, season
    except Exception as exc:
        logger.error(
            "Strength calculation failed for league %s season %s round %s: %s",
            league_id,
            season,
            round_number,
            str(exc),
        )
        return False, season


def reanalyse_league_matches(execute_query_fn, logger, league_id: int) -> None:
    """Re-run odds analysis so stored results use the latest power ratings."""
    sql = """
    SELECT DISTINCT oc.match_id
    FROM odds_changes oc
    JOIN matches m ON m.match_id = oc.match_id
    WHERE m.league_id = %s
      AND m.match_status IN ('scheduled', 'live')
    """

    matches = execute_query_fn(sql, (league_id,))
    if not matches:
        return

    match_ids = [m['match_id'] for m in matches]
    logger.info(
        "Re-analysing %d upcoming matches in league %s after strength update",
        len(match_ids),
        league_id,
    )

    from odds_analysis.realtime_analyzer import RealtimeOddsAnalyzer
    import os

    max_workers = int(os.getenv("EXECUTOR_MAX_WORKERS", "16"))
    analyzer = RealtimeOddsAnalyzer(max_workers=max_workers)
    try:
        analyzer.batch_analyze_matches(match_ids)
    finally:
        try:
            analyzer.shutdown()
        except Exception:
            pass


def analyse_matches_with_changes(fundamental_service, logger, changed_matches: List[Dict[str, Any]]) -> None:
    """
    Ensure fundamental/odds analyses are refreshed for matches with odds movements.

    [性能优化] 限制每次分析的比赛数量和并发数，避免数据库过载
    """
    max_matches_per_batch = 60
    if len(changed_matches) > max_matches_per_batch:
        logger.warning(
            f"需要分析的比赛数量({len(changed_matches)})超过限制，只分析前{max_matches_per_batch}场"
        )
        changed_matches = changed_matches[:max_matches_per_batch]

    for match in changed_matches:
        match_id = str(match['match_id'])
        if not fundamental_service.has_existing_analysis(match_id):
            fundamental_service.analyze_single_match(match_id)

    match_ids = [m['match_id'] for m in changed_matches]
    from odds_analysis.realtime_analyzer import RealtimeOddsAnalyzer

    max_workers = min(6, len(match_ids))
    analyzer = RealtimeOddsAnalyzer(max_workers=max_workers)
    try:
        results = analyzer.batch_analyze_matches(match_ids)
        success = sum(1 for r in results if r.get('success'))
        logger.info("Realtime odds analysis completed: %s/%s", success, len(match_ids))
    finally:
        try:
            analyzer.shutdown()
        except Exception:
            pass


__all__ = [
    "analyse_matches_with_changes",
    "calculate_strength",
    "find_completed_rounds",
    "reanalyse_league_matches",
]
