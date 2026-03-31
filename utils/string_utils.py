#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
String utilities for OddsMind system.
Text processing, cleaning, and normalization functions.
"""

import re
from typing import Optional, List, Dict, Any
import unicodedata
import html

from core.logger import get_logger


class StringUtils:
    """Utility class for string operations."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        
        # Common team name variations and normalizations
        self.team_name_replacements = {
            # English replacements
            'FC': '',
            'F.C.': '',
            'AFC': '',
            'A.F.C.': '',
            'BFC': '',
            'B.F.C.': '',
            'United': 'Utd',
            'Athletic': 'Ath',
            'Association': 'Assoc',
            
            # Remove common suffixes
            ' FC': '',
            ' F.C.': '',
            ' AFC': '',
            ' United': ' Utd',
        }
        
        # Chinese to English common translations
        self.chinese_team_translations = {
            '曼联': 'Manchester United',
            '曼城': 'Manchester City', 
            '利物浦': 'Liverpool',
            '阿森纳': 'Arsenal',
            '切尔西': 'Chelsea',
            '巴萨': 'Barcelona',
            '皇马': 'Real Madrid',
            '马竞': 'Atletico Madrid',
        }
    
    def clean_text(self, text: str, remove_html: bool = True) -> str:
        """
        Clean and normalize text.
        
        Args:
            text: Input text
            remove_html: Whether to remove HTML tags
            
        Returns:
            Cleaned text
        """
        if not isinstance(text, str):
            return str(text) if text is not None else ''
        
        # Remove HTML entities and tags if requested
        if remove_html:
            text = html.unescape(text)
            text = re.sub(r'<[^>]+>', '', text)
        
        # Normalize Unicode characters
        text = unicodedata.normalize('NFKC', text)
        
        # Remove excessive whitespace
        text = ' '.join(text.split())
        
        # Remove control characters
        text = ''.join(char for char in text if not unicodedata.category(char).startswith('C'))
        
        return text.strip()
    
    def normalize_name(self, name: str, type_hint: str = 'team') -> str:
        """
        Normalize team or league names for consistency.
        
        Args:
            name: Name to normalize
            type_hint: Type of name ('team', 'league', 'player')
            
        Returns:
            Normalized name
        """
        if not name:
            return ''
        
        # Clean the text first
        name = self.clean_text(name)
        
        if type_hint == 'team':
            return self._normalize_team_name(name)
        elif type_hint == 'league':
            return self._normalize_league_name(name)
        else:
            return name
    
    def _normalize_team_name(self, name: str) -> str:
        """Normalize team name specifically."""
        original_name = name
        
        # Apply common replacements
        for old, new in self.team_name_replacements.items():
            name = name.replace(old, new)
        
        # Remove extra spaces
        name = ' '.join(name.split())
        
        # Handle special cases
        name = name.strip()
        
        if not name:  # If name became empty after cleaning
            return original_name
        
        return name
    
    def _normalize_league_name(self, name: str) -> str:
        """Normalize league name specifically.""" 
        # Remove common league suffixes/prefixes for matching
        replacements = {
            '联赛': '',
            '甲级联赛': '甲',
            '乙级联赛': '乙',
            'Premier League': '超',
            'First Division': '甲',
            'Second Division': '乙',
        }
        
        normalized = name
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        return normalized.strip()
    
    def extract_numbers(self, text: str) -> List[int]:
        """
        Extract all numbers from text.
        
        Args:
            text: Input text
            
        Returns:
            List of integers found in text
        """
        if not text:
            return []
        
        numbers = re.findall(r'\d+', str(text))
        return [int(num) for num in numbers]
    
    def extract_score(self, score_text: str) -> Optional[tuple]:
        """
        Extract score tuple from score text.
        
        Args:
            score_text: Score string like "2-1", "3:0", etc.
            
        Returns:
            Tuple of (home_score, away_score) or None
        """
        if not score_text:
            return None
        
        # Common score patterns
        patterns = [
            r'^(\d+)[-:](\d+)$',  # 2-1, 3:0
            r'^(\d+)\s*[-:]\s*(\d+)$',  # 2 - 1, 3 : 0
        ]
        
        for pattern in patterns:
            match = re.match(pattern, score_text.strip())
            if match:
                try:
                    home_score = int(match.group(1))
                    away_score = int(match.group(2))
                    return (home_score, away_score)
                except ValueError:
                    continue
        
        return None
    
    def format_score(self, home_score: int, away_score: int, separator: str = '-') -> str:
        """Format score tuple as string."""
        return f"{home_score}{separator}{away_score}"
    
    def truncate_text(self, text: str, max_length: int = 100, suffix: str = '...') -> str:
        """
        Truncate text to maximum length.
        
        Args:
            text: Input text
            max_length: Maximum length
            suffix: Suffix to add if truncated
            
        Returns:
            Truncated text
        """
        if not text or len(text) <= max_length:
            return text
        
        # Try to break at word boundary
        truncated = text[:max_length - len(suffix)]
        last_space = truncated.rfind(' ')
        
        if last_space > max_length * 0.7:  # If word boundary is not too far back
            truncated = truncated[:last_space]
        
        return truncated + suffix
    
    def similarity_score(self, text1: str, text2: str) -> float:
        """
        Calculate similarity score between two texts (0.0 to 1.0).
        Simple implementation based on common characters.
        
        Args:
            text1: First text
            text2: Second text
            
        Returns:
            Similarity score
        """
        if not text1 or not text2:
            return 0.0
        
        # Normalize both texts
        text1 = self.clean_text(text1).lower()
        text2 = self.clean_text(text2).lower()
        
        if text1 == text2:
            return 1.0
        
        # Simple character-based similarity
        set1 = set(text1)
        set2 = set(text2)
        
        intersection = len(set1.intersection(set2))
        union = len(set1.union(set2))
        
        return intersection / union if union > 0 else 0.0
    
    def find_best_match(self, target: str, candidates: List[str], min_score: float = 0.5) -> Optional[str]:
        """
        Find best matching string from candidates.
        
        Args:
            target: Target string to match
            candidates: List of candidate strings
            min_score: Minimum similarity score required
            
        Returns:
            Best matching candidate or None
        """
        if not target or not candidates:
            return None
        
        best_match = None
        best_score = 0.0
        
        for candidate in candidates:
            score = self.similarity_score(target, candidate)
            if score > best_score and score >= min_score:
                best_score = score
                best_match = candidate
        
        return best_match
    
    def parse_team_vs_team(self, text: str) -> Optional[tuple]:
        """
        Parse "Team A vs Team B" format text.
        
        Args:
            text: Text containing team matchup
            
        Returns:
            Tuple of (home_team, away_team) or None
        """
        if not text:
            return None
        
        # Common vs patterns
        vs_patterns = [
            r'^(.+?)\s+vs\s+(.+)$',
            r'^(.+?)\s+v\s+(.+)$', 
            r'^(.+?)\s+-\s+(.+)$',
            r'^(.+?)\s+对\s+(.+)$',  # Chinese
        ]
        
        for pattern in vs_patterns:
            match = re.match(pattern, text.strip(), re.IGNORECASE)
            if match:
                home_team = match.group(1).strip()
                away_team = match.group(2).strip()
                return (home_team, away_team)
        
        return None
    
    def format_currency(self, amount: float, currency: str = 'USD') -> str:
        """Format currency amount."""
        currency_symbols = {
            'USD': '$',
            'EUR': '€', 
            'GBP': '£',
            'CNY': '¥',
            'JPY': '¥'
        }
        
        symbol = currency_symbols.get(currency, currency)
        return f"{symbol}{amount:,.2f}"
    
    def format_percentage(self, value: float, decimals: int = 1) -> str:
        """Format percentage value."""
        return f"{value:.{decimals}f}%"
    
    def slugify(self, text: str) -> str:
        """
        Convert text to URL-friendly slug.
        
        Args:
            text: Input text
            
        Returns:
            URL-friendly slug
        """
        if not text:
            return ''
        
        # Normalize and clean
        text = self.clean_text(text).lower()
        
        # Replace spaces and special characters with hyphens
        text = re.sub(r'[^\w\s-]', '', text)
        text = re.sub(r'[\s_-]+', '-', text)
        
        return text.strip('-')
    
    def mask_sensitive_data(self, text: str, mask_char: str = '*') -> str:
        """
        Mask potentially sensitive data in text.
        
        Args:
            text: Input text
            mask_char: Character to use for masking
            
        Returns:
            Text with sensitive data masked
        """
        if not text:
            return text
        
        # Mask email addresses
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 
                     f'{mask_char * 5}@{mask_char * 5}.com', text)
        
        # Mask phone numbers (simple pattern)
        text = re.sub(r'\b\d{3}-\d{3}-\d{4}\b', f'{mask_char * 3}-{mask_char * 3}-{mask_char * 4}', text)
        
        # Mask credit card numbers
        text = re.sub(r'\b\d{4}\s\d{4}\s\d{4}\s\d{4}\b', 
                     f'{mask_char * 4} {mask_char * 4} {mask_char * 4} {mask_char * 4}', text)
        
        return text


# Convenience functions
def clean_text(text: str, **kwargs) -> str:
    """Clean text using StringUtils."""
    utils = StringUtils()
    return utils.clean_text(text, **kwargs)


def normalize_name(name: str, type_hint: str = 'team') -> str:
    """Normalize name using StringUtils."""
    utils = StringUtils()
    return utils.normalize_name(name, type_hint)


def extract_numbers(text: str) -> List[int]:
    """Extract numbers from text."""
    utils = StringUtils()
    return utils.extract_numbers(text)


def extract_score(score_text: str) -> Optional[tuple]:
    """Extract score tuple from text."""
    utils = StringUtils()
    return utils.extract_score(score_text)


# String constants
COMMON_STOPWORDS = {
    'english': ['the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by'],
    'chinese': ['的', '和', '或', '但是', '在', '到', '为', '与', '由'],
    'spanish': ['el', 'la', 'y', 'o', 'pero', 'en', 'a', 'para', 'de', 'con', 'por'],
    'german': ['der', 'die', 'das', 'und', 'oder', 'aber', 'in', 'zu', 'für', 'von', 'mit', 'durch']
}