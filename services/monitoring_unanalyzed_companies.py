#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helpers for handling companies with odds data but missing analysis."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Set


def verify_priority_companies_analyzed(
    execute_query: Callable[..., List[Dict[str, Any]]],
    logger,
    match_ids: List[int],
    priority_companies: Set[int],
) -> None:
    """Verify priority companies have analysis results."""
    if not match_ids or not priority_companies:
        return

    try:
        placeholders = ','.join(['%s'] * len(match_ids))
        priority_placeholders = ','.join(['%s'] * len(priority_companies))

        query = f"""
            SELECT DISTINCT
                oc.match_id,
                oc.company_id,
                c.name_cn as company_name,
                CASE WHEN oar.match_id IS NOT NULL THEN 1 ELSE 0 END as is_analyzed
            FROM odds_changes oc
            LEFT JOIN odds_analysis_results oar ON oar.match_id = oc.match_id AND oar.company_id = oc.company_id
            LEFT JOIN companies c ON c.company_id = oc.company_id
            WHERE oc.match_id IN ({placeholders})
              AND oc.company_id IN ({priority_placeholders})
              AND oc.initial_home IS NOT NULL
        """

        results = execute_query(query, tuple(match_ids) + tuple(priority_companies))
        if not results:
            return

        still_missing = []
        for row in results:
            if not row.get('is_analyzed'):
                still_missing.append(
                    f"{row.get('company_name', 'unknown')}({row['company_id']})-match{row['match_id']}"
                )

        if still_missing:
            logger.error(
                "Priority companies still missing analysis after remediation: %s%s",
                ', '.join(still_missing[:10]),
                '...' if len(still_missing) > 10 else '',
            )
        else:
            logger.info("All priority companies have analysis results")

    except Exception as exc:
        logger.error("Failed to verify priority company analysis: %s", exc, exc_info=True)


def check_and_analyze_unanalyzed_companies(
    execute_query: Callable[..., List[Dict[str, Any]]],
    logger,
    runtime,
    match_ids: List[int],
    verify_priority_callback: Callable[[List[int], Set[int]], None],
) -> None:
    """Find and analyze companies that have odds data but no analysis rows."""
    if not match_ids:
        return

    try:
        logger.info("Checking companies that have odds rows but missing analysis rows")

        from app_constants import PERSONAL_COMPANY_ORDER

        priority_companies = set(PERSONAL_COMPANY_ORDER)
        placeholders = ','.join(['%s'] * len(match_ids))
        priority_placeholders = ','.join(['%s'] * len(priority_companies))

        query_priority = f"""
            SELECT DISTINCT
                oc.match_id,
                oc.company_id,
                c.name_cn as company_name
            FROM odds_changes oc
            JOIN matches m ON m.match_id = oc.match_id
            LEFT JOIN odds_analysis_results oar ON oar.match_id = oc.match_id AND oar.company_id = oc.company_id
            LEFT JOIN companies c ON c.company_id = oc.company_id
            WHERE oc.match_id IN ({placeholders})
              AND oc.company_id IN ({priority_placeholders})
              AND m.match_status IN ('scheduled', 'live')
              AND oc.initial_home IS NOT NULL
              AND oc.initial_away IS NOT NULL
              AND oc.initial_draw IS NOT NULL
              AND oar.match_id IS NULL
        """

        priority_results = execute_query(query_priority, tuple(match_ids) + tuple(priority_companies))

        query_others = f"""
            SELECT DISTINCT
                oc.match_id,
                oc.company_id,
                c.name_cn as company_name
            FROM odds_changes oc
            JOIN matches m ON m.match_id = oc.match_id
            LEFT JOIN odds_analysis_results oar ON oar.match_id = oc.match_id AND oar.company_id = oc.company_id
            LEFT JOIN companies c ON c.company_id = oc.company_id
            WHERE oc.match_id IN ({placeholders})
              AND oc.company_id NOT IN ({priority_placeholders})
              AND m.match_status IN ('scheduled', 'live')
              AND oc.initial_home IS NOT NULL
              AND oc.initial_away IS NOT NULL
              AND oc.initial_draw IS NOT NULL
              AND oar.match_id IS NULL
            LIMIT 100
        """

        other_results = execute_query(query_others, tuple(match_ids) + tuple(priority_companies))
        all_results = (priority_results or []) + (other_results or [])
        if not all_results:
            logger.info("No companies with missing analysis found")
            return

        match_analysis_map: Dict[int, List[int]] = {}
        priority_missing_log: List[str] = []

        for row in all_results:
            match_id = row['match_id']
            company_id = row['company_id']
            company_name = row.get('company_name', f'company-{company_id}')

            if match_id not in match_analysis_map:
                match_analysis_map[match_id] = []
            match_analysis_map[match_id].append(company_id)

            if company_id in priority_companies:
                priority_missing_log.append(f"match{match_id}-{company_name}({company_id})")

        if priority_missing_log:
            logger.error(
                "Priority companies missing analysis: %s",
                ', '.join(priority_missing_log),
            )

        for match_id, company_ids in match_analysis_map.items():
            priority_in_match = [cid for cid in company_ids if cid in priority_companies]
            other_in_match = [cid for cid in company_ids if cid not in priority_companies]
            logger.warning(
                "Match %s has %s companies with odds but no analysis: priority=%s, others=%s",
                match_id,
                len(company_ids),
                priority_in_match,
                len(other_in_match),
            )

        from odds_analysis.realtime_analyzer import RealtimeOddsAnalyzer

        match_ids_to_analyze = list(match_analysis_map.keys())
        logger.info("Preparing to analyze %s matches with missing company analysis", len(match_ids_to_analyze))

        def _analyze_async():
            analyzer = None
            try:
                analyzer = RealtimeOddsAnalyzer(max_workers=min(5, len(match_ids_to_analyze)))
                results = analyzer.batch_analyze_matches(match_ids_to_analyze)

                success_count = sum(1 for item in results if item.get('success', False))
                logger.info(
                    "Unanalyzed-company analysis completed: %s/%s",
                    success_count,
                    len(match_ids_to_analyze),
                )
                verify_priority_callback(match_ids_to_analyze, priority_companies)
            except Exception as exc:
                logger.error("Failed analyzing companies without results: %s", exc, exc_info=True)
            finally:
                if analyzer is not None:
                    try:
                        analyzer.shutdown()
                    except Exception:
                        logger.debug("Failed to shutdown analyzer after async run", exc_info=True)

        try:
            runtime.executor.submit(_analyze_async)
        except RuntimeError as exc:
            logger.warning("Executor unavailable, skip unanalyzed-company async task: %s", exc)
        except Exception as exc:
            logger.error("Failed to submit unanalyzed-company async task: %s", exc, exc_info=True)

    except Exception as exc:
        logger.error("Failed checking unanalyzed companies: %s", exc, exc_info=True)


__all__ = [
    "check_and_analyze_unanalyzed_companies",
    "verify_priority_companies_analyzed",
]
