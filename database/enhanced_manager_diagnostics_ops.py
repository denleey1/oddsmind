#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Diagnostics/statistics helpers extracted from EnhancedDatabaseManager."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from .enhanced_manager import EnhancedDatabaseManager


def get_enhanced_database_stats_impl(manager: "EnhancedDatabaseManager") -> Dict[str, Any]:
    with manager._stats_lock:
        base_stats = manager._operation_stats.copy()

    repository_stats = {
        "odds_repository": manager.odds.get_operation_stats(),
        "companies_repository": manager.companies.get_operation_stats(),
    }

    try:
        table_counts = {}
        for table in ["leagues", "teams", "matches", "companies", "european_odds"]:
            count_query = f"SELECT COUNT(*) as count FROM {table}"
            result = manager.odds.db.execute_query(count_query, fetch="one")
            table_counts[table] = result["count"] if result else 0

        base_stats["table_counts"] = table_counts
    except Exception as exc:
        manager.logger.error(f"Failed to get table counts: {exc}")
        base_stats["table_counts"] = {}

    return {
        "enhanced_manager_stats": base_stats,
        "repository_stats": repository_stats,
        "uptime_hours": (datetime.utcnow() - base_stats["last_reset"]).total_seconds() / 3600,
    }


def diagnose_database_issues_impl(manager: "EnhancedDatabaseManager") -> Dict[str, Any]:
    diagnosis = {
        "timestamp": datetime.utcnow().isoformat(),
        "issues_found": [],
        "recommendations": [],
        "health_score": 100,
    }

    try:
        orphan_odds_query = """
            SELECT COUNT(*) as count
            FROM european_odds eo
            WHERE eo.company_id NOT IN (SELECT company_id FROM companies)
        """
        result = manager.odds.db.execute_query(orphan_odds_query, fetch="one")
        orphan_count = result["count"] if result else 0

        if orphan_count > 0:
            diagnosis["issues_found"].append(
                {
                    "type": "orphan_odds_records",
                    "severity": "high",
                    "count": orphan_count,
                    "description": f"Found {orphan_count} odds records referencing non-existent companies",
                }
            )
            diagnosis["recommendations"].append(
                "Run: python complete_database_fix.py to fix orphaned records"
            )
            diagnosis["health_score"] -= 30

        duplicate_companies_query = """
            SELECT name_en, COUNT(*) as count
            FROM companies
            GROUP BY name_en
            HAVING COUNT(*) > 1
        """
        duplicates = manager.odds.db.execute_query(duplicate_companies_query, fetch="all")
        if duplicates:
            diagnosis["issues_found"].append(
                {
                    "type": "duplicate_company_names",
                    "severity": "medium",
                    "count": len(duplicates),
                    "examples": [dup["name_en"] for dup in duplicates[:5]],
                    "description": f"Found {len(duplicates)} duplicate company names",
                }
            )
            diagnosis["recommendations"].append(
                "Use EnhancedDatabaseManager.resolve_duplicate_companies() method"
            )
            diagnosis["health_score"] -= 15

        connection_stats = manager.odds.get_operation_stats()
        if connection_stats["failed_operations"] > connection_stats["successful_operations"] * 0.1:
            diagnosis["issues_found"].append(
                {
                    "type": "high_failure_rate",
                    "severity": "high",
                    "failure_rate": round(
                        connection_stats["failed_operations"]
                        / max(connection_stats["total_operations"], 1)
                        * 100,
                        2,
                    ),
                    "description": "High database operation failure rate detected",
                }
            )
            diagnosis["health_score"] -= 25

        diagnosis["health_status"] = (
            "excellent"
            if diagnosis["health_score"] >= 90
            else "good"
            if diagnosis["health_score"] >= 75
            else "fair"
            if diagnosis["health_score"] >= 60
            else "poor"
        )

    except Exception as exc:
        diagnosis["issues_found"].append(
            {
                "type": "diagnosis_error",
                "severity": "high",
                "description": f"Failed to complete database diagnosis: {str(exc)}",
            }
        )
        diagnosis["health_score"] = 0
        diagnosis["health_status"] = "unknown"

    return diagnosis


__all__ = ["diagnose_database_issues_impl", "get_enhanced_database_stats_impl"]
