#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Odds/company operations extracted from EnhancedDatabaseManager."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Dict, Optional

from core.decorators import log_execution_time
from core.exceptions import DatabaseError
from core.logger import log_performance
from .models import OddsModel

if TYPE_CHECKING:
    from .enhanced_manager import EnhancedDatabaseManager


@log_execution_time()
def store_odds_data_enhanced_impl(
    manager: "EnhancedDatabaseManager",
    match_id: int,
    odds_data: Dict[str, Any],
) -> int:
    if not odds_data or "odds" not in odds_data:
        return 0

    start_time = time.time()

    try:
        with log_performance(manager.logger, f"store_odds_data_enhanced_{match_id}"):
            odds_models = []
            for odds_record in odds_data["odds"]:
                if isinstance(odds_record, dict):
                    normalized_record = odds_record.copy()
                    normalized_record["match_id"] = match_id
                    normalized_record = normalize_odds_data_enhanced_impl(manager, normalized_record)
                    odds_models.append(OddsModel.from_dict(normalized_record))

            if not odds_models:
                return 0

            manager.odds.bulk_upsert_odds_with_company_validation(odds_models, ensure_companies=True)
            execution_time = time.time() - start_time

            with manager._stats_lock:
                manager._operation_stats["odds_operations"] += 1
                manager._operation_stats["total_records_processed"] += len(odds_models)
                update_avg_batch_time_impl(manager, execution_time)

            manager.logger.info(
                "Enhanced odds storage completed for match %s: %s records in %.3fs",
                match_id,
                len(odds_models),
                execution_time,
            )
            return len(odds_models)
    except Exception as exc:
        with manager._stats_lock:
            manager._operation_stats["failed_operations"] += 1
        manager.logger.error(f"Enhanced odds storage failed for match {match_id}: {exc}")
        raise DatabaseError(f"Failed to store enhanced odds data: {str(exc)}")


@log_execution_time()
def store_multiple_odds_data_enhanced_impl(
    manager: "EnhancedDatabaseManager",
    odds_batch: Dict[int, Dict[str, Any]],
    max_batch_size: int = 500,
) -> Dict[int, int]:
    if not odds_batch:
        return {}

    start_time = time.time()
    results: Dict[int, int] = {}

    try:
        all_odds_models = []

        for match_id, odds_data in odds_batch.items():
            if not odds_data or "odds" not in odds_data:
                results[match_id] = 0
                continue

            match_odds_models = []
            for odds_record in odds_data["odds"]:
                if isinstance(odds_record, dict):
                    normalized_record = odds_record.copy()
                    normalized_record["match_id"] = match_id
                    normalized_record = normalize_odds_data_enhanced_impl(manager, normalized_record)
                    match_odds_models.append(OddsModel.from_dict(normalized_record))

            all_odds_models.extend(match_odds_models)
            results[match_id] = len(match_odds_models)

        if all_odds_models:
            with log_performance(manager.logger, f"bulk_odds_enhanced_{len(odds_batch)}_matches"):
                for index in range(0, len(all_odds_models), max_batch_size):
                    batch = all_odds_models[index:index + max_batch_size]
                    manager.odds.bulk_upsert_odds_with_company_validation(batch, ensure_companies=True)

                execution_time = time.time() - start_time

                with manager._stats_lock:
                    manager._operation_stats["odds_operations"] += len(odds_batch)
                    manager._operation_stats["total_records_processed"] += len(all_odds_models)
                    update_avg_batch_time_impl(manager, execution_time)

                manager.logger.info(
                    "Enhanced bulk odds storage completed: %s records for %s matches in %.2fs (%.1f records/sec)",
                    len(all_odds_models),
                    len(odds_batch),
                    execution_time,
                    len(all_odds_models) / execution_time if execution_time else 0.0,
                )

        return results
    except Exception as exc:
        with manager._stats_lock:
            manager._operation_stats["failed_operations"] += 1
        manager.logger.error(f"Enhanced bulk odds storage failed: {exc}")
        raise DatabaseError(f"Failed to store enhanced bulk odds data: {str(exc)}")


def ensure_company_exists_enhanced_impl(
    manager: "EnhancedDatabaseManager",
    company_id: int,
    company_data: Dict[str, Any],
) -> bool:
    try:
        from .models import CompanyModel

        company_info = get_company_from_config_impl(manager, company_id)
        if company_info:
            company = CompanyModel.from_dict(company_info)
        else:
            company = CompanyModel(
                company_id=company_id,
                name_en=company_data.get("company_name", f"Company_{company_id}"),
                name_cn=company_data.get("company_name_cn", f"公司_{company_id}"),
                country="Unknown",
                website="",
                is_main=False,
                is_asian=False,
                priority=999,
                is_active=True,
            )

        created_company, was_created = manager.companies.safe_create_company(company)
        if was_created:
            with manager._stats_lock:
                manager._operation_stats["company_operations"] += 1
            manager.logger.info(
                "Created company %s: %s (%s)",
                company_id,
                created_company.name_cn,
                created_company.name_en,
            )

        return True
    except Exception as exc:
        manager.logger.error(f"Failed to ensure company {company_id} exists: {exc}")
        return False


def normalize_odds_data_enhanced_impl(
    manager: "EnhancedDatabaseManager",
    odds_data: Dict[str, Any],
) -> Dict[str, Any]:
    normalized = odds_data.copy()

    if "company_id" in normalized and normalized["company_id"]:
        try:
            company_id = int(normalized["company_id"])
            if company_id <= 0:
                raise ValueError("Invalid company_id")
            normalized["company_id"] = company_id
        except (ValueError, TypeError):
            manager.logger.warning("Invalid company_id in odds data: %s", normalized.get("company_id"))
            normalized["company_id"] = 0

    if "odds_type" not in normalized:
        normalized["odds_type"] = "1x2"

    if "data_source" not in normalized:
        normalized["data_source"] = "titan007"

    return normalized


def get_company_from_config_impl(
    manager: "EnhancedDatabaseManager",
    company_id: int,
) -> Optional[Dict[str, Any]]:
    try:
        from config.companies_config import COMPANIES_CONFIG

        for company_info in COMPANIES_CONFIG.values():
            if company_info.company_id == company_id:
                return {
                    "company_id": company_info.company_id,
                    "name_en": company_info.name_en,
                    "name_cn": company_info.name_cn,
                    "country": company_info.country,
                    "website": company_info.website,
                    "is_main": company_info.is_main,
                    "is_asian": company_info.is_asian,
                    "priority": company_info.priority,
                    "is_active": company_info.is_active,
                }
    except Exception as exc:
        manager.logger.debug("Could not get company %s from config: %s", company_id, exc)

    return None


def update_avg_batch_time_impl(manager: "EnhancedDatabaseManager", execution_time: float) -> None:
    current_avg = manager._operation_stats["avg_batch_time"]
    operations = manager._operation_stats["odds_operations"]

    if operations == 1:
        manager._operation_stats["avg_batch_time"] = execution_time
    else:
        manager._operation_stats["avg_batch_time"] = (
            (current_avg * (operations - 1) + execution_time) / operations
        )


__all__ = [
    "ensure_company_exists_enhanced_impl",
    "get_company_from_config_impl",
    "normalize_odds_data_enhanced_impl",
    "store_multiple_odds_data_enhanced_impl",
    "store_odds_data_enhanced_impl",
    "update_avg_batch_time_impl",
]
