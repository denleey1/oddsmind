#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Shared application context utilities."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from core.logger import get_logger
from core.runtime import AppRuntime
from app_environment import init_environment, get_secure_config, get_environment_manager


@lru_cache(maxsize=1)
def get_runtime() -> AppRuntime:
    """Return the lazily initialised application runtime."""
    runtime = AppRuntime()
    runtime.configure_logging()
    if not init_environment():
        logger = get_logger(__name__)
        logger.error("环境配置初始化失败，应用启动中止")
        raise RuntimeError("Failed to initialise environment configuration")
    return runtime


@lru_cache(maxsize=1)
def get_secure_configuration():
    """Return cached secure configuration."""
    return get_secure_config()


def get_settings():
    """Expose runtime settings for compatibility."""
    return get_runtime().settings


def get_logger_for(name: str):
    """Convenience wrapper for acquiring configured loggers."""
    return get_logger(name)


def get_environment_manager_cached():
    """Expose the shared environment manager."""
    return get_environment_manager()
