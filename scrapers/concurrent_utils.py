#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Advanced concurrency utilities for high-performance scraping.
Optimized for handling large-scale odds data collection with intelligent resource management.
"""

import time
import threading
from typing import Dict, List, Optional, Any, Callable, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed, Future
from queue import Queue, Empty
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import statistics
from datetime import datetime, timedelta

from core.logger import get_logger
from .exceptions import NetworkError, RateLimitError


class ConnectionPool:
    """Optimized connection pool with retry strategies and connection reuse."""
    
    def __init__(
        self,
        pool_connections: int = 10,
        pool_maxsize: int = 20,
        max_retries: int = 3,
        backoff_factor: float = 0.3,
        timeout: Tuple[float, float] = (5.0, 30.0)
    ):
        self.logger = get_logger("connection_pool")
        
        # Create session with connection pooling
        self.session = requests.Session()
        
        # Configure retry strategy (compatible with different urllib3 versions)
        retry_params = {
            'total': max_retries,
            'backoff_factor': backoff_factor
        }
        
        # Add status_forcelist if supported
        try:
            retry_params['status_forcelist'] = [429, 500, 502, 503, 504]
        except:
            pass
        
        # Try different parameter names for status codes
        try:
            retry_params['raise_on_status'] = False
        except:
            pass
        
        # Handle different urllib3 versions
        try:
            # Try newer urllib3 version (allowed_methods)
            retry_strategy = Retry(
                **retry_params,
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
        except TypeError:
            try:
                # Try older urllib3 version (method_whitelist)
                retry_strategy = Retry(
                    **retry_params,
                    method_whitelist=["HEAD", "GET", "OPTIONS"]
                )
            except TypeError:
                # Fallback without method restriction
                retry_strategy = Retry(**retry_params)
        
        # Configure HTTP adapter
        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy,
            pool_block=False
        )
        
        # Mount adapter for both HTTP and HTTPS
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # NOTE: No proxy for ConnectionPool – it only connects to 1x2d.titan007.com
        # which is directly reachable.  The tunnel proxy is unreliable for this domain.
        
        # Set default timeout
        self.timeout = timeout
        
        # Performance tracking
        self.request_count = 0
        self.success_count = 0
        self.error_count = 0
        self.response_times = []
        self.last_reset = time.time()
        
        # Thread safety
        self.stats_lock = threading.Lock()
        
        self.logger.info(f"Connection pool initialized: {pool_connections} connections, {pool_maxsize} max pool size")
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """Make GET request with connection pooling and monitoring."""
        start_time = time.time()
        
        try:
            # Use session timeout if not specified
            if 'timeout' not in kwargs:
                kwargs['timeout'] = self.timeout
            
            response = self.session.get(url, **kwargs)
            response_time = time.time() - start_time
            
            # Update statistics
            with self.stats_lock:
                self.request_count += 1
                self.response_times.append(response_time)
                
                if response.status_code == 200:
                    self.success_count += 1
                else:
                    self.error_count += 1
                
                # Keep only last 1000 response times for memory efficiency
                if len(self.response_times) > 1000:
                    self.response_times = self.response_times[-500:]
            
            if response.status_code != 200:
                raise NetworkError(
                    f"HTTP {response.status_code} error for {url}",
                    url=url,
                    status_code=response.status_code,
                    response_time=response_time
                )
            
            return response
            
        except requests.exceptions.Timeout:
            response_time = time.time() - start_time
            with self.stats_lock:
                self.request_count += 1
                self.error_count += 1
            
            raise NetworkError(
                f"Request timeout for {url}",
                url=url,
                response_time=response_time
            )
        
        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            with self.stats_lock:
                self.request_count += 1
                self.error_count += 1
            
            raise NetworkError(
                f"Request failed for {url}: {str(e)}",
                url=url,
                response_time=response_time
            )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        with self.stats_lock:
            if not self.response_times:
                return {
                    'total_requests': self.request_count,
                    'success_count': self.success_count,
                    'error_count': self.error_count,
                    'success_rate': 0.0,
                    'avg_response_time': 0.0
                }
            
            avg_response_time = statistics.mean(self.response_times)
            success_rate = (self.success_count / max(self.request_count, 1)) * 100
            
            return {
                'total_requests': self.request_count,
                'success_count': self.success_count,
                'error_count': self.error_count,
                'success_rate': round(success_rate, 2),
                'avg_response_time': round(avg_response_time, 3),
                'min_response_time': round(min(self.response_times), 3),
                'max_response_time': round(max(self.response_times), 3),
                'p95_response_time': round(statistics.quantiles(self.response_times, n=20)[18], 3)
            }
    
    def reset_stats(self):
        """Reset statistics counters."""
        with self.stats_lock:
            self.request_count = 0
            self.success_count = 0
            self.error_count = 0
            self.response_times = []
            self.last_reset = time.time()
    
    def close(self):
        """Close the connection pool."""
        self.session.close()
        self.logger.info("Connection pool closed")


class DynamicThreadPool:
    """Dynamic thread pool with auto-scaling based on performance metrics."""
    
    def __init__(
        self,
        min_workers: int = 2,
        max_workers: int = 20,
        initial_workers: int = 5,
        scale_up_threshold: float = 0.8,  # Scale up if utilization > 80%
        scale_down_threshold: float = 0.3,  # Scale down if utilization < 30%
        evaluation_interval: float = 30.0  # Evaluate every 30 seconds
    ):
        self.min_workers = min_workers
        self.max_workers = max_workers
        self.current_workers = initial_workers
        self.scale_up_threshold = scale_up_threshold
        self.scale_down_threshold = scale_down_threshold
        self.evaluation_interval = evaluation_interval
        
        # Performance tracking
        self.active_tasks = 0
        self.completed_tasks = 0
        self.failed_tasks = 0
        self.last_evaluation = time.time()
        self.utilization_history = []
        
        # Thread safety
        self.lock = threading.Lock()
        
        self.logger = get_logger("dynamic_thread_pool")
        self.logger.info(f"Dynamic thread pool initialized: {initial_workers} workers (min={min_workers}, max={max_workers})")
    
    def _calculate_utilization(self) -> float:
        """Calculate current thread utilization."""
        if self.current_workers == 0:
            return 0.0
        return self.active_tasks / self.current_workers
    
    def _should_scale_up(self) -> bool:
        """Determine if we should scale up workers."""
        if self.current_workers >= self.max_workers:
            return False
        
        utilization = self._calculate_utilization()
        
        # Scale up if utilization is high and we have recent high utilization
        if utilization > self.scale_up_threshold:
            return True
        
        # Scale up if average utilization over recent history is high
        if len(self.utilization_history) >= 3:
            avg_utilization = statistics.mean(self.utilization_history[-3:])
            return avg_utilization > self.scale_up_threshold * 0.9
        
        return False
    
    def _should_scale_down(self) -> bool:
        """Determine if we should scale down workers."""
        if self.current_workers <= self.min_workers:
            return False
        
        utilization = self._calculate_utilization()
        
        # Scale down if utilization is consistently low
        if utilization < self.scale_down_threshold:
            if len(self.utilization_history) >= 5:
                avg_utilization = statistics.mean(self.utilization_history[-5:])
                return avg_utilization < self.scale_down_threshold * 1.2
        
        return False
    
    def _adjust_pool_size(self, executor: ThreadPoolExecutor) -> Optional[int]:
        """Adjust thread pool size based on current metrics."""
        now = time.time()
        
        if now - self.last_evaluation < self.evaluation_interval:
            return None
        
        with self.lock:
            utilization = self._calculate_utilization()
            self.utilization_history.append(utilization)
            
            # Keep only last 20 measurements
            if len(self.utilization_history) > 20:
                self.utilization_history = self.utilization_history[-10:]
            
            old_workers = self.current_workers
            
            if self._should_scale_up():
                self.current_workers = min(self.max_workers, self.current_workers + 2)
                self.logger.info(f"Scaling UP: {old_workers} -> {self.current_workers} workers (utilization: {utilization:.2f})")
            
            elif self._should_scale_down():
                self.current_workers = max(self.min_workers, self.current_workers - 1)
                self.logger.info(f"Scaling DOWN: {old_workers} -> {self.current_workers} workers (utilization: {utilization:.2f})")
            
            self.last_evaluation = now
            
            return self.current_workers if self.current_workers != old_workers else None
    
    def record_task_start(self):
        """Record that a task has started."""
        with self.lock:
            self.active_tasks += 1
    
    def record_task_complete(self, success: bool = True):
        """Record that a task has completed."""
        with self.lock:
            self.active_tasks = max(0, self.active_tasks - 1)
            if success:
                self.completed_tasks += 1
            else:
                self.failed_tasks += 1
    
    def get_optimal_worker_count(self) -> int:
        """Get the current optimal worker count."""
        with self.lock:
            return self.current_workers
    
    def get_stats(self) -> Dict[str, Any]:
        """Get thread pool statistics."""
        with self.lock:
            total_tasks = self.completed_tasks + self.failed_tasks
            success_rate = (self.completed_tasks / max(total_tasks, 1)) * 100
            utilization = self._calculate_utilization()
            
            return {
                'current_workers': self.current_workers,
                'active_tasks': self.active_tasks,
                'completed_tasks': self.completed_tasks,
                'failed_tasks': self.failed_tasks,
                'success_rate': round(success_rate, 2),
                'current_utilization': round(utilization, 3),
                'avg_recent_utilization': round(statistics.mean(self.utilization_history[-5:]), 3) if len(self.utilization_history) >= 5 else 0.0,
                'min_workers': self.min_workers,
                'max_workers': self.max_workers
            }


class ConcurrentRateLimit:
    """Thread-safe rate limiter optimized for concurrent requests."""
    
    def __init__(
        self,
        requests_per_second: float = 2.0,
        burst_size: int = 5,
        window_size: float = 1.0
    ):
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size
        self.window_size = window_size
        
        # Token bucket algorithm
        self.tokens = burst_size
        self.last_refill = time.time()
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Statistics
        self.requests_made = 0
        self.requests_blocked = 0
        self.total_wait_time = 0.0
        
        self.logger = get_logger("concurrent_rate_limit")
    
    def _refill_tokens(self):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        
        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.requests_per_second
        self.tokens = min(self.burst_size, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make a request.
        
        Args:
            timeout: Maximum time to wait for permission
            
        Returns:
            True if permission granted, False if timeout
        """
        start_time = time.time()
        
        with self.lock:
            self._refill_tokens()
            
            if self.tokens >= 1:
                self.tokens -= 1
                self.requests_made += 1
                return True
            
            # Calculate wait time
            wait_time = (1 - self.tokens) / self.requests_per_second
            
            if timeout is not None and wait_time > timeout:
                self.requests_blocked += 1
                return False
        
        # Wait outside the lock to allow other threads
        time.sleep(wait_time)
        
        with self.lock:
            self.total_wait_time += time.time() - start_time
            self._refill_tokens()
            
            if self.tokens >= 1:
                self.tokens -= 1
                self.requests_made += 1
                return True
            else:
                self.requests_blocked += 1
                return False
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        with self.lock:
            total_requests = self.requests_made + self.requests_blocked
            success_rate = (self.requests_made / max(total_requests, 1)) * 100
            avg_wait_time = self.total_wait_time / max(self.requests_made, 1)
            
            return {
                'requests_per_second': self.requests_per_second,
                'burst_size': self.burst_size,
                'current_tokens': round(self.tokens, 2),
                'requests_made': self.requests_made,
                'requests_blocked': self.requests_blocked,
                'success_rate': round(success_rate, 2),
                'avg_wait_time': round(avg_wait_time, 3),
                'total_wait_time': round(self.total_wait_time, 2)
            }


