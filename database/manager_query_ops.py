#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Query and reporting operations extracted from DatabaseManager."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .manager import DatabaseManager
    from .models import CompanyModel


def get_latest_odds_analysis(manager: "DatabaseManager", match_id: int) -> Optional[Dict]:
    """
    从 odds_analysis_results 表中获取指定比赛的最新一条分析结果。
    """
    columns_str = ", ".join(manager.analysis_results.all_columns)
    query = f"""
        SELECT {columns_str}
        FROM {manager.analysis_results.table_name}
        WHERE match_id = %s
        ORDER BY created_at DESC
        LIMIT 1
    """
    return manager.analysis_results.db.execute_query(query, [match_id], fetch='one')


def get_all_companies_map(manager: "DatabaseManager") -> Dict[int, "CompanyModel"]:
    """
    获取所有博彩公司ID到公司模型的映射字典。
    """
    try:
        companies = manager.companies.find_all()
        company_map = {company.company_id: company for company in companies}
        manager.logger.info(f"成功加载了 {len(company_map)} 家公司的映射。")
        return company_map
    except Exception as e:
        manager.logger.error(f"加载公司映射时出错: {e}", exc_info=True)
        return {}


def get_today_scheduled_match_ids(manager: "DatabaseManager", league_ids: Optional[List[int]] = None) -> List[int]:
    """
    获取今天所有状态为“未开始”的比赛ID。
    可选择按联赛ID进行过滤。
    """
    try:
        query = """
            SELECT match_id
            FROM matches
            WHERE match_status = 'scheduled'
              AND DATE(match_time) = CURDATE()
        """
        params = []

        if league_ids:
            placeholders = ','.join(['%s'] * len(league_ids))
            query += f" AND league_id IN ({placeholders})"
            params.extend(league_ids)

        query += " ORDER BY match_time ASC"

        results = manager.matches.db.execute_query(query, params, fetch='all')
        match_ids = [row['match_id'] for row in results] if results else []
        manager.logger.info(f"找到 {len(match_ids)} 场今天未开始的比赛。")
        return match_ids

    except Exception as e:
        manager.logger.error(f"获取今日比赛ID时出错: {e}", exc_info=True)
        return []


def get_match_ids_by_league(
    manager: "DatabaseManager",
    league_code: str,
    limit: int = 10,
    status: Optional[str] = None,
) -> List[int]:
    """
    根据联赛代码获取最新的比赛ID列表。
    注意：这里的 league_code 是字符串形式，需要转换为整数ID。
    """
    try:
        league_id = int(league_code)
        criteria = {'league_id': league_id}
        if status:
            criteria['match_status'] = status

        results = manager.matches.find_by_criteria(
            criteria=criteria,
            order_by='match_time DESC',
            limit=limit,
        )
        return [match.match_id for match in results] if results else []
    except (ValueError, TypeError):
        manager.logger.error(f"Invalid league_code provided: {league_code}. Must be an integer.")
        return []
    except Exception as e:
        manager.logger.error(f"Error getting match IDs for league {league_code}: {e}")
        return []


def get_finished_matches_with_zero_odds(manager: "DatabaseManager", league_id: int) -> List[int]:
    """
    获取指定联赛中，已完成但赔率公司数量为0的比赛ID列表。
    """
    try:
        query = """
            SELECT m.match_id
            FROM matches m
            LEFT JOIN (
                SELECT match_id, COUNT(DISTINCT company_id) as odds_count
                FROM european_odds
                GROUP BY match_id
            ) AS o ON m.match_id = o.match_id
            WHERE m.league_id = %s
              AND m.match_status = 'finished'
              AND (o.odds_count IS NULL OR o.odds_count = 0)
            ORDER BY m.match_time ASC;
        """
        results = manager.matches.db.execute_query(query, (league_id,), fetch='all')
        return [row['match_id'] for row in results] if results else []
    except Exception as e:
        manager.logger.error(f"Error getting finished matches with zero odds for league {league_id}: {e}")
        return []


def get_all_companies(manager: "DatabaseManager") -> list:
    """获取所有已知的博彩公司"""
    try:
        return manager.companies.find_all()
    except Exception as e:
        manager.logger.error(f"Error getting all companies: {e}")
        return []


def get_matches_needing_odds(
    manager: "DatabaseManager",
    league_id: Optional[int] = None,
    only_finished: bool = True,
) -> List[int]:
    """
    Get list of match IDs that need odds data.

    Args:
        league_id: Optional league filter
        only_finished: Whether to only include finished matches

    Returns:
        List of match IDs
    """
    try:
        query = """
            SELECT m.match_id
            FROM matches m
            LEFT JOIN european_odds o ON m.match_id = o.match_id
            WHERE o.match_id IS NULL
        """

        params = []

        if league_id:
            query += " AND m.league_id = %s"
            params.append(league_id)

        if only_finished:
            query += " AND m.match_status = %s"
            params.append('finished')

        query += " ORDER BY m.match_time DESC"

        results = manager.matches.db.execute_query(query, params, fetch='all')
        return [row['match_id'] for row in results] if results else []

    except Exception as e:
        manager.logger.error(f"Error finding matches needing odds: {e}")
        return []


