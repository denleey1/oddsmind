#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
League scraper for fetching and processing league data.
Specialized scraper focused on league information, teams, matches, and standings.
"""

import time
from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import random

from core.base_scraper import BaseScraper, ScrapingResult
from core.logger import get_logger, log_performance
from core.decorators import retry, rate_limit, log_execution_time
from core.exceptions import ScrapingError, ValidationError
from .exceptions import ContentError, NetworkError, DataValidationError, log_error_context
from config.leagues_config import LEAGUES_CONFIG, LeagueInfo
from .parser import Titan007Parser
from .utils import ContentProcessor, StatisticsTracker, AdaptiveRateLimit
from .url_config import get_url


class LeagueScraper(BaseScraper):
    """
    Scraper for league data from Titan007.
    
    Handles:
    - League information
    - Teams data  
    - Match schedules and results
    - League standings
    - Smart incremental updates
    """
    
    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize league scraper.
        
        Args:
            config: Optional configuration overrides
        """
        super().__init__("league_scraper", config)
        
        # Initialize parser
        self.parser = Titan007Parser()
        
        # Initialize utilities
        self.content_processor = ContentProcessor()
        self.stats_tracker = StatisticsTracker("league_scraper")
        # [修复] base_delay 从 2.0s 降到 0.5s — 原来每联赛纯等待2秒太浪费
        # make_request() 的 @rate_limit(2.0 calls/s) 已提供足够的限速保护
        self.rate_limiter = AdaptiveRateLimit(base_delay=0.5, max_delay=5.0)
        
        # Tracking
        self.processed_leagues: Set[str] = set()
        self.failed_leagues: Set[str] = set()
        
        # Statistics specific to league scraping
        self.league_stats = {
            'leagues_processed': 0,
            'teams_found': 0,
            'matches_found': 0,
            'standings_sections': 0
        }

    def _fetch_validated_league_content(
        self,
        league_code: str,
        url: str,
        max_attempts: int = 3,
    ) -> str:
        """Retry transient short/error responses before marking a league failed."""
        last_error: Optional[Exception] = None

        for attempt in range(1, max_attempts + 1):
            try:
                response = self.make_request(url)
                content = self.content_processor.decode_content(response.content)

                if self.content_processor.validate_content(
                    content,
                    min_length=100,
                    required_markers=['var arrLeague']
                ):
                    return content

                raise ContentError(
                    f"Invalid or incomplete content for {league_code}",
                    content_length=len(content),
                    expected_markers=['var arrLeague'],
                    url=url
                )
            except (ContentError, ScrapingError) as exc:
                last_error = exc
                if attempt >= max_attempts:
                    break

                delay = min(0.8 * attempt, 3.0) + random.uniform(0.1, 0.4)
                self.logger.warning(
                    "League %s fetch attempt %s/%s failed, retrying in %.1fs: %s",
                    league_code,
                    attempt,
                    max_attempts,
                    delay,
                    exc,
                )
                time.sleep(delay)

        raise last_error or ContentError(
            f"Invalid or incomplete content for {league_code}",
            url=url
        )
    
    @log_execution_time()
    def scrape(
        self,
        league_codes: Optional[List[str]] = None,
        force_refresh: bool = False,
        **kwargs
    ) -> ScrapingResult:
        """
        Scrape league data for specified leagues.
        
        Args:
            league_codes: List of league codes to scrape (None for all)
            force_refresh: Whether to force refresh even if recently updated
            
        Returns:
            ScrapingResult with operation outcome
        """
        start_time = time.time()
        
        try:
            # Determine which leagues to process
            if league_codes:
                leagues_to_process = {
                    code: info for code, info in LEAGUES_CONFIG.items()
                    if code in league_codes and info.is_active
                }
            else:
                leagues_to_process = {
                    code: info for code, info in LEAGUES_CONFIG.items()
                    if info.is_active
                }
            
            if not leagues_to_process:
                return ScrapingResult(
                    success=False,
                    error="No active leagues found to process"
                )
            
            self.logger.info(f"Starting league scraping for {len(leagues_to_process)} leagues")
            self.stats_tracker.start_session()
            
            # Load checkpoint if available
            if not force_refresh:
                checkpoint = self.load_checkpoint()
                if checkpoint:
                    self.processed_leagues = set(checkpoint.get('processed_leagues', []))
                    self.failed_leagues = set(checkpoint.get('failed_leagues', []))
                    self.logger.info(f"Resuming from checkpoint: {len(self.processed_leagues)} already processed")
            
            # Process each league
            results = {}
            for league_code, league_info in leagues_to_process.items():
                
                # Skip if already processed recently (unless force refresh)
                if not force_refresh and league_code in self.processed_leagues:
                    self.logger.debug(f"Skipping {league_code} (already processed)")
                    continue
                
                try:
                    result = self._scrape_league(league_code, league_info)
                    results[league_code] = result
                    
                    if result.success:
                        self.processed_leagues.add(league_code)
                        self.failed_leagues.discard(league_code)
                        self.league_stats['leagues_processed'] += 1
                        self.stats_tracker.record_success(result.execution_time)
                        self.rate_limiter.record_success()
                    else:
                        self.failed_leagues.add(league_code)
                        self.logger.error(f"Failed to scrape league {league_code}: {result.error}")
                        self.stats_tracker.record_failure("scraping_error")
                        self.rate_limiter.record_failure()
                    
                    # Save checkpoint periodically
                    if len(results) % 5 == 0:
                        self._save_progress_checkpoint()
                    
                    # Adaptive rate limiting between leagues
                    self.rate_limiter.wait()
                    
                except Exception as e:
                    self.logger.error(f"Unexpected error scraping {league_code}: {e}", exc_info=True)
                    self.failed_leagues.add(league_code)
                    results[league_code] = ScrapingResult(
                        success=False,
                        error=f"Unexpected error: {str(e)}"
                    )
            
            # Final statistics
            execution_time = time.time() - start_time
            successful_leagues = len([r for r in results.values() if r.success])
            
            # End statistics session
            self.stats_tracker.end_session()
            
            # Update global stats
            self.stats['items_processed'] = len(results)
            self.stats['items_success'] = successful_leagues
            self.stats['items_failed'] = len(results) - successful_leagues
            
            # Clear checkpoint if all successful
            if self.stats['items_failed'] == 0:
                self.clear_checkpoint()
            
            return ScrapingResult(
                success=True,
                data=results,
                metadata={
                    'leagues_processed': successful_leagues,
                    'leagues_failed': self.stats['items_failed'],
                    'total_teams': self.league_stats['teams_found'],
                    'total_matches': self.league_stats['matches_found'],
                    'standings_sections': self.league_stats['standings_sections']
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            self.logger.error(f"League scraping failed: {e}", exc_info=True)
            return ScrapingResult(
                success=False,
                error=f"League scraping failed: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    @retry(max_attempts=2, delay=1.0, backoff_factor=2.0)
    # [修复] 移除 @rate_limit — make_request() 已有限速装饰器，双重限速导致串行化
    # [修复] retry: 3次→2次, delay: 2s→1s — 减少失败联赛的阻塞时间
    def _scrape_league(self, league_code: str, league_info: LeagueInfo) -> ScrapingResult:
        """
        Scrape a single league.
        
        Args:
            league_code: League identifier code
            league_info: League configuration information
            
        Returns:
            ScrapingResult for the league operation
        """
        start_time = time.time()
        
        self.logger.info(f"Scraping league: {league_info.name_cn} ({league_code})")
        
        try:
            # Fetch league data
            with log_performance(self.logger, f"fetch_league_data_{league_code}"):
                url = get_url(
                    "league_results",
                    season=league_info.season,
                    league_filename=league_info.league_filename
                )
                content = self._fetch_validated_league_content(league_code, url)
            
            # Parse the data
            with log_performance(self.logger, f"parse_league_data_{league_code}"):
                parsed_data = self.parser.parse(content)
            
            # Validate parsed data
            validation_errors = self.parser.validate_parsed_data(parsed_data)
            if validation_errors:
                raise DataValidationError(
                    f"League data validation failed for {league_code}",
                    validation_errors=validation_errors,
                    data_type="league_data"
                )
            
            # Update statistics
            if 'teams' in parsed_data:
                self.league_stats['teams_found'] += len(parsed_data['teams'])
            
            if 'matches' in parsed_data:
                matches_count = sum(len(matches) for matches in parsed_data['matches'].values())
                self.league_stats['matches_found'] += matches_count
            
            if 'standings' in parsed_data:
                self.league_stats['standings_sections'] += len(parsed_data['standings'])
            
            execution_time = time.time() - start_time
            
            self.logger.info(
                f"Successfully scraped {league_code}: "
                f"{len(parsed_data.get('teams', []))} teams, "
                f"{sum(len(m) for m in parsed_data.get('matches', {}).values())} matches"
            )
            
            return ScrapingResult(
                success=True,
                data=parsed_data,
                metadata={
                    'league_code': league_code,
                    'league_info': league_info._asdict(),
                    'content_size': len(content),
                    'teams_count': len(parsed_data.get('teams', [])),
                    'matches_count': sum(len(m) for m in parsed_data.get('matches', {}).values()),
                    'rounds_found': len(parsed_data.get('matches', {}))
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            error_msg = f"Failed to scrape league {league_code}: {str(e)}"
            self.logger.error(error_msg)
            
            return ScrapingResult(
                success=False,
                error=error_msg,
                metadata={
                    'league_code': league_code,
                    'league_info': league_info._asdict()
                },
                execution_time=execution_time
            )
    
    def _save_progress_checkpoint(self) -> None:
        """Save current progress to checkpoint."""
        checkpoint_data = {
            'processed_leagues': list(self.processed_leagues),
            'failed_leagues': list(self.failed_leagues),
            'league_stats': self.league_stats.copy(),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.save_checkpoint(checkpoint_data)
    
    def get_league_summary(self, league_code: str) -> Optional[Dict[str, Any]]:
        """
        Get summary information for a specific league.
        
        Args:
            league_code: League identifier
            
        Returns:
            League summary or None if not found
        """
        if league_code not in LEAGUES_CONFIG:
            return None
        
        league_info = LEAGUES_CONFIG[league_code]
        
        return {
            'code': league_code,
            'name_cn': league_info.name_cn,
            'name_en': league_info.name_en,
            'country': league_info.country,
            'level': league_info.level,
            'season': league_info.season,
            'total_rounds': league_info.total_rounds,
            'is_active': league_info.is_active,
            'league_filename': league_info.league_filename,
            'processed': league_code in self.processed_leagues,
            'failed': league_code in self.failed_leagues
        }
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get current processing status."""
        total_leagues = len([info for info in LEAGUES_CONFIG.values() if info.is_active])
        
        return {
            'total_active_leagues': total_leagues,
            'processed_leagues': len(self.processed_leagues),
            'failed_leagues': len(self.failed_leagues),
            'remaining_leagues': total_leagues - len(self.processed_leagues),
            'success_rate': len(self.processed_leagues) / max(total_leagues, 1) * 100,
            'league_stats': self.league_stats.copy(),
            'global_stats': self.get_stats()
        }
