#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""CLI application logic for OddsMind."""

from __future__ import annotations

import argparse

from typing import Any, Dict, List

from core.logger import get_logger
from core.exceptions import OddsMindError
from config.leagues_config import (
    LEAGUES_CONFIG,
    get_league_group_codes,
)
from config.companies_config import COMPANIES_CONFIG
from database import DatabaseManager, get_connection
from scrapers import LeagueScraper
from utils import get_performance_monitor
from application.cli.cli_command_handlers import (
    handle_analyze_fundamental as _handle_analyze_fundamental,
    handle_analyze_odds as _handle_analyze_odds,
    handle_calculate_strength as _handle_calculate_strength,
    handle_scrape_odds as _handle_scrape_odds,
)


class OddsMindCLI:
    """Main CLI application class."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.db_manager = DatabaseManager()
        self.performance_monitor = get_performance_monitor()
    
    def __del__(self):
        """Cleanup on destruction."""
        try:
            if hasattr(self, 'db_manager') and self.db_manager and self.db_manager.batch_writer:
                if self.db_manager.batch_writer.running:
                    self.logger.info("Stopping BatchWriter on cleanup...")
                    self.db_manager.batch_writer.stop(timeout=10)
        except Exception as e:
            pass  # Ignore errors during cleanup
    
    def run(self, args) -> int:
        """Run the CLI application."""
        try:
            # Set up performance monitoring if requested
            if args.performance_monitoring:
                self.logger.info("Performance monitoring enabled")
            
            # Route to appropriate command handler
            if args.command == 'db-init':
                return self.handle_db_init(args)
            elif args.command == 'db-status':
                return self.handle_db_status(args)
            elif args.command == 'db-test':
                return self.handle_db_test(args)
            elif args.command == 'scrape-leagues':
                return self.handle_scrape_leagues(args)
            elif args.command == 'scrape-odds':
                return self.handle_scrape_odds(args)
            elif args.command == 'full-pipeline':
                return self.handle_full_pipeline(args)
            elif args.command == 'monitor-performance':
                return self.handle_monitor_performance(args)
            elif args.command == 'show-stats':
                return self.handle_show_stats(args)
            elif args.command == 'analyze-fundamental':
                return self.handle_analyze_fundamental(args)
            elif args.command == 'analyze-odds':
                return self.handle_analyze_odds(args)
            elif args.command == 'calculate-strength':
                return self.handle_calculate_strength(args)
            elif args.command == 'maintenance':
                return self.handle_maintenance(args)
            else:
                self.logger.error(f"Unknown command: {args.command}")
                return 1
                
        except KeyboardInterrupt:
            self.logger.info("\nOperation interrupted by user")
            self._cleanup()
            return 130
        except OddsMindError as e:
            self.logger.error(f"OddsMind error: {e}")
            self._cleanup()
            return 1
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}", exc_info=True)
            self._cleanup()
            return 1
        finally:
            self._cleanup()
    
    def _cleanup(self):
        """Cleanup resources."""
        try:
            if self.db_manager and self.db_manager.batch_writer:
                if self.db_manager.batch_writer.running:
                    self.logger.info("Stopping BatchWriter and flushing remaining data...")
                    self.db_manager.batch_writer.stop(timeout=10)
        except Exception as e:
            self.logger.warning(f"Error during cleanup: {e}")
    
    def handle_db_init(self, args) -> int:
        """Initialize database."""
        self.logger.info("Initializing database...")
        
        try:
            # Test connection first
            db_conn = get_connection()
            if not db_conn.test_connection():
                self.logger.error("Database connection test failed")
                return 1
            
            # Clear existing companies data and re-initialize
            try:
                db_conn.execute_query("DELETE FROM companies WHERE company_id NOT IN (SELECT DISTINCT company_id FROM european_odds)")
                self.logger.info("Cleared existing companies data")
                
                # Re-initialize companies data
                db_conn._initialize_reference_data()
                self.logger.info("Re-initialized companies data")
            except Exception as e:
                self.logger.warning(f"Could not reinitialize companies: {e}")
            
            self.logger.info("Database initialized successfully")
            return 0
            
        except Exception as e:
            self.logger.error(f"Database initialization failed: {e}")
            return 1
    
    def handle_db_status(self, args) -> int:
        """Show database status."""
        try:
            db_conn = get_connection()
            
            # Test connection
            if db_conn.test_connection():
                self.logger.info("Database connection: OK")
            else:
                self.logger.error("Database connection: FAILED")
                return 1
            
            # Get table info
            tables = ['leagues', 'teams', 'matches', 'companies', 'european_odds', 'standings']
            
            self.logger.info("\nDatabase Status:")
            self.logger.info("=" * 50)
            
            for table in tables:
                try:
                    count = db_conn.get_table_row_count(table)
                    self.logger.info(f"{table:20}: {count:>10,} rows")
                except Exception as e:
                    self.logger.warning(f"{table:20}: Error - {e}")
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error getting database status: {e}")
            return 1
    
    def handle_db_test(self, args) -> int:
        """Test database connection."""
        try:
            db_conn = get_connection()
            if db_conn.test_connection():
                self.logger.info("Database connection test passed")
                return 0
            else:
                self.logger.error("Database connection test failed")
                return 1
        except Exception as e:
            self.logger.error(f"Database test error: {e}")
            return 1
    
    def handle_scrape_leagues(self, args) -> int:
        """Handle league scraping command."""
        self.logger.info("Starting league scraping...")
        
        # Determine which leagues to scrape
        if args.leagues:
            league_codes = [code.strip() for code in args.leagues.split(',')]
        elif args.league_group:
            league_codes = get_league_group_codes(args.league_group)
        else:
            league_codes = list(LEAGUES_CONFIG.keys())[:5]  # Limit for safety
        
        self.logger.info(f"Scraping {len(league_codes)} leagues: {', '.join(league_codes)}")
        
        # Create league scraper
        scraper = LeagueScraper()
        
        # Run scraping
        with self.performance_monitor.monitor_operation("scrape_leagues"):
            result = scraper.scrape(
                league_codes=league_codes,
                force_refresh=args.force_refresh
            )
        
        # Store results
        if result.success and result.data:
            stored_count = 0
            for league_code, league_result in result.data.items():
                if league_result.success:
                    try:
                        # 注入分区标识（用于分区赛制联赛, 如日职J1东/西区）
                        league_info = LEAGUES_CONFIG.get(league_code)
                        division = league_info.division if league_info and league_info.division else None
                        if division and league_result.data and 'matches' in league_result.data:
                            for round_key, round_matches in league_result.data['matches'].items():
                                for match_data in round_matches:
                                    if isinstance(match_data, dict):
                                        match_data['division'] = division

                        counts = self.db_manager.store_league_data(league_result.data)
                        stored_count += sum(counts.values())
                        self.logger.info(
                            f"Stored {league_code}: "
                            f"{counts.get('teams', 0)} teams, "
                            f"{counts.get('matches', 0)} matches, "
                            f"{counts.get('standings', 0)} standings"
                            + (f" [division={division}]" if division else "")
                        )
                    except Exception as e:
                        self.logger.error(f"Error storing {league_code}: {e}")
            
            self.logger.info(f"League scraping completed. Total records stored: {stored_count}")
        
        return 0 if result.success else 1
    
    def handle_scrape_odds(self, args) -> int:
        """Handle odds scraping command."""
        return _handle_scrape_odds(self, args)
    
    def handle_full_pipeline(self, args) -> int:
        """Handle full pipeline command."""
        self.logger.info("Starting full scraping pipeline...")
        
        # Step 1: Scrape leagues
        self.logger.info("Step 1: Scraping league data...")
        league_args = argparse.Namespace(
            league_group=args.league_group,
            leagues=None,
            force_refresh=False,
            max_workers=args.max_workers
        )
        
        league_result = self.handle_scrape_leagues(league_args)
        if league_result != 0:
            self.logger.error("League scraping failed, aborting pipeline")
            return league_result
        
        # Step 2: Scrape odds
        self.logger.info("Step 2: Scraping odds data...")
        odds_args = argparse.Namespace(
            match_ids=None,
            league_id=None,
            league_group=args.league_group, # Pass through league group
            company_filter=args.company_filter,
            company_group=None,
            company_ids=None,
            company_names=None,
            max_workers=args.max_workers,
            skip_existing=True,
            batch_size=100
        )
        
        odds_result = self.handle_scrape_odds(odds_args)
        
        self.logger.info("Full pipeline completed")
        return odds_result
    
    def handle_monitor_performance(self, args) -> int:
        """Handle performance monitoring command."""
        try:
            stats = self.performance_monitor.get_overall_stats()
            
            self.logger.info("\nPerformance Statistics:")
            self.logger.info("=" * 50)
            self.logger.info(f"Total operations: {stats.get('total_operations', 0)}")
            self.logger.info(f"Unique operations: {stats.get('unique_operations', 0)}")
            self.logger.info(f"Total execution time: {stats.get('total_execution_time_ms', 0):.1f}ms")
            self.logger.info(f"Current memory usage: {stats.get('current_memory_mb', 0):.1f}MB")
            
            if 'operation_summaries' in stats:
                self.logger.info("\nOperation Details:")
                for op_name, summary in stats['operation_summaries'].items():
                    self.logger.info(
                        f"  {op_name}: {summary['count']} executions, "
                        f"avg {summary['avg_time_ms']:.1f}ms"
                    )
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error getting performance stats: {e}")
            return 1
    
    def handle_show_stats(self, args) -> int:
        """Handle show stats command."""
        try:
            stats = self.db_manager.get_scraping_stats()
            
            self.logger.info("\nScraping Statistics:")
            self.logger.info("=" * 50)
            self.logger.info(f"Total operations: {stats.get('total_operations', 0)}")
            self.logger.info(f"Success rate: {stats.get('success_rate_pct', 0):.1f}%")
            
            if 'target_type_breakdown' in stats:
                for target_type, breakdown in stats['target_type_breakdown'].items():
                    self.logger.info(
                        f"{target_type}: {breakdown['success']}/{breakdown['total']} successful"
                    )
            
            return 0
            
        except Exception as e:
            self.logger.error(f"Error getting scraping stats: {e}")
            return 1
    
    def _get_companies_by_ids(self, company_ids: List[int]) -> Dict[str, Any]:
        """Get company info by IDs."""
        from config.companies_config import COMPANIES_CONFIG
        target_companies = {}
        
        for company_id in company_ids:
            # Find company by ID
            for company_info in COMPANIES_CONFIG.values():
                if company_info.company_id == company_id:
                    target_companies[str(company_id)] = company_info
                    break
            else:
                self.logger.warning(f"Company ID {company_id} not found in config")
        
        return target_companies
    
    def _get_companies_by_names(self, company_names: List[str]) -> Dict[str, Any]:
        """Get company info by names (supports both English and Chinese names)."""
        from config.companies_config import COMPANIES_CONFIG
        target_companies = {}
        
        for name in company_names:
            # Find company by name (check both English and Chinese names)
            for key, company_info in COMPANIES_CONFIG.items():
                if (name.lower() == company_info.name_en.lower() or 
                    name == company_info.name_cn or 
                    name.lower() == key.lower()):
                    target_companies[str(company_info.company_id)] = company_info
                    break
            else:
                self.logger.warning(f"Company name '{name}' not found in config")
        
        return target_companies

    def handle_maintenance(self, args) -> int:
        """Handle maintenance operations."""
        if args.clean_logs:
            self.logger.info("Cleaning old log entries...")
            try:
                deleted = self.db_manager.cleanup_old_logs(days_to_keep=30)
                self.logger.info(f"Cleaned up {deleted} old log entries")
            except Exception as e:
                self.logger.error(f"Error cleaning logs: {e}")
                return 1
        
        if args.optimize_db:
            self.logger.info("Database optimization not implemented yet")
        
        return 0

    def handle_analyze_odds(self, args) -> int:
        """Handle odds analysis command via unified CLI (single or batch)."""
        return _handle_analyze_odds(self, args)

    def handle_analyze_fundamental(self, args) -> int:
        """Handle fundamental analysis command."""
        return _handle_analyze_fundamental(self, args)

    def handle_calculate_strength(self, args) -> int:
        """Handle strength calculation command."""
        return _handle_calculate_strength(self, args)
