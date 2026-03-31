#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
欧核数据分析系统
Entry point with modern architecture and comprehensive functionality.

Usage Examples:
    # Scrape leagues with all companies
    python main.py scrape-leagues --leagues ENG1,ESP1,ITA1
    
    # Scrape odds with company filtering
    python main.py scrape-odds --company-filter tier1 --max-workers 10
    
    # Full pipeline: leagues + odds
    python main.py full-pipeline --league-group big5
    
    # Database operations
    python main.py db-init  # Initialize database
    python main.py db-status  # Show database status
    
    # Performance monitoring
    python main.py monitor-performance
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables from oddsmind.env file
from dotenv import load_dotenv
load_dotenv('oddsmind.env')

from core.logger import setup_logging
from config.settings import settings

from application.cli.parser import create_parser, parse_args
from application.cli.cli_app import OddsMindCLI

# Initialize logging with the consolidated configuration
setup_logging(settings.app_config.logging, level=settings.logging.level)


def main() -> int:
    """Main entry point."""
    args = parse_args()

    if not args.command:
        # Show help if no command provided
        parser = create_parser()
        parser.print_help()
        return 1

    # Update log level if specified
    if args.log_level != 'INFO':
        setup_logging(settings.app_config.logging, level=args.log_level)

    # Run CLI application
    cli = OddsMindCLI()
    return cli.run(args)


if __name__ == '__main__':
    main()
