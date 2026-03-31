"""
Database package for OddsMind system.
Modern MySQL-first database operations with connection pooling and ORM-like interface.
"""

from .connection import DatabaseConnection, get_connection
from .models import (
    LeagueModel,
    TeamModel, 
    MatchModel,
    CompanyModel,
    OddsModel,
    StandingModel
)
from .repository import (
    LeagueRepository,
    TeamRepository,
    MatchRepository,
    OddsRepository,
    StandingRepository
)
from .manager import DatabaseManager

# Legacy compatibility
from .db_manager import db_manager, get_db_connection, get_db_manager

__all__ = [
    'DatabaseConnection',
    'get_connection',
    'LeagueModel',
    'TeamModel',
    'MatchModel', 
    'CompanyModel',
    'OddsModel',
    'StandingModel',
    'LeagueRepository',
    'TeamRepository',
    'MatchRepository',
    'OddsRepository',
    'StandingRepository',
    'DatabaseManager',
    # Legacy
    'db_manager',
    'get_db_connection', 
    'get_db_manager'
]