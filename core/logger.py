#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Logging configuration and utilities for OddsMind scraper system.
Modern logging setup with structured logging and performance monitoring.
"""

import logging
import logging.handlers
import sys
import json
from pathlib import Path
from typing import Optional, Dict, Any, Union
from datetime import datetime

from core.config import LoggingConfig


class StructuredFormatter(logging.Formatter):
    """
    Custom formatter that outputs structured JSON logs.
    Useful for log aggregation and analysis systems.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        # 延迟导入，避免循环导入
        from utils.timezone_utils import now as get_now
        log_entry = {
            'timestamp': get_now().isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields if present
        if hasattr(record, 'extra'):
            log_entry.update(record.extra)
        
        return json.dumps(log_entry, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Console formatter with color coding for different log levels.
    """
    
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record: logging.LogRecord) -> str:
        if record.levelname in self.COLORS:
            record.levelname = (
                f"{self.COLORS[record.levelname]}"
                f"{record.levelname}{self.RESET}"
            )
        return super().format(record)


def setup_logging(logging_config: Optional[LoggingConfig] = None, *, level: Optional[Union[int, str]] = None) -> None:
    """Configure root logging handlers based on the provided configuration."""
    config = logging_config or LoggingConfig.from_env()
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    # Get root logger
    root_logger = logging.getLogger()

    # Set log level
    effective_level = level if level is not None else config.level
    if isinstance(effective_level, str):
        root_logger.setLevel(effective_level.upper())
    else:
        root_logger.setLevel(effective_level)

    # Remove existing handlers to avoid duplication
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if isinstance(effective_level, str):
        console_handler.setLevel(effective_level.upper())
    else:
        console_handler.setLevel(effective_level)
    
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler for general logs
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / config.app_log_name,
        maxBytes=config.max_file_size,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    if isinstance(effective_level, str):
        file_handler.setLevel(effective_level.upper())
    else:
        file_handler.setLevel(effective_level)
        
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Error handler for errors and above
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / config.error_log_name,
        maxBytes=config.max_file_size,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # Performance handler for timing information
    perf_handler = logging.handlers.RotatingFileHandler(
        log_dir / config.performance_log_name,
        maxBytes=config.max_file_size,
        backupCount=config.backup_count,
        encoding='utf-8'
    )
    perf_handler.setLevel(logging.DEBUG)
    perf_handler.addFilter(lambda record: hasattr(record, 'execution_time'))
    perf_handler.setFormatter(StructuredFormatter())
    root_logger.addHandler(perf_handler)
    
    # Set specific logger levels
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('pymysql').setLevel(logging.WARNING)
    
    # Log setup completion
    logging.info(f"Logging configured with level {effective_level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


class PerformanceLogger:
    """
    Context manager for logging performance metrics.
    """
    
    def __init__(self, logger: logging.Logger, operation: str, **kwargs):
        self.logger = logger
        self.operation = operation
        self.extra = kwargs
        self.start_time = None
    
    def __enter__(self):
        # 延迟导入，避免循环导入
        from utils.timezone_utils import now as get_now
        self.start_time = get_now()
        self.logger.debug(f"Starting {self.operation}", extra={
            'operation': self.operation,
            'start_time': self.start_time.isoformat(),
            **self.extra
        })
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # 延迟导入，避免循环导入
        from utils.timezone_utils import now as get_now
        end_time = get_now()
        execution_time = (end_time - self.start_time).total_seconds()
        
        log_data = {
            'operation': self.operation,
            'execution_time': execution_time,
            'start_time': self.start_time.isoformat(),
            'end_time': end_time.isoformat(),
            'success': exc_type is None,
            **self.extra
        }
        
        if exc_type:
            log_data['error_type'] = exc_type.__name__
            log_data['error_message'] = str(exc_val)
            self.logger.error(f"{self.operation} failed after {execution_time:.3f}s", extra=log_data)
        else:
            self.logger.info(f"{self.operation} completed in {execution_time:.3f}s", extra=log_data)


def log_performance(logger: logging.Logger, operation: str, **kwargs):
    """
    Convenience function to create a PerformanceLogger context manager.
    
    Args:
        logger: Logger instance
        operation: Description of the operation being timed
        **kwargs: Additional context to log
    
    Returns:
        PerformanceLogger context manager
    """
    return PerformanceLogger(logger, operation, **kwargs)


# Initialize logging on module import
if not logging.getLogger().handlers:
    setup_logging()
