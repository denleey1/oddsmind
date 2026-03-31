#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Data validation utilities for OddsMind system.
Comprehensive validation for scraped data integrity.
"""

import re
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime
from dataclasses import dataclass

from core.logger import get_logger
from core.exceptions import ValidationError


@dataclass
class ValidationResult:
    """Validation result container."""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    
    def add_error(self, error: str) -> None:
        """Add validation error."""
        self.errors.append(error)
        self.is_valid = False
    
    def add_warning(self, warning: str) -> None:
        """Add validation warning."""
        self.warnings.append(warning)
    
    @property
    def has_errors(self) -> bool:
        """Check if has validation errors."""
        return len(self.errors) > 0
    
    @property
    def has_warnings(self) -> bool:
        """Check if has validation warnings."""
        return len(self.warnings) > 0


class DataValidator:
    """Comprehensive data validator for scraped content."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    def validate_league_data(self, league_data: Dict[str, Any]) -> ValidationResult:
        """
        Validate league data structure and content.
        
        Args:
            league_data: League data dictionary
            
        Returns:
            ValidationResult with validation outcome
        """
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        # Check required structure
        required_keys = ['league', 'teams', 'matches']
        for key in required_keys:
            if key not in league_data:
                result.add_error(f"Missing required key: {key}")
        
        # Validate league info
        if 'league' in league_data:
            self._validate_league_info(league_data['league'], result)
        
        # Validate teams
        if 'teams' in league_data:
            self._validate_teams_data(league_data['teams'], result)
        
        # Validate matches
        if 'matches' in league_data:
            self._validate_matches_data(league_data['matches'], result)
        
        # Validate standings if present
        if 'standings' in league_data:
            self._validate_standings_data(league_data['standings'], result)
        
        return result
    
    def _validate_league_info(self, league_info: Dict[str, Any], result: ValidationResult) -> None:
        """Validate league information."""
        required_fields = ['id', 'name_cn']
        
        for field in required_fields:
            if not league_info.get(field):
                result.add_error(f"League missing required field: {field}")
        
        # Validate league ID
        if 'id' in league_info:
            try:
                league_id = int(league_info['id'])
                if league_id <= 0:
                    result.add_error("League ID must be positive")
            except (ValueError, TypeError):
                result.add_error("League ID must be an integer")
        
        # Validate rounds
        if 'total_rounds' in league_info:
            try:
                total_rounds = int(league_info['total_rounds'])
                if total_rounds <= 0 or total_rounds > 100:
                    result.add_warning(f"Unusual total_rounds value: {total_rounds}")
            except (ValueError, TypeError):
                result.add_error("total_rounds must be an integer")
    
    def _validate_teams_data(self, teams_data: List[Dict[str, Any]], result: ValidationResult) -> None:
        """Validate teams data."""
        if not isinstance(teams_data, list):
            result.add_error("Teams data must be a list")
            return
        
        if len(teams_data) == 0:
            result.add_error("No teams found")
            return
        
        if len(teams_data) < 2:
            result.add_warning(f"Very few teams found: {len(teams_data)}")
        elif len(teams_data) > 50:
            result.add_warning(f"Unusually many teams: {len(teams_data)}")
        
        team_ids = set()
        for i, team in enumerate(teams_data):
            if not isinstance(team, dict):
                result.add_error(f"Team {i} is not a dictionary")
                continue
            
            # Check required fields
            if not team.get('id'):
                result.add_error(f"Team {i} missing ID")
            
            if not team.get('name_cn'):
                result.add_error(f"Team {i} missing Chinese name")
            
            # Check for duplicate IDs
            team_id = team.get('id')
            if team_id in team_ids:
                result.add_error(f"Duplicate team ID: {team_id}")
            else:
                team_ids.add(team_id)
    
    def _validate_matches_data(self, matches_data: Dict[str, List], result: ValidationResult) -> None:
        """Validate matches data."""
        if not isinstance(matches_data, dict):
            result.add_error("Matches data must be a dictionary")
            return
        
        total_matches = 0
        round_numbers = set()
        
        for round_key, round_matches in matches_data.items():
            if not isinstance(round_matches, list):
                result.add_error(f"Round {round_key} matches must be a list")
                continue
            
            total_matches += len(round_matches)
            
            # Extract round number
            try:
                round_num = int(round_key.split('_')[1])
                round_numbers.add(round_num)
            except (IndexError, ValueError):
                result.add_warning(f"Cannot parse round number from: {round_key}")
            
            # Validate individual matches
            for j, match in enumerate(round_matches):
                if not isinstance(match, dict):
                    result.add_error(f"Match {j} in {round_key} is not a dictionary")
                    continue
                
                self._validate_single_match(match, f"{round_key}[{j}]", result)
        
        # Overall matches validation
        if total_matches == 0:
            result.add_error("No matches found")
        elif total_matches < 10:
            result.add_warning(f"Very few matches found: {total_matches}")
        
        # Check round continuity
        if round_numbers:
            expected_rounds = set(range(1, max(round_numbers) + 1))
            missing_rounds = expected_rounds - round_numbers
            if missing_rounds:
                result.add_warning(f"Missing rounds: {sorted(missing_rounds)}")
    
    def _validate_single_match(self, match: Dict[str, Any], context: str, result: ValidationResult) -> None:
        """Validate a single match."""
        required_fields = ['match_id', 'home_team_id', 'away_team_id']
        
        for field in required_fields:
            if not match.get(field):
                result.add_error(f"{context} missing {field}")
        
        # Validate match ID
        try:
            match_id = int(match['match_id'])
            if match_id <= 0:
                result.add_error(f"{context} match_id must be positive")
        except (ValueError, TypeError, KeyError):
            result.add_error(f"{context} match_id must be an integer")
        
        # Validate team IDs
        try:
            home_id = int(match['home_team_id'])
            away_id = int(match['away_team_id'])
            
            if home_id == away_id:
                result.add_error(f"{context} home and away team cannot be the same")
            
            if home_id <= 0 or away_id <= 0:
                result.add_error(f"{context} team IDs must be positive")
                
        except (ValueError, TypeError, KeyError):
            result.add_error(f"{context} team IDs must be integers")
        
        # Validate match time if present
        if 'match_time' in match and match['match_time']:
            if not self._validate_datetime_string(match['match_time']):
                result.add_warning(f"{context} invalid match_time format")
        
        # Validate scores if present
        if 'full_score' in match and match['full_score']:
            if not self._validate_score_format(match['full_score']):
                result.add_warning(f"{context} invalid full_score format")
    
    def _validate_standings_data(self, standings_data: Dict[str, List], result: ValidationResult) -> None:
        """Validate standings data."""
        if not isinstance(standings_data, dict):
            result.add_error("Standings data must be a dictionary")
            return
        
        valid_types = {'overall', 'home', 'away', 'total'}  # total is alias for overall
        
        for standing_type, standings in standings_data.items():
            if standing_type not in valid_types:
                result.add_warning(f"Unknown standings type: {standing_type}")
            
            if not isinstance(standings, list):
                result.add_error(f"Standings {standing_type} must be a list")
                continue
            
            if len(standings) == 0:
                result.add_warning(f"No standings found for type: {standing_type}")
                continue
            
            # Validate individual standings
            positions = set()
            for i, standing in enumerate(standings):
                if not isinstance(standing, dict):
                    result.add_error(f"Standing {i} in {standing_type} is not a dictionary")
                    continue
                
                # Check position
                position = standing.get('position') or standing.get('rank')
                if position:
                    if position in positions:
                        result.add_error(f"Duplicate position {position} in {standing_type}")
                    else:
                        positions.add(position)
                
                # Validate numeric fields
                numeric_fields = ['played', 'wins', 'draws', 'losses', 'goals_for', 'goals_against', 'points']
                for field in numeric_fields:
                    value = standing.get(field)
                    if value is not None:
                        try:
                            num_value = int(value)
                            if num_value < 0:
                                result.add_warning(f"Negative value for {field} in {standing_type}")
                        except (ValueError, TypeError):
                            result.add_error(f"Invalid {field} value in {standing_type}")
    
    def _validate_datetime_string(self, dt_string: str) -> bool:
        """Validate datetime string format."""
        if not isinstance(dt_string, str):
            return False
        
        # Common datetime patterns
        patterns = [
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$',  # YYYY-MM-DD HH:MM
            r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$',  # YYYY-MM-DD HH:MM:SS
            r'^\d{2}-\d{2} \d{2}:\d{2}$',  # MM-DD HH:MM
        ]
        
        return any(re.match(pattern, dt_string) for pattern in patterns)
    
    def _validate_score_format(self, score_string: str) -> bool:
        """Validate score format."""
        if not isinstance(score_string, str):
            return False
        
        # Common score patterns
        patterns = [
            r'^\d+-\d+$',  # 1-0, 2-1, etc.
            r'^\d+:\d+$',  # 1:0, 2:1, etc. 
        ]
        
        return any(re.match(pattern, score_string) for pattern in patterns)


