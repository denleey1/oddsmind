#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Modern odds scraper for fetching betting odds from various sources.
Focused specifically on odds data with company filtering and advanced retry logic.
"""

import time
import random
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from core.base_scraper import BaseScraper, ScrapingResult
from core.logger import get_logger, log_performance
from core.decorators import retry, rate_limit, log_execution_time
from core.exceptions import ScrapingError, ValidationError
from .exceptions import ContentError, NetworkError, CompanyFilterError, log_error_context
from config.companies_config import COMPANIES_CONFIG, CompanyInfo, get_companies_by_priority
from .parser import OddsParser
from .utils import ContentProcessor, StatisticsTracker, AdaptiveRateLimit, create_url_with_cache_buster
from .concurrent_utils import HighPerformanceExecutor, ConnectionPool, ConcurrentRateLimit
from .url_config import get_url


class OddsScraperModern(BaseScraper):
    """
    Modern odds scraper with comprehensive error handling and filtering.
    
    Features:
    - Company-based filtering
    - Concurrent processing with rate limiting
    - Smart retry logic with exponential backoff
    - Checkpoint/resume capability
    - Real-time statistics and monitoring
    """
    
    def __init__(
        self,
        company_filter: Optional[str] = None,
        target_companies: Optional[Dict[str, CompanyInfo]] = None,
        parse_all_companies: bool = False,
        config: Optional[Dict[str, Any]] = None,
        executor: Optional[ThreadPoolExecutor] = None
    ):
        """
        Initialize odds scraper.
        
        Args:
            company_filter: Company filter type ('tier1', 'asian', 'european', 'all')
            target_companies: Specific companies to target
            parse_all_companies: If True, parse all companies regardless of filters (for storage)
            config: Optional configuration overrides
            executor: Optional external ThreadPoolExecutor
        """
        super().__init__("odds_scraper", config)
        
        # Use external executor if provided, otherwise create a new one for single-use cases
        self.executor = executor or ThreadPoolExecutor(max_workers=self.config.get('crawler', {}).get('max_workers', 15))
        self.owns_executor = executor is None # Flag to know if we need to shut it down
        
        # Initialize parser
        self.parser = OddsParser()
        
        # Initialize utilities
        self.content_processor = ContentProcessor()
        self.stats_tracker = StatisticsTracker("odds_scraper")
        self.rate_limiter = AdaptiveRateLimit(base_delay=1.0, max_delay=5.0)
        
        # High-performance concurrent components
        max_workers_val = (config.get('crawler', {}).get('max_workers') if config 
                          else self.config.get('crawler', {}).get('max_workers', 15))
        
        self.connection_pool = ConnectionPool(
            pool_connections=max_workers_val,
            pool_maxsize=max_workers_val * 2,
            timeout=(3.0, 20.0)  # Shorter timeout for odds scraping
        )
        self.concurrent_rate_limiter = ConcurrentRateLimit(
            requests_per_second=2.0,  # Conservative for odds scraping
            burst_size=8
        )
        
        # Company filtering setup
        self.company_filter = company_filter
        self.parse_all_companies = parse_all_companies
        
        if target_companies:
            self.target_companies = target_companies
        elif company_filter:
            self.target_companies = self._get_companies_by_filter(company_filter)
        else:
            self.target_companies = {}
        
        # Create company ID set for fast lookup
        self.target_company_ids = {
            str(info.company_id) for info in self.target_companies.values()
        } if self.target_companies else set()
        
        # Only apply filtering if not parsing all companies
        self.filter_companies = bool(self.target_companies) and not self.parse_all_companies
        
        # Thread safety
        self.processing_lock = threading.Lock()
        
        # Tracking
        self.processed_matches: Set[int] = set()
        self.failed_matches: Set[int] = set()
        self.empty_matches: Set[int] = set()  # Matches with no odds data
        
        # 404 ID 缓存已移除 — 之前的永久缓存导致数据源上线后仍被跳过
        # Titan007 的 404 多为暂时性（赛前未收录），下轮抓取自然会成功，无需缓存
        
        # Enhanced statistics
        self.odds_stats = {
            'matches_processed': 0,
            'matches_with_odds': 0,
            'matches_empty': 0,
            'total_odds_records': 0,
            'filtered_odds_records': 0,
            'companies_found': set(),
            'avg_odds_per_match': 0.0
        }
        
        self._log_initialization()
    
    def _log_initialization(self) -> None:
        """Log initialization information."""
        if self.parse_all_companies:
            self.logger.info("Odds scraper initialized to parse ALL companies (no filtering)")
        elif self.filter_companies:
            company_names = [comp.name_cn for comp in self.target_companies.values()]
            self.logger.info(f"Odds scraper initialized with company filter: {', '.join(company_names)}")
            self.logger.info(f"Target company IDs: {', '.join(self.target_company_ids)}")
        else:
            self.logger.info("Odds scraper initialized without company filtering")
    
    def _get_companies_by_filter(self, filter_type: str) -> Dict[str, CompanyInfo]:
        """Get companies based on filter type."""
        if filter_type == 'tier1':
            return get_companies_by_priority(max_priority=10)
        elif filter_type == 'asian':
            return {
                code: info for code, info in COMPANIES_CONFIG.items()
                if info.is_asian and info.is_active
            }
        elif filter_type == 'european':
            return {
                code: info for code, info in COMPANIES_CONFIG.items()
                if not info.is_asian and info.is_active
            }
        else:  # 'all' or unknown
            return {
                code: info for code, info in COMPANIES_CONFIG.items()
                if info.is_active
            }
    
    @log_execution_time()
    def scrape(
        self,
        match_ids: List[int],
        max_workers: Optional[int] = None,
        skip_existing: bool = True,
        **kwargs
    ) -> ScrapingResult:
        """
        Scrape odds for specified matches.
        
        Args:
            match_ids: List of match IDs to process
            max_workers: Maximum concurrent workers
            skip_existing: Whether to skip matches with existing odds
            
        Returns:
            ScrapingResult with operation outcome
        """
        start_time = time.time()
        
        if not match_ids:
            return ScrapingResult(
                success=False,
                error="No match IDs provided"
            )
        
        max_workers = max_workers or self.config['crawler']['max_workers']
        
        self.logger.info(
            f"Starting odds scraping for {len(match_ids)} matches "
            f"(max_workers={max_workers}, skip_existing={skip_existing})"
        )
        self.stats_tracker.start_session()
        
        try:
            # Load checkpoint
            checkpoint = self.load_checkpoint()
            if checkpoint and not kwargs.get('force_refresh', False):
                self.processed_matches = set(checkpoint.get('processed_matches', []))
                self.failed_matches = set(checkpoint.get('failed_matches', []))
                self.empty_matches = set(checkpoint.get('empty_matches', []))
                self.logger.info(f"Resumed from checkpoint: {len(self.processed_matches)} processed")
            
            # Filter match IDs if skip_existing is enabled
            if skip_existing:
                original_count = len(match_ids)
                match_ids = [mid for mid in match_ids if mid not in self.processed_matches]
                if len(match_ids) < original_count:
                    self.logger.info(f"Skipped {original_count - len(match_ids)} already processed matches")
            
            if not match_ids:
                return ScrapingResult(
                    success=True,
                    data={},
                    metadata={'message': 'All matches already processed'}
                )
            
            # Process matches with concurrent execution
            results = self._process_matches_concurrent(match_ids, max_workers)
            
            # Calculate final statistics
            execution_time = time.time() - start_time
            successful_matches = len([r for r in results.values() if r.success])
            
            # End statistics session
            self.stats_tracker.end_session()
            
            # Update global stats
            self.stats['items_processed'] = len(results)
            self.stats['items_success'] = successful_matches
            self.stats['items_failed'] = len(results) - successful_matches
            
            # Update odds-specific stats
            self.odds_stats['matches_processed'] = len(results)
            self.odds_stats['matches_with_odds'] = len([
                r for r in results.values() 
                if r.success and r.data and len(r.data.get('odds', [])) > 0
            ])
            self.odds_stats['matches_empty'] = len([
                r for r in results.values()
                if r.success and (not r.data or len(r.data.get('odds', [])) == 0)
            ])
            
            total_odds = sum(
                len(r.data.get('odds', []))
                for r in results.values() 
                if r.success and r.data
            )
            self.odds_stats['total_odds_records'] = total_odds
            
            if self.odds_stats['matches_with_odds'] > 0:
                self.odds_stats['avg_odds_per_match'] = total_odds / self.odds_stats['matches_with_odds']
            
            # Clear checkpoint if all successful
            if self.stats['items_failed'] == 0:
                self.clear_checkpoint()
            
            return ScrapingResult(
                success=True,
                data=results,
                metadata={
                    'matches_processed': self.odds_stats['matches_processed'],
                    'matches_with_odds': self.odds_stats['matches_with_odds'],
                    'matches_empty': self.odds_stats['matches_empty'],
                    'total_odds_records': self.odds_stats['total_odds_records'],
                    'avg_odds_per_match': round(self.odds_stats['avg_odds_per_match'], 2),
                    'companies_found': len(self.odds_stats['companies_found']),
                    'filter_enabled': self.filter_companies,
                    'target_companies': len(self.target_companies) if self.target_companies else 0
                },
                execution_time=execution_time
            )
            
        except Exception as e:
            self.logger.error(f"Odds scraping failed: {e}", exc_info=True)
            return ScrapingResult(
                success=False,
                error=f"Odds scraping failed: {str(e)}",
                execution_time=time.time() - start_time
            )
    
    def _process_matches_concurrent(
        self, 
        match_ids: List[int], 
        max_workers: int
    ) -> Dict[int, ScrapingResult]:
        """Process matches with optimized concurrent execution."""
        results = {}
        executor = self.executor # Use the class-level executor
        
        # Pre-allocate futures with rate limiting
        future_to_match = {}
        submitted_count = 0
        
        for match_id in match_ids:
            # [性能优化] 速率限制：超时时延迟重试，不直接跳过
            max_rate_limit_retries = 3
            rate_limit_retry_count = 0
            
            while rate_limit_retry_count < max_rate_limit_retries:
                if self.concurrent_rate_limiter.acquire(timeout=5.0):
                    # 成功获取许可，提交任务
                    break
                else:
                    # 速率限制超时，延迟后重试
                    rate_limit_retry_count += 1
                    if rate_limit_retry_count < max_rate_limit_retries:
                        retry_delay = 2.0 + (rate_limit_retry_count * 0.5)  # 递增延迟：2s, 2.5s, 3s
                        self.logger.warning(
                            f"Rate limit timeout for match {match_id}, "
                            f"retrying after {retry_delay}s (attempt {rate_limit_retry_count}/{max_rate_limit_retries})"
                        )
                        time.sleep(retry_delay)
                    else:
                        # 达到最大重试次数，跳过（避免无限等待）
                        self.logger.warning(f"Rate limit timeout for match {match_id} after {max_rate_limit_retries} retries, skipping")
                        continue
            
            # 如果成功获取许可，提交任务
            if rate_limit_retry_count < max_rate_limit_retries:
                future = executor.submit(self._scrape_match_odds, match_id)
                future_to_match[future] = match_id
                submitted_count += 1
            # 注意：如果达到最大重试次数，这个match_id会被跳过，不提交任务
        
        self.logger.info(f"Submitted {submitted_count}/{len(match_ids)} tasks to thread pool")
        
        # Process results with enhanced monitoring
        completed = 0
        success_count = 0
        batch_start_time = time.time()
        
        for future in as_completed(future_to_match):
            match_id = future_to_match[future]
            completed += 1
            
            try:
                result = future.result(timeout=30.0)  # Add timeout to prevent hanging
                results[match_id] = result
                
                # Track processing results with thread safety
                with self.processing_lock:
                    if result.success:
                        self.processed_matches.add(match_id)
                        self.failed_matches.discard(match_id)
                        success_count += 1
                        
                        # Track statistics
                        if result.data and len(result.data.get('odds', [])) == 0:
                            self.empty_matches.add(match_id)
                            self.stats_tracker.record_empty()
                        else:
                            self.stats_tracker.record_success(result.execution_time)
                    else:
                        self.failed_matches.add(match_id)
                        self.stats_tracker.record_failure("scraping_error")
                
                # Enhanced progress reporting with throughput metrics
                if completed % 10 == 0 or completed == submitted_count:
                    elapsed = time.time() - batch_start_time
                    throughput = completed / max(elapsed, 1)
                    progress_pct = (completed / submitted_count) * 100
                    
                    self.logger.info(
                        f"Progress: {completed}/{submitted_count} ({progress_pct:.1f}%) - "
                        f"Success: {success_count}, Failed: {completed - success_count} - "
                        f"Throughput: {throughput:.1f} req/s"
                    )
                    
                    # Log connection pool stats periodically
                    if completed % 25 == 0:
                        conn_stats = self.connection_pool.get_stats()
                        self.logger.info(f"Connection pool: {conn_stats['success_rate']:.1f}% success, "
                                       f"{conn_stats['avg_response_time']:.2f}s avg response time")
                        self._save_progress_checkpoint()
            
            except Exception as e:
                self.logger.error(f"Error processing match {match_id}: {e}")
                results[match_id] = ScrapingResult(
                    success=False,
                    error=f"Processing error: {str(e)}"
                )
                
                with self.processing_lock:
                    self.failed_matches.add(match_id)
        
        # Log final performance metrics
        total_time = time.time() - batch_start_time
        final_throughput = completed / max(total_time, 1)
        self.logger.info(f"Concurrent processing completed: {final_throughput:.1f} req/s average throughput")
        
        return results
    
    def _scrape_match_odds(self, match_id: int) -> ScrapingResult:
        """
        Optimized scrape odds for a single match with connection pooling.
        
        [性能优化] 404错误快速失败，不重试；缓存无效ID避免重复请求。
        
        Args:
            match_id: Match identifier
            
        Returns:
            ScrapingResult for the match
        """
        start_time = time.time()
        
        self.logger.debug(f"Scraping odds for match {match_id}")
        
        # Retry logic with exponential backoff
        max_attempts = 3
        base_delay = 0.5
        
        for attempt in range(max_attempts):
            try:
                # Fetch odds data using connection pool
                with log_performance(self.logger, f"fetch_odds_{match_id}"):
                    base_url = get_url("match_odds", match_id=match_id)
                    odds_url = create_url_with_cache_buster(base_url)
                    
                    # Use connection pool instead of make_request
                    response = self.connection_pool.get(odds_url)
                    
                    # 404错误：数据源暂未收录，快速失败不重试，下轮抓取自然重试
                    if response.status_code == 404:
                        self.logger.warning(f"Match {match_id} returned 404 from data source, will retry next cycle")
                        return ScrapingResult(
                            success=False,
                            error=f"Match {match_id} not found (404)",
                            metadata={
                                'match_id': match_id,
                                'status_code': 404,
                                'attempt': attempt + 1,
                                'fast_fail': True
                            },
                            execution_time=time.time() - start_time
                        )
                    
                    # Handle encoding using utility
                    content = self.content_processor.decode_content(response.content)
            
                # Validate content using utility
                if not self.content_processor.validate_content(content, min_length=50):
                    raise ContentError(
                        f"Invalid odds content for match {match_id}",
                        content_length=len(content),
                        url=odds_url
                    )
                
                # Check for empty odds data
                if 'var game=Array();' in content or 'var game=Array( );' in content:
                    self.logger.debug(f"Match {match_id} has no odds data")
                    return ScrapingResult(
                        success=True,
                        data={'odds': [], 'empty': True},
                        metadata={
                            'match_id': match_id,
                            'content_size': len(content),
                            'empty_data': True,
                            'attempt': attempt + 1
                        },
                        execution_time=time.time() - start_time
                    )
                
                # Parse odds data
                with log_performance(self.logger, f"parse_odds_{match_id}"):
                    parsed_data = self.parser.parse(content)
                
                # Filter by companies if enabled
                if self.filter_companies and parsed_data.get('odds'):
                    original_count = len(parsed_data['odds'])
                    parsed_data['odds'] = [
                        odds for odds in parsed_data['odds']
                        if str(odds.get('company_id', '')) in self.target_company_ids
                    ]
                    filtered_count = len(parsed_data['odds'])
                    
                    self.logger.debug(
                        f"Match {match_id}: filtered {original_count} -> {filtered_count} odds records"
                    )
                    self.odds_stats['filtered_odds_records'] += filtered_count
                
                # Track companies found
                if parsed_data.get('odds'):
                    for odds in parsed_data['odds']:
                        if odds.get('company_id'):
                            self.odds_stats['companies_found'].add(odds['company_id'])
                
                execution_time = time.time() - start_time
                odds_count = len(parsed_data.get('odds', []))
                
                if odds_count > 0:
                    self.logger.debug(f"Match {match_id}: found {odds_count} odds records")
                
                return ScrapingResult(
                    success=True,
                    data=parsed_data,
                    metadata={
                        'match_id': match_id,
                        'odds_count': odds_count,
                        'content_size': len(content),
                        'companies_count': len(set(
                            odds.get('company_id') for odds in parsed_data.get('odds', [])
                            if odds.get('company_id')
                        )),
                        'filtered': self.filter_companies,
                        'attempt': attempt + 1
                    },
                    execution_time=execution_time
                )
                
            except NetworkError as e:
                # [性能优化] 检查是否是404错误（NetworkError可能包含status_code）
                status_code = getattr(e, 'context', {}).get('status_code') if hasattr(e, 'context') else None
                if status_code == 404:
                    # 404错误快速失败，不重试，下轮抓取自然重试
                    execution_time = time.time() - start_time
                    self.logger.warning(f"Match {match_id} returned 404 via NetworkError, will retry next cycle")
                    return ScrapingResult(
                        success=False,
                        error=f"Match {match_id} not found (404)",
                        metadata={
                            'match_id': match_id,
                            'status_code': 404,
                            'attempt': attempt + 1,
                            'fast_fail': True
                        },
                        execution_time=execution_time
                    )
                
                # 其他网络错误（连接超时、DNS错误等）可以重试
                if attempt < max_attempts - 1:
                    delay = base_delay * (2 ** attempt)  # Exponential backoff
                    self.logger.warning(f"Match {match_id} attempt {attempt + 1} failed (network error): {e}, retrying in {delay}s")
                    time.sleep(delay)
                    continue
                else:
                    # Final attempt failed
                    execution_time = time.time() - start_time
                    error_msg = f"Failed to scrape odds for match {match_id} after {max_attempts} attempts: {str(e)}"
                    self.logger.error(error_msg)
                    
                    return ScrapingResult(
                        success=False,
                        error=error_msg,
                        metadata={
                            'match_id': match_id,
                            'attempts': max_attempts,
                            'final_error_type': type(e).__name__
                        },
                        execution_time=execution_time
                    )
            
            except ContentError as e:
                # 内容错误通常不需要重试（可能是数据格式问题）
                execution_time = time.time() - start_time
                error_msg = f"Content error for match {match_id}: {str(e)}"
                self.logger.warning(error_msg)
                
                return ScrapingResult(
                    success=False,
                    error=error_msg,
                    metadata={
                        'match_id': match_id,
                        'attempt': attempt + 1,
                        'error_type': type(e).__name__
                    },
                    execution_time=execution_time
                )
            
            except Exception as e:
                # Unexpected errors - don't retry
                execution_time = time.time() - start_time
                error_msg = f"Unexpected error scraping match {match_id}: {str(e)}"
                self.logger.error(error_msg)
                
                return ScrapingResult(
                    success=False,
                    error=error_msg,
                    metadata={
                        'match_id': match_id,
                        'attempt': attempt + 1,
                        'error_type': type(e).__name__
                    },
                    execution_time=execution_time
                )
        
        # Should never reach here, but just in case
        return ScrapingResult(
            success=False,
            error=f"Unexpected end of retry loop for match {match_id}",
            execution_time=time.time() - start_time
        )
    
    def _save_progress_checkpoint(self) -> None:
        """Save current progress to checkpoint."""
        checkpoint_data = {
            'processed_matches': list(self.processed_matches),
            'failed_matches': list(self.failed_matches),
            'empty_matches': list(self.empty_matches),
            'odds_stats': {
                **self.odds_stats,
                'companies_found': list(self.odds_stats['companies_found'])
            },
            'filter_config': {
                'filter_companies': self.filter_companies,
                'company_filter': self.company_filter,
                'target_company_ids': list(self.target_company_ids)
            }
        }
        
        self.save_checkpoint(checkpoint_data)
    
    def get_company_summary(self) -> Dict[str, Any]:
        """Get summary of company filtering configuration."""
        if not self.target_companies:
            return {
                'filtering_enabled': False,
                'message': 'No company filtering active'
            }
        
        companies_info = []
        for code, info in self.target_companies.items():
            companies_info.append({
                'code': code,
                'id': info.company_id,
                'name_en': info.name_en,
                'name_cn': info.name_cn,
                'country': info.country,
                'priority': info.priority,
                'is_asian': info.is_asian
            })
        
        # Sort by priority
        companies_info.sort(key=lambda x: x['priority'])
        
        return {
            'filtering_enabled': True,
            'filter_type': self.company_filter,
            'total_companies': len(companies_info),
            'companies': companies_info,
            'target_ids': sorted(self.target_company_ids)
        }
    
    def get_processing_status(self) -> Dict[str, Any]:
        """Get detailed processing status with performance metrics."""
        base_status = {
            'processed_matches': len(self.processed_matches),
            'failed_matches': len(self.failed_matches),
            'empty_matches': len(self.empty_matches),
            'odds_statistics': {
                **self.odds_stats,
                'companies_found': list(self.odds_stats['companies_found'])
            },
            'company_config': self.get_company_summary(),
            'global_stats': self.get_stats()
        }
        
        # Add performance metrics from concurrent components
        try:
            base_status['connection_pool_stats'] = self.connection_pool.get_stats()
            base_status['rate_limiter_stats'] = self.concurrent_rate_limiter.get_stats()
            base_status['statistics_tracker'] = self.stats_tracker.get_summary()
        except Exception as e:
            self.logger.warning(f"Could not get performance stats: {e}")
        
        return base_status
    
    def close(self):
        """Clean up resources when scraper is done."""
        try:
            if hasattr(self, 'connection_pool'):
                self.connection_pool.close()
            
            # Shut down the executor only if this instance created it
            if hasattr(self, 'owns_executor') and self.owns_executor and hasattr(self, 'executor'):
                self.executor.shutdown(wait=False)

            self.logger.info("Odds scraper resources cleaned up successfully")
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")
    
    def __del__(self):
        """Ensure cleanup on object destruction."""
        try:
            self.close()
        except:
            pass