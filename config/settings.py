#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Global settings facade built on top of :mod:`core.config` to retain backwards
compatibility with existing modules while centralising configuration loading.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.config import AppConfig, DatabaseConfig, PerformanceConfig
from app_environment import get_environment_manager


@dataclass
class CrawlerSettings:
    """Crawler-specific settings."""
    max_workers: int = 10
    request_timeout: int = 15  # [修复] 30s→15s: .js文件正常5秒内返回，30秒太久导致失败联赛拖垮整个扫描
    retry_times: int = 1  # [修复] 3→1: urllib3层重试, @retry装饰器会再重试, 叠加太多
    min_delay: float = 0.5
    max_delay: float = 2.0
    batch_size: int = 50
    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    )


@dataclass
class LoggingSettings:
    """Logging configuration."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir: str = "logs"
    max_file_size: int = 10 * 1024 * 1024  # 10MB
    backup_count: int = 5


@dataclass
class DatabaseSettings:
    """Database configuration."""
    type: str = "mysql"  # mysql or sqlite
    mysql_host: str = "localhost"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = ""
    mysql_database: str = "oddsmind"
    mysql_charset: str = "utf8mb4"
    sqlite_path: str = "data/oddsmind.db"
    pool_size: int = 20
    pool_recycle: int = 3600
    pool_pre_ping: bool = True

    @classmethod
    def from_config(cls, db_config: DatabaseConfig, perf_config: PerformanceConfig) -> "DatabaseSettings":
        return cls(
            mysql_host=db_config.host,
            mysql_port=db_config.port,
            mysql_user=db_config.user,
            mysql_password=db_config.password,
            mysql_database=db_config.name,
            mysql_charset=db_config.charset,
            pool_size=perf_config.database_pool_size,
        )


@dataclass
class ScrapingSettings:
    """Scraping behaviour settings."""
    enable_checkpoints: bool = True
    checkpoint_interval: int = 10  # Save checkpoint every N items
    enable_incremental_updates: bool = True
    skip_existing: bool = True

    # Data filtering
    filter_companies: bool = False
    target_companies: Optional[List[str]] = None

    # Performance
    enable_compression: bool = True
    enable_caching: bool = True
    cache_ttl: int = 3600  # seconds


@dataclass
class TimezoneSettings:
    """Timezone configuration settings."""
    # 默认使用 Asia/Shanghai (UTC+8)
    timezone_name: str = "Asia/Shanghai"
    # MySQL时区偏移格式，例如: +08:00
    mysql_timezone_offset: str = "+08:00"
    # 是否使用时区感知的datetime对象
    use_timezone_aware: bool = True


class Settings:
    """Compatibility layer that wraps the modern :class:`AppConfig`."""

    def __init__(self, config_file: Optional[str] = None, app_config: Optional[AppConfig] = None):
        manager = get_environment_manager()
        self.app_config = app_config or manager.config

        self.project_root = Path(__file__).parent.parent
        self._init_directories()

        self.crawler = CrawlerSettings()
        self.logging = LoggingSettings(
            level=self.app_config.logging.level,
            format=self.app_config.logging.format,
            log_dir=str(self.app_config.logging.log_dir),
            max_file_size=self.app_config.logging.max_file_size,
            backup_count=self.app_config.logging.backup_count,
        )
        self.database = DatabaseSettings.from_config(
            self.app_config.database,
            self.app_config.performance,
        )
        self.scraping = ScrapingSettings()
        self.timezone = TimezoneSettings(
            timezone_name=self.app_config.timezone.timezone_name,
            mysql_timezone_offset=self.app_config.timezone.mysql_timezone_offset,
            use_timezone_aware=self.app_config.timezone.use_timezone_aware,
        )

        if config_file:
            self.load_from_file(config_file)

        self._load_from_env()

    # ------------------------------------------------------------------
    def _init_directories(self) -> None:
        """Create necessary directories."""
        directories = [
            self.project_root / "data",
            self.project_root / "logs",
            self.project_root / "data" / "checkpoints",
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def _load_from_env(self) -> None:
        """Legacy environment overrides for backwards compatibility."""
        # Database overrides
        if os.getenv("MYSQL_HOST"):
            self.database.mysql_host = os.getenv("MYSQL_HOST")
        if os.getenv("MYSQL_PORT"):
            self.database.mysql_port = int(os.getenv("MYSQL_PORT"))
        if os.getenv("MYSQL_USER"):
            self.database.mysql_user = os.getenv("MYSQL_USER")
        if os.getenv("MYSQL_PASSWORD"):
            self.database.mysql_password = os.getenv("MYSQL_PASSWORD")
        if os.getenv("MYSQL_DATABASE"):
            self.database.mysql_database = os.getenv("MYSQL_DATABASE")

        # Crawler settings
        if os.getenv("MAX_WORKERS"):
            self.crawler.max_workers = int(os.getenv("MAX_WORKERS"))
        if os.getenv("REQUEST_TIMEOUT"):
            self.crawler.request_timeout = int(os.getenv("REQUEST_TIMEOUT"))

        # Timezone settings
        if os.getenv("TIMEZONE"):
            self.timezone.timezone_name = os.getenv("TIMEZONE")
        if os.getenv("MYSQL_TIMEZONE_OFFSET"):
            self.timezone.mysql_timezone_offset = os.getenv("MYSQL_TIMEZONE_OFFSET")

    def load_from_file(self, config_file: str) -> None:
        """Load settings from configuration file (reserved for future use)."""
        # FIXME: implement YAML/JSON parsing if required
        pass

    def get_data_dir(self) -> Path:
        """Get data directory path."""
        return self.project_root / "data"

    def get_log_dir(self) -> Path:
        """Get logs directory path."""
        return self.project_root / "logs"

    def get_checkpoint_dir(self) -> Path:
        """Get checkpoints directory path."""
        return self.get_data_dir() / "checkpoints"

    def get_mysql_dsn(self) -> str:
        """Get MySQL connection DSN."""
        return (
            f"mysql+pymysql://{self.database.mysql_user}:"
            f"{self.database.mysql_password}@{self.database.mysql_host}:"
            f"{self.database.mysql_port}/{self.database.mysql_database}"  # type: ignore[attr-defined]
            f"?charset={self.database.mysql_charset}"
        )

    def get_sqlite_path(self) -> Path:
        """Get SQLite database path."""
        return self.project_root / self.database.sqlite_path

    def is_mysql_enabled(self) -> bool:
        """Check if MySQL is configured and enabled."""
        return (
            self.database.type == "mysql"
            and self.database.mysql_password != "password"
        )

    def validate(self) -> List[str]:
        """Validate configuration settings."""
        errors = []
        if not self.database.mysql_host:
            errors.append("MYSQL_HOST is required")
        if self.database.mysql_port <= 0 or self.database.mysql_port > 65535:
            errors.append("MYSQL_PORT must be between 1 and 65535")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        """Convert settings into a plain dict for legacy code paths."""
        return {
            'crawler': asdict(self.crawler),
            'logging': asdict(self.logging),
            'database': {
                'mysql_host': self.database.mysql_host,
                'mysql_port': self.database.mysql_port,
                'mysql_user': self.database.mysql_user,
                'mysql_password': self.database.mysql_password,
                'mysql_database': self.database.mysql_database,
                'mysql_charset': self.database.mysql_charset,
                'pool_size': self.database.pool_size,
            },
            'scraping': asdict(self.scraping),
            'timezone': asdict(self.timezone),
        }


# Maintain backwards-compatible singleton
settings = Settings()
