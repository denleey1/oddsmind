#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Write and maintenance helper operations extracted from DatabaseManager."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from core.exceptions import DatabaseError
from .models import CompanyModel, ComprehensiveAnalysisModel

if TYPE_CHECKING:
    from .manager import DatabaseManager
    from .models import AsianHandicapOddsModel, OddsChangeModel, OverUnderOddsChangeModel


def store_analysis_result(manager: "DatabaseManager", analysis_data: Dict[str, Any]) -> None:
    """Store comprehensive analysis result."""
    try:
        match_id = analysis_data['match_id']

        flat_data = {
            'match_id': match_id,
            'analysis_time': analysis_data.get('analysis_time'),
            'home_team_power_level': analysis_data.get('strength_comparison', {}).get('home_strength', {}).get('power_level'),
            'away_team_power_level': analysis_data.get('strength_comparison', {}).get('away_strength', {}).get('power_level'),
            'power_level_diff': analysis_data.get('strength_comparison', {}).get('power_level_diff'),
            'fundamental_home_score': analysis_data.get('fundamental_analysis', {}).get('final_scores', {}).get('home_win'),
            'fundamental_draw_score': analysis_data.get('fundamental_analysis', {}).get('final_scores', {}).get('draw'),
            'fundamental_away_score': analysis_data.get('fundamental_analysis', {}).get('final_scores', {}).get('away_win'),
            'fundamental_confidence': analysis_data.get('fundamental_analysis', {}).get('confidence_level'),
            'fundamental_recommendation': analysis_data.get('fundamental_analysis', {}).get('recommended_outcome'),
            'odds_confidence': analysis_data.get('odds_analysis', {}).get('confidence'),
            'odds_recommendation': analysis_data.get('odds_analysis', {}).get('recommendation'),
            'final_recommendation': analysis_data.get('final_recommendation', {}).get('recommendation'),
            'final_confidence': analysis_data.get('final_recommendation', {}).get('confidence'),
            'risk_level': analysis_data.get('final_recommendation', {}).get('risk_level'),
            'is_reasonable': analysis_data.get('reasonableness_check', {}).get('overall_reasonable'),
        }

        flat_data = {k: v for k, v in flat_data.items() if v is not None}

        analysis_model = ComprehensiveAnalysisModel.from_dict(flat_data)
        manager.analysis_results.upsert(analysis_model, ['match_id'])
        manager.logger.info(f"Successfully stored analysis result for match_id: {match_id}")

        try:
            from utils.cache_invalidation import invalidate_analysis_cache
            invalidate_analysis_cache(match_id)
        except Exception as cache_exc:
            manager.logger.warning(f"清除分析缓存失败: {cache_exc}")

    except KeyError as e:
        manager.logger.error(f"Missing key in analysis data: {e}")
        raise DatabaseError(f"Failed to store analysis data due to missing key: {e}")
    except Exception as e:
        manager.logger.error(f"Error storing analysis result: {e}")
        raise DatabaseError(f"Failed to store analysis data: {str(e)}")


def upsert_odds_changes(manager: "DatabaseManager", odds_changes: List["OddsChangeModel"]) -> int:
    """
    将赔率状态数据批量插入或更新到 `odds_changes` 表。
    使用 (match_id, company_id) 作为冲突键。
    """
    if not odds_changes:
        return 0

    processed_count = 0
    try:
        for change_model in odds_changes:
            manager.odds_changes.upsert(change_model, ['match_id', 'company_id'])
            processed_count += 1

        manager.logger.info(f"成功向 odds_changes 表中插入/更新了 {processed_count} 条赔率状态记录。")
        return processed_count
    except Exception as e:
        manager.logger.error(f"向 odds_changes 表中插入/更新数据时出错: {e}", exc_info=True)
        return 0


def bulk_upsert_odds_changes(manager: "DatabaseManager", odds_changes: List["OddsChangeModel"]) -> int:
    """
    使用更高效的单条SQL语句批量插入或更新 odds_changes 表。

    如果启用了批量写入队列，则使用队列；否则直接写入。
    这样可以避免多线程并发写入导致的数据库竞锁问题。

    Ensures all referenced company_ids exist in companies table before insertion
    to prevent foreign key constraint violations.
    """
    if not odds_changes:
        return 0

    if manager.batch_writer and manager.batch_writer.running:
        success = manager.batch_writer.enqueue_odds_changes(odds_changes)
        if success:
            return len(odds_changes)
        manager.logger.warning(
            f"Failed to enqueue {len(odds_changes)} odds_changes (queue full), falling back to direct write"
        )

    return _direct_bulk_upsert_odds_changes(manager, odds_changes)


