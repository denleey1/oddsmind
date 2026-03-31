#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Extracted high-level DatabaseManager operations."""

from __future__ import annotations

from datetime import datetime
import time
from typing import Any, Dict, TYPE_CHECKING

from core.exceptions import DatabaseError
from core.logger import log_performance

from .models import LeagueModel, TeamModel, MatchModel, OddsModel, StandingModel

if TYPE_CHECKING:
    from .manager import DatabaseManager


def store_multiple_odds_data(
    manager: "DatabaseManager",
    odds_batch: Dict[int, Dict[str, Any]],
    force_direct_write: bool = False,
) -> Dict[int, int]:
    """
    Store odds data for multiple matches.

    This function intentionally preserves the legacy behavior from
    ``DatabaseManager.store_multiple_odds_data``.
    """
    if not odds_batch:
        return {}

    # 如果启用了批量写入队列且不是强制直接写入，使用队列（避免竞锁）
    if manager.batch_writer and manager.batch_writer.running and not force_direct_write:
        for match_id, odds_data in odds_batch.items():
            manager.batch_writer.enqueue_odds(match_id, odds_data)
        return {match_id: len(odds_data.get('odds', [])) for match_id, odds_data in odds_batch.items()}

    start_time = time.time()
    results: Dict[int, int] = {}

    try:
        all_odds_models = []

        for match_id, odds_data in odds_batch.items():
            if not odds_data or 'odds' not in odds_data:
                results[match_id] = 0
                continue

            match_odds_models = []
            for odds_record in odds_data['odds']:
                if isinstance(odds_record, dict):
                    normalized_record = odds_record.copy()
                    normalized_record['match_id'] = match_id
                    normalized_record = manager._normalize_odds_data_enhanced(normalized_record)
                    match_odds_models.append(OddsModel.from_dict(normalized_record))

            all_odds_models.extend(match_odds_models)
            results[match_id] = len(match_odds_models)

        if all_odds_models:
            with log_performance(manager.logger, f"bulk_odds_optimized_{len(odds_batch)}_matches"):
                max_batch_size = 400

                for i in range(0, len(all_odds_models), max_batch_size):
                    batch = all_odds_models[i:i + max_batch_size]
                    manager.odds.bulk_upsert_odds_with_company_validation(
                        batch,
                        ensure_companies=True,
                    )

                execution_time = time.time() - start_time

                with manager._stats_lock:
                    manager._operation_stats['odds_operations'] += len(odds_batch)
                    manager._operation_stats['total_records_processed'] += len(all_odds_models)
                    manager._update_avg_batch_time(execution_time)

                manager.logger.info(
                    "Optimized bulk storage completed: "
                    "%s records for %s matches in %.2fs (%.1f records/sec)",
                    len(all_odds_models),
                    len(odds_batch),
                    execution_time,
                    len(all_odds_models) / execution_time if execution_time > 0 else 0.0,
                )

                try:
                    from utils.cache_invalidation import invalidate_odds_cache

                    for match_id in odds_batch.keys():
                        invalidate_odds_cache(match_id)
                except Exception as cache_exc:
                    manager.logger.warning("清除赔率缓存失败: %s", cache_exc)

        return results

    except Exception as exc:
        with manager._stats_lock:
            manager._operation_stats['failed_operations'] += 1

        manager.logger.error("Optimized bulk odds storage failed: %s", exc)
        raise DatabaseError(f"Failed to store bulk odds data: {str(exc)}")


def store_odds_data(
    manager: "DatabaseManager",
    match_id: int,
    odds_data: Dict[str, Any],
) -> int:
    """Store odds data for a single match via bulk storage path."""
    if not odds_data or 'odds' not in odds_data or not odds_data['odds']:
        manager.logger.debug("No odds data provided for match %s, skipping storage.", match_id)
        return 0

    try:
        results = store_multiple_odds_data(manager, {match_id: odds_data})
        stored_count = results.get(match_id, 0)
        if stored_count > 0:
            manager.logger.info("Successfully stored %s odds records for match %s", stored_count, match_id)
        return stored_count
    except DatabaseError as exc:
        manager.logger.error("Failed to store odds for match %s: %s", match_id, exc)
        return 0


