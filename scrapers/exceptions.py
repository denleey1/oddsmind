#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced exception classes for scrapers.
Provides more specific error types for better error handling and debugging.
"""

from typing import Optional, Any, Dict


class ScraperException(Exception):
    """Base exception for scraper-related errors."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.context = context or {}
    
    def __str__(self) -> str:
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            return f"{self.message} (Context: {context_str})"
        return self.message


class ContentError(ScraperException):
    """Raised when content validation fails."""
    
    def __init__(
        self, 
        message: str, 
        content_length: Optional[int] = None,
        expected_markers: Optional[list] = None,
        url: Optional[str] = None
    ):
        context = {}
        if content_length is not None:
            context['content_length'] = content_length
        if expected_markers:
            context['expected_markers'] = expected_markers
        if url:
            context['url'] = url
        
        super().__init__(message, context)


class EncodingError(ScraperException):
    """Raised when content encoding fails."""
    
    def __init__(
        self, 
        message: str, 
        attempted_encodings: Optional[list] = None,
        content_preview: Optional[str] = None
    ):
        context = {}
        if attempted_encodings:
            context['attempted_encodings'] = attempted_encodings
        if content_preview:
            context['content_preview'] = content_preview[:200] + '...' if len(content_preview) > 200 else content_preview
        
        super().__init__(message, context)


class ParseError(ScraperException):
    """Raised when parsing fails."""
    
    def __init__(
        self, 
        message: str, 
        parser_type: Optional[str] = None,
        data_type: Optional[str] = None,
        content_sample: Optional[str] = None
    ):
        context = {}
        if parser_type:
            context['parser_type'] = parser_type
        if data_type:
            context['data_type'] = data_type
        if content_sample:
            context['content_sample'] = content_sample[:500] + '...' if len(content_sample) > 500 else content_sample
        
        super().__init__(message, context)


class RateLimitError(ScraperException):
    """Raised when rate limiting is exceeded."""
    
    def __init__(
        self, 
        message: str, 
        retry_after: Optional[float] = None,
        current_delay: Optional[float] = None,
        attempts_made: Optional[int] = None
    ):
        context = {}
        if retry_after is not None:
            context['retry_after'] = retry_after
        if current_delay is not None:
            context['current_delay'] = current_delay
        if attempts_made is not None:
            context['attempts_made'] = attempts_made
        
        super().__init__(message, context)


class CompanyFilterError(ScraperException):
    """Raised when company filtering configuration is invalid."""
    
    def __init__(
        self, 
        message: str, 
        filter_type: Optional[str] = None,
        available_companies: Optional[list] = None,
        invalid_companies: Optional[list] = None
    ):
        context = {}
        if filter_type:
            context['filter_type'] = filter_type
        if available_companies:
            context['available_companies_count'] = len(available_companies)
        if invalid_companies:
            context['invalid_companies'] = invalid_companies
        
        super().__init__(message, context)


class DataValidationError(ScraperException):
    """Raised when scraped data fails validation."""
    
    def __init__(
        self, 
        message: str, 
        validation_errors: Optional[list] = None,
        data_type: Optional[str] = None,
        item_count: Optional[int] = None
    ):
        context = {}
        if validation_errors:
            context['validation_errors'] = validation_errors
            context['error_count'] = len(validation_errors)
        if data_type:
            context['data_type'] = data_type
        if item_count is not None:
            context['item_count'] = item_count
        
        super().__init__(message, context)


class CheckpointError(ScraperException):
    """Raised when checkpoint operations fail."""
    
    def __init__(
        self, 
        message: str, 
        checkpoint_path: Optional[str] = None,
        operation: Optional[str] = None,
        data_size: Optional[int] = None
    ):
        context = {}
        if checkpoint_path:
            context['checkpoint_path'] = checkpoint_path
        if operation:
            context['operation'] = operation
        if data_size is not None:
            context['data_size'] = data_size
        
        super().__init__(message, context)


class NetworkError(ScraperException):
    """Raised when network operations fail."""
    
    def __init__(
        self, 
        message: str, 
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        response_time: Optional[float] = None,
        attempt_number: Optional[int] = None
    ):
        context = {}
        if url:
            context['url'] = url
        if status_code is not None:
            context['status_code'] = status_code
        if response_time is not None:
            context['response_time'] = round(response_time, 2)
        if attempt_number is not None:
            context['attempt_number'] = attempt_number
        
        super().__init__(message, context)


class ConfigurationError(ScraperException):
    """Raised when scraper configuration is invalid."""
    
    def __init__(
        self, 
        message: str, 
        config_key: Optional[str] = None,
        expected_type: Optional[str] = None,
        actual_value: Optional[Any] = None
    ):
        context = {}
        if config_key:
            context['config_key'] = config_key
        if expected_type:
            context['expected_type'] = expected_type
        if actual_value is not None:
            context['actual_value'] = str(actual_value)
            context['actual_type'] = type(actual_value).__name__
        
        super().__init__(message, context)


def create_contextual_error(
    error_type: type,
    base_message: str,
    **context
) -> ScraperException:
    """
    Create a contextual error with additional information.
    
    Args:
        error_type: Exception class to instantiate
        base_message: Base error message
        **context: Additional context information
        
    Returns:
        Configured exception instance
    """
    if issubclass(error_type, ScraperException):
        return error_type(base_message, context=context)
    else:
        # Fallback for non-scraper exceptions
        return ScraperException(base_message, context=context)


def log_error_context(logger, exception: ScraperException, operation: Optional[str] = None):
    """
    Log detailed error context information.
    
    Args:
        logger: Logger instance
        exception: Scraper exception with context
        operation: Optional operation description
    """
    error_msg = f"{'Operation' if operation else 'Error'}: {operation or 'Unknown'}"
    error_msg += f"\nException: {type(exception).__name__}: {exception.message}"
    
    if exception.context:
        error_msg += "\nContext:"
        for key, value in exception.context.items():
            error_msg += f"\n  - {key}: {value}"
    
    logger.error(error_msg)