def get_matches_ready_for_odds(
    manager: "DatabaseManager",
    league_id: Optional[int] = None,
    skip_existing_odds: bool = True,
) -> List[int]:
    """
    Get list of match IDs that are ready for odds scraping based on match status.

    Args:
        league_id: Optional league filter
        skip_existing_odds: Whether to skip matches with existing odds data

    Returns:
        List of match IDs ready for odds scraping
    """
    try:
        query = """
            SELECT m.match_id, m.match_status, m.match_time
            FROM matches m
        """

        if skip_existing_odds:
            query += """
                LEFT JOIN european_odds o ON m.match_id = o.match_id
            """

        query += """
            WHERE (
                m.match_status = 'finished' OR
                m.match_status = 'live' OR
                (m.match_status = 'scheduled' AND m.match_time <= DATE_ADD(NOW(), INTERVAL 24 HOUR))
            )
        """

        params = []

        if skip_existing_odds:
            query += " AND o.match_id IS NULL"

        if league_id:
            query += " AND m.league_id = %s"
            params.append(league_id)

        query += " ORDER BY m.match_time DESC"

        results = manager.matches.db.execute_query(query, params, fetch='all')

        if results:
            match_ids = [row['match_id'] for row in results]
            manager.logger.info(
                f"Found {len(match_ids)} matches ready for odds scraping "
                f"(league_id={league_id}, skip_existing={skip_existing_odds})"
            )
            return match_ids

        return []

    except Exception as e:
        manager.logger.error(f"Error finding matches ready for odds: {e}")
        return []


def get_league_summary(manager: "DatabaseManager", league_id: int) -> Dict[str, Any]:
    """Get comprehensive summary for a league."""
    try:
        league = manager.leagues.find_by_id(league_id)
        if not league:
            return {}

        teams_count = manager.teams.count({'league_id': league_id})
        matches_count = manager.matches.count({'league_id': league_id})
        finished_matches = manager.matches.count({
            'league_id': league_id,
            'match_status': 'finished',
        })

        odds_query = """
            SELECT COUNT(DISTINCT m.match_id) as matches_with_odds
            FROM matches m
            INNER JOIN european_odds o ON m.match_id = o.match_id
            WHERE m.league_id = %s AND m.match_status = 'finished'
        """

        result = manager.matches.db.execute_query(odds_query, (league_id,), fetch='one')
        matches_with_odds = result['matches_with_odds'] if result else 0
        odds_coverage = (matches_with_odds / max(finished_matches, 1)) * 100

        return {
            'league': league.to_dict(),
            'statistics': {
                'teams_count': teams_count,
                'matches_count': matches_count,
                'finished_matches': finished_matches,
                'matches_with_odds': matches_with_odds,
                'odds_coverage_pct': round(odds_coverage, 2),
            },
        }

    except Exception as e:
        manager.logger.error(f"Error getting league summary for {league_id}: {e}")
        return {}


def get_match_with_odds(manager: "DatabaseManager", match_id: int) -> Dict[str, Any]:
    """Get match information with associated odds data."""
    try:
        match = manager.matches.find_by_id(match_id)
        if not match:
            return {}

        odds = manager.odds.find_by_match(match_id)
        return {
            'match': match.to_dict(),
            'odds': [o.to_dict() for o in odds],
            'odds_count': len(odds),
            'companies_count': len(set(o.company_id for o in odds)),
        }

    except Exception as e:
        manager.logger.error(f"Error getting match with odds for {match_id}: {e}")
        return {}


def get_company_odds_stats(manager: "DatabaseManager", company_id: int) -> Dict[str, Any]:
    """Get statistics for a specific company's odds."""
    try:
        company = manager.companies.find_by_id(company_id)
        if not company:
            return {}

        odds_count = manager.odds.count({'company_id': company_id})

        query = """
            SELECT COUNT(DISTINCT match_id) as unique_matches
            FROM european_odds
            WHERE company_id = %s
        """

        result = manager.odds.db.execute_query(query, (company_id,), fetch='one')
        unique_matches = result['unique_matches'] if result else 0

        return {
            'company': company.to_dict(),
            'statistics': {
                'total_odds_records': odds_count,
                'unique_matches': unique_matches,
                'avg_records_per_match': round(odds_count / max(unique_matches, 1), 2),
            },
        }

    except Exception as e:
        manager.logger.error(f"Error getting company stats for {company_id}: {e}")
        return {}


def get_scraping_stats(manager: "DatabaseManager", scraper_name: Optional[str] = None) -> Dict[str, Any]:
    """Get scraping statistics."""
    try:
        recent_logs = manager.logs.find_recent_logs(scraper_name, limit=1000)

        if not recent_logs:
            return {'message': 'No recent scraping logs found'}

        total_operations = len(recent_logs)
        successful_operations = len([log for log in recent_logs if log.status == 'success'])
        failed_operations = len([log for log in recent_logs if log.status == 'failed'])
        success_rate = (successful_operations / total_operations) * 100 if total_operations > 0 else 0

        target_type_stats = {}
        for log in recent_logs:
            if log.target_type not in target_type_stats:
                target_type_stats[log.target_type] = {'total': 0, 'success': 0, 'failed': 0}

            target_type_stats[log.target_type]['total'] += 1
            if log.status == 'success':
                target_type_stats[log.target_type]['success'] += 1
            elif log.status == 'failed':
                target_type_stats[log.target_type]['failed'] += 1

        return {
            'scraper_name': scraper_name,
            'total_operations': total_operations,
            'successful_operations': successful_operations,
            'failed_operations': failed_operations,
            'success_rate_pct': round(success_rate, 2),
            'target_type_breakdown': target_type_stats,
            'latest_operation': recent_logs[0].to_dict() if recent_logs else None,
        }

    except Exception as e:
        manager.logger.error(f"Error getting scraping stats: {e}")
        return {}


__all__ = [
    "get_all_companies",
    "get_all_companies_map",
    "get_company_odds_stats",
    "get_finished_matches_with_zero_odds",
    "get_latest_odds_analysis",
    "get_league_summary",
    "get_match_ids_by_league",
    "get_match_with_odds",
    "get_matches_needing_odds",
    "get_matches_ready_for_odds",
    "get_scraping_stats",
    "get_today_scheduled_match_ids",
]