def _direct_bulk_upsert_odds_changes(
    manager: "DatabaseManager",
    odds_changes: List["OddsChangeModel"],
) -> int:
    """Write odds_changes directly to MySQL, bypassing BatchWriter re-enqueue."""
    if not odds_changes:
        return 0

    company_ids = set(change.company_id for change in odds_changes if change.company_id)
    if company_ids:
        manager._ensure_companies_exist(company_ids)

    try:
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
        affected_rows = manager.odds_changes.db.execute_many(query, data_to_save)
        manager.logger.info(f"成功通过批量方式向 odds_changes 表插入/更新了 {affected_rows} 条记录。")
        return affected_rows

    except Exception as e:
        manager.logger.error(f"批量向 odds_changes 表插入/更新数据时出错: {e}", exc_info=True)
        if "foreign key constraint fails" in str(e).lower():
            missing_companies = manager._find_missing_company_ids(company_ids)
            if missing_companies:
                manager.logger.error("检测到缺失的 company_id: %s", missing_companies)
        return 0


def bulk_upsert_over_under_odds_changes(
    manager: "DatabaseManager",
    changes: List["OverUnderOddsChangeModel"],
) -> int:
    """
    Persist over/under odds change snapshots.

    如果启用了批量写入队列，则使用队列；否则直接写入。

    Ensures all referenced company_ids exist in companies table before insertion
    to prevent foreign key constraint violations.
    """
    if not changes:
        return 0

    if manager.batch_writer and manager.batch_writer.running:
        success = manager.batch_writer.enqueue_over_under(changes)
        if success:
            return len(changes)
        manager.logger.warning(
            f"Failed to enqueue {len(changes)} over_under changes (queue full), falling back to direct write"
        )

    return _direct_bulk_upsert_over_under_odds_changes(manager, changes)


def _direct_bulk_upsert_over_under_odds_changes(
    manager: "DatabaseManager",
    changes: List["OverUnderOddsChangeModel"],
) -> int:
    """Write over/under odds directly to MySQL, bypassing BatchWriter re-enqueue."""
    if not changes:
        return 0

    company_ids = set(change.company_id for change in changes if change.company_id)
    if company_ids:
        manager._ensure_companies_exist(company_ids)

    processed = 0
    try:
        for change_model in changes:
            manager.over_under_odds_changes.upsert(
                change_model, ['match_id', 'company_id', 'market_line', 'variant']
            )
            processed += 1
        manager.logger.info("成功向 over_under_odds_changes 表中插入/更新了 %s 条记录。", processed)
        return processed
    except Exception as exc:
        manager.logger.error("在 over_under_odds_changes 表执行 upsert 时出错: %s", exc, exc_info=True)
        if "foreign key constraint fails" in str(exc).lower():
            missing_companies = manager._find_missing_company_ids(company_ids)
            if missing_companies:
                manager.logger.error("检测到缺失的 company_id: %s", missing_companies)
        return processed


def add_companies(manager: "DatabaseManager", companies: list) -> None:
    """批量添加新的博彩公司"""
    try:
        company_models = []
        for company_data in companies:
            company_models.append(CompanyModel.from_dict(company_data._asdict()))

        if company_models:
            for company in company_models:
                manager.companies.upsert(company, ['company_id'])
            manager.logger.info(f"Successfully added/updated {len(company_models)} companies.")

    except Exception as e:
        manager.logger.error(f"Error adding new companies: {e}")


def log_scraping_operation(
    manager: "DatabaseManager",
    scraper_name: str,
    target_type: str,
    target_id: str,
    status: str,
    **kwargs,
) -> None:
    """Log a scraping operation."""
    try:
        manager.logs.log_operation(
            scraper_name=scraper_name,
            target_type=target_type,
            target_id=target_id,
            status=status,
            **kwargs,
        )
    except Exception as e:
        manager.logger.error(f"Error logging scraping operation: {e}")


def cleanup_old_logs(manager: "DatabaseManager", days_to_keep: int = 30) -> int:
    """Clean up old scraping logs."""
    try:
        cutoff_date = datetime.utcnow().date() - timedelta(days=days_to_keep)
        deleted = manager.logs.delete_by_criteria({'created_at': ('<=', cutoff_date)})
        manager.logger.info(f"Cleaned up {deleted} old scraping logs")
        return deleted

    except Exception as e:
        manager.logger.error(f"Error cleaning up old logs: {e}")
        return 0


