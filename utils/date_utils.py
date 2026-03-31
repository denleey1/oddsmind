#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Date and time utilities for OddsMind system.
Comprehensive date/time handling with timezone support.
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, List
from dateutil import parser as date_parser
import pytz

from core.logger import get_logger
from utils.timezone_utils import now as get_now


class DateUtils:
    """Utility class for date and time operations."""
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        
        # Common timezone mappings
        self.timezone_map = {
            'UTC': pytz.UTC,
            'GMT': pytz.timezone('GMT'),
            'CST': pytz.timezone('Asia/Shanghai'),  # China Standard Time
            'JST': pytz.timezone('Asia/Tokyo'),     # Japan Standard Time
            'KST': pytz.timezone('Asia/Seoul'),     # Korea Standard Time
            'EST': pytz.timezone('US/Eastern'),
            'PST': pytz.timezone('US/Pacific'),
        }
        
        # Common date patterns from Titan007
        self.date_patterns = [
            # YYYY-MM-DD HH:MM formats
            (r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2})$', '%Y-%m-%d %H:%M'),
            (r'^(\d{4})-(\d{2})-(\d{2}) (\d{2}):(\d{2}):(\d{2})$', '%Y-%m-%d %H:%M:%S'),
            
            # MM-DD HH:MM formats (current year assumed)
            (r'^(\d{2})-(\d{2}) (\d{2}):(\d{2})$', '%m-%d %H:%M'),
            
            # DD/MM/YYYY formats
            (r'^(\d{2})/(\d{2})/(\d{4}) (\d{2}):(\d{2})$', '%d/%m/%Y %H:%M'),
            
            # Other common formats
            (r'^(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})$', '%Y%m%d%H%M'),  # YYYYMMDDHHMM
        ]
    
    def parse_datetime(
        self, 
        date_string: str,
        default_year: Optional[int] = None,
        timezone_name: str = 'UTC'
    ) -> Optional[datetime]:
        """
        Parse datetime string with multiple format support.
        
        Args:
            date_string: Date string to parse
            default_year: Default year for formats without year
            timezone_name: Target timezone name
            
        Returns:
            Parsed datetime object or None if parsing fails
        """
        if not date_string or not isinstance(date_string, str):
            return None
        
        date_string = date_string.strip()
        
        # Try common patterns first
        for pattern, format_str in self.date_patterns:
            match = re.match(pattern, date_string)
            if match:
                try:
                    # Handle MM-DD format (needs current year)
                    if format_str == '%m-%d %H:%M':
                        current_year = default_year or get_now().year
                        full_date_string = f"{current_year}-{date_string}"
                        dt = datetime.strptime(full_date_string, f'%Y-%m-%d %H:%M')
                    else:
                        dt = datetime.strptime(date_string, format_str)
                    
                    # Apply timezone
                    return self._apply_timezone(dt, timezone_name)
                    
                except ValueError:
                    continue
        
        # Try dateutil parser as fallback
        try:
            dt = date_parser.parse(date_string)
            return self._apply_timezone(dt, timezone_name)
        
        except (ValueError, TypeError):
            self.logger.debug(f"Failed to parse date string: {date_string}")
            return None
    
    def _apply_timezone(self, dt: datetime, timezone_name: str) -> datetime:
        """Apply timezone to datetime object."""
        try:
            if timezone_name in self.timezone_map:
                tz = self.timezone_map[timezone_name]
            else:
                tz = pytz.timezone(timezone_name)
            
            # If datetime is naive, localize it
            if dt.tzinfo is None:
                return tz.localize(dt)
            else:
                return dt.astimezone(tz)
                
        except Exception as e:
            self.logger.debug(f"Error applying timezone {timezone_name}: {e}")
            # Return as UTC if timezone application fails
            if dt.tzinfo is None:
                return pytz.UTC.localize(dt)
            return dt.astimezone(pytz.UTC)
    
    def format_datetime(
        self, 
        dt: datetime, 
        format_str: str = '%Y-%m-%d %H:%M:%S',
        timezone_name: Optional[str] = None
    ) -> str:
        """
        Format datetime object to string.
        
        Args:
            dt: Datetime object
            format_str: Format string
            timezone_name: Target timezone for conversion
            
        Returns:
            Formatted datetime string
        """
        if timezone_name and timezone_name in self.timezone_map:
            tz = self.timezone_map[timezone_name]
            dt = dt.astimezone(tz)
        
        return dt.strftime(format_str)
    
    def get_current_season(self, reference_date: Optional[datetime] = None) -> str:
        """
        Get current football season string.
        
        Args:
            reference_date: Reference date (uses current date if None)
            
        Returns:
            Season string like "2024-2025"
        """
        if reference_date is None:
            reference_date = get_now()
        
        year = reference_date.year
        month = reference_date.month
        
        # Football season typically starts in August/September
        # So if we're in first half of year, season started previous year
        if month <= 7:  # Jan-July: previous year season
            season_start = year - 1
            season_end = year
        else:  # Aug-Dec: current year season
            season_start = year
            season_end = year + 1
        
        return f"{season_start}-{season_end}"
    
    def parse_season_string(self, season_str: str) -> Optional[tuple]:
        """
        Parse season string into start and end years.
        
        Args:
            season_str: Season string like "2024-2025" or "2024/25"
            
        Returns:
            Tuple of (start_year, end_year) or None if parsing fails
        """
        if not season_str:
            return None
        
        # Handle different season formats
        patterns = [
            r'^(\d{4})-(\d{4})$',  # 2024-2025
            r'^(\d{4})/(\d{4})$',  # 2024/2025
            r'^(\d{4})-(\d{2})$',  # 2024-25
            r'^(\d{4})/(\d{2})$',  # 2024/25
            r'^(\d{4})$',          # 2024 (single year)
        ]
        
        for pattern in patterns:
            match = re.match(pattern, season_str)
            if match:
                groups = match.groups()
                start_year = int(groups[0])
                
                if len(groups) == 1:  # Single year
                    return (start_year, start_year + 1)
                elif len(groups[1]) == 2:  # Short format like 2024-25
                    end_year = int(f"{str(start_year)[:2]}{groups[1]}")
                else:  # Full format like 2024-2025
                    end_year = int(groups[1])
                
                return (start_year, end_year)
        
        return None
    
    def is_match_today(self, match_datetime: datetime) -> bool:
        """Check if match is today."""
        if not match_datetime:
            return False
        
        today = get_now().date()
        match_date = match_datetime.date()
        
        return match_date == today
    
    def is_match_recent(self, match_datetime: datetime, days: int = 7) -> bool:
        """Check if match is within recent days."""
        if not match_datetime:
            return False
        
        cutoff_date = get_now() - timedelta(days=days)
        return match_datetime >= cutoff_date
    
    def get_week_boundaries(self, reference_date: Optional[datetime] = None) -> tuple:
        """
        Get start and end of week for reference date.
        
        Returns:
            Tuple of (week_start, week_end)
        """
        if reference_date is None:
            reference_date = get_now()
        
        # Monday as start of week (weekday() returns 0 for Monday)
        days_since_monday = reference_date.weekday()
        week_start = reference_date - timedelta(days=days_since_monday)
        week_end = week_start + timedelta(days=6)
        
        # Set to start/end of day
        week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        week_end = week_end.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        return (week_start, week_end)
    
    def calculate_age_in_days(self, start_date: datetime, end_date: Optional[datetime] = None) -> int:
        """Calculate age in days between two dates."""
        if end_date is None:
            end_date = get_now()
        
        # Ensure both dates are timezone-naive or both are timezone-aware
        if start_date.tzinfo is not None and end_date.tzinfo is None:
            end_date = pytz.UTC.localize(end_date)
        elif start_date.tzinfo is None and end_date.tzinfo is not None:
            start_date = pytz.UTC.localize(start_date)
        
        delta = end_date - start_date
        return delta.days
    
    def get_next_match_day(self) -> datetime:
        """Get next Saturday (typical match day)."""
        today = get_now()
        days_until_saturday = (5 - today.weekday()) % 7  # 5 = Saturday
        
        if days_until_saturday == 0 and today.hour > 12:  # If it's Saturday afternoon
            days_until_saturday = 7  # Next Saturday
        
        next_saturday = today + timedelta(days=days_until_saturday)
        return next_saturday.replace(hour=15, minute=0, second=0, microsecond=0)


# Convenience functions
def parse_datetime(date_string: str, **kwargs) -> Optional[datetime]:
    """Parse datetime string."""
    utils = DateUtils()
    return utils.parse_datetime(date_string, **kwargs)


def format_datetime(dt: datetime, **kwargs) -> str:
    """Format datetime object."""
    utils = DateUtils()
    return utils.format_datetime(dt, **kwargs)


def get_current_season() -> str:
    """Get current football season."""
    utils = DateUtils()
    return utils.get_current_season()


# Common date format functions
def format_match_time(dt: datetime) -> str:
    """Format match time for display."""
    return dt.strftime('%Y-%m-%d %H:%M')


def format_short_date(dt: datetime) -> str:
    """Format date in short format."""
    return dt.strftime('%m-%d %H:%M')


def format_iso_date(dt: datetime) -> str:
    """Format date in ISO format."""
    return dt.isoformat()


def is_weekend(dt: datetime) -> bool:
    """Check if datetime is on weekend."""
    return dt.weekday() >= 5  # Saturday = 5, Sunday = 6