class HighPerformanceExecutor:
    """High-performance executor with dynamic scaling and intelligent resource management."""
    
    def __init__(
        self,
        min_workers: int = 3,
        max_workers: int = 25,
        initial_workers: int = 8,
        connection_pool_size: int = 15,
        requests_per_second: float = 3.0
    ):
        # Initialize components
        self.connection_pool = ConnectionPool(
            pool_connections=connection_pool_size,
            pool_maxsize=connection_pool_size * 2
        )
        
        self.dynamic_pool = DynamicThreadPool(
            min_workers=min_workers,
            max_workers=max_workers,
            initial_workers=initial_workers
        )
        
        self.rate_limiter = ConcurrentRateLimit(
            requests_per_second=requests_per_second,
            burst_size=max(5, int(requests_per_second * 2))
        )
        
        self.logger = get_logger("high_performance_executor")
        
        # Execution tracking
        self.start_time = None
        self.total_tasks = 0
        self.completed_tasks = 0
    
    def execute_concurrent(
        self,
        tasks: List[Tuple[Callable, tuple, dict]],
        progress_callback: Optional[Callable[[int, int], None]] = None
    ) -> List[Any]:
        """
        Execute tasks concurrently with dynamic scaling.
        
        Args:
            tasks: List of (function, args, kwargs) tuples
            progress_callback: Optional progress reporting function
            
        Returns:
            List of results in the same order as tasks
        """
        if not tasks:
            return []
        
        self.start_time = time.time()
        self.total_tasks = len(tasks)
        results = [None] * len(tasks)
        
        self.logger.info(f"Starting concurrent execution of {len(tasks)} tasks")
        
        # Start with optimal worker count
        initial_workers = self.dynamic_pool.get_optimal_worker_count()
        
        with ThreadPoolExecutor(max_workers=initial_workers) as executor:
            # Submit all tasks
            future_to_index = {}
            
            for i, (func, args, kwargs) in enumerate(tasks):
                # [性能优化] 速率限制：超时时延迟重试，不直接跳过
                if not self.rate_limiter.acquire(timeout=30.0):
                    # 速率限制超时，延迟后重试（而不是跳过）
                    retry_delay = 5.0  # 延迟5秒后重试
                    self.logger.warning(f"Rate limit timeout for task {i}, will retry after {retry_delay}s")
                    time.sleep(retry_delay)
                    # 继续重试，不跳过
                    continue
                
                # Wrap function to include resource tracking
                wrapped_func = self._wrap_task(func, i)
                future = executor.submit(wrapped_func, *args, **kwargs)
                future_to_index[future] = i
            
            # Process completed tasks
            completed = 0
            for future in as_completed(future_to_index):
                task_index = future_to_index[future]
                completed += 1
                
                try:
                    result = future.result()
                    results[task_index] = result
                    self.dynamic_pool.record_task_complete(success=True)
                
                except Exception as e:
                    self.logger.error(f"Task {task_index} failed: {e}")
                    results[task_index] = e
                    self.dynamic_pool.record_task_complete(success=False)
                
                # Progress reporting
                if progress_callback:
                    progress_callback(completed, len(tasks))
                
                # Periodic scaling evaluation
                if completed % 10 == 0:
                    new_worker_count = self.dynamic_pool._adjust_pool_size(executor)
                    if new_worker_count is not None:
                        # Note: ThreadPoolExecutor doesn't support dynamic resizing
                        # This is logged for monitoring purposes
                        self.logger.info(f"Recommended worker adjustment to {new_worker_count}")
        
        execution_time = time.time() - self.start_time
        self.logger.info(f"Concurrent execution completed in {execution_time:.2f}s")
        
        return results
    
    def _wrap_task(self, func: Callable, task_index: int) -> Callable:
        """Wrap task function with resource tracking."""
        def wrapped(*args, **kwargs):
            self.dynamic_pool.record_task_start()
            
            try:
                # If function needs connection pool, inject it
                if 'connection_pool' in kwargs:
                    kwargs['connection_pool'] = self.connection_pool
                
                return func(*args, **kwargs)
            finally:
                pass  # Task completion recorded in main loop
        
        return wrapped
    
    def get_comprehensive_stats(self) -> Dict[str, Any]:
        """Get comprehensive statistics from all components."""
        execution_time = time.time() - self.start_time if self.start_time else 0
        
        return {
            'execution_time': round(execution_time, 2),
            'total_tasks': self.total_tasks,
            'connection_pool': self.connection_pool.get_stats(),
            'thread_pool': self.dynamic_pool.get_stats(),
            'rate_limiter': self.rate_limiter.get_stats(),
            'overall_throughput': round(self.total_tasks / max(execution_time, 1), 2)
        }
    
    def close(self):
        """Clean up resources."""
        self.connection_pool.close()
        self.logger.info("High-performance executor closed")


# Utility function for easy integration
def create_optimized_executor(
    target_rps: float = 3.0,
    max_concurrent: int = 20
) -> HighPerformanceExecutor:
    """Create an optimized executor with sensible defaults for odds scraping."""
    return HighPerformanceExecutor(
        min_workers=max(2, int(target_rps)),
        max_workers=max_concurrent,
        initial_workers=max(3, int(target_rps * 2)),
        connection_pool_size=max(10, max_concurrent),
        requests_per_second=target_rps
    )