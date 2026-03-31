#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Integrity helper functions extracted from DatabaseManager."""

from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING, Tuple

from core.exceptions import DatabaseError
from config.companies_config import COMPANIES_CONFIG

from .models import CompanyModel, TeamModel

if TYPE_CHECKING:
    from config.companies_config import CompanyInfo
    from .manager import DatabaseManager


def ensure_companies_exist(manager: "DatabaseManager", company_ids: set) -> None:
    """Ensure all company IDs exist in ``companies`` table."""
    if not company_ids:
        return

    missing_ids = find_missing_company_ids(manager, company_ids)
    if not missing_ids:
        return

    companies_to_create: List[CompanyModel] = []
    for company_id in missing_ids:
        company_info = find_company_info_by_id(company_id)
        if company_info:
            company_model = CompanyModel(
                company_id=company_id,
                name_en=company_info.name_en,
                name_cn=company_info.name_cn,
                country=company_info.country,
                website=company_info.website,
                is_asian=company_info.is_asian,
                priority=company_info.priority,
                is_active=company_info.is_active,
            )
        else:
            company_model = CompanyModel(
                company_id=company_id,
                name_en=f"Company_{company_id}",
                name_cn=None,
                country=None,
                website=None,
                is_asian=False,
                priority=999,
                is_active=False,
            )
        companies_to_create.append(company_model)

    if companies_to_create:
        try:
            created_count = manager.companies.create_many(companies_to_create)
            manager.logger.info("自动创建了 %s 个缺失的公司记录: %s", created_count, missing_ids)
        except Exception as exc:
            manager.logger.error("创建缺失公司记录时出错: %s", exc, exc_info=True)
            raise DatabaseError(f"无法创建缺失的公司记录: {str(exc)}")


def ensure_teams_exist(
    manager: "DatabaseManager",
    team_pairs: List[Tuple[int, Optional[str]]],
) -> None:
    """Ensure all team IDs exist in ``teams`` table."""
    if not team_pairs:
        return

    team_ids = {pair[0] for pair in team_pairs if pair and pair[0]}
    if not team_ids:
        return

    placeholders = ', '.join(['%s'] * len(team_ids))
    query = f"SELECT team_id FROM teams WHERE team_id IN ({placeholders})"
    existing_rows = manager.teams.db.execute_query(query, list(team_ids), fetch='all')
    existing_ids = {row['team_id'] for row in existing_rows} if existing_rows else set()
    missing_ids = team_ids - existing_ids
    if not missing_ids:
        return

    team_models = []
    for team_id in missing_ids:
        name = None
        for pair in team_pairs:
            if pair and pair[0] == team_id and pair[1]:
                name = pair[1]
                break
        if not name:
            name = f"Team_{team_id}"
        team_models.append(TeamModel(team_id=team_id, name_cn=name, is_active=True))

    if team_models:
        manager.logger.info(
            "自动补齐缺失球队 %s 条 (ids: %s%s)",
            len(team_models),
            sorted(list(missing_ids))[:5],
            "..." if len(missing_ids) > 5 else "",
        )
        manager.teams.create_many(team_models)


def find_missing_company_ids(manager: "DatabaseManager", company_ids: set) -> set:
    """Find company IDs that do not exist in ``companies`` table."""
    if not company_ids:
        return set()

    try:
        placeholders = ', '.join(['%s'] * len(company_ids))
        query = f"SELECT company_id FROM companies WHERE company_id IN ({placeholders})"

        existing_records = manager.companies.db.execute_query(query, list(company_ids), fetch='all')
        existing_ids = {record['company_id'] for record in existing_records} if existing_records else set()
        missing_ids = company_ids - existing_ids

        if missing_ids:
            manager.logger.warning("发现缺失的 company_id: %s", missing_ids)

        return missing_ids

    except Exception as exc:
        manager.logger.error("检查缺失公司ID时出错: %s", exc, exc_info=True)
        return company_ids


def find_company_info_by_id(company_id: int) -> Optional['CompanyInfo']:
    """Find company info by ID from static config."""
    for company_info in COMPANIES_CONFIG.values():
        if company_info.company_id == company_id:
            return company_info
    return None


__all__ = [
    "ensure_companies_exist",
    "ensure_teams_exist",
    "find_missing_company_ids",
    "find_company_info_by_id",
]
