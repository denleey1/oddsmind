#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Application environment bootstrap utilities built on top of the shared AppConfig
model. This module is responsible for lazily loading configuration, validating
critical settings, and exposing helpers that the legacy entry points rely on.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from core.config import AppConfig
from core.logger import get_logger

logger = get_logger(__name__)


class EnvironmentManager:
    """Facade around :class:`AppConfig` with legacy-friendly helpers."""

    def __init__(self, config: Optional[AppConfig] = None) -> None:
        self._config = config or AppConfig.from_env()

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------
    @property
    def config(self) -> AppConfig:
        return self._config

    def get_database_config(self) -> Dict[str, Any]:
        return self._config.database.as_dict()

    def get_security_config(self) -> Dict[str, Any]:
        data = self._config.security.__dict__.copy()
        return data

    def get_app_config(self) -> Dict[str, Any]:
        return self._config.application.__dict__.copy()

    def get_logging_config(self) -> Dict[str, Any]:
        return self._config.logging.as_dict()

    def get_performance_config(self) -> Dict[str, Any]:
        return self._config.performance.__dict__.copy()

    def get_external_apis_config(self) -> Dict[str, Any]:
        return self._config.external_apis.as_dict()

    def get_flask_config(self) -> Dict[str, Any]:
        return self._config.to_flask_config()

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def is_production(self) -> bool:
        return self._config.application.is_production

    def is_development(self) -> bool:
        return self._config.application.is_development

    def validate_configuration(self) -> bool:
        """Validate configuration and log any issues."""
        errors = self._config.validate()
        for err in errors:
            logger.error(err)
        if errors:
            return False

        if self._config.security.auto_generated_secret:
            logger.warning(
                "SECRET_KEY not provided. A placeholder key is being used; "
                "replace it with a strong random value in production."
            )
        return True

    def log_configuration_summary(self) -> None:
        """Output a concise configuration overview (non-sensitive)."""
        db = self._config.database
        app_cfg = self._config.application
        perf = self._config.performance

        logger.info("=== Application configuration ===")
        logger.info(f"Environment        : {app_cfg.environment}")
        logger.info(f"Debug              : {app_cfg.debug}")
        logger.info(f"HTTP host/port    : {app_cfg.host}:{app_cfg.port}")
        logger.info(f"Database host      : {db.host}:{db.port}")
        logger.info(f"Database name      : {db.name}")
        logger.info(f"Executor workers   : {perf.executor_max_workers}")
        logger.info(f"Scraper workers    : {perf.scraper_executor_max_workers}")
        logger.info(f"DB pool size       : {perf.database_pool_size}")
        logger.info("================================")


_env_manager: Optional[EnvironmentManager] = None


def get_environment_manager() -> EnvironmentManager:
    global _env_manager
    if _env_manager is None:
        _env_manager = EnvironmentManager()
    return _env_manager


def init_environment() -> bool:
    """Initialise configuration, validate, and prepare directories."""
    manager = get_environment_manager()
    logger.info("Initialising environment configuration...")

    if not manager.validate_configuration():
        logger.error("Environment configuration validation failed")
        return False

    manager.config.ensure_directories()
    manager.log_configuration_summary()
    logger.info("Environment configuration ready")
    return True


def get_secure_config() -> Dict[str, Any]:
    manager = get_environment_manager()
    return {
        "database": manager.get_database_config(),
        "flask": manager.get_flask_config(),
        "performance": manager.get_performance_config(),
        "logging": manager.get_logging_config(),
        "security": manager.get_security_config(),
        "external_apis": manager.get_external_apis_config(),
    }