def normalize_odds_data(manager: "DatabaseManager", odds_data: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize odds data for database storage."""
    normalized = odds_data.copy()

    if 'company_id' in normalized and normalized['company_id']:
        try:
            company_id = int(normalized['company_id'])
            normalized['company_id'] = company_id
            manager._ensure_company_exists(company_id, normalized)
        except (ValueError, TypeError):
            normalized['company_id'] = 0

    if 'odds_type' not in normalized:
        normalized['odds_type'] = '1x2'

    return normalized


def ensure_company_exists(manager: "DatabaseManager", company_id: int, odds_data: Dict[str, Any]) -> None:
    """
    Ensure a company exists - OPTIMIZED VERSION with concurrent safety.
    Now uses enhanced repository methods to prevent race conditions.
    """
    try:
        company_info = manager._get_company_from_config(company_id)

        if company_info:
            company = CompanyModel.from_dict(company_info)
        else:
            company_name_en = odds_data.get('company_name', f'Company_{company_id}')
            company_name_cn = odds_data.get('company_name_cn', f'公司_{company_id}')

            company = CompanyModel(
                company_id=company_id,
                name_en=company_name_en,
                name_cn=company_name_cn,
                country='Unknown',
                website='',
                is_main=False,
                is_asian=False,
                priority=999,
                is_active=True,
            )

        created_company, was_created = manager.companies.safe_create_company(company)

        if was_created:
            with manager._stats_lock:
                manager._operation_stats['company_operations'] += 1

            manager.logger.info(
                f"Auto-created missing company: {company_id} - "
                f"{created_company.name_cn} ({created_company.name_en})"
            )

    except Exception as e:
        manager.logger.error(f"Failed to ensure company {company_id} exists: {e}")


def normalize_odds_data_enhanced(manager: "DatabaseManager", odds_data: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced odds data normalization with improved validation."""
    normalized = odds_data.copy()

    if 'company_id' in normalized and normalized['company_id']:
        try:
            company_id = int(normalized['company_id'])
            if company_id <= 0:
                raise ValueError("Invalid company_id")
            normalized['company_id'] = company_id
        except (ValueError, TypeError):
            manager.logger.warning(f"Invalid company_id in odds data: {normalized.get('company_id')}")
            normalized['company_id'] = 0

    if 'odds_type' not in normalized:
        normalized['odds_type'] = '1x2'

    if 'data_source' not in normalized:
        normalized['data_source'] = 'titan007'

    return normalized


def get_company_from_config(manager: "DatabaseManager", company_id: int) -> Optional[Dict[str, Any]]:
    """Get company information from configuration."""
    try:
        from config.companies_config import COMPANIES_CONFIG

        for company_info in COMPANIES_CONFIG.values():
            if company_info.company_id == company_id:
                return {
                    'company_id': company_info.company_id,
                    'name_en': company_info.name_en,
                    'name_cn': company_info.name_cn,
                    'country': company_info.country,
                    'website': company_info.website,
                    'is_main': company_info.is_main,
                    'is_asian': company_info.is_asian,
                    'priority': company_info.priority,
                    'is_active': company_info.is_active,
                }
    except Exception as e:
        manager.logger.debug(f"Could not get company {company_id} from config: {e}")

    return None


def update_avg_batch_time(manager: "DatabaseManager", execution_time: float) -> None:
    """Update average batch processing time."""
    current_avg = manager._operation_stats['avg_batch_time']
    operations = manager._operation_stats['odds_operations']

    if operations == 1:
        manager._operation_stats['avg_batch_time'] = execution_time
    else:
        manager._operation_stats['avg_batch_time'] = (
            (current_avg * (operations - 1) + execution_time) / operations
        )


def bulk_upsert_asian_handicap_odds(
    manager: "DatabaseManager",
    records: List["AsianHandicapOddsModel"],
) -> int:
    """批量写入亚盘赔率数据到 asian_handicap_odds 表。

    使用 match_id + company_id 作为唯一键做 upsert。
    写入前确保 company_id 存在于 companies 表。
    """
    if not records:
        return 0

    company_ids = set(r.company_id for r in records if r.company_id)
    if company_ids:
        manager._ensure_companies_exist(company_ids)

    processed = 0
    try:
        for model in records:
            manager.asian_handicap_odds.upsert(model, ["match_id", "company_id"])
            processed += 1
        manager.logger.info("asian_handicap_odds 表 upsert %s 条记录", processed)
        return processed
    except Exception as exc:
        manager.logger.error("asian_handicap_odds upsert 失败: %s", exc, exc_info=True)
        if "foreign key constraint fails" in str(exc).lower():
            missing = manager._find_missing_company_ids(company_ids)
            if missing:
                manager.logger.error("缺失的 company_id: %s", missing)
        return processed


__all__ = [
    "add_companies",
    "bulk_upsert_asian_handicap_odds",
    "bulk_upsert_odds_changes",
    "bulk_upsert_over_under_odds_changes",
    "cleanup_old_logs",
    "_direct_bulk_upsert_odds_changes",
    "_direct_bulk_upsert_over_under_odds_changes",
    "ensure_company_exists",
    "get_company_from_config",
    "log_scraping_operation",
    "normalize_odds_data",
    "normalize_odds_data_enhanced",
    "store_analysis_result",
    "update_avg_batch_time",
    "upsert_odds_changes",
]
