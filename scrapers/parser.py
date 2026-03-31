#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Modern data parser for Titan007 and other sources.
Comprehensive parsing with validation and error handling.
"""

import re
import json
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
import logging
from abc import ABC, abstractmethod

from core.logger import get_logger
from core.exceptions import ParseError, ValidationError
from .exceptions import ParseError as ScraperParseError, DataValidationError
from core.decorators import log_execution_time
from .utils import SafeJSParser, safe_convert


class DataParser(ABC):
    """Abstract base class for data parsers."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"parser.{name}")
    
    @abstractmethod
    def parse(self, content: str) -> Dict[str, Any]:
        """Parse content and return structured data."""
        pass
    
    def validate_parsed_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate parsed data and return list of errors."""
        return []


class Titan007Parser(DataParser):
    """
    Parser for Titan007 football data.
    Handles league data, matches, teams, standings, and odds parsing.
    """
    
    def __init__(self):
        super().__init__("titan007")
        self.teams_cache = {}
        self.current_league = {}
    
    @log_execution_time()
    def parse(self, content: str) -> Dict[str, Any]:
        """
        Parse all data from Titan007 JavaScript content.
        
        Args:
            content: JavaScript content from Titan007
            
        Returns:
            Dictionary containing all parsed data
            
        Raises:
            ParseError: If parsing fails
        """
        try:
            # Parse main components
            league_data = self._parse_league_info(content)
            teams_data = self._parse_teams(content)
            
            # Cache teams for reference before parsing standings
            self.teams_cache = {team['id']: team for team in teams_data}
            self.current_league = league_data
            
            matches_data = self._parse_matches(content)
            standings_data = self._parse_standings(content)
            
            return {
                'league': league_data,
                'teams': teams_data,
                'matches': matches_data,
                'standings': standings_data,
                'metadata': {
                    'parsed_at': datetime.utcnow().isoformat(),
                    'parser_version': '2.0',
                    'teams_count': len(teams_data),
                    'matches_count': sum(len(matches) for matches in matches_data.values()),
                    'standings_sections': len(standings_data)
                }
            }
            
        except Exception as e:
            raise ScraperParseError(
                f"Failed to parse Titan007 content: {str(e)}",
                parser_type="titan007",
                data_type="league_data",
                content_sample=content[:1000] if content else None
            )
    
    def _parse_league_info(self, content: str) -> Dict[str, Any]:
        """Parse league information from JavaScript content."""
        pattern = r'var\s+arrLeague\s*=\s*\[(.*?)\];'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            self.logger.warning("No league information found")
            return {}
        
        try:
            fields = self._parse_js_array(match.group(1))
            
            league_data = {
                'id': safe_convert(fields[0], int) if len(fields) > 0 else None,
                'name_cn': fields[1] if len(fields) > 1 else '',
                'name_tw': fields[2] if len(fields) > 2 else '', 
                'name_en': fields[3] if len(fields) > 3 else '',
                'season': fields[4] if len(fields) > 4 else '',
                'color': fields[5] if len(fields) > 5 else '',
                'logo': fields[6] if len(fields) > 6 else '',
                'total_rounds': safe_convert(fields[7], int, 38) if len(fields) > 7 else 38,
                'current_round': safe_convert(fields[8], int, 1) if len(fields) > 8 else 1,
                'description': fields[12] if len(fields) > 12 else ''
            }
            
            self.logger.info(f"Parsed league: {league_data['name_cn']} {league_data['season']}")
            return league_data
            
        except Exception as e:
            self.logger.error(f"Error parsing league info: {e}")
            return {}
    
    def _parse_teams(self, content: str) -> List[Dict[str, Any]]:
        """Parse team information from JavaScript content."""
        pattern = r'var\s+arrTeam\s*=\s*(\[.*?\]);'
        match = re.search(pattern, content, re.DOTALL)
        
        if not match:
            self.logger.warning("No team information found")
            return []
        
        try:
            # Use safe JavaScript parser instead of eval
            teams_array = SafeJSParser.parse_js_array(match.group(1))
            teams_list = []
            
            for team_data in teams_array:
                if len(team_data) >= 4:  # Minimum required fields
                    team = {
                        'id': team_data[0],
                        'name_cn': team_data[1],
                        'name_tw': team_data[2] if len(team_data) > 2 else '',
                        'name_en': team_data[3] if len(team_data) > 3 else '',
                        'short_name': team_data[4] if len(team_data) > 4 else '',
                        'logo': team_data[5] if len(team_data) > 5 else ''
                    }
                    teams_list.append(team)
            
            self.logger.info(f"Parsed {len(teams_list)} teams")
            return teams_list
            
        except Exception as e:
            self.logger.error(f"Error parsing teams: {e}")
            return []
    
    def _parse_matches(self, content: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parse match data for all rounds."""
        all_matches = {}
        
        # Look for rounds from 1 to 50 (covers most league structures)
        for round_num in range(1, 51):
            pattern = rf'jh\["R_{round_num}"\]\s*=\s*(\[.*?\]);'
            match = re.search(pattern, content, re.DOTALL)
            
            if match:
                round_matches = self._parse_round_matches(match.group(1), round_num)
                if round_matches:
                    all_matches[f'round_{round_num}'] = round_matches
        
        self.logger.info(f"Parsed matches for {len(all_matches)} rounds")
        return all_matches
    
    def _parse_round_matches(self, data_str: str, round_num: int) -> List[Dict[str, Any]]:
        """Parse matches for a specific round."""
        try:
            # Use safe JavaScript parser instead of eval
            matches_array = SafeJSParser.parse_js_array(data_str)
            
            matches = []
            for match_data in matches_array:
                if len(match_data) >= 6:  # Minimum required fields
                    match = self._parse_single_match(match_data, round_num)
                    matches.append(match)
            
            return matches
            
        except Exception as e:
            self.logger.debug(f"Error parsing round {round_num}: {e}")
            return []
    
    def _parse_single_match(self, match_data: List, round_num: int) -> Dict[str, Any]:
        """Parse a single match from array data."""
        match = {
            'match_id': match_data[0],
            'league_id': match_data[1] if len(match_data) > 1 else None,
            'round_number': round_num,
            'round_status': match_data[2] if len(match_data) > 2 else None,
            'match_time': match_data[3] if len(match_data) > 3 else '',
            'home_team_id': match_data[4] if len(match_data) > 4 else None,
            'away_team_id': match_data[5] if len(match_data) > 5 else None,
            'full_score': match_data[6] if len(match_data) > 6 else '',
            'half_score': match_data[7] if len(match_data) > 7 else '',
            'home_rank': match_data[8] if len(match_data) > 8 else '',
            'away_rank': match_data[9] if len(match_data) > 9 else '',
            'handicap': safe_convert(match_data[10], float) if len(match_data) > 10 else None,
            'total_goals': safe_convert(match_data[12], float) if len(match_data) > 12 else None
        }
        
        # Add team names from cache
        if match['home_team_id'] in self.teams_cache:
            match['home_team_name'] = self.teams_cache[match['home_team_id']]['name_cn']
        else:
            match['home_team_name'] = f"Team_{match['home_team_id']}"
        
        if match['away_team_id'] in self.teams_cache:
            match['away_team_name'] = self.teams_cache[match['away_team_id']]['name_cn']
        else:
            match['away_team_name'] = f"Team_{match['away_team_id']}"
        
        # Parse scores
        if match['full_score']:
            home_score, away_score = self._parse_score(match['full_score'])
            match['home_score'] = home_score
            match['away_score'] = away_score
        else:
            match['home_score'] = None
            match['away_score'] = None
        
        # Determine match status
        match['match_status'] = self._get_match_status(match['round_status'])
        
        return match
    
    def _parse_standings(self, content: str) -> Dict[str, List[Dict[str, Any]]]:
        """Parse league standings (total, home, away)."""
        standings = {}
        
        # Parse different standing types
        standings_patterns = {
            'overall': r'var\s+totalScore\s*=\s*(\[.*?\]);',
            'home': r'var\s+homeScore\s*=\s*(\[.*?\]);',
            'away': r'var\s+guestScore\s*=\s*(\[.*?\]);'
        }
        
        for standings_type, pattern in standings_patterns.items():
            match = re.search(pattern, content, re.DOTALL)
            if match:
                standings[standings_type] = self._parse_standings_table(match.group(1))
        
        return standings
    
    def _parse_standings_table(self, data_str: str) -> List[Dict[str, Any]]:
        """Parse a standings table from JavaScript array."""
        try:
            # Use safe JavaScript parser instead of eval
            standings_array = SafeJSParser.parse_js_array(data_str)
            standings = []
            
            for row in standings_array:
                if len(row) >= 17:  # Minimum fields for standings
                    team_id = row[2] if len(row) > 2 else 0
                    team_name = self.teams_cache.get(team_id, {}).get('name_cn', f'Team_{team_id}')
                    
                    standing = {
                        'position': safe_convert(row[1], int),
                        'team_id': team_id,
                        'team_name': team_name,
                        'played': safe_convert(row[4], int),
                        'wins': safe_convert(row[5], int),
                        'draws': safe_convert(row[6], int),
                        'losses': safe_convert(row[7], int),
                        'goals_for': safe_convert(row[8], int),
                        'goals_against': safe_convert(row[9], int),
                        'goal_difference': safe_convert(row[10], int),
                        'points': safe_convert(row[16], int),
                        'recent_form': row[19:25] if len(row) > 24 else []
                    }
                    standings.append(standing)
            
            # Sort by position
            standings.sort(key=lambda x: x['position'] or 999)
            return standings
            
        except Exception as e:
            self.logger.error(f"Error parsing standings table: {e}")
            return []
    
    def _parse_js_array(self, content: str) -> List[str]:
        """Parse JavaScript array string into list of strings."""
        fields = []
        current_field = ''
        in_string = False
        quote_char = None
        
        for char in content:
            if char in ['"', "'"] and (not in_string or char == quote_char):
                if in_string:
                    in_string = False
                    quote_char = None
                else:
                    in_string = True
                    quote_char = char
            elif char == ',' and not in_string:
                fields.append(current_field.strip().strip('"\''))
                current_field = ''
                continue
            
            current_field += char
        
        # Add the last field
        if current_field:
            fields.append(current_field.strip().strip('"\''))
        
        return fields
    
    
    def _parse_score(self, score_str: str) -> Tuple[Optional[int], Optional[int]]:
        """Parse score string like '2-1' into tuple of integers."""
        if not score_str or '-' not in score_str:
            return None, None
        
        try:
            parts = score_str.split('-')
            if len(parts) == 2:
                return int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, AttributeError):
            pass
        
        return None, None
    
    def _get_match_status(self, round_status: Optional[int]) -> str:
        """Convert round status to readable match status."""
        status_map = {
            -1: "finished",
            0: "scheduled", 
            1: "live",
            2: "live",
            3: "live"
        }
        return status_map.get(round_status, "scheduled")
    
    def validate_parsed_data(self, data: Dict[str, Any]) -> List[str]:
        """Validate parsed league data."""
        errors = []
        
        # Validate league data
        if 'league' in data:
            league = data['league']
            if not league.get('id'):
                errors.append("League ID is missing")
            if not league.get('name_cn'):
                errors.append("League Chinese name is missing")
        
        # Validate teams data
        if 'teams' in data:
            if not isinstance(data['teams'], list):
                errors.append("Teams data should be a list")
            elif len(data['teams']) == 0:
                errors.append("No teams found")
            else:
                for i, team in enumerate(data['teams']):
                    if not team.get('id'):
                        errors.append(f"Team {i} is missing ID")
                    if not team.get('name_cn'):
                        errors.append(f"Team {i} is missing Chinese name")
        
        # Validate matches data
        if 'matches' in data:
            if not isinstance(data['matches'], dict):
                errors.append("Matches data should be a dictionary")
            else:
                total_matches = sum(len(matches) for matches in data['matches'].values())
                if total_matches == 0:
                    errors.append("No matches found")
        
        return errors


