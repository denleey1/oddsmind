#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Odds-change persistence helpers extracted from monitoring coordinator."""

from __future__ import annotations

from typing import Any, List, TYPE_CHECKING

from app_database import execute_query

if TYPE_CHECKING:
    from database.manager import DatabaseManager


def sync_write_odds_changes(
    db_manager: "DatabaseManager",
    odds_changes: List[Any],
    logger,
) -> int:
    """
    Synchronously persist odds changes, bypassing async batch queue.

    Behavior intentionally mirrors the legacy coordinator implementation.
    """
    if not odds_changes:
        return 0

    try:
        company_ids = set(change.company_id for change in odds_changes if change.company_id)
        if company_ids:
            db_manager._ensure_companies_exist(company_ids)

        query = """
            INSERT INTO odds_changes (
                match_id, company_id, 
                initial_home, initial_draw, initial_away, initial_return_rate,
                current_home, current_draw, current_away, current_return_rate, 
                last_updated
            ) VALUES (
                %(match_id)s, %(company_id)s,
                %(initial_home)s, %(initial_draw)s, %(initial_away)s, %(initial_return_rate)s,
                %(current_home)s, %(current_draw)s, %(current_away)s, %(current_return_rate)s,
                %(last_updated)s
            )
            ON DUPLICATE KEY UPDATE
                initial_home = VALUES(initial_home),
                initial_draw = VALUES(initial_draw),
                initial_away = VALUES(initial_away),
                initial_return_rate = VALUES(initial_return_rate),
                current_home = VALUES(current_home),
                current_draw = VALUES(current_draw),
                current_away = VALUES(current_away),
                current_return_rate = VALUES(current_return_rate),
                last_updated = VALUES(last_updated);
        """

        data_to_save = [change.to_db_dict() for change in odds_changes]
        affected_rows = db_manager.odds_changes.db.execute_many(query, data_to_save)
        logger.info("同步写入 odds_changes: %s 条记录（绕过BatchWriter队列）", affected_rows)
        return affected_rows

    except Exception as exc:
        logger.error("同步写入 odds_changes 失败: %s", exc, exc_info=True)
        return 0


def verify_odds_changes_in_db(
    odds_changes: List[Any],
    logger,
    *,
    batch_size: int = 100,
) -> int:
    """Verify persisted odds-change rows exist in DB."""
    if not odds_changes:
        return 0

    try:
        match_company_pairs = [
            (change.match_id, change.company_id)
            for change in odds_changes
        ]

        total_found = 0
        for index in range(0, len(match_company_pairs), batch_size):
            batch = match_company_pairs[index:index + batch_size]
            if not batch:
                continue

            where_clauses = []
            params: List[Any] = []
            for match_id, company_id in batch:
                where_clauses.append("(match_id = %s AND company_id = %s)")
                params.extend([match_id, company_id])

            query = f"""
                SELECT COUNT(*) as cnt
                FROM odds_changes
                WHERE {' OR '.join(where_clauses)}
            """

            result = execute_query(query, tuple(params))
            if result and result[0]:
                total_found += result[0].get('cnt', 0)

        return total_found

    except Exception as exc:
        logger.error("验证 odds_changes 数据库写入失败: %s", exc, exc_info=True)
        return 0


__all__ = ["sync_write_odds_changes", "verify_odds_changes_in_db"]
