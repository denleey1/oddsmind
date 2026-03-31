#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Performance monitoring utilities for OddsMind system.
Memory usage, execution time, and system resource monitoring.
"""

import time
import psutil
import threading
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections import deque
import statistics

from core.logger import get_logger
from utils.timezone_utils import now as get_now


@dataclass
class PerformanceMetrics:
    """Performance metrics data container."""
    operation_name: str
    execution_time_ms: float
    memory_before_mb: float
    memory_after_mb: float
    memory_delta_mb: float
    cpu_percent: float
    timestamp: datetime = field(default_factory=get_now)
    thread_id: int = field(default_factory=lambda: threading.get_ident())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'operation_name': self.operation_name,
            'execution_time_ms': self.execution_time_ms,
            'memory_before_mb': self.memory_before_mb,
            'memory_after_mb': self.memory_after_mb,
            'memory_delta_mb': self.memory_delta_mb,
            'cpu_percent': self.cpu_percent,
            'timestamp': self.timestamp.isoformat(),
            'thread_id': self.thread_id
        }


class PerformanceMonitor:
    """
    Comprehensive performance monitoring system.
    Tracks execution time, memory usage, and system resources.
    """
    
    def __init__(self, max_history: int = 1000):
        self.logger = get_logger(self.__class__.__name__)
        self.max_history = max_history
        self.metrics_history: deque = deque(maxlen=max_history)
        self.lock = threading.Lock()
        
        # Initialize process
        self.process = psutil.Process()
        
        self.logger.info("Performance monitor initialized")
    
    @contextmanager
    def monitor_operation(self, operation_name: str, log_result: bool = True):
        """
        Context manager for monitoring operation performance.
        
        Args:
            operation_name: Name of the operation being monitored
            log_result: Whether to log the result
            
        Usage:
            with monitor.monitor_operation("data_processing"):
                # your code here
                process_data()
        """
        # Capture initial state
        start_time = time.perf_counter()
        memory_before = self._get_memory_usage_mb()
        cpu_before = self.process.cpu_percent()
        
        try:
            yield
            
        finally:
            # Capture final state
            end_time = time.perf_counter()
            memory_after = self._get_memory_usage_mb()
            cpu_after = self.process.cpu_percent()
            
            # Calculate metrics
            execution_time_ms = (end_time - start_time) * 1000
            memory_delta = memory_after - memory_before
            avg_cpu_percent = (cpu_before + cpu_after) / 2
            
            # Create metrics object
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                execution_time_ms=execution_time_ms,
                memory_before_mb=memory_before,
                memory_after_mb=memory_after,
                memory_delta_mb=memory_delta,
                cpu_percent=avg_cpu_percent
            )
            
            # Store metrics
            with self.lock:
                self.metrics_history.append(metrics)
            
            # Log if requested
            if log_result:
                self.logger.info(
                    f"Performance [{operation_name}]: "
                    f"Time={execution_time_ms:.1f}ms, "
                    f"Memory={memory_delta:+.1f}MB, "
                    f"CPU={avg_cpu_percent:.1f}%"
                )
    
    def measure_function(self, func: Callable, *args, **kwargs) -> tuple:
        """
        Measure function execution and return result with metrics.
        
        Args:
            func: Function to measure
            *args: Function arguments
            **kwargs: Function keyword arguments
            
        Returns:
            Tuple of (result, metrics)
        """
        operation_name = getattr(func, '__name__', 'function')
        
        with self.monitor_operation(operation_name, log_result=False) as _:
            result = func(*args, **kwargs)
        
        # Get the latest metrics (just added)
        with self.lock:
            latest_metrics = self.metrics_history[-1] if self.metrics_history else None
        
        return result, latest_metrics
    
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific operation.
        
        Args:
            operation_name: Name of the operation
            
        Returns:
            Statistics dictionary
        """
        with self.lock:
            operation_metrics = [
                m for m in self.metrics_history 
                if m.operation_name == operation_name
            ]
        
        if not operation_metrics:
            return {'error': f'No metrics found for operation: {operation_name}'}
        
        # Calculate statistics
        execution_times = [m.execution_time_ms for m in operation_metrics]
        memory_deltas = [m.memory_delta_mb for m in operation_metrics]
        cpu_percentages = [m.cpu_percent for m in operation_metrics]
        
        return {
            'operation_name': operation_name,
            'total_executions': len(operation_metrics),
            'execution_time_stats': {
                'min_ms': min(execution_times),
                'max_ms': max(execution_times),
                'avg_ms': statistics.mean(execution_times),
                'median_ms': statistics.median(execution_times),
                'std_dev_ms': statistics.stdev(execution_times) if len(execution_times) > 1 else 0
            },
            'memory_stats': {
                'min_delta_mb': min(memory_deltas),
                'max_delta_mb': max(memory_deltas),
                'avg_delta_mb': statistics.mean(memory_deltas),
                'total_delta_mb': sum(memory_deltas)
            },
            'cpu_stats': {
                'min_percent': min(cpu_percentages),
                'max_percent': max(cpu_percentages),
                'avg_percent': statistics.mean(cpu_percentages)
            },
            'latest_execution': operation_metrics[-1].timestamp.isoformat()
        }
    
    def get_overall_stats(self) -> Dict[str, Any]:
        """Get overall performance statistics."""
        with self.lock:
            if not self.metrics_history:
                return {'message': 'No performance metrics available'}
            
            all_metrics = list(self.metrics_history)
        
        # Group by operation
        operations = {}
        for metric in all_metrics:
            op_name = metric.operation_name
            if op_name not in operations:
                operations[op_name] = []
            operations[op_name].append(metric)
        
        # Calculate per-operation stats
        operation_summaries = {}
        for op_name, op_metrics in operations.items():
            execution_times = [m.execution_time_ms for m in op_metrics]
            operation_summaries[op_name] = {
                'count': len(op_metrics),
                'total_time_ms': sum(execution_times),
                'avg_time_ms': statistics.mean(execution_times),
                'memory_impact_mb': sum(m.memory_delta_mb for m in op_metrics)
            }
        
        # Overall statistics
        total_execution_time = sum(m.execution_time_ms for m in all_metrics)
        total_memory_impact = sum(m.memory_delta_mb for m in all_metrics)
        
        return {
            'total_operations': len(all_metrics),
            'unique_operations': len(operations),
            'total_execution_time_ms': total_execution_time,
            'total_memory_impact_mb': total_memory_impact,
            'current_memory_mb': self._get_memory_usage_mb(),
            'current_cpu_percent': self.process.cpu_percent(),
            'operation_summaries': operation_summaries,
            'monitoring_period': {
                'start': min(m.timestamp for m in all_metrics).isoformat(),
                'end': max(m.timestamp for m in all_metrics).isoformat()
            }
        }
    
    def get_recent_metrics(self, count: int = 10) -> List[Dict[str, Any]]:
        """Get recent performance metrics."""
        with self.lock:
            recent = list(self.metrics_history)[-count:]
        
        return [metric.to_dict() for metric in recent]
    
    def clear_history(self) -> None:
        """Clear metrics history."""
        with self.lock:
            self.metrics_history.clear()
        
        self.logger.info("Performance metrics history cleared")
    
    def _get_memory_usage_mb(self) -> float:
        """Get current memory usage in MB."""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / 1024 / 1024  # Convert bytes to MB
        except Exception as e:
            self.logger.debug(f"Error getting memory usage: {e}")
            return 0.0
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            memory = psutil.virtual_memory()
            cpu_count = psutil.cpu_count()
            
            return {
                'cpu_count': cpu_count,
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_total_gb': memory.total / 1024 / 1024 / 1024,
                'memory_available_gb': memory.available / 1024 / 1024 / 1024,
                'memory_percent': memory.percent,
                'process_memory_mb': self._get_memory_usage_mb(),
                'process_cpu_percent': self.process.cpu_percent(),
                'process_threads': self.process.num_threads()
            }
        
        except Exception as e:
            self.logger.error(f"Error getting system info: {e}")
            return {'error': str(e)}


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None
_monitor_lock = threading.Lock()


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    
    if _performance_monitor is None:
        with _monitor_lock:
            if _performance_monitor is None:
                _performance_monitor = PerformanceMonitor()
    
    return _performance_monitor


