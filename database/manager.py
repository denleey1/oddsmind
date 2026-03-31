#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Database manager for high-level database operations.
Orchestrates repositories and provides business logic layer.
"""

from typing import List, Dict, Any, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from config.companies_config import CompanyInfo

from .repository import (
    LeagueRepository, TeamRepository, MatchRepository, 
    CompanyRepository, OddsRepository, StandingRepository,
    ScrapingLogRepository, BaseRepository
)
from .optimized_repository import OptimizedOddsRepository, OptimizedCompanyRepository
from .models import (
    AsianHandicapOddsModel,
    LeagueModel, TeamModel, MatchModel, OddsModel, 
    StandingModel, MatchStatus, ComprehensiveAnalysisModel,
    OddsChangeModel, OverUnderOddsChangeModel, CompanyModel
)
from core.logger import get_logger
from core.exceptions import DatabaseError, ValidationError
from core.decorators import log_execution_time
from .manager_operations import (
    diagnose_database_health as _diagnose_database_health,
    get_enhanced_performance_stats as _get_enhanced_performance_stats,
    store_league_data as _store_league_data,
    store_multiple_odds_data as _store_multiple_odds_data,
    store_odds_data as _store_odds_data,
)
from .manager_integrity_helpers import (
    ensure_companies_exist as _ensure_companies_exist_impl,
    ensure_teams_exist as _ensure_teams_exist_impl,
    find_company_info_by_id as _find_company_info_by_id_impl,
    find_missing_company_ids as _find_missing_company_ids_impl,
)
from .manager_query_ops import (
    get_all_companies as _get_all_companies,
    get_all_companies_map as _get_all_companies_map,
    get_company_odds_stats as _get_company_odds_stats,
    get_finished_matches_with_zero_odds as _get_finished_matches_with_zero_odds,
    get_latest_odds_analysis as _get_latest_odds_analysis,
    get_league_summary as _get_league_summary,
    get_match_ids_by_league as _get_match_ids_by_league,
    get_match_with_odds as _get_match_with_odds,
    get_matches_needing_odds as _get_matches_needing_odds,
    get_matches_ready_for_odds as _get_matches_ready_for_odds,
    get_scraping_stats as _get_scraping_stats,
    get_today_scheduled_match_ids as _get_today_scheduled_match_ids,
)
from .manager_write_helpers import (
    add_companies as _add_companies,
    bulk_upsert_asian_handicap_odds as _bulk_upsert_asian_handicap_odds,
    bulk_upsert_odds_changes as _bulk_upsert_odds_changes,
    bulk_upsert_over_under_odds_changes as _bulk_upsert_over_under_odds_changes,
    cleanup_old_logs as _cleanup_old_logs,
    ensure_company_exists as _ensure_company_exists,
    get_company_from_config as _get_company_from_config,
    log_scraping_operation as _log_scraping_operation,
    normalize_odds_data as _normalize_odds_data_impl,
    normalize_odds_data_enhanced as _normalize_odds_data_enhanced_impl,
    store_analysis_result as _store_analysis_result,
    update_avg_batch_time as _update_avg_batch_time_impl,
    upsert_odds_changes as _upsert_odds_changes,
)
import threading


class DatabaseManager:
    """
    High-level database manager that orchestrates all database operations.
    Provides business logic and coordinates between different repositories.
    """
    
    def __init__(self, use_batch_writer: bool = True):
        self.logger = get_logger(self.__class__.__name__)
        
        # Initialize repositories with optimized versions
        self.leagues = LeagueRepository()
        self.teams = TeamRepository()
        self.matches = MatchRepository()
        
        # Use optimized repositories for critical operations
        self.companies = OptimizedCompanyRepository()
        self.odds = OptimizedOddsRepository()
        
        self.standings = StandingRepository()
        self.logs = ScrapingLogRepository()
        self.analysis_results = BaseRepository(table_name="comprehensive_analysis_results", model_class=ComprehensiveAnalysisModel)
        self.odds_changes = BaseRepository(table_name="odds_changes", model_class=OddsChangeModel)
        self.over_under_odds_changes = BaseRepository(table_name="over_under_odds_changes", model_class=OverUnderOddsChangeModel)
        self.asian_handicap_odds = BaseRepository(table_name="asian_handicap_odds", model_class=AsianHandicapOddsModel)
        
        # Performance tracking
        self._operation_stats = {
            'odds_operations': 0,
            'company_operations': 0,
            'total_records_processed': 0,
            'failed_operations': 0,
            'avg_batch_time': 0.0
        }
        self._stats_lock = threading.Lock()
        
        # 批量写入队列（用于避免多线程并发写入导致的数据库竞锁）
        self.batch_writer = None
        if use_batch_writer:
            try:
                from database.batch_writer import BatchWriter
                self.batch_writer = BatchWriter(
                    self,
                    batch_size=500,
                    flush_interval=2.0,
                    max_queue_size=10000
                )
                self.batch_writer.start()
                self.logger.info("BatchWriter enabled for DatabaseManager (避免数据库竞锁)")
            except Exception as e:
                self.logger.warning(f"Failed to initialize BatchWriter: {e}, 将使用直接写入模式")
                self.batch_writer = None
        
        self.logger.info("Database manager initialized with optimized repositories")
    
    def store_analysis_result(self, analysis_data: Dict[str, Any]):
        """Store comprehensive analysis result."""
        return _store_analysis_result(self, analysis_data)

    def get_latest_odds_analysis(self, match_id: int) -> Optional[Dict]:
        """
        从 odds_analysis_results 表中获取指定比赛的最新一条分析结果。
        """
        return _get_latest_odds_analysis(self, match_id)

    def get_all_companies_map(self) -> Dict[int, CompanyModel]:
        """
        获取所有博彩公司ID到公司模型的映射字典。
        """
        return _get_all_companies_map(self)
    
    def get_today_scheduled_match_ids(self, league_ids: Optional[List[int]] = None) -> List[int]:
        """
        获取今天所有状态为“未开始”的比赛ID。
        可选择按联赛ID进行过滤。
        """
        return _get_today_scheduled_match_ids(self, league_ids=league_ids)

    def upsert_odds_changes(self, odds_changes: List[OddsChangeModel]) -> int:
        """
        将赔率状态数据批量插入或更新到 `odds_changes` 表。
        使用 (match_id, company_id) 作为冲突键。

        Args:
            odds_changes: OddsChangeModel 对象的列表。

        Returns:
            成功处理的记录数。
        """
        return _upsert_odds_changes(self, odds_changes)

    def bulk_upsert_odds_changes(self, odds_changes: List[OddsChangeModel]) -> int:
        """
        使用更高效的单条SQL语句批量插入或更新 odds_changes 表。
        
        如果启用了批量写入队列，则使用队列；否则直接写入。
        这样可以避免多线程并发写入导致的数据库竞锁问题。
        
        Ensures all referenced company_ids exist in companies table before insertion
        to prevent foreign key constraint violations.
        """
        return _bulk_upsert_odds_changes(self, odds_changes)

    def bulk_upsert_over_under_odds_changes(self, changes: List[OverUnderOddsChangeModel]) -> int:
        """
        Persist over/under odds change snapshots.
        
        如果启用了批量写入队列，则使用队列；否则直接写入。
        
        Ensures all referenced company_ids exist in companies table before insertion
        to prevent foreign key constraint violations.
        """
        return _bulk_upsert_over_under_odds_changes(self, changes)

    def bulk_upsert_asian_handicap_odds(self, records: List[AsianHandicapOddsModel]) -> int:
        """批量写入亚盘赔率到 asian_handicap_odds 表。"""
        return _bulk_upsert_asian_handicap_odds(self, records)


    def get_match_ids_by_league(self, league_code: str, limit: int = 10, status: Optional[str] = None) -> List[int]:
        """
        根据联赛代码获取最新的比赛ID列表。
        注意：这里的 league_code 是字符串形式，需要转换为整数ID。
        """
        return _get_match_ids_by_league(self, league_code=league_code, limit=limit, status=status)

    def get_finished_matches_with_zero_odds(self, league_id: int) -> List[int]:
        """
        获取指定联赛中，已完成但赔率公司数量为0的比赛ID列表。
        """
        return _get_finished_matches_with_zero_odds(self, league_id)

    def get_all_companies(self) -> list:
        """获取所有已知的博彩公司"""
        return _get_all_companies(self)

    def add_companies(self, companies: list) -> None:
        """批量添加新的博彩公司"""
        return _add_companies(self, companies)

    def store_multiple_odds_data(self, odds_batch: Dict[int, Dict[str, Any]], force_direct_write: bool = False) -> Dict[int, int]:
        """Store odds data for multiple matches."""
        return _store_multiple_odds_data(
            self,
            odds_batch=odds_batch,
            force_direct_write=force_direct_write,
        )
    
    def get_matches_needing_odds(
        self, 
        league_id: Optional[int] = None,
        only_finished: bool = True
    ) -> List[int]:
        """
        Get list of match IDs that need odds data.
        
        Args:
            league_id: Optional league filter
            only_finished: Whether to only include finished matches
            
        Returns:
            List of match IDs
        """
        return _get_matches_needing_odds(self, league_id=league_id, only_finished=only_finished)
    
    def get_matches_ready_for_odds(
        self, 
        league_id: Optional[int] = None,
        skip_existing_odds: bool = True
    ) -> List[int]:
        """
        Get list of match IDs that are ready for odds scraping based on match status.
        
        Args:
            league_id: Optional league filter
            skip_existing_odds: Whether to skip matches with existing odds data
            
        Returns:
            List of match IDs ready for odds scraping
        """
        return _get_matches_ready_for_odds(
            self,
            league_id=league_id,
            skip_existing_odds=skip_existing_odds,
        )
    
    def get_league_summary(self, league_id: int) -> Dict[str, Any]:
        """Get comprehensive summary for a league."""
        return _get_league_summary(self, league_id)
    
    def get_match_with_odds(self, match_id: int) -> Dict[str, Any]:
        """Get match information with associated odds data."""
        return _get_match_with_odds(self, match_id)
    
    def get_company_odds_stats(self, company_id: int) -> Dict[str, Any]:
        """Get statistics for a specific company's odds."""
        return _get_company_odds_stats(self, company_id)
    
    def log_scraping_operation(
        self,
        scraper_name: str,
        target_type: str,
        target_id: str,
        status: str,
        **kwargs
    ) -> None:
        """Log a scraping operation."""
        return _log_scraping_operation(
            self,
            scraper_name=scraper_name,
            target_type=target_type,
            target_id=target_id,
            status=status,
            **kwargs,
        )
    
    def get_scraping_stats(self, scraper_name: Optional[str] = None) -> Dict[str, Any]:
        """Get scraping statistics."""
        return _get_scraping_stats(self, scraper_name=scraper_name)
    
    def _normalize_match_data_round_status_legacy(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Legacy helper kept for compatibility-focused refactors.

        NOTE:
        The active match normalization entry point is the later
        ``_normalize_match_data`` definition used by ``store_league_data``.
        """
        normalized = match_data.copy()
        
        # Convert match status
        if 'round_status' in normalized:
            round_status = normalized['round_status']
            if round_status == -1:
                normalized['match_status'] = 'finished'
            elif round_status == 0:
                normalized['match_status'] = 'scheduled'
            else:
                normalized['match_status'] = 'live'
        
        return normalized
    
    def _normalize_odds_data(self, odds_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize odds data for database storage."""
        return _normalize_odds_data_impl(self, odds_data)
    
    def _ensure_company_exists(self, company_id: int, odds_data: Dict[str, Any]) -> None:
        """
        Ensure a company exists - OPTIMIZED VERSION with concurrent safety.
        Now uses enhanced repository methods to prevent race conditions.
        """
        return _ensure_company_exists(self, company_id, odds_data)
    
    def cleanup_old_logs(self, days_to_keep: int = 30) -> int:
        """Clean up old scraping logs."""
        return _cleanup_old_logs(self, days_to_keep=days_to_keep)
    
    # ==================== ENHANCED OPTIMIZATION METHODS ====================
    
    def _normalize_odds_data_enhanced(self, odds_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced odds data normalization with improved validation."""
        return _normalize_odds_data_enhanced_impl(self, odds_data)
    
    def _get_company_from_config(self, company_id: int) -> Optional[Dict[str, Any]]:
        """Get company information from configuration."""
        return _get_company_from_config(self, company_id)
    
    def _update_avg_batch_time(self, execution_time: float):
        """Update average batch processing time."""
        return _update_avg_batch_time_impl(self, execution_time)
    
    def get_enhanced_performance_stats(self) -> Dict[str, Any]:
        """Get enhanced performance statistics."""
        return _get_enhanced_performance_stats(self)
    
    def diagnose_database_health(self) -> Dict[str, Any]:
        """Diagnose database health and identify potential issues."""
        return _diagnose_database_health(self)

    def store_odds_data(self, match_id: int, odds_data: Dict[str, Any], **kwargs) -> int:
        """Store odds data for a single match."""
        return _store_odds_data(self, match_id=match_id, odds_data=odds_data)

    def store_league_data(self, league_data: Dict[str, Any]) -> Dict[str, int]:
        """Store league data including teams, matches, and standings."""
        return _store_league_data(self, league_data=league_data)
    
    def _normalize_match_data(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize match data for database storage."""
        normalized = match_data.copy()
        
        # Handle field mappings if needed
        if 'id' in normalized and 'match_id' not in normalized:
            normalized['match_id'] = normalized['id']
        
        # Set default values
        if 'match_status' not in normalized:
            normalized['match_status'] = 'scheduled'
        
        return normalized

    def _ensure_companies_exist(self, company_ids: set) -> None:
        """Ensure all company IDs exist in ``companies`` table."""
        return _ensure_companies_exist_impl(self, company_ids)

    def _ensure_teams_exist(self, team_pairs: list) -> None:
        """Ensure given team IDs exist in ``teams`` table."""
        return _ensure_teams_exist_impl(self, team_pairs)

    def _find_missing_company_ids(self, company_ids: set) -> set:
        """Find missing company IDs in ``companies`` table."""
        return _find_missing_company_ids_impl(self, company_ids)

    def _find_company_info_by_id(self, company_id: int) -> Optional['CompanyInfo']:
        """Find company info by ID from static config."""
        return _find_company_info_by_id_impl(company_id)