def store_league_data(
    manager: "DatabaseManager",
    league_data: Dict[str, Any],
) -> Dict[str, int]:
    """Store league data including teams, matches, and standings."""
    try:
        counts = {
            'leagues': 0,
            'teams': 0,
            'matches': 0,
            'standings': 0,
        }

        if 'league' in league_data and league_data['league']:
            league_model = LeagueModel.from_dict(league_data['league'])
            manager.leagues.upsert(league_model, ['league_id'])
            counts['leagues'] = 1
            manager.logger.debug("Stored league: %s", league_model.name_cn)

        if 'teams' in league_data and league_data['teams']:
            team_models = []
            for team_data in league_data['teams']:
                if isinstance(team_data, dict):
                    team_models.append(TeamModel.from_dict(team_data))

            for team in team_models:
                manager.teams.upsert(team, ['team_id'])
            counts['teams'] = len(team_models)
            manager.logger.debug("Stored %s teams", len(team_models))

        if 'matches' in league_data and league_data['matches']:
            match_models = []
            team_pairs = []

            for _, round_matches in league_data['matches'].items():
                for match_data in round_matches:
                    if isinstance(match_data, dict):
                        normalized_match = manager._normalize_match_data(match_data)
                        match_model = MatchModel.from_dict(normalized_match)
                        match_models.append(match_model)

                        if match_model.home_team_id:
                            team_pairs.append((match_model.home_team_id, match_model.home_team_name))
                        if match_model.away_team_id:
                            team_pairs.append((match_model.away_team_id, match_model.away_team_name))

            try:
                manager._ensure_teams_exist(team_pairs)
            except Exception as team_exc:
                manager.logger.error("预先创建缺失球队记录失败: %s", team_exc, exc_info=True)

            for match in match_models:
                manager.matches.upsert(match, ['match_id'])
            counts['matches'] = len(match_models)
            manager.logger.debug("Stored %s matches", len(match_models))

        if 'standings' in league_data and league_data['standings']:
            standings_models = []
            standings_data = league_data['standings']

            if isinstance(standings_data, dict):
                for standings_type, standings_list in standings_data.items():
                    if isinstance(standings_list, list) and standings_list:
                        for standing_data in standings_list:
                            if isinstance(standing_data, dict):
                                normalized_standing = standing_data.copy()
                                normalized_standing['league_id'] = league_data.get('league', {}).get('id', 0)
                                normalized_standing['standing_type'] = standings_type
                                standings_models.append(StandingModel.from_dict(normalized_standing))
            else:
                for standing_data in standings_data:
                    if isinstance(standing_data, dict):
                        normalized_standing = standing_data.copy()
                        normalized_standing['league_id'] = league_data.get('league', {}).get('id', 0)
                        standings_models.append(StandingModel.from_dict(normalized_standing))

            for standing in standings_models:
                manager.standings.upsert(standing, ['league_id', 'team_id', 'standing_type'])
            counts['standings'] = len(standings_models)
            manager.logger.debug("Stored %s standings", len(standings_models))

        total_stored = sum(counts.values())
        if total_stored > 0:
            manager.logger.info("Successfully stored league data: %s", counts)

        return counts

    except Exception as exc:
        manager.logger.error("Error storing league data: %s", exc, exc_info=True)
        return {'leagues': 0, 'teams': 0, 'matches': 0, 'standings': 0}


def get_enhanced_performance_stats(manager: "DatabaseManager") -> Dict[str, Any]:
    """Get enhanced performance statistics."""
    with manager._stats_lock:
        base_stats = manager._operation_stats.copy()

    repository_stats = {
        'odds_repository': manager.odds.get_operation_stats() if hasattr(manager.odds, 'get_operation_stats') else {},
        'companies_repository': manager.companies.get_operation_stats() if hasattr(manager.companies, 'get_operation_stats') else {},
    }

    return {
        'manager_stats': base_stats,
        'repository_stats': repository_stats,
        'performance_metrics': {
            'success_rate': round(
                (base_stats['odds_operations'] - base_stats['failed_operations']) /
                max(base_stats['odds_operations'], 1) * 100,
                2,
            ),
            'avg_records_per_operation': round(
                base_stats['total_records_processed'] / max(base_stats['odds_operations'], 1),
                2,
            ),
            'avg_batch_time_seconds': round(base_stats['avg_batch_time'], 3),
        },
    }


def diagnose_database_health(manager: "DatabaseManager") -> Dict[str, Any]:
    """Diagnose database health and identify potential issues."""
    diagnosis: Dict[str, Any] = {
        'timestamp': datetime.utcnow().isoformat(),
        'issues_found': [],
        'recommendations': [],
        'health_score': 100,
    }

    try:
        orphan_check_query = """
            SELECT COUNT(*) as count
            FROM european_odds eo
            WHERE eo.company_id NOT IN (SELECT company_id FROM companies)
        """

        result = manager.odds.db.execute_query(orphan_check_query, fetch='one')
        orphan_count = result['count'] if result else 0

        if orphan_count > 0:
            diagnosis['issues_found'].append({
                'type': 'orphan_odds_records',
                'severity': 'high',
                'count': orphan_count,
                'description': f'Found {orphan_count} odds records with invalid company references',
            })
            diagnosis['recommendations'].append('Run database repair to fix orphaned records')
            diagnosis['health_score'] -= 30

        duplicate_check_query = """
            SELECT name_en, COUNT(*) as count
            FROM companies
            GROUP BY name_en
            HAVING COUNT(*) > 1
        """

        duplicates = manager.odds.db.execute_query(duplicate_check_query, fetch='all')
        if duplicates:
            diagnosis['issues_found'].append({
                'type': 'duplicate_company_names',
                'severity': 'medium',
                'count': len(duplicates),
                'description': f'Found {len(duplicates)} duplicate company names',
            })
            diagnosis['health_score'] -= 15

        diagnosis['health_status'] = (
            'excellent' if diagnosis['health_score'] >= 90
            else 'good' if diagnosis['health_score'] >= 75
            else 'fair' if diagnosis['health_score'] >= 60
            else 'poor'
        )

    except Exception as exc:
        diagnosis['issues_found'].append({
            'type': 'diagnosis_error',
            'severity': 'high',
            'description': f'Failed to complete health check: {str(exc)}',
        })
        diagnosis['health_score'] = 0
        diagnosis['health_status'] = 'unknown'

    return diagnosis


__all__ = [
    "store_multiple_odds_data",
    "store_odds_data",
    "store_league_data",
    "get_enhanced_performance_stats",
    "diagnose_database_health",
]
