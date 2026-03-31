#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Detection helpers for matches requiring odds re-analysis."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List


def collect_matches_requiring_analysis(
    execute_query: Callable[..., List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """
    Detect matches with fresh odds changes or missing analysis results.

    Extracted from ``MonitoringCoordinator.monitor_odds_changes``.
    """
    sql_1x2_changed = """
    SELECT DISTINCT
        oc.match_id,
        m.home_team_name,
        m.away_team_name,
        m.league_id,
        MIN(m.match_time) AS match_time,
        COUNT(DISTINCT oc.company_id) AS changed_companies,
        MAX(oc.last_updated) AS latest_change_time,
        COALESCE(MAX(oar.analyzed_at), '1900-01-01') AS latest_analysis_time
    FROM odds_changes oc
    JOIN matches m ON m.match_id = oc.match_id
    LEFT JOIN odds_analysis_results oar ON oar.match_id = oc.match_id AND oar.company_id = oc.company_id
    WHERE oc.last_updated >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
      AND m.match_status IN ('scheduled', 'live')
    GROUP BY oc.match_id, m.home_team_name, m.away_team_name, m.league_id
    HAVING MAX(oc.last_updated) > COALESCE(MAX(oar.analyzed_at), '1900-01-01')
    """

    sql_1x2_unanalyzed = """
    SELECT DISTINCT
        oc.match_id,
        m.home_team_name,
        m.away_team_name,
        m.league_id,
        MIN(m.match_time) AS match_time,
        COUNT(DISTINCT oc.company_id) AS changed_companies,
        MAX(oc.last_updated) AS latest_change_time,
        COALESCE(MAX(oar.analyzed_at), '1900-01-01') AS latest_analysis_time
    FROM odds_changes oc
    JOIN matches m ON m.match_id = oc.match_id
    LEFT JOIN odds_analysis_results oar ON oar.match_id = oc.match_id AND oar.company_id = oc.company_id
    WHERE oc.initial_home IS NOT NULL
      AND oc.initial_draw IS NOT NULL
      AND oc.initial_away IS NOT NULL
      AND m.match_status IN ('scheduled', 'live')
      AND m.match_time BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 2 DAY)
      AND oar.match_id IS NULL
    GROUP BY oc.match_id, m.home_team_name, m.away_team_name, m.league_id
    ORDER BY MIN(m.match_time) ASC
    LIMIT 60
    """

    sql_ou = """
    SELECT DISTINCT
        ou.match_id,
        m.home_team_name,
        m.away_team_name,
        m.league_id,
        MIN(m.match_time) AS match_time,
        COUNT(DISTINCT ou.company_id) AS changed_companies,
        MAX(ou.last_updated) AS latest_change_time,
        COALESCE(MAX(oar.analyzed_at), '1900-01-01') AS latest_analysis_time
    FROM over_under_odds_changes ou
    JOIN matches m ON m.match_id = ou.match_id
    LEFT JOIN odds_analysis_results oar ON oar.match_id = ou.match_id AND oar.company_id = ou.company_id
    WHERE ou.last_updated >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
      AND m.match_status IN ('scheduled', 'live')
    GROUP BY ou.match_id, m.home_team_name, m.away_team_name, m.league_id
    HAVING MAX(ou.last_updated) > COALESCE(MAX(oar.analyzed_at), '1900-01-01')
    """

    combined: Dict[int, Dict[str, Any]] = {}

    def merge(records: List[Dict[str, Any]] | None, source: str) -> None:
        for record in records or []:
            match_id = record['match_id']
            entry = combined.get(match_id)
            if not entry:
                entry = {
                    'match_id': match_id,
                    'home_team_name': record.get('home_team_name'),
                    'away_team_name': record.get('away_team_name'),
                    'league_id': record.get('league_id'),
                    'match_time': record.get('match_time'),
                    'changed_companies': 0,
                    'latest_change_time': record.get('latest_change_time'),
                    'latest_analysis_time': record.get('latest_analysis_time'),
                    'sources': set(),
                }
            entry['changed_companies'] = entry.get('changed_companies', 0) + record.get('changed_companies', 0)
            latest_change = record.get('latest_change_time')
            if latest_change and (entry.get('latest_change_time') is None or latest_change > entry['latest_change_time']):
                entry['latest_change_time'] = latest_change
            latest_analysis = record.get('latest_analysis_time')
            if latest_analysis and (entry.get('latest_analysis_time') is None or latest_analysis > entry['latest_analysis_time']):
                entry['latest_analysis_time'] = latest_analysis
            entry['sources'].add(source)
            combined[match_id] = entry

    merge(execute_query(sql_1x2_changed), '1x2_changed')
    merge(execute_query(sql_1x2_unanalyzed), '1x2_unanalyzed')
    merge(execute_query(sql_ou), 'over_under')

    changes_list: List[Dict[str, Any]] = []
    far_future = datetime(2099, 1, 1)
    for entry in combined.values():
        entry.pop('sources', None)
        changes_list.append(entry)
    # Sort by match_time ascending so near-kickoff matches are analyzed first
    changes_list.sort(key=lambda x: x.get('match_time') or far_future)
    return changes_list


__all__ = ["collect_matches_requiring_analysis"]
