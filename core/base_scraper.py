#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Base scraper class providing common functionality for all scrapers.
Modern, type-annotated base class with comprehensive error handling and monitoring.
"""

import abc
import time
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, Type
from dataclasses import dataclass, field
from pathlib import Path
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import settings
from .logger import get_logger, log_performance
from .decorators import retry, rate_limit, log_execution_time
from .exceptions import (
    ScrapingError, 
    ValidationError, 
    TimeoutError,
    ConfigurationError
)


@dataclass
class ScrapingResult:
    """
    Standardized result object for scraping operations.
    """
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    execution_time: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            'success': self.success,
            'data': self.data,
            'error': self.error,
            'metadata': self.metadata,
            'execution_time': self.execution_time,
            'timestamp': self.timestamp.isoformat()
        }


class BaseScraper(abc.ABC):
    """
    Abstract base class for all scrapers.
    
    Provides:
    - Standardized configuration management
    - HTTP session with retry logic
    - Rate limiting
    - Error handling and logging
    - Checkpoint/resume functionality
    - Performance monitoring
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Initialize base scraper.
        
        Args:
            name: Unique name for this scraper instance
            config: Optional configuration overrides
        """
        self.name = name
        self.config = {**settings.to_dict(), **(config or {})}
        self.logger = get_logger(f"{self.__class__.__module__}.{name}")
        
        # Initialize components
        self._init_session()
        self._init_checkpoints()
        
        # Statistics
        self.stats = {
            'total_requests': 0,
            'successful_requests': 0,
            'failed_requests': 0,
            'start_time': None,
            'end_time': None,
            'items_processed': 0,
            'items_success': 0,
            'items_failed': 0
        }
        
        self.logger.info(f"Initialized scraper: {self.name}")
    
    def _init_session(self) -> None:
        """Initialize HTTP session with retry strategy and timeout."""
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.config['crawler']['retry_times'],
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        
        # Mount adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers (including Referer to avoid WAF blocking)
        # Cache-busting headers prevent CDN/proxy from serving stale .js files,
        # which caused match status updates to lag behind by 30+ minutes.
        self.session.headers.update({
            'User-Agent': self.config['crawler']['user_agent'],
            'Accept': '*/*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Referer': 'https://zq.titan007.com/',
            'Connection': 'keep-alive',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
        })
        
        # Apply tunnel proxy (if configured via env vars)
        try:
            from scrapers.proxy_config import apply_proxy_to_session
            apply_proxy_to_session(self.session)
        except ImportError:
            pass
        
        # Set timeout
        self.session.timeout = self.config['crawler']['request_timeout']
    
    def _init_checkpoints(self) -> None:
        """Initialize checkpoint functionality."""
        if self.config['scraping']['enable_checkpoints']:
            self.checkpoint_dir = settings.get_checkpoint_dir()
            self.checkpoint_file = self.checkpoint_dir / f"{self.name}.json"
        else:
            self.checkpoint_dir = None
            self.checkpoint_file = None
    
    @rate_limit(calls_per_second=2.0)  # Default rate limiting
    @log_execution_time()
    def make_request(
        self,
        url: str,
        method: str = 'GET',
        **kwargs
    ) -> requests.Response:
        """
        Make HTTP request with error handling and statistics tracking.
        
        Args:
            url: URL to request
            method: HTTP method
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
            
        Raises:
            ScrapingError: On request failure
        """
        self.stats['total_requests'] += 1
        
        try:
            # Append a cache-busting timestamp to every GET request so that
            # CDN / reverse-proxy layers return fresh data instead of cached
            # .js files, which previously caused match status lag of 30+ min.
            if method.upper() == 'GET':
                sep = '&' if '?' in url else '?'
                url = f"{url}{sep}_={int(time.time() * 1000)}"

            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            
            self.stats['successful_requests'] += 1
            self.logger.debug(f"Request successful: {method} {url}")
            
            return response
            
        except requests.exceptions.RequestException as e:
            self.stats['failed_requests'] += 1
            error_msg = f"Request failed: {method} {url} - {str(e)}"
            self.logger.error(error_msg)
            
            raise ScrapingError(
                error_msg,
                url=url,
                status_code=getattr(e.response, 'status_code', None),
                response_text=getattr(e.response, 'text', None)
            )
    
    def save_checkpoint(self, data: Dict[str, Any]) -> None:
        """
        Save checkpoint data to file.
        
        Args:
            data: Data to save in checkpoint
        """
        if not self.checkpoint_file:
            return
        
        try:
            checkpoint_data = {
                'timestamp': datetime.utcnow().isoformat(),
                'scraper': self.name,
                'stats': self.stats.copy(),
                'data': data
            }
            
            with open(self.checkpoint_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)
            
            self.logger.debug(f"Checkpoint saved: {self.checkpoint_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to save checkpoint: {e}")
    
    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """
        Load checkpoint data from file.
        
        Returns:
            Checkpoint data or None if not available
        """
        if not self.checkpoint_file or not self.checkpoint_file.exists():
            return None
        
        try:
            with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                checkpoint_data = json.load(f)
            
            # Check if checkpoint is not too old
            timestamp = datetime.fromisoformat(checkpoint_data['timestamp'])
            max_age = datetime.utcnow().timestamp() - 24*3600  # 24 hours
            
            if timestamp.timestamp() < max_age:
                self.logger.info("Checkpoint too old, ignoring")
                return None
            
            self.logger.info(f"Loaded checkpoint from: {checkpoint_data['timestamp']}")
            return checkpoint_data['data']
            
        except Exception as e:
            self.logger.error(f"Failed to load checkpoint: {e}")
            return None
    
    def clear_checkpoint(self) -> None:
        """Clear checkpoint file."""
        if self.checkpoint_file and self.checkpoint_file.exists():
            try:
                self.checkpoint_file.unlink()
                self.logger.debug("Checkpoint cleared")
            except Exception as e:
                self.logger.error(f"Failed to clear checkpoint: {e}")
    
    def start_operation(self) -> None:
        """Mark the start of a scraping operation."""
        self.stats['start_time'] = datetime.utcnow()
        self.logger.info(f"Starting scraping operation: {self.name}")
    
    def end_operation(self) -> None:
        """Mark the end of a scraping operation and log statistics."""
        self.stats['end_time'] = datetime.utcnow()
        
        if self.stats['start_time']:
            duration = (self.stats['end_time'] - self.stats['start_time']).total_seconds()
            
            self.logger.info(
                f"Scraping operation completed: {self.name}\n"
                f"Duration: {duration:.2f}s\n"
                f"Requests: {self.stats['total_requests']} "
                f"(Success: {self.stats['successful_requests']}, "
                f"Failed: {self.stats['failed_requests']})\n"
                f"Items: {self.stats['items_processed']} "
                f"(Success: {self.stats['items_success']}, "
                f"Failed: {self.stats['items_failed']})"
            )
    
    def validate_config(self) -> None:
        """
        Validate scraper configuration.
        
        Raises:
            ConfigurationError: If configuration is invalid
        """
        errors = []
        
        # Validate crawler settings
        if self.config['crawler']['max_workers'] <= 0:
            errors.append("max_workers must be positive")
        
        if self.config['crawler']['request_timeout'] <= 0:
            errors.append("request_timeout must be positive")
        
        # Validate rate limits
        if self.config['crawler']['min_delay'] < 0:
            errors.append("min_delay cannot be negative")
        
        if self.config['crawler']['max_delay'] < self.config['crawler']['min_delay']:
            errors.append("max_delay must be >= min_delay")
        
        if errors:
            raise ConfigurationError(f"Configuration errors: {'; '.join(errors)}")
    
    @abc.abstractmethod
    def scrape(self, **kwargs) -> ScrapingResult:
        """
        Main scraping method - must be implemented by subclasses.
        
        Returns:
            ScrapingResult with operation outcome
        """
        pass
    
    def cleanup(self) -> None:
        """Clean up resources."""
        if hasattr(self, 'session'):
            self.session.close()
        
        self.logger.info(f"Scraper cleanup completed: {self.name}")
    
    def __enter__(self):
        """Context manager entry."""
        self.start_operation()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.end_operation()
        self.cleanup()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get current statistics."""
        return self.stats.copy()