# Convenience functions
def memory_usage() -> float:
    """Get current memory usage in MB."""
    try:
        process = psutil.Process()
        memory_info = process.memory_info()
        return memory_info.rss / 1024 / 1024
    except Exception:
        return 0.0


def execution_time_ms(func: Callable) -> Callable:
    """
    Decorator to measure function execution time.
    
    Usage:
        @execution_time_ms
        def my_function():
            pass
    """
    def wrapper(*args, **kwargs):
        start_time = time.perf_counter()
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            end_time = time.perf_counter()
            exec_time_ms = (end_time - start_time) * 1000
            logger = get_logger(func.__module__)
            logger.debug(f"{func.__name__} executed in {exec_time_ms:.1f}ms")
    
    return wrapper


@contextmanager
def measure_time(operation_name: str = "operation"):
    """
    Context manager to measure execution time.
    
    Usage:
        with measure_time("data_processing"):
            process_data()
    """
    monitor = get_performance_monitor()
    with monitor.monitor_operation(operation_name):
        yield


def log_memory_usage(operation: str) -> None:
    """Log current memory usage for an operation."""
    memory_mb = memory_usage()
    logger = get_logger("performance")
    logger.info(f"Memory usage after {operation}: {memory_mb:.1f} MB")


class ResourceTracker:
    """Track resource usage over time."""
    
    def __init__(self, interval_seconds: int = 60):
        self.interval = interval_seconds
        self.tracking = False
        self.data_points: List[Dict[str, Any]] = []
        self.thread: Optional[threading.Thread] = None
        self.logger = get_logger(self.__class__.__name__)
    
    def start_tracking(self) -> None:
        """Start resource tracking."""
        if self.tracking:
            return
        
        self.tracking = True
        self.thread = threading.Thread(target=self._track_resources, daemon=True)
        self.thread.start()
        self.logger.info(f"Started resource tracking (interval: {self.interval}s)")
    
    def stop_tracking(self) -> None:
        """Stop resource tracking."""
        self.tracking = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
        self.logger.info("Stopped resource tracking")
    
    def _track_resources(self) -> None:
        """Track resources in background thread."""
        while self.tracking:
            try:
                monitor = get_performance_monitor()
                system_info = monitor.get_system_info()
                
                data_point = {
                    'timestamp': get_now().isoformat(),
                    **system_info
                }
                
                self.data_points.append(data_point)
                
                # Keep only last 1000 data points
                if len(self.data_points) > 1000:
                    self.data_points = self.data_points[-1000:]
                
                time.sleep(self.interval)
                
            except Exception as e:
                self.logger.error(f"Error tracking resources: {e}")
                time.sleep(self.interval)
    
    def get_tracking_data(self) -> List[Dict[str, Any]]:
        """Get tracked resource data."""
        return self.data_points.copy()