class OddsParser(DataParser):
    """Parser for odds data from various sources."""
    
    def __init__(self):
        super().__init__("odds")
    
    
    def parse(self, content: str) -> Dict[str, Any]:
        """Parse odds data from JavaScript content."""
        return self._parse_european_odds(content)
    
    def _parse_european_odds(self, js_content: str) -> Dict[str, Any]:
        """Parse European odds from JavaScript content."""
        odds_data = {'odds': []}
        
        # Parse current odds - game array
        game_pattern = r'var game=Array\((.*?)\);'
        game_match = re.search(game_pattern, js_content, re.DOTALL)
        
        if game_match:
            records = re.findall(r'"(.*?)"', game_match.group(1))
            
            for record_str in records:
                parts = record_str.split('|')
                
                if len(parts) >= 21:  # Minimum required fields
                    try:
                        odds_record = {
                            'company_id': safe_convert(parts[0], int),
                            'company_name': parts[2] if len(parts) > 2 else '',
                            'company_name_cn': parts[21] if len(parts) > 21 else '',
                            
                            # Initial odds
                            'initial_home': safe_convert(parts[3], float),
                            'initial_draw': safe_convert(parts[4], float),
                            'initial_away': safe_convert(parts[5], float),
                            'initial_home_prob': safe_convert(parts[6], float),
                            'initial_draw_prob': safe_convert(parts[7], float),
                            'initial_away_prob': safe_convert(parts[8], float),
                            'initial_return_rate': safe_convert(parts[9], float),
                            
                            # Current odds
                            'current_home': safe_convert(parts[10], float),
                            'current_draw': safe_convert(parts[11], float),
                            'current_away': safe_convert(parts[12], float),
                            'current_home_prob': safe_convert(parts[13], float),
                            'current_draw_prob': safe_convert(parts[14], float),
                            'current_away_prob': safe_convert(parts[15], float),
                            'current_return_rate': safe_convert(parts[16], float),
                            
                            # Kelly indices
                            'kelly_home': safe_convert(parts[17], float),
                            'kelly_draw': safe_convert(parts[18], float),
                            'kelly_away': safe_convert(parts[19], float),
                            
                            'update_time': parts[20] if len(parts) > 20 else None
                        }

                        # Manually calculate return rates if they are missing or invalid
                        if not odds_record.get('initial_return_rate'):
                            odds_record['initial_return_rate'] = self._calculate_return_rate(
                                odds_record['initial_home'],
                                odds_record['initial_draw'],
                                odds_record['initial_away']
                            )
                        
                        if not odds_record.get('current_return_rate'):
                            odds_record['current_return_rate'] = self._calculate_return_rate(
                                odds_record['current_home'],
                                odds_record['current_draw'],
                                odds_record['current_away']
                            )
                        
                        odds_data['odds'].append(odds_record)
                        
                    except (ValueError, IndexError) as e:
                        self.logger.debug(f"Error parsing odds record: {e}")

        # 计算即时平均值 (company_id=0)，基于所有公司的即时赔率均值
        avg_record = self._calculate_odds_averages(odds_data['odds'])
        if avg_record:
            odds_data['odds'].append(avg_record)

        return odds_data

    def _calculate_odds_averages(self, odds_list: list) -> Optional[dict]:
        """
        计算所有公司的即时赔率均值，作为 company_id=0 的特殊条目返回。
        只对 current_home/draw/away 均有效值的记录参与计算。
        """
        valid = [
            o for o in odds_list
            if o.get('current_home') and o.get('current_draw') and o.get('current_away')
            and o['current_home'] > 0 and o['current_draw'] > 0 and o['current_away'] > 0
            and o.get('company_id', 0) != 0  # 排除已有的平均条目（防重复）
        ]
        if len(valid) < 2:
            return None

        n = len(valid)

        def _avg(key):
            vals = [o[key] for o in valid if o.get(key) is not None]
            return round(sum(vals) / len(vals), 3) if vals else None

        avg_ch = _avg('current_home')
        avg_cd = _avg('current_draw')
        avg_ca = _avg('current_away')

        # 返还率从均值赔率反推（而非直接平均各公司返还率）
        avg_crr = self._calculate_return_rate(avg_ch, avg_cd, avg_ca)

        # 概率从均值赔率计算
        if avg_ch and avg_cd and avg_ca:
            inv_sum = 1/avg_ch + 1/avg_cd + 1/avg_ca
            avg_ch_prob = round(1/avg_ch / inv_sum * 100, 2)
            avg_cd_prob = round(1/avg_cd / inv_sum * 100, 2)
            avg_ca_prob = round(1/avg_ca / inv_sum * 100, 2)
        else:
            avg_ch_prob = avg_cd_prob = avg_ca_prob = None

        # 初盘均值
        i_valid = [o for o in valid if o.get('initial_home') and o['initial_home'] > 0]
        avg_ih = round(sum(o['initial_home'] for o in i_valid) / len(i_valid), 3) if i_valid else None
        avg_id = round(sum(o['initial_draw'] for o in i_valid) / len(i_valid), 3) if i_valid else None
        avg_ia = round(sum(o['initial_away'] for o in i_valid) / len(i_valid), 3) if i_valid else None
        avg_irr = self._calculate_return_rate(avg_ih, avg_id, avg_ia)
        if avg_ih and avg_id and avg_ia:
            i_inv = 1/avg_ih + 1/avg_id + 1/avg_ia
            avg_ih_prob = round(1/avg_ih / i_inv * 100, 2)
            avg_id_prob = round(1/avg_id / i_inv * 100, 2)
            avg_ia_prob = round(1/avg_ia / i_inv * 100, 2)
        else:
            avg_ih_prob = avg_id_prob = avg_ia_prob = None

        # Kelly 均值
        avg_kh = _avg('kelly_home')
        avg_kd = _avg('kelly_draw')
        avg_ka = _avg('kelly_away')

        return {
            'company_id': 0,
            'company_name': 'Average',
            'company_name_cn': '即时平均',
            'initial_home': avg_ih,
            'initial_draw': avg_id,
            'initial_away': avg_ia,
            'initial_home_prob': avg_ih_prob,
            'initial_draw_prob': avg_id_prob,
            'initial_away_prob': avg_ia_prob,
            'initial_return_rate': avg_irr,
            'current_home': avg_ch,
            'current_draw': avg_cd,
            'current_away': avg_ca,
            'current_home_prob': avg_ch_prob,
            'current_draw_prob': avg_cd_prob,
            'current_away_prob': avg_ca_prob,
            'current_return_rate': avg_crr,
            'kelly_home': avg_kh,
            'kelly_draw': avg_kd,
            'kelly_away': avg_ka,
            'update_time': None,
            '_avg_n': n,  # 参与计算的公司数，调试用
        }

    def _calculate_return_rate(self, home: Optional[float], draw: Optional[float], away: Optional[float]) -> Optional[float]:
        """Calculate the return rate from odds."""
        if home and draw and away and home > 0 and draw > 0 and away > 0:
            try:
                return_rate = 1 / ((1 / home) + (1 / draw) + (1 / away)) * 100
                return round(return_rate, 2)
            except (TypeError, ZeroDivisionError):
                return None
        return None