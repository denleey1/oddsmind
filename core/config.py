"""Core configuration models and loaders for the OddsMind application."""
from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse boolean-like environment variables."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class DatabasePoolConfig:
    """Connection-pool tuning parameters."""
    min_cached: int = 2
    max_cached: int = 5
    max_connections: int = 10
    blocking: bool = True


@dataclass
class DatabaseConfig:
    """Database connectivity configuration."""
    host: str = "localhost"
    port: int = 3306
    user: str = "root"
    password: str = ""
    name: str = "oddsmind"
    charset: str = "utf8mb4"
    pool: DatabasePoolConfig = field(default_factory=DatabasePoolConfig)

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        pool = DatabasePoolConfig(
            min_cached=int(os.getenv("DB_POOL_MIN_CACHED", os.getenv("DATABASE_POOL_MIN", "2"))),
            max_cached=int(os.getenv("DB_POOL_MAX_CACHED", os.getenv("DATABASE_POOL_MAX", "5"))),
            max_connections=int(os.getenv("DATABASE_POOL_SIZE", os.getenv("DB_POOL_MAX_CONNECTIONS", "10"))),
            blocking=_env_flag("DATABASE_POOL_BLOCKING", True),
        )
        return cls(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            name=os.getenv("MYSQL_DATABASE", "oddsmind"),
            charset=os.getenv("MYSQL_CHARSET", "utf8mb4"),
            pool=pool,
        )

    def as_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["database"] = data.pop("name")
        data["pool"] = asdict(self.pool)
        return data


@dataclass
class SecurityConfig:
    """Security-related configuration (sessions, payload limits)."""
    secret_key: str
    session_timeout: int = 3600
    max_content_length: int = 16 * 1024 * 1024
    force_https: bool = False
    auto_generated_secret: bool = False

    @classmethod
    def from_env(cls, *, is_production: bool) -> "SecurityConfig":
        secret = os.getenv("SECRET_KEY") or os.getenv("SESSION_SECRET_KEY")
        generated = False
        if not secret:
            # Fall back to deterministic development key to avoid downtime, but mark it.
            secret = "change-me-please"
            generated = True
        session_timeout = int(os.getenv("SESSION_TIMEOUT", "3600"))
        max_len = int(os.getenv("MAX_CONTENT_LENGTH", str(16 * 1024 * 1024)))
        require_https = _env_flag("SESSION_COOKIE_SECURE", is_production)
        return cls(
            secret_key=secret,
            session_timeout=session_timeout,
            max_content_length=max_len,
            force_https=require_https,
            auto_generated_secret=generated,
        )


@dataclass
class ApplicationConfig:
    """Process-level application configuration."""
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8889
    debug: bool = False

    @classmethod
    def from_env(cls) -> "ApplicationConfig":
        environment = os.getenv("ENVIRONMENT") or os.getenv("APP_ENV") or "development"
        debug = _env_flag("DEBUG", environment.lower() == "development")
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", os.getenv("APP_PORT", "8889")))
        return cls(environment=environment, host=host, port=port, debug=debug)

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"


@dataclass
class LoggingConfig:
    """Logging destinations and rotation limits."""
    level: str = "INFO"
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    log_dir: Path = Path("logs")
    app_log_name: str = "oddsmind.log"
    error_log_name: str = "errors.log"
    performance_log_name: str = "performance.log"
    max_file_size: int = 10 * 1024 * 1024
    backup_count: int = 5

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        level = os.getenv("LOG_LEVEL", "INFO")
        log_dir = Path(os.getenv("LOG_DIR", "logs"))
        max_file_size = int(os.getenv("LOG_MAX_FILE_SIZE", str(10 * 1024 * 1024)))
        backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
        return cls(
            level=level,
            log_dir=log_dir,
            max_file_size=max_file_size,
            backup_count=backup_count,
        )

    def as_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data["log_dir"] = str(self.log_dir)
        return data


@dataclass
class PerformanceConfig:
    """Concurrency and resource tuning knobs."""
    executor_max_workers: int = 20
    scraper_executor_max_workers: int = 10
    database_pool_size: int = 20
    request_timeout: int = 30

    @classmethod
    def from_env(cls) -> "PerformanceConfig":
        return cls(
            executor_max_workers=int(os.getenv("EXECUTOR_MAX_WORKERS", "20")),
            scraper_executor_max_workers=int(os.getenv("SCRAPER_EXECUTOR_MAX_WORKERS", "10")),
            database_pool_size=int(os.getenv("DATABASE_POOL_SIZE", "20")),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30")),
        )


