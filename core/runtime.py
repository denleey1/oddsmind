#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Application runtime container that wires shared infrastructure services."""
from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, List, Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app_constants import AUTO_START_MONITORING
from app_environment import get_environment_manager
from config.settings import Settings
from core.logger import get_logger, setup_logging
from database.manager import DatabaseManager
from database.connection import get_connection as get_database_connection
from scrapers.all_companies_scraper import AllCompaniesOddsScraper


class AppRuntime:
    """Runtime container storing lazily-initialised infrastructure singletons."""

    def __init__(self) -> None:
        self.env_manager = get_environment_manager()
        self.config = self.env_manager.config
        self.settings = Settings(app_config=self.config)
        self.logger = get_logger(self.__class__.__name__)
        self.auto_start_monitoring = AUTO_START_MONITORING

        self._db_manager: Optional[DatabaseManager] = None
        self._db = None
        self._executor: Optional[ThreadPoolExecutor] = None
        self._scraper_executor: Optional[ThreadPoolExecutor] = None
        self._scraper: Optional[AllCompaniesOddsScraper] = None
        self._scheduler: Optional[BackgroundScheduler] = None

        self.monitor = None
        self.league_status_monitor = None
        self.scheduled_data_updater = None
        self._monitoring_coordinator = None
        self.monitoring_thread: Optional[threading.Thread] = None

        self._initialised = False
        self._init_lock = threading.Lock()
        self._slow_init_started = False
        self._slow_init_lock = threading.Lock()
        self._shutdown_hooks: List[Callable[[], None]] = []

    # ------------------------------------------------------------------
    # Lifecycle helpers
    # ------------------------------------------------------------------
    def configure_logging(self) -> None:
        """Initialise logging sinks based on configuration."""
        setup_logging(self.config.logging)
        logging.getLogger("apscheduler").setLevel(logging.WARNING)

    def ensure_initialised(self, initialiser) -> None:
        """Run the provided callable exactly once in a threadsafe way."""
        if self._initialised:
            return
        with self._init_lock:
            if self._initialised:
                return
            initialiser()
            self._initialised = True

    def shutdown(self) -> None:
        """Release resources when the process terminates."""
        self.logger.info("Shutting down application runtime...")
        try:
            scheduler = self._scheduler
            if scheduler and scheduler.running:
                scheduler.shutdown(wait=False)
        except Exception:
            self.logger.exception("Failed to shutdown scheduler cleanly")

        for pool, name in ((self._executor, "executor"), (self._scraper_executor, "scraper_executor")):
            try:
                pool.shutdown(wait=False)
            except Exception:
                self.logger.exception("Failed to shutdown %s", name)

        try:
            if self.monitor and hasattr(self.monitor, "stop"):
                self.monitor.stop()
            self.monitor = None
        except Exception:
            self.logger.exception("Failed to stop odds monitor")

        try:
            if self.league_status_monitor and hasattr(self.league_status_monitor, "stop"):
                self.league_status_monitor.stop()
            self.league_status_monitor = None
        except Exception:
            self.logger.exception("Failed to stop league status monitor")

        try:
            if self.scheduled_data_updater and hasattr(self.scheduled_data_updater, "stop"):
                self.scheduled_data_updater.stop()
            self.scheduled_data_updater = None
        except Exception:
            self.logger.exception("Failed to stop scheduled updater")

        # 停止批量写入队列（优雅关闭）
        try:
            if self._db_manager and hasattr(self._db_manager, 'batch_writer') and self._db_manager.batch_writer:
                self.logger.info("Stopping BatchWriter...")
                self._db_manager.batch_writer.stop(timeout=60.0)
                self.logger.info("BatchWriter stopped")
        except Exception:
            self.logger.exception("Failed to stop BatchWriter")

        for hook in self._shutdown_hooks:
            try:
                hook()
            except Exception:  # pragma: no cover - defensive guard
                self.logger.exception("Shutdown hook failed")

        self.logger.info("Runtime shutdown complete")
        self._monitoring_coordinator = None

    # ------------------------------------------------------------------
    # Lazy-loaded resources
    # ------------------------------------------------------------------
    @property
    def db_manager(self) -> DatabaseManager:
        if self._db_manager is None:
            self._db_manager = DatabaseManager()
        return self._db_manager

    @property
    def db(self):
        if self._db is None:
            self._db = get_database_connection()
        return self._db

    @property
    def executor(self) -> ThreadPoolExecutor:
        if self._executor is None:
            workers = self.config.performance.executor_max_workers
            self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="app-bg")
        return self._executor

    @property
    def scraper_executor(self) -> ThreadPoolExecutor:
        if self._scraper_executor is None:
            workers = self.config.performance.scraper_executor_max_workers
            self._scraper_executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="scraper")
        return self._scraper_executor

    @property
    def scraper(self) -> AllCompaniesOddsScraper:
        if self._scraper is None:
            self._scraper = AllCompaniesOddsScraper(executor=self.scraper_executor)
        return self._scraper

    @property
    def scheduler(self) -> BackgroundScheduler:
        if self._scheduler is None:
            self._scheduler = BackgroundScheduler()
        return self._scheduler

    @property
    def monitoring_coordinator(self):
        if self._monitoring_coordinator is None:
            from services.monitoring_coordinator import MonitoringCoordinator

            self._monitoring_coordinator = MonitoringCoordinator(self)
        return self._monitoring_coordinator

    # ------------------------------------------------------------------
    def register_shutdown_hook(self, hook: Callable[[], None]) -> None:
        self._shutdown_hooks.append(hook)

    def mark_slow_initialization_started(self) -> bool:
        """
        Mark deferred/slow initialization as started exactly once.

        Returns:
            bool: True if this call marked the initialization as started,
            False if it had already been started before.
        """
        with self._slow_init_lock:
            if self._slow_init_started:
                return False
            self._slow_init_started = True
            return True

    @property
    def slow_initialization_started(self) -> bool:
        return self._slow_init_started

    @property
    def is_initialised(self) -> bool:
        return self._initialised

    @is_initialised.setter
    def is_initialised(self, value: bool) -> None:
        # 允许外部标记初始化状态，避免 AttributeError
        self._initialised = bool(value)
