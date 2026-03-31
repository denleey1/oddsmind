#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Custom exceptions for OddsMind scraper system.
Comprehensive exception hierarchy for better error handling.
"""

from typing import Optional, Any, Dict


class OddsMindError(Exception):
    """Base exception class for all OddsMind errors."""
    
    def __init__(
        self, 
        message: str,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
    
    def __str__(self) -> str:
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class ConfigurationError(OddsMindError):
    """Raised when there's an issue with configuration."""
    pass


class DatabaseError(OddsMindError):
    """Raised when database operations fail."""
    
    def __init__(
        self,
        message: str, 
        query: Optional[str] = None,
        params: Optional[tuple] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.query = query
        self.params = params


class ConnectionError(OddsMindError):
    """Raised when database connection fails."""
    pass


class ScrapingError(OddsMindError):
    """Raised when scraping operations fail."""
    
    def __init__(
        self,
        message: str,
        url: Optional[str] = None,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.url = url
        self.status_code = status_code
        self.response_text = response_text


class ParseError(ScrapingError):
    """Raised when parsing scraped content fails."""
    
    def __init__(
        self,
        message: str,
        content: Optional[str] = None,
        parser_type: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.content = content
        self.parser_type = parser_type


class ValidationError(OddsMindError):
    """Raised when data validation fails."""
    
    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.field = field
        self.value = value


class RateLimitError(ScrapingError):
    """Raised when rate limits are exceeded."""
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.retry_after = retry_after


class AuthenticationError(OddsMindError):
    """Raised when authentication fails."""
    pass


class TimeoutError(ScrapingError):
    """Raised when operations timeout."""
    
    def __init__(
        self,
        message: str,
        timeout_seconds: Optional[float] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.timeout_seconds = timeout_seconds


class DataIntegrityError(DatabaseError):
    """Raised when data integrity constraints are violated."""
    pass


class ResourceNotFoundError(OddsMindError):
    """Raised when a required resource is not found."""
    
    def __init__(
        self,
        message: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs
    ) -> None:
        super().__init__(message, **kwargs)
        self.resource_type = resource_type
        self.resource_id = resource_id


class ConcurrencyError(OddsMindError):
    """Raised when concurrency issues occur."""
    pass


def handle_exception(exc: Exception, context: Optional[str] = None) -> OddsMindError:
    """
    Convert generic exceptions to OddsMind-specific exceptions.
    
    Args:
        exc: The original exception
        context: Additional context about where the error occurred
        
    Returns:
        An OddsMindError subclass appropriate for the original exception
    """
    message = str(exc)
    if context:
        message = f"{context}: {message}"
    
    # Map common exceptions to our hierarchy
    if isinstance(exc, (ConnectionRefusedError, ConnectionAbortedError)):
        return ConnectionError(message, error_code="CONN_FAILED")
    
    elif isinstance(exc, TimeoutError):
        return TimeoutError(message, error_code="TIMEOUT")
    
    elif isinstance(exc, ValueError):
        return ValidationError(message, error_code="VALIDATION_ERROR")
    
    elif isinstance(exc, KeyError):
        return ResourceNotFoundError(message, error_code="NOT_FOUND")
    
    elif isinstance(exc, PermissionError):
        return AuthenticationError(message, error_code="AUTH_FAILED")
    
    else:
        # Generic wrapper for unhandled exceptions
        return OddsMindError(
            message, 
            error_code="UNKNOWN_ERROR",
            details={"original_type": type(exc).__name__}
        )