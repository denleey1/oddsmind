#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Command-line argument parsing utilities for OddsMind."""

from __future__ import annotations

import argparse
from typing import Optional, Sequence

from config.leagues_config import list_league_group_names
from config.companies_config import COMPANY_GROUPS


def create_parser() -> argparse.ArgumentParser:
    """Create command line parser with subcommands."""
    parser = argparse.ArgumentParser(
        description='欧核数据分析系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Global options
    parser.add_argument('--config', help='Configuration file path')
    parser.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level',
    )
    parser.add_argument(
        '--performance-monitoring',
        action='store_true',
        help='Enable detailed performance monitoring',
    )

    league_group_choices = list_league_group_names()

    # Subcommands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Database commands
    db_parser = subparsers.add_parser('db-init', help='Initialize database')
    db_parser.add_argument('--force', action='store_true', help='Force recreate tables')

    subparsers.add_parser('db-status', help='Show database status')
    subparsers.add_parser('db-test', help='Test database connection')

    # League scraping
    leagues_parser = subparsers.add_parser('scrape-leagues', help='Scrape league data')
    leagues_parser.add_argument('--leagues', help='Comma-separated league codes (e.g., ENG1,ESP1)')
    leagues_parser.add_argument(
        '--league-group',
        choices=league_group_choices,
        help='Predefined league group',
    )
    leagues_parser.add_argument(
        '--force-refresh',
        action='store_true',
        help='Force refresh even if recently updated',
    )
    leagues_parser.add_argument(
        '--max-workers',
        type=int,
        default=5,
        help='Maximum concurrent workers',
    )

    # Odds scraping
    odds_parser = subparsers.add_parser('scrape-odds', help='Scrape odds data')
    odds_parser.add_argument('--match-ids', help='Comma-separated match IDs')
    odds_parser.add_argument('--league-id', type=int, help='Scrape odds for all matches in league')
    odds_parser.add_argument('--league-group', choices=league_group_choices, help='Predefined league group')
    odds_parser.add_argument(
        '--company-filter',
        choices=['tier1', 'asian', 'european', 'all'],
        default='all',
        help='Company filter',
    )
    odds_parser.add_argument(
        '--company-group',
        choices=list(COMPANY_GROUPS.keys()),
        help='Predefined company group',
    )
    odds_parser.add_argument('--company-ids', help='Comma-separated company IDs (e.g., 4,81,115,188)')
    odds_parser.add_argument(
        '--company-names',
        help='Comma-separated company names (e.g., "bet365,威廉希尔,立博")',
    )
    odds_parser.add_argument(
        '--max-workers',
        type=int,
        default=10,
        help='Maximum concurrent workers',
    )
    odds_parser.add_argument(
        '--skip-existing',
        action='store_true',
        default=True,
        help='Skip matches with existing odds',
    )
    odds_parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of matches to process in each batch',
    )

    # Full pipeline
    pipeline_parser = subparsers.add_parser('full-pipeline', help='Run complete scraping pipeline')
    pipeline_parser.add_argument(
        '--league-group',
        choices=league_group_choices,
        default='big5',
        help='League group to process',
    )
    pipeline_parser.add_argument(
        '--company-filter',
        choices=['tier1', 'asian', 'european', 'all'],
        default='tier1',
        help='Company filter for odds',
    )
    pipeline_parser.add_argument(
        '--max-workers',
        type=int,
        default=8,
        help='Maximum concurrent workers',
    )

    # Monitoring and status
    subparsers.add_parser('monitor-performance', help='Show performance monitoring data')
    subparsers.add_parser('show-stats', help='Show scraping statistics')

    # Fundamental analysis
    fundamental_parser = subparsers.add_parser('analyze-fundamental', help='Analyze match fundamentals')
    fundamental_parser.add_argument('--match-id', required=True, help='Match ID to analyze')
    fundamental_parser.add_argument(
        '--save-to-db',
        action='store_true',
        help='Save results to database',
    )

    # Odds analysis
    analyze_odds_parser = subparsers.add_parser('analyze-odds', help='Analyze odds for match(es)')
    analyze_odds_parser.add_argument('--match-id', type=int, help='Single match ID to analyze')
    analyze_odds_parser.add_argument('--match-ids', help='Comma-separated match IDs to analyze')
    analyze_odds_parser.add_argument('--league-id', type=int, help='Analyze all matches in a league')
    analyze_odds_parser.add_argument(
        '--limit',
        type=int,
        default=50,
        help='Limit number of matches when using --league-id',
    )
    analyze_odds_parser.add_argument(
        '--data-source',
        choices=['odds_changes', 'european_odds'],
        default='odds_changes',
        help='Odds data source (default: odds_changes)',
    )

    # Strength calculation
    strength_parser = subparsers.add_parser('calculate-strength', help='Calculate team strength ratings')
    strength_parser.add_argument('--league-ids', help='Comma-separated league IDs (e.g., 25,15,36)')
    strength_parser.add_argument('--all', action='store_true', help='Calculate strength for all leagues')
    strength_parser.add_argument(
        '--league-group',
        choices=league_group_choices,
        help='Predefined league group',
    )
    strength_parser.add_argument('--season', help='Season (e.g., 2025)')
    strength_parser.add_argument(
        '--max-workers',
        type=int,
        default=4,
        help='Maximum concurrent workers',
    )

    # Maintenance
    maintenance_parser = subparsers.add_parser('maintenance', help='Maintenance operations')
    maintenance_parser.add_argument('--clean-logs', action='store_true', help='Clean old log entries')
    maintenance_parser.add_argument('--optimize-db', action='store_true', help='Optimize database')

    return parser


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command line arguments."""
    parser = create_parser()
    return parser.parse_args(argv)
