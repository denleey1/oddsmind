"""
Scrapers package for OddsMind system.
Contains specific scraper implementations for different data sources.
"""

from .league_scraper import LeagueScraper
from .odds_scraper import OddsScraperModern  
from .parser import Titan007Parser, DataParser, OddsParser
from .utils import (
    ContentProcessor, StatisticsTracker, AdaptiveRateLimit, 
    SafeJSParser, CheckpointManager, create_url_with_cache_buster, safe_convert
)
from .exceptions import (
    ScraperException, ContentError, EncodingError, ParseError, RateLimitError,
    CompanyFilterError, DataValidationError, CheckpointError, NetworkError,
    ConfigurationError, create_contextual_error, log_error_context
)

__all__ = [
    # Scrapers
    'LeagueScraper',
    'OddsScraperModern',
    
    # Parsers
    'Titan007Parser',
    'DataParser',
    'OddsParser',
    
    # Utilities
    'ContentProcessor',
    'StatisticsTracker', 
    'AdaptiveRateLimit',
    'SafeJSParser',
    'CheckpointManager',
    'create_url_with_cache_buster',
    'safe_convert',
    
    # Exceptions
    'ScraperException',
    'ContentError',
    'EncodingError', 
    'ParseError',
    'RateLimitError',
    'CompanyFilterError',
    'DataValidationError',
    'CheckpointError',
    'NetworkError',
    'ConfigurationError',
    'create_contextual_error',
    'log_error_context'
]