class OddsValidator:
    """Validator specifically for odds data."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    def validate_odds_data(self, odds_data: Dict[str, Any]) -> ValidationResult:
        """Validate odds data structure and values."""
        result = ValidationResult(is_valid=True, errors=[], warnings=[])
        
        if 'odds' not in odds_data:
            result.add_error("Missing 'odds' key in odds data")
            return result
        
        odds_list = odds_data['odds']
        
        if not isinstance(odds_list, list):
            result.add_error("Odds data must be a list")
            return result
        
        if len(odds_list) == 0:
            # This might be valid for matches with no odds available
            result.add_warning("No odds records found")
            return result
        
        company_ids = set()
        
        for i, odds_record in enumerate(odds_list):
            if not isinstance(odds_record, dict):
                result.add_error(f"Odds record {i} is not a dictionary")
                continue
            
            self._validate_single_odds_record(odds_record, i, result)
            
            # Track company IDs for duplicates
            company_id = odds_record.get('company_id')
            if company_id:
                if company_id in company_ids:
                    result.add_error(f"Duplicate company_id: {company_id}")
                else:
                    company_ids.add(company_id)
        
        return result
    
    def _validate_single_odds_record(self, odds: Dict[str, Any], index: int, result: ValidationResult) -> None:
        """Validate a single odds record."""
        context = f"Odds record {index}"
        
        # Required fields
        if not odds.get('company_id'):
            result.add_error(f"{context} missing company_id")
        
        # Validate company ID
        try:
            company_id = int(odds['company_id'])
            if company_id <= 0:
                result.add_error(f"{context} company_id must be positive")
        except (ValueError, TypeError, KeyError):
            result.add_error(f"{context} company_id must be an integer")
        
        # Validate odds values
        odds_fields = [
            'initial_home', 'initial_draw', 'initial_away',
            'current_home', 'current_draw', 'current_away'
        ]
        
        for field in odds_fields:
            value = odds.get(field)
            if value is not None:
                try:
                    odds_value = float(value)
                    if odds_value <= 1.0:
                        result.add_warning(f"{context} {field} value seems low: {odds_value}")
                    elif odds_value > 100.0:
                        result.add_warning(f"{context} {field} value seems high: {odds_value}")
                except (ValueError, TypeError):
                    result.add_error(f"{context} {field} must be a number")
        
        # Validate probability fields
        prob_fields = [
            'initial_home_prob', 'initial_draw_prob', 'initial_away_prob',
            'current_home_prob', 'current_draw_prob', 'current_away_prob'
        ]
        
        for field in prob_fields:
            value = odds.get(field)
            if value is not None:
                try:
                    prob_value = float(value)
                    if prob_value < 0.0 or prob_value > 1.0:
                        result.add_error(f"{context} {field} must be between 0 and 1")
                except (ValueError, TypeError):
                    result.add_error(f"{context} {field} must be a number")


# Convenience functions
def validate_league_data(league_data: Dict[str, Any]) -> ValidationResult:
    """Validate league data."""
    validator = DataValidator()
    return validator.validate_league_data(league_data)


def validate_match_data(match_data: Dict[str, Any]) -> ValidationResult:
    """Validate single match data."""
    result = ValidationResult(is_valid=True, errors=[], warnings=[])
    validator = DataValidator()
    validator._validate_single_match(match_data, "match", result)
    return result


def validate_odds_data(odds_data: Dict[str, Any]) -> ValidationResult:
    """Validate odds data."""
    validator = OddsValidator()
    return validator.validate_odds_data(odds_data)