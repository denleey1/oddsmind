#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
联赛状态实时监控系统
定期爬取联赛数据，实时更新比赛状态，为赔率监控提供准确的状态信息
这是解决监控系统根本问题的核心服务
"""

import threading
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.runtime import AppRuntime
from database.connection import DatabaseConnection, get_connection as get_database_connection
from scrapers.league_scraper import LeagueScraper
from .league_status_monitor_scan_ops import (
    build_league_id_map_impl,
    get_leagues_to_monitor_impl,
    init_status_cache_from_db_impl,
    update_league_status_impl,
    update_single_league_impl,
)
from .league_status_monitor_state_ops import (
    get_monitoring_stats_impl,
    get_status_distribution_impl,
    monitor_loop_impl,
    notify_odds_monitor_impl,
    update_match_status_in_db_impl,
)


class LeagueStatusMonitor:
    """
    联赛状态监控器

    核心功能：
    1. 实时监控配置联赛中所有比赛的状态变化
    2. 检测 scheduled → live → finished 的状态转换
    3. 为赔率监控系统提供准确的状态信息
    4. 解决监控系统的根本数据源问题
    """

    def __init__(
        self,
        update_interval: int = 300,
        status_change_callback=None,
        database: Optional[DatabaseConnection] = None,
        runtime: Optional[AppRuntime] = None,
        scraper: Optional[LeagueScraper] = None,
    ):
        self.update_interval = update_interval
        self.logger = get_logger(self.__class__.__name__)
        self.scraper = scraper or LeagueScraper()
        self.db = database or (runtime.db if runtime else get_database_connection())
        self.status_change_callback = status_change_callback

        self.is_running = False
        self._thread = None
        self._lock = threading.Lock()
        self._wake_event = threading.Event()

        self._league_id_to_code_map = self._build_league_id_map()

        self._status_cache: Dict[int, str] = {}
        self._last_update = None

        self._init_status_cache_from_db()

        self.stats = {
            "total_updates": 0,
            "status_changes": 0,
            "leagues_monitored": 0,
            "matches_tracked": 0,
            "errors": 0,
        }

    def start(self):
        """启动联赛状态监控"""
        if self.is_running:
            self.logger.warning("联赛状态监控已在运行")
            return

        self.is_running = True
        self._wake_event.clear()
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.logger.info("联赛状态监控已启动")

    def stop(self):
        """停止联赛状态监控"""
        self.is_running = False
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            join_timeout = max(5, min(int(self.update_interval or 0) + 10, 120))
            self._thread.join(timeout=join_timeout)
            if self._thread.is_alive():
                self.logger.warning(
                    "联赛状态监控线程在 %ss 内未停止，将继续执行关闭流程",
                    join_timeout,
                )
        self.logger.info("联赛状态监控已停止")

    def get_match_status(self, match_id: int) -> Optional[str]:
        """获取比赛的实时状态"""
        with self._lock:
            return self._status_cache.get(match_id)

    def get_status_distribution(self) -> Dict[str, int]:
        """获取当前监控比赛的状态分布"""
        return get_status_distribution_impl(self)

    def get_monitoring_stats(self) -> Dict[str, Any]:
        """获取监控统计信息"""
        return get_monitoring_stats_impl(self)

    def _build_league_id_map(self) -> Dict[int, str]:
        """从 leagues_config.py 构建 league_id 到 league_code 的映射"""
        return build_league_id_map_impl(self)

    def _init_status_cache_from_db(self):
        """从数据库加载当前比赛状态到缓存，确保缓存和数据库同步"""
        init_status_cache_from_db_impl(self)

    def _monitor_loop(self):
        """主监控循环"""
        monitor_loop_impl(self)

    def _update_league_status(self) -> int:
        """更新联赛状态，返回变化数量"""
        return update_league_status_impl(self)

    def _get_leagues_to_monitor(self) -> List[int]:
        """获取需要监控的联赛ID列表"""
        return get_leagues_to_monitor_impl(self)

    def _update_single_league(self, league_id: int) -> int:
        """更新单个联赛的比赛状态"""
        return update_single_league_impl(self, league_id)

    def _update_match_status_in_db(self, match_id: int, new_status: str, match_data: Dict):
        """更新数据库中的比赛状态"""
        update_match_status_in_db_impl(self, match_id, new_status, match_data)

    def _notify_odds_monitor(self, changes_count: int):
        """通知赔率监控系统状态发生了变化"""
        notify_odds_monitor_impl(self, changes_count)


def get_league_status_monitor(
    update_interval: int = 300,
    status_change_callback=None,
    database: Optional[DatabaseConnection] = None,
    runtime: Optional[AppRuntime] = None,
) -> LeagueStatusMonitor:
    """创建联赛状态监控实例。"""
    if runtime and database is None:
        database = runtime.db
    return LeagueStatusMonitor(
        update_interval,
        status_change_callback,
        database=database,
        runtime=runtime,
    )


def start_league_status_monitoring(
    update_interval: int = 300,
    status_change_callback=None,
    database: Optional[DatabaseConnection] = None,
    runtime: Optional[AppRuntime] = None,
):
    """启动全局联赛状态监控"""
    monitor = get_league_status_monitor(update_interval, status_change_callback, database=database, runtime=runtime)
    monitor.start()
    return monitor


if __name__ == "__main__":
    import logging
    import time

    logging.basicConfig(level=logging.INFO)

    monitor = LeagueStatusMonitor(update_interval=60)
    monitor.start()

    try:
        while True:
            time.sleep(30)
            stats = monitor.get_monitoring_stats()
            print(f"监控统计: {stats}")
    except KeyboardInterrupt:
        print("停止监控...")
        monitor.stop()
