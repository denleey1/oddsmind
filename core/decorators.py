#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for common scraper functionality.
Retry logic, rate limiting, performance monitoring, etc.
"""

import time
import functools
import asyncio
from typing import Callable, Any, Optional, Type, Tuple, Union, Dict
from datetime import datetime, timedelta
import logging
import threading
from collections import defaultdict

from .exceptions import RateLimitError, TimeoutError


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Optional[Callable] = None
) -> Callable:
    """
    Decorator that retries a function on failure with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff_factor: Multiplier for delay on each retry
        exceptions: Tuple of exception types to catch and retry on
        on_retry: Optional callback function called on each retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:  # Last attempt failed
                        break
                    
                    # Call retry callback if provided
                    if on_retry:
                        on_retry(attempt + 1, e, current_delay)
                    
                    # Wait before retry
                    time.sleep(current_delay)
                    current_delay *= backoff_factor
            
            # All attempts failed, raise the last exception
            raise last_exception
            
        return wrapper
    return decorator


class RateLimiter:
    """
    Thread-safe rate limiter using token bucket algorithm.

    [BUG FIX] 原实现在持锁状态下 sleep，导致所有并发线程被串行化。
    修复后: 先在锁内计算需要等待的时间并预占时间槽，然后释放锁后再 sleep。
    这样多线程可以并发等待而不互相阻塞。
    """
    
    def __init__(self, calls_per_second: float):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_called = defaultdict(float)
        self.lock = threading.Lock()
    
    def wait_if_needed(self, key: str = "default") -> None:
        """Wait if necessary to respect rate limit."""
        sleep_time = 0.0
        with self.lock:
            now = time.time()
            # 计算这个请求最早可以执行的时间
            earliest = self.last_called[key] + self.min_interval
            if now < earliest:
                sleep_time = earliest - now
            # 预占时间槽（即使还没sleep，也先记录，让下一个线程排到更后面）
            self.last_called[key] = max(now, earliest)
        # 释放锁后再 sleep，不阻塞其他线程
        if sleep_time > 0:
            time.sleep(sleep_time)


def rate_limit(
    calls_per_second: float,
    per_key: Optional[Callable] = None
) -> Callable:
    """
    Decorator that enforces rate limiting on function calls.
    
    Args:
        calls_per_second: Maximum number of calls per second
        per_key: Optional function to extract rate limiting key from args
        
    Returns:
        Decorated function with rate limiting
    """
    limiter = RateLimiter(calls_per_second)
    
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Determine rate limiting key
            if per_key:
                key = per_key(*args, **kwargs)
            else:
                key = "default"
            
            # Wait if needed
            limiter.wait_if_needed(key)
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def log_execution_time(
    logger: Optional[logging.Logger] = None,
    level: int = logging.INFO,
    include_args: bool = False
) -> Callable:
    """
    Decorator that logs function execution time.
    
    Args:
        logger: Logger to use (creates one if None)
        level: Log level for timing messages
        include_args: Whether to include function arguments in log
        
    Returns:
        Decorated function with execution time logging
    """
    def decorator(func: Callable) -> Callable:
        nonlocal logger
        if logger is None:
            logger = logging.getLogger(func.__module__)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                execution_time = time.time() - start_time
                
                # Build log message
                func_name = f"{func.__module__}.{func.__name__}"
                message = f"{func_name} executed in {execution_time:.3f}s"
                
                if not success:
                    message += f" (FAILED: {error})"
                
                # Add arguments if requested
                extra_data = {
                    'function': func_name,
                    'execution_time': execution_time,
                    'success': success
                }
                
                if include_args:
                    extra_data['args'] = str(args)
                    extra_data['kwargs'] = str(kwargs)
                
                if error:
                    extra_data['error'] = error
                
                logger.log(level, message, extra=extra_data)
            
            return result
        
        return wrapper
    return decorator


def timeout(seconds: float) -> Callable:
    """
    Decorator that enforces a timeout on function execution.
    
    Args:
        seconds: Timeout in seconds
        
    Returns:
        Decorated function with timeout enforcement
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # This is a simplified timeout implementation
            # In production, you might want to use threading.Timer or asyncio
            start_time = time.time()
            
            def check_timeout():
                if time.time() - start_time > seconds:
                    raise TimeoutError(
                        f"Function {func.__name__} timed out after {seconds}s"
                    )
            
            # Execute function (this is simplified - real implementation would need
            # proper timeout handling, possibly with threading or signals)
            result = func(*args, **kwargs)
            check_timeout()
            
            return result
        
        return wrapper
    return decorator


def cache_result(
    ttl_seconds: int = 3600,
    max_size: int = 128,
    per_instance: bool = True
) -> Callable:
    """
    Decorator that caches function results with TTL.
    
    Args:
        ttl_seconds: Time to live for cached results
        max_size: Maximum cache size
        per_instance: Whether to cache per instance (for methods)
        
    Returns:
        Decorated function with caching
    """
    def decorator(func: Callable) -> Callable:
        cache = {}
        cache_times = {}
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Create cache key
            if per_instance and args:
                # Include instance in key for methods
                cache_key = (id(args[0]), args[1:], frozenset(kwargs.items()))
            else:
                cache_key = (args, frozenset(kwargs.items()))
            
            # Check if result is cached and still valid
            now = time.time()
            if cache_key in cache and cache_key in cache_times:
                if now - cache_times[cache_key] < ttl_seconds:
                    return cache[cache_key]
            
            # Execute function and cache result
            result = func(*args, **kwargs)
            
            # Manage cache size
            if len(cache) >= max_size:
                # Remove oldest entry
                oldest_key = min(cache_times.keys(), key=lambda k: cache_times[k])
                del cache[oldest_key]
                del cache_times[oldest_key]
            
            cache[cache_key] = result
            cache_times[cache_key] = now
            
            return result
        
        return wrapper
    return decorator


def validate_args(**validators) -> Callable:
    """
    Decorator that validates function arguments.
    
    Args:
        **validators: Mapping of argument names to validator functions
        
    Returns:
        Decorated function with argument validation
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Get function signature
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Validate arguments
            for arg_name, validator in validators.items():
                if arg_name in bound_args.arguments:
                    value = bound_args.arguments[arg_name]
                    if not validator(value):
                        raise ValueError(
                            f"Invalid value for argument '{arg_name}': {value}"
                        )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


# Async versions of decorators

async def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
) -> Callable:
    """Async version of retry decorator."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_attempts - 1:
                        break
                    
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff_factor
            
            raise last_exception
            
        return wrapper
    return decorator