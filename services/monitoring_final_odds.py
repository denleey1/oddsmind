#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helpers for syncing final odds of finished matches."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


def sync_final_odds(
    execute_query: Callable[..., List[Dict[str, Any]]],
    logger,
    runtime,
    db_manager,
    odds_record_to_model: Callable[[int, Dict[str, Any]], Optional[Any]],
    *,
    lookback_hours: int = 24,
    match_ids: Optional[List[int]] = None,
    force_update: bool = False,
) -> int:
    """Sync final odds into DB for finished matches."""
    if match_ids is None:
        if force_update:
            sql = """
            SELECT DISTINCT m.match_id
            FROM matches m
            WHERE m.match_status = 'finished'
              AND m.updated_at >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            LIMIT 100
            """
        else:
            sql = """
            SELECT DISTINCT m.match_id
            FROM matches m
            WHERE m.match_status = 'finished'
              AND m.updated_at >= DATE_SUB(NOW(), INTERVAL %s HOUR)
              AND NOT EXISTS (
                  SELECT 1 FROM european_odds eo
                  WHERE eo.match_id = m.match_id
                    AND eo.current_home IS NOT NULL
              )
            LIMIT 100
            """

        matches = execute_query(sql, (lookback_hours,))
        if not matches:
            return 0
        match_ids = [item['match_id'] for item in matches]
    else:
        match_ids = list({int(match_id) for match_id in match_ids})
        if not match_ids:
            return 0

    logger.info("Fetching final odds for %d finished matches", len(match_ids))

    scrape_result = runtime.scraper.scrape_with_all_companies(match_ids)
    if not scrape_result.success or not scrape_result.data:
        logger.warning("Unable to fetch final odds for finished matches")
        return 0

    odds_models: List[Any] = []
    for match_id, result in scrape_result.data.items():
        data = result.data if hasattr(result, 'data') else result
        if not isinstance(data, dict) or 'odds' not in data:
            continue

        for record in data['odds']:
            model = odds_record_to_model(match_id, record)
            if model:
                odds_models.append(model)

    if not odds_models:
        return 0

    saved = db_manager.odds.bulk_upsert_odds_with_company_validation(odds_models)
    logger.info("Persisted %d final odds rows for finished matches", saved)
    return saved


__all__ = ["sync_final_odds"]