@dataclass
class ExternalAPIConfig:
    """Configuration for third-party API integrations."""
    titan007_base_url: str = "https://live.titan007.com"
    request_delay: float = 0.5
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "ExternalAPIConfig":
        return cls(
            titan007_base_url=os.getenv("TITAN007_BASE_URL", "https://live.titan007.com"),
            request_delay=float(os.getenv("API_REQUEST_DELAY", "0.5")),
            max_retries=int(os.getenv("API_MAX_RETRIES", "3")),
        )

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class TimezoneConfig:
    """Timezone configuration for the application."""
    # 默认使用 Asia/Shanghai (UTC+8)
    timezone_name: str = "Asia/Shanghai"
    # MySQL时区偏移格式，例如: +08:00
    mysql_timezone_offset: str = "+08:00"
    # 是否使用时区感知的datetime对象
    use_timezone_aware: bool = True

    @classmethod
    def from_env(cls) -> "TimezoneConfig":
        """从环境变量加载时区配置，默认使用Asia/Shanghai (UTC+8)"""
        timezone_name = os.getenv("TIMEZONE", "Asia/Shanghai")
        mysql_offset = os.getenv("MYSQL_TIMEZONE_OFFSET", "+08:00")
        use_aware = _env_flag("USE_TIMEZONE_AWARE", True)
        return cls(
            timezone_name=timezone_name,
            mysql_timezone_offset=mysql_offset,
            use_timezone_aware=use_aware,
        )

    def as_dict(self) -> Dict[str, object]:
        return asdict(self)


@dataclass
class AppConfig:
    """Aggregated runtime configuration."""
    application: ApplicationConfig = field(default_factory=ApplicationConfig)
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    external_apis: ExternalAPIConfig = field(default_factory=ExternalAPIConfig)
    timezone: TimezoneConfig = field(default_factory=TimezoneConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        application = ApplicationConfig.from_env()
        database = DatabaseConfig.from_env()
        logging_cfg = LoggingConfig.from_env()
        performance = PerformanceConfig.from_env()
        external = ExternalAPIConfig.from_env()
        security = SecurityConfig.from_env(is_production=application.is_production)
        timezone = TimezoneConfig.from_env()
        return cls(
            application=application,
            database=database,
            security=security,
            logging=logging_cfg,
            performance=performance,
            external_apis=external,
            timezone=timezone,
        )

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not self.security.secret_key or len(self.security.secret_key) < 16:
            errors.append("SECRET_KEY must be at least 16 characters long")
        if self.database.port <= 0 or self.database.port > 65535:
            errors.append("MYSQL_PORT must be between 1 and 65535")
        if self.application.port <= 0 or self.application.port > 65535:
            errors.append("Application port must be between 1 and 65535")
        return errors

    def to_flask_config(self) -> Dict[str, object]:
        cfg = {
            "SECRET_KEY": self.security.secret_key,
            "DEBUG": self.application.debug,
            "TESTING": False,
            "PERMANENT_SESSION_LIFETIME": self.security.session_timeout,
            "MAX_CONTENT_LENGTH": self.security.max_content_length,
            "SESSION_COOKIE_SECURE": self.security.force_https,
            "SESSION_COOKIE_HTTPONLY": True,
            "SESSION_COOKIE_SAMESITE": "None" if self.security.force_https else "Lax",
        }

        if self.security.force_https:
            cfg["PREFERRED_URL_SCHEME"] = "https"

        return cfg

    def ensure_directories(self) -> None:
        """Create filesystem directories required by the application."""
        log_dir = self.logging.log_dir
        log_dir.mkdir(parents=True, exist_ok=True)

        data_dir = Path("data")
        checkpoints_dir = data_dir / "checkpoints"
        for path in (data_dir, checkpoints_dir):
            path.mkdir(parents=True, exist_ok=True)

    def as_dict(self) -> Dict[str, Dict[str, object]]:
        """Return a serialisable snapshot of the complete configuration."""
        return {
            "application": asdict(self.application),
            "database": self.database.as_dict(),
            "security": asdict(self.security),
            "logging": self.logging.as_dict(),
            "performance": asdict(self.performance),
            "external_apis": self.external_apis.as_dict(),
            "timezone": self.timezone.as_dict(),
        }
