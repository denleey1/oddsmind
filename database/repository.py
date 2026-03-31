#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Repository classes for database operations.
Modern repository pattern with type safety and batch operations.
"""

from typing import List, Dict, Any, Optional, Union, Tuple
from datetime import datetime
import logging
from abc import ABC, abstractmethod

from .connection import get_connection
from .models import (
    LeagueModel, TeamModel, MatchModel, CompanyModel, 
    OddsModel, StandingModel, ScrapingLogModel, BaseModel
)
from core.logger import get_logger
from core.exceptions import DatabaseError, ValidationError
from .repository_upsert_ops import (
    batch_upsert_odds as _batch_upsert_odds_impl,
    upsert_record as _upsert_record,
)


class BaseRepository(ABC):
    """Abstract base repository class."""
    
    def __init__(self, model_class: type, table_name: str):
        self.model_class = model_class
        self.table_name = table_name
        self.db = get_connection()
        self.logger = get_logger(f"repo.{table_name}")
    
    def create(self, model: BaseModel) -> int:
        """Create a new record."""
        data = model.to_db_dict()
        
        # Remove None values and id if present
        data = {k: v for k, v in data.items() if v is not None}
        if 'id' in data and data['id'] is None:
            del data['id']
        
        if not data:
            raise ValidationError("No data to insert")
        
        columns = list(data.keys())
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join(columns)
        
        query = f"INSERT INTO {self.table_name} ({columns_str}) VALUES ({placeholders})"
        values = list(data.values())
        
        result = self.db.execute_query(query, values)
        return result
    
    def create_many(self, models: List[BaseModel]) -> int:
        """Create multiple records in batch."""
        if not models:
            return 0
        
        # Convert all models to db dict format
        records_data = []
        for model in models:
            data = model.to_db_dict()
            # Remove None values and id if present
            data = {k: v for k, v in data.items() if v is not None}
            if 'id' in data and data['id'] is None:
                del data['id']
            records_data.append(data)
        
        if not records_data:
            return 0
        
        # Use the first record to determine columns
        columns = list(records_data[0].keys())
        placeholders = ', '.join(['%s'] * len(columns))
        columns_str = ', '.join(columns)
        
        query = f"INSERT INTO {self.table_name} ({columns_str}) VALUES ({placeholders})"
        
        # Prepare values for executemany
        values_list = []
        for record in records_data:
            values = [record.get(col) for col in columns]
            values_list.append(values)
        
        return self.db.execute_many(query, values_list)
    
    def upsert(self, model: BaseModel, conflict_columns: List[str]) -> int:
        """Insert or update on conflict."""
        return _upsert_record(self, model, conflict_columns)
    
    def find_by_id(self, record_id: Union[int, str]) -> Optional[BaseModel]:
        """Find record by ID."""
        # Determine the primary key column name
        pk_column = self._get_primary_key_column()
        
        query = f"SELECT * FROM {self.table_name} WHERE {pk_column} = %s"
        result = self.db.execute_query(query, (record_id,), fetch='one')
        
        return self.model_class.from_dict(result) if result else None
    
    def find_all(
        self, 
        limit: Optional[int] = None,
        offset: int = 0,
        order_by: Optional[str] = None
    ) -> List[BaseModel]:
        """Find all records with optional pagination."""
        query = f"SELECT * FROM {self.table_name}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit} OFFSET {offset}"
        
        results = self.db.execute_query(query, fetch='all')
        return [self.model_class.from_dict(row) for row in results] if results else []
    
    def find_by_criteria(
        self,
        criteria: Dict[str, Any],
        limit: Optional[int] = None,
        order_by: Optional[str] = None
    ) -> List[BaseModel]:
        """Find records by criteria."""
        if not criteria:
            return self.find_all(limit=limit, order_by=order_by)
        
        where_clauses = []
        values = []
        
        for column, value in criteria.items():
            if isinstance(value, (list, tuple)):
                placeholders = ', '.join(['%s'] * len(value))
                where_clauses.append(f"{column} IN ({placeholders})")
                values.extend(value)
            elif value is None:
                where_clauses.append(f"{column} IS NULL")
            else:
                where_clauses.append(f"{column} = %s")
                values.append(value)
        
        where_str = ' AND '.join(where_clauses)
        query = f"SELECT * FROM {self.table_name} WHERE {where_str}"
        
        if order_by:
            query += f" ORDER BY {order_by}"
        
        if limit:
            query += f" LIMIT {limit}"
        
        results = self.db.execute_query(query, values, fetch='all')
        return [self.model_class.from_dict(row) for row in results] if results else []
    
    def count(self, criteria: Optional[Dict[str, Any]] = None) -> int:
        """Count records matching criteria."""
        if not criteria:
            query = f"SELECT COUNT(*) as count FROM {self.table_name}"
            result = self.db.execute_query(query, fetch='one')
            return result['count'] if result else 0
        
        where_clauses = []
        values = []
        
        for column, value in criteria.items():
            if isinstance(value, (list, tuple)):
                placeholders = ', '.join(['%s'] * len(value))
                where_clauses.append(f"{column} IN ({placeholders})")
                values.extend(value)
            elif value is None:
                where_clauses.append(f"{column} IS NULL")
            else:
                where_clauses.append(f"{column} = %s")
                values.append(value)
        
        where_str = ' AND '.join(where_clauses)
        query = f"SELECT COUNT(*) as count FROM {self.table_name} WHERE {where_str}"
        
        result = self.db.execute_query(query, values, fetch='one')
        return result['count'] if result else 0
    
    def delete_by_id(self, record_id: Union[int, str]) -> int:
        """Delete record by ID."""
        pk_column = self._get_primary_key_column()
        query = f"DELETE FROM {self.table_name} WHERE {pk_column} = %s"
        return self.db.execute_query(query, (record_id,))
    
    def delete_by_criteria(self, criteria: Dict[str, Any]) -> int:
        """Delete records by criteria."""
        if not criteria:
            raise ValidationError("Cannot delete without criteria")
        
        where_clauses = []
        values = []
        
        for column, value in criteria.items():
            if isinstance(value, (list, tuple)):
                placeholders = ', '.join(['%s'] * len(value))
                where_clauses.append(f"{column} IN ({placeholders})")
                values.extend(value)
            else:
                where_clauses.append(f"{column} = %s")
                values.append(value)
        
        where_str = ' AND '.join(where_clauses)
        query = f"DELETE FROM {self.table_name} WHERE {where_str}"
        
        return self.db.execute_query(query, values)
    
    def _get_primary_key_column(self) -> str:
        """Get primary key column name for the table."""
        # Default logic - can be overridden by subclasses
        if hasattr(self.model_class, '__dataclass_fields__'):
            fields = list(self.model_class.__dataclass_fields__.keys())
            # Common primary key patterns
            for field in ['id', f'{self.table_name}_id', f'{self.table_name.rstrip("s")}_id']:
                if field in fields:
                    return field
        
        return 'id'  # Default


class LeagueRepository(BaseRepository):
    """Repository for league operations."""
    
    def __init__(self):
        super().__init__(LeagueModel, 'leagues')
    
    def _get_primary_key_column(self) -> str:
        return 'league_id'
    
    def find_by_country(self, country: str) -> List[LeagueModel]:
        """Find leagues by country."""
        return self.find_by_criteria({'country': country}, order_by='level, name_cn')
    
    def find_active_leagues(self) -> List[LeagueModel]:
        """Find all active leagues."""
        return self.find_by_criteria({'is_active': True}, order_by='country, level')


class TeamRepository(BaseRepository):
    """Repository for team operations."""
    
    def __init__(self):
        super().__init__(TeamModel, 'teams')
    
    def _get_primary_key_column(self) -> str:
        return 'team_id'
    
    def find_by_name(self, name: str, partial: bool = False) -> List[TeamModel]:
        """Find teams by name."""
        if partial:
            query = "SELECT * FROM teams WHERE name_cn LIKE %s OR name_en LIKE %s"
            pattern = f"%{name}%"
            results = self.db.execute_query(query, (pattern, pattern), fetch='all')
        else:
            criteria = {'name_cn': name}
            results = self.find_by_criteria(criteria)
        
        return results if isinstance(results, list) else [results] if results else []


class MatchRepository(BaseRepository):
    """Repository for match operations."""
    
    def __init__(self):
        super().__init__(MatchModel, 'matches')
    
    def _get_primary_key_column(self) -> str:
        return 'match_id'
    
    def find_by_league(
        self, 
        league_id: int, 
        season: Optional[str] = None
    ) -> List[MatchModel]:
        """Find matches by league."""
        criteria = {'league_id': league_id}
        if season:
            criteria['season'] = season
        
        return self.find_by_criteria(criteria, order_by='match_time')
    
    def find_by_teams(
        self, 
        home_team_id: int, 
        away_team_id: int
    ) -> List[MatchModel]:
        """Find matches between two teams."""
        query = """
            SELECT * FROM matches 
            WHERE (home_team_id = %s AND away_team_id = %s)
               OR (home_team_id = %s AND away_team_id = %s)
            ORDER BY match_time DESC
        """
        
        results = self.db.execute_query(
            query, 
            (home_team_id, away_team_id, away_team_id, home_team_id),
            fetch='all'
        )
        
        return [MatchModel.from_dict(row) for row in results] if results else []
    
    def find_finished_matches(
        self, 
        league_id: Optional[int] = None
    ) -> List[MatchModel]:
        """Find finished matches."""
        criteria = {'match_status': 'finished'}
        if league_id:
            criteria['league_id'] = league_id
        
        return self.find_by_criteria(criteria, order_by='match_time DESC')


class CompanyRepository(BaseRepository):
    """Repository for bookmaker company operations."""
    
    def __init__(self):
        super().__init__(CompanyModel, 'companies')
    
    def _get_primary_key_column(self) -> str:
        return 'company_id'
    
    def find_main_companies(self) -> List[CompanyModel]:
        """Find main/tier 1 companies."""
        return self.find_by_criteria({'is_main': True}, order_by='priority')
    
    def find_asian_companies(self) -> List[CompanyModel]:
        """Find Asian bookmakers."""
        return self.find_by_criteria({'is_asian': True}, order_by='priority')


class OddsRepository(BaseRepository):
    """Repository for odds operations."""
    
    def __init__(self):
        super().__init__(OddsModel, 'european_odds')
    
    def find_by_match(self, match_id: int) -> List[OddsModel]:
        """Find odds for a match."""
        return self.find_by_criteria({'match_id': match_id}, order_by='company_id')
    
    def find_by_company(self, company_id: int) -> List[OddsModel]:
        """Find odds by company."""
        return self.find_by_criteria({'company_id': company_id}, order_by='match_id')
    
    def find_by_match_and_companies(
        self, 
        match_id: int, 
        company_ids: List[int]
    ) -> List[OddsModel]:
        """Find odds for specific match and companies."""
        query = """
            SELECT * FROM european_odds 
            WHERE match_id = %s AND company_id IN ({})
            ORDER BY company_id
        """.format(', '.join(['%s'] * len(company_ids)))
        
        results = self.db.execute_query(
            query, 
            [match_id] + company_ids,
            fetch='all'
        )
        
        return [OddsModel.from_dict(row) for row in results] if results else []
    
    def upsert_odds(self, odds_list: List[OddsModel]) -> int:
        """Batch upsert odds data with optimized performance."""
        if not odds_list:
            return 0
        
        # Group by 50 records for optimal batch processing
        batch_size = 50
        total_affected = 0
        
        for i in range(0, len(odds_list), batch_size):
            batch = odds_list[i:i + batch_size]
            affected = self._batch_upsert_odds(batch)
            total_affected += affected
        
        return total_affected
    
    def _batch_upsert_odds(self, odds_batch: List[OddsModel]) -> int:
        """
        OPTIMIZED batch upsert for odds data - Enhanced version.
        Uses improved MySQL syntax and error handling.
        """
        return _batch_upsert_odds_impl(self, odds_batch)


class StandingRepository(BaseRepository):
    """Repository for league standings operations."""
    
    def __init__(self):
        super().__init__(StandingModel, 'standings')
    
    def find_by_league(
        self, 
        league_id: int, 
        standing_type: str = 'overall',
        season: Optional[str] = None
    ) -> List[StandingModel]:
        """Find standings for a league."""
        criteria = {
            'league_id': league_id,
            'standing_type': standing_type
        }
        if season:
            criteria['season'] = season
        
        return self.find_by_criteria(criteria, order_by='position')


class ScrapingLogRepository(BaseRepository):
    """Repository for scraping log operations."""
    
    def __init__(self):
        super().__init__(ScrapingLogModel, 'scraping_logs')
    
    def log_operation(
        self,
        scraper_name: str,
        target_type: str,
        target_id: str,
        status: str,
        **kwargs
    ) -> int:
        """Log a scraping operation."""
        log_model = ScrapingLogModel(
            scraper_name=scraper_name,
            target_type=target_type,
            target_id=target_id,
            status=status,
            created_at=datetime.utcnow(),
            **kwargs
        )
        
        return self.create(log_model)
    
    def find_recent_logs(
        self, 
        scraper_name: Optional[str] = None,
        limit: int = 100
    ) -> List[ScrapingLogModel]:
        """Find recent scraping logs."""
        criteria = {}
        if scraper_name:
            criteria['scraper_name'] = scraper_name
        
        return self.find_by_criteria(
            criteria, 
            limit=limit, 
            order_by='created_at DESC'
        )
