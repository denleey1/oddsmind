#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Odds/company helpers extracted from optimized_repository."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Set

from core.exceptions import DatabaseError

if TYPE_CHECKING:
    from .models import OddsModel
    from .optimized_repository import OptimizedOddsRepository


def ensure_all_companies_exist_impl(
    repository: "OptimizedOddsRepository",
    odds_list: List["OddsModel"],
) -> None:
    company_ids_needed = {
        odds.company_id
        for odds in odds_list
        if odds.company_id and odds.company_id > 0
    }
    if not company_ids_needed:
        return

    with repository._cache_lock:
        cached_companies = set(repository._company_cache.keys())
        new_companies = company_ids_needed - cached_companies

    if not new_companies:
        return

    existing_companies = get_existing_companies_impl(repository, list(new_companies))
    missing_companies = new_companies - existing_companies
    if missing_companies:
        create_missing_companies_impl(repository, missing_companies)

    with repository._cache_lock:
        for company_id in new_companies:
            repository._company_cache[company_id] = True


def get_existing_companies_impl(
    repository: "OptimizedOddsRepository",
    company_ids: List[int],
) -> Set[int]:
    if not company_ids:
        return set()

    placeholders = ", ".join(["%s"] * len(company_ids))
    query = f"SELECT company_id FROM companies WHERE company_id IN ({placeholders})"
    results = repository.db.execute_query(query, company_ids, fetch="all")
    return {row["company_id"] for row in results} if results else set()


def create_missing_companies_impl(
    repository: "OptimizedOddsRepository",
    company_ids: Set[int],
) -> None:
    if not company_ids:
        return

    from .models import CompanyModel

    companies_to_create = [
        CompanyModel(
            company_id=company_id,
            name_en=f"Company_{company_id}",
            name_cn=f"公司_{company_id}",
            country="Unknown",
            website="",
            is_asian=False,
            priority=999,
            is_active=True,
        )
        for company_id in company_ids
    ]

    if not companies_to_create:
        return

    try:
        company_data = []
        for company in companies_to_create:
            data = {key: value for key, value in company.to_db_dict().items() if value is not None}
            company_data.append(
                (
                    data["company_id"],
                    data["name_en"],
                    data["name_cn"],
                    data["country"],
                    data["website"],
                    data["is_asian"],
                    data["priority"],
                    data["is_active"],
                )
            )

        query = """
            INSERT IGNORE INTO companies
            (company_id, name_en, name_cn, country, website, is_asian, priority, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """
        affected = repository.db.execute_many(query, company_data)
        repository.logger.info(
            "Created %s missing companies for company_ids: %s",
            affected,
            sorted(company_ids),
        )
    except Exception as exc:
        repository.logger.error(f"Failed to create missing companies: {exc}")


def _build_empty_match_odds_payload(match_id: int) -> Dict[str, Any]:
    return {
        "match_id": match_id,
        "odds": [],
        "stats": {
            "total_companies": 0,
            "main_companies": 0,
            "avg_home_odds": 0,
            "avg_draw_odds": 0,
            "avg_away_odds": 0,
        },
    }


def get_match_odds_with_stats_impl(
    repository: "OptimizedOddsRepository",
    match_id: int,
) -> Dict[str, Any]:
    try:
        query = """
            SELECT
                eo.*,
                c.name_en as company_name_en,
                c.name_cn as company_name_cn,
                c.is_main,
                c.priority
            FROM european_odds eo
            LEFT JOIN companies c ON eo.company_id = c.company_id
            WHERE eo.match_id = %s
            ORDER BY c.priority ASC, c.company_id ASC
        """

        results = repository.db.execute_query(query, (match_id,), fetch="all")
        if not results:
            return _build_empty_match_odds_payload(match_id)

        from .models import OddsModel

        odds_models = []
        home_odds: List[float] = []
        draw_odds: List[float] = []
        away_odds: List[float] = []
        main_companies_count = 0

        for row in results:
            odds_models.append(OddsModel.from_dict(row))

            if row["current_home"] and row["current_home"] > 0:
                home_odds.append(float(row["current_home"]))
            if row["current_draw"] and row["current_draw"] > 0:
                draw_odds.append(float(row["current_draw"]))
            if row["current_away"] and row["current_away"] > 0:
                away_odds.append(float(row["current_away"]))

            if row["is_main"]:
                main_companies_count += 1

        stats = {
            "total_companies": len(results),
            "main_companies": main_companies_count,
            "avg_home_odds": round(sum(home_odds) / len(home_odds), 3) if home_odds else 0,
            "avg_draw_odds": round(sum(draw_odds) / len(draw_odds), 3) if draw_odds else 0,
            "avg_away_odds": round(sum(away_odds) / len(away_odds), 3) if away_odds else 0,
        }

        return {
            "match_id": match_id,
            "odds": [odds.to_dict() for odds in odds_models],
            "stats": stats,
        }
    except Exception as exc:
        repository.logger.error(f"Failed to get match odds with stats for {match_id}: {exc}")
        return {"match_id": match_id, "odds": [], "stats": {}}


__all__ = [
    "create_missing_companies_impl",
    "ensure_all_companies_exist_impl",
    "get_existing_companies_impl",
    "get_match_odds_with_stats_impl",
]
