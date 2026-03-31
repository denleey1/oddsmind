"""
Configuration package for OddsMind scraper system.
"""

from .settings import Settings
from .database_config import DatabaseConfig
from .leagues_config import LEAGUES_CONFIG
from .companies_config import COMPANIES_CONFIG

__all__ = [
    'Settings',
    'DatabaseConfig', 
    'LEAGUES_CONFIG',
    'COMPANIES_CONFIG'
]