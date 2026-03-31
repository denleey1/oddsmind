#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Common utilities for scrapers.
Shared functionality to reduce code duplication and improve maintainability.
"""

import re
import json
import time
import random
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime
import logging

from core.logger import get_logger


class ContentProcessor:
    """Utilities for processing scraped content."""
    
    @staticmethod
    def decode_content(content_bytes: bytes) -> str:
        """
        Safely decode content with fallback encoding strategies.
        
        Args:
            content_bytes: Raw content bytes
            
        Returns:
            Decoded string content
        """
        encoding_priority = ['gbk', 'utf-8', 'gb2312', 'latin1']
        
        for encoding in encoding_priority:
            try:
                return content_bytes.decode(encoding)
            except UnicodeDecodeError:
                continue
        
        # Final fallback with error handling
        return content_bytes.decode('gbk', errors='ignore')
    
    @staticmethod
    def validate_content(content: str, min_length: int = 100, required_markers: Optional[List[str]] = None) -> bool:
        """
        Validate that content is usable.
        
        Args:
            content: Content string to validate
            min_length: Minimum required content length
            required_markers: List of required strings in content
            
        Returns:
            True if content is valid
        """
        if not content or len(content) < min_length:
            return False
        
        if required_markers:
            return all(marker in content for marker in required_markers)
        
        return True


class StatisticsTracker:
    """Common statistics tracking for scrapers."""
    
    def __init__(self, name: str):
        self.name = name
        self.logger = get_logger(f"stats.{name}")
        self.stats = {
            'items_processed': 0,
            'items_success': 0,
            'items_failed': 0,
            'items_empty': 0,
            'start_time': None,
            'end_time': None,
            'processing_times': [],
            'error_counts': {}
        }
    
    def start_session(self):
        """Start a processing session."""
        self.stats['start_time'] = time.time()
        self.logger.info(f"Started {self.name} processing session")
    
    def record_success(self, processing_time: float = None, item_count: int = 1):
        """Record successful processing."""
        self.stats['items_success'] += item_count
        self.stats['items_processed'] += item_count
        
        if processing_time:
            self.stats['processing_times'].append(processing_time)
    
    def record_failure(self, error_type: str = "unknown", item_count: int = 1):
        """Record failed processing."""
        self.stats['items_failed'] += item_count
        self.stats['items_processed'] += item_count
        
        if error_type in self.stats['error_counts']:
            self.stats['error_counts'][error_type] += 1
        else:
            self.stats['error_counts'][error_type] = 1
    
    def record_empty(self, item_count: int = 1):
        """Record empty results."""
        self.stats['items_empty'] += item_count
        self.stats['items_success'] += item_count  # Empty is still successful
        self.stats['items_processed'] += item_count
    
    def end_session(self):
        """End processing session and calculate final stats."""
        self.stats['end_time'] = time.time()
        
        if self.stats['start_time']:
            total_time = self.stats['end_time'] - self.stats['start_time']
            self.logger.info(f"Completed {self.name} session in {total_time:.2f}s")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get statistics summary."""
        summary = self.stats.copy()
        
        # Calculate derived metrics
        if self.stats['processing_times']:
            summary['avg_processing_time'] = sum(self.stats['processing_times']) / len(self.stats['processing_times'])
            summary['min_processing_time'] = min(self.stats['processing_times'])
            summary['max_processing_time'] = max(self.stats['processing_times'])
        
        if self.stats['items_processed'] > 0:
            summary['success_rate'] = (self.stats['items_success'] / self.stats['items_processed']) * 100
            summary['failure_rate'] = (self.stats['items_failed'] / self.stats['items_processed']) * 100
            summary['empty_rate'] = (self.stats['items_empty'] / self.stats['items_processed']) * 100
        
        if self.stats['start_time'] and self.stats['end_time']:
            total_time = self.stats['end_time'] - self.stats['start_time']
            summary['total_session_time'] = total_time
            if total_time > 0:
                summary['items_per_second'] = self.stats['items_processed'] / total_time
        
        return summary


class AdaptiveRateLimit:
    """Adaptive rate limiting based on success/failure rates."""
    
    def __init__(
        self,
        base_delay: float = 1.0,
        min_delay: float = 0.5,
        max_delay: float = 10.0,
        backoff_factor: float = 1.5,
        recovery_factor: float = 0.8,
        failure_threshold: int = 3
    ):
        self.base_delay = base_delay
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.recovery_factor = recovery_factor
        self.failure_threshold = failure_threshold
        
        self.current_delay = base_delay
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.logger = get_logger("adaptive_rate_limit")
    
    def record_success(self):
        """Record successful request."""
        self.consecutive_failures = 0
        self.consecutive_successes += 1
        
        # Reduce delay after sustained success
        if self.consecutive_successes >= 5:
            self.current_delay = max(
                self.min_delay,
                self.current_delay * self.recovery_factor
            )
            self.consecutive_successes = 0
            self.logger.debug(f"Reduced delay to {self.current_delay:.2f}s")
    
    def record_failure(self):
        """Record failed request."""
        self.consecutive_successes = 0
        self.consecutive_failures += 1
        
        # Increase delay after failures
        if self.consecutive_failures >= self.failure_threshold:
            self.current_delay = min(
                self.max_delay,
                self.current_delay * self.backoff_factor
            )
            self.logger.warning(f"Increased delay to {self.current_delay:.2f}s after {self.consecutive_failures} failures")
    
    def wait(self):
        """Wait for the current delay period with jitter."""
        # Add random jitter (±20%)
        jitter = random.uniform(-0.2, 0.2)
        actual_delay = self.current_delay * (1 + jitter)
        
        time.sleep(actual_delay)
    
    def get_current_delay(self) -> float:
        """Get current delay value."""
        return self.current_delay


class SafeJSParser:
    """Safe JavaScript array parser to replace eval()."""
    
    @staticmethod
    def parse_js_array(js_array_str: str) -> List[Any]:
        """
        Safely parse JavaScript array string.
        
        Args:
            js_array_str: JavaScript array string
            
        Returns:
            Parsed list
            
        Raises:
            ValueError: If parsing fails
        """
        try:
            # Clean the string first
            cleaned = SafeJSParser._clean_js_array_string(js_array_str)
            
            # Convert to valid JSON
            json_str = SafeJSParser._js_to_json(cleaned)
            
            # Parse as JSON
            return json.loads(json_str)
            
        except (json.JSONDecodeError, ValueError) as e:
            # Fallback to regex-based parsing
            return SafeJSParser._regex_parse_array(js_array_str)
    
    @staticmethod
    def _clean_js_array_string(js_str: str) -> str:
        """Clean JavaScript array string."""
        # Remove outer brackets if present
        js_str = js_str.strip()
        if js_str.startswith('[') and js_str.endswith(']'):
            js_str = js_str[1:-1]
        
        return js_str
    
    @staticmethod
    def _js_to_json(js_str: str) -> str:
        """Convert JavaScript array syntax to JSON."""
        # Handle undefined/null values
        js_str = re.sub(r'\bundefined\b', 'null', js_str)
        js_str = re.sub(r'\bNaN\b', 'null', js_str)
        
        # Handle empty array elements
        js_str = re.sub(r',,+', ',null,', js_str)
        js_str = re.sub(r'\[,', '[null,', js_str)
        js_str = re.sub(r',\]', ',null]', js_str)
        
        # Ensure proper quoting of strings
        js_str = re.sub(r"'([^']*)'", r'"\1"', js_str)
        
        # Add array brackets
        return f'[{js_str}]'
    
    @staticmethod
    def _regex_parse_array(js_str: str) -> List[Any]:
        """Fallback regex-based array parsing."""
        result = []
        
        # Find array elements using regex
        pattern = r'(?:^|,)\s*([^,\[\]]+|\[[^\]]*\])\s*(?=,|$)'
        matches = re.findall(pattern, js_str)
        
        for match in matches:
            match = match.strip()
            
            # Parse different value types
            if match in ['undefined', 'null', '']:
                result.append(None)
            elif match.startswith('[') and match.endswith(']'):
                # Nested array
                result.append(SafeJSParser._regex_parse_array(match[1:-1]))
            elif match.startswith('"') and match.endswith('"'):
                # String
                result.append(match[1:-1])
            elif match.startswith("'") and match.endswith("'"):
                # String with single quotes
                result.append(match[1:-1])
            else:
                # Try to parse as number
                try:
                    if '.' in match:
                        result.append(float(match))
                    else:
                        result.append(int(match))
                except ValueError:
                    # Keep as string
                    result.append(match)
        
        return result


class CheckpointManager:
    """Common checkpoint management for scrapers."""
    
    @staticmethod
    def create_checkpoint_data(
        processed_items: set,
        failed_items: set,
        empty_items: set = None,
        custom_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Create standardized checkpoint data."""
        checkpoint = {
            'processed_items': list(processed_items),
            'failed_items': list(failed_items),
            'timestamp': datetime.utcnow().isoformat(),
            'checkpoint_version': '1.0'
        }
        
        if empty_items:
            checkpoint['empty_items'] = list(empty_items)
        
        if custom_data:
            checkpoint['custom_data'] = custom_data
        
        return checkpoint
    
    @staticmethod
    def load_checkpoint_data(checkpoint: Dict[str, Any]) -> Tuple[set, set, set]:
        """Load checkpoint data into sets."""
        processed = set(checkpoint.get('processed_items', []))
        failed = set(checkpoint.get('failed_items', []))
        empty = set(checkpoint.get('empty_items', []))
        
        return processed, failed, empty


def create_url_with_cache_buster(base_url: str, params: Dict[str, str] = None) -> str:
    """Create URL with cache busting parameter."""
    cache_buster = str(int(time.time() * 1000))
    
    if '?' in base_url:
        url = f"{base_url}&r={cache_buster}"
    else:
        url = f"{base_url}?r={cache_buster}"
    
    if params:
        for key, value in params.items():
            url += f"&{key}={value}"
    
    return url


def safe_convert(value: Any, target_type: type, default: Any = None) -> Any:
    """Safely convert value to target type with default fallback."""
    if value is None or value == '':
        return default
    
    try:
        if target_type == int:
            return int(float(str(value)))
        elif target_type == float:
            return float(value)
        elif target_type == str:
            return str(value)
        else:
            return target_type(value)
    except (ValueError, TypeError):
        return default