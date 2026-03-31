#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
比赛状态更新服务
定期爬取联赛数据，更新所有比赛的状态和基础信息。
解决监控系统无法跟踪已完成比赛的问题。
"""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any, Dict, List, Optional
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from core.logger import get_logger
from utils.timezone_utils import now
from core.runtime import AppRuntime
from database.connection import DatabaseConnection, get_connection as get_database_connection
from scrapers.league_scraper import LeagueScraper
from config.monitoring_config import MONITORED_LEAGUES, MONITOR_ALL_LEAGUES
from config.leagues_config import LEAGUE_ID_TO_CODE, LEAGUES_CONFIG, get_divisional_league_codes
from database.manager import DatabaseManager
from services.match_status_match_ops import (
    ensure_team_record as _ensure_team_record_impl,
    get_or_create_team_id as _get_or_create_team_id_impl,
    update_single_match as _update_single_match_impl,
)


class MatchStatusUpdater:
    """比赛状态更新器"""

    def __init__(
        self,
        database: Optional[DatabaseConnection] = None,
        runtime: Optional[AppRuntime] = None,
        db_manager: Optional[DatabaseManager] = None,
        scraper: Optional[LeagueScraper] = None,
    ) -> None:
        self.logger = get_logger(self.__class__.__name__)
        self._runtime = runtime
        self.db_manager = db_manager or (runtime.db_manager if runtime else DatabaseManager())
        self.scraper = scraper or LeagueScraper()
        self.db = database or (runtime.db if runtime else get_database_connection())

        self.stats: Dict[str, Any] = {
            "leagues_processed": 0,
            "matches_updated": 0,
            "status_changes": 0,
            "new_matches": 0,
            "errors": 0,
            "last_update": None,
            "status_changes_detail": [],
            "new_match_ids": [],
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_all_match_status(self) -> Dict[str, Any]:
        """更新所有配置联赛的比赛状态。"""
        self.logger.info("开始更新比赛状态...")
        start_time = time.time()

        self.stats.update(
            {
                "leagues_processed": 0,
                "matches_updated": 0,
                "status_changes": 0,
                "new_matches": 0,
                "errors": 0,
                "status_changes_detail": [],
                "new_match_ids": [],
            }
        )

        try:
            leagues_to_update = self._get_leagues_to_update()
            if not leagues_to_update:
                self.logger.warning("没有找到需要更新的联赛")
                return self.stats

            self.logger.info("准备更新 %s 个联赛的比赛状态", len(leagues_to_update))

            # [修复] 并发数从3→6，超时计算更合理
            executor = ThreadPoolExecutor(max_workers=6, thread_name_prefix="match-status")
            future_to_league = {
                executor.submit(self._update_league_matches, league_code): league_code
                for league_code in leagues_to_update
            }
            pending = set(future_to_league.keys())
            # 每联赛预估15秒(含超时重试)，但并发6线程，所以除以6再加缓冲
            overall_timeout = min(600.0, max(120.0, len(leagues_to_update) * 15.0 / 6 + 60))
            deadline = time.monotonic() + overall_timeout

            try:
                while pending:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break

                    done, pending = wait(
                        pending,
                        timeout=min(5.0, remaining),
                        return_when=FIRST_COMPLETED,
                    )
                    for future in done:
                        league_code = future_to_league[future]
                        try:
                            result = future.result()
                            self._merge_league_stats(result)
                            self.stats["leagues_processed"] += 1
                            self.logger.info("联赛 %s 更新完成: %s", league_code, result)
                        except Exception as exc:  # pragma: no cover - defensive
                            self.logger.error("联赛 %s 更新失败: %s", league_code, exc)
                            self.stats["errors"] += 1

                if pending:
                    for future in pending:
                        future.cancel()
                    self.stats["errors"] += len(pending)
                    self.logger.warning(
                        "比赛状态更新超时，已完成 %s/%s 个联赛，取消 %s 个未完成任务",
                        self.stats["leagues_processed"],
                        len(future_to_league),
                        len(pending),
                    )
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

            elapsed = time.time() - start_time
            self.stats["last_update"] = now().isoformat()
            self.logger.info(
                "比赛状态更新完成 - 耗时: %.2fs, 联赛: %s, 比赛更新: %s, 状态变化: %s, 新比赛: %s, 错误: %s",
                elapsed,
                self.stats["leagues_processed"],
                self.stats["matches_updated"],
                self.stats["status_changes"],
                self.stats["new_matches"],
                self.stats["errors"],
            )
            return self.stats

        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("更新比赛状态过程中发生错误: %s", exc, exc_info=True)
            self.stats["errors"] += 1
            return self.stats

    # ------------------------------------------------------------------
    # League selection helpers
    # ------------------------------------------------------------------
    def _get_leagues_to_update(self) -> List[str]:
        if MONITOR_ALL_LEAGUES:
            # 如果配置为监控所有联赛，则返回 LEAGUES_CONFIG 中的所有键
            return list(LEAGUES_CONFIG.keys())
        return self._get_monitored_league_codes()

    def _get_active_league_codes(self) -> List[str]:
        try:
            recent_leagues = self.db.execute_query(
                """
                SELECT DISTINCT l.league_id, l.name_en
                FROM leagues l
                JOIN matches m ON l.league_id = m.league_id
                WHERE m.match_time >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                  AND m.match_time <= DATE_ADD(NOW(), INTERVAL 30 DAY)
                ORDER BY l.league_id
                """,
                fetch="all",
            )
            codes: List[str] = []
            for league in recent_leagues or []:
                league_id = league["league_id"]
                code = LEAGUE_ID_TO_CODE.get(league_id)
                codes.append(code or f"L{league_id}")
            return codes
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("获取活跃联赛失败: %s", exc)
            return []

    def _get_monitored_league_codes(self) -> List[str]:
        if not MONITORED_LEAGUES:
            return []
        try:
            codes: List[str] = []
            for league_id in MONITORED_LEAGUES:
                # 分区联赛: 一个 league_id 对应多个 config code (如 JPN_J1_EAST + JPN_J1_WEST)
                div_codes = get_divisional_league_codes(league_id)
                if div_codes:
                    codes.extend(div_codes.values())
                else:
                    codes.append(LEAGUE_ID_TO_CODE.get(league_id) or f"L{league_id}")
            return codes
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("获取监控联赛代码失败: %s", exc)
            return []

    # ------------------------------------------------------------------
    # League update pipeline
    # ------------------------------------------------------------------
    def _update_league_matches(self, league_code: str) -> Dict[str, Any]:
        league_stats: Dict[str, Any] = {
            "matches_updated": 0,
            "status_changes": 0,
            "new_matches": 0,
            "errors": 0,
            "status_changes_detail": [],
            "new_match_ids": [],
        }

        try:
            league_id = self._resolve_league_id(league_code)
            if not league_id:
                self.logger.error("无效的联赛代码: %s", league_code)
                league_stats["errors"] += 1
                return league_stats

            self.logger.info("开始更新联赛 %s 的比赛状态...", league_id)

            scraping_result = self.scraper.scrape(league_codes=[league_code], force_refresh=True)
            if not scraping_result.success:
                self.logger.error("爬取联赛 %s 失败: %s", league_code, scraping_result.error)
                league_stats["errors"] += 1
                return league_stats

            payload, error = self._extract_league_payload(scraping_result, league_code)
            if error:
                self.logger.error("处理联赛 %s 数据失败: %s", league_code, error)
                league_stats["errors"] += 1
                return league_stats
            if not payload or "matches" not in payload:
                self.logger.warning("联赛 %s 未返回比赛数据", league_code)
                return league_stats

            matches_data = payload.get("matches", {}) or {}

            # 注入分区标识和赛季（用于分区赛制联赛, 如日职J1东/西区）
            league_info = LEAGUES_CONFIG.get(league_code)
            division = league_info.division if league_info and league_info.division else None
            season = league_info.season if league_info else None
            if matches_data:
                for round_key, round_matches in matches_data.items():
                    if isinstance(round_matches, list):
                        for match_data_item in round_matches:
                            if isinstance(match_data_item, dict):
                                if division:
                                    match_data_item['division'] = division
                                if season:
                                    match_data_item['season'] = season

            # [修正] 预先存储球队数据，防止比赛表外键约束失败 (FK away_team_id / home_team_id)
            if "teams" in payload and payload["teams"]:
                self.logger.info("联赛 %s: 预先同步 %d 个球队数据...", league_id, len(payload["teams"]))
                try:
                    # 使用 DatabaseManager 存储球队
                    self.db_manager.store_league_data({"teams": payload["teams"], "league": payload.get("league")})
                except Exception as team_exc:
                    self.logger.error("联赛 %s 球队同步失败: %s", league_id, team_exc)
            
            # [修正] 同步存储standings积分榜数据（之前被遗漏！）
            if "standings" in payload and payload["standings"]:
                standings_data = payload["standings"]
                standings_count = sum(len(s) for s in standings_data.values()) if isinstance(standings_data, dict) else len(standings_data)
                self.logger.info("联赛 %s: 同步 %d 条积分榜数据...", league_id, standings_count)
                try:
                    self.db_manager.store_league_data({
                        "standings": standings_data,
                        "league": payload.get("league")
                    })
                except Exception as standings_exc:
                    self.logger.error("联赛 %s 积分榜同步失败: %s", league_id, standings_exc)
            
            processed_stats = self._process_matches_data(league_id, matches_data)
            self._merge_league_stats(processed_stats)
            return processed_stats

        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("更新联赛 %s 比赛状态失败: %s", league_code, exc, exc_info=True)
            league_stats["errors"] += 1
            return league_stats

    def _resolve_league_id(self, league_code: str) -> Optional[int]:
        if league_code.startswith("L"):
            try:
                return int(league_code[1:])
            except ValueError:
                return None
        info = LEAGUES_CONFIG.get(league_code)
        if not info:
            return None
        import re

        match = re.match(r"s(\d+)", info.league_filename)
        return int(match.group(1)) if match else None

    def _extract_league_payload(
        self, scraping_result: Any, league_code: str
    ) -> tuple[Optional[Dict[str, Any]], Optional[str]]:
        base_data = getattr(scraping_result, "data", None)
        if isinstance(base_data, dict):
            league_result = base_data.get(league_code)
        else:
            league_result = base_data

        if league_result is None:
            return None, "league not present in scraping result"

        # Handle ScrapingResult wrappers
        success_attr = getattr(league_result, "success", None)
        if success_attr is not None:
            if not success_attr:
                return None, getattr(league_result, "error", "unknown scrape error")
            league_result = getattr(league_result, "data", None)

        if league_result is None:
            return None, "empty league payload"

        # Some implementations nest yet another data attribute
        if hasattr(league_result, "data"):
            league_result = league_result.data

        if not isinstance(league_result, dict):
            return None, f"unexpected payload type: {type(league_result).__name__}"

        return league_result, None

    # ------------------------------------------------------------------
    # Match-level processing helpers
    # ------------------------------------------------------------------
    def _process_matches_data(self, league_id: int, matches_data: Dict[str, Any]) -> Dict[str, Any]:
        stats: Dict[str, Any] = {
            "matches_updated": 0,
            "status_changes": 0,
            "new_matches": 0,
            "errors": 0,
            "status_changes_detail": [],
            "new_match_ids": [],
        }

        try:
            for round_matches in matches_data.values():
                if not isinstance(round_matches, list):
                    continue
                for match_data in round_matches:
                    try:
                        result = self._update_single_match(league_id, match_data)
                        if result["updated"]:
                            stats["matches_updated"] += 1
                        if result["status_changed"]:
                            stats["status_changes"] += 1
                            stats["status_changes_detail"].append(
                                {
                                    "match_id": match_data.get("match_id"),
                                    "old_status": result.get("old_status"),
                                    "new_status": result.get("new_status"),
                                }
                            )
                        if result["is_new"]:
                            stats["new_matches"] += 1
                            stats["new_match_ids"].append(match_data.get("match_id"))
                    except Exception as exc:  # pragma: no cover - defensive
                        self.logger.error("更新比赛失败 %s: %s", match_data.get("match_id", "Unknown"), exc)
                        stats["errors"] += 1
            return stats
        except Exception as exc:  # pragma: no cover - defensive
            self.logger.error("处理联赛 %s 比赛数据失败: %s", league_id, exc)
            stats["errors"] += 1
            return stats

    def _get_or_create_team_id(self, team_name: str) -> Optional[int]:
        """根据球队名称获取或创建team_id"""
        return _get_or_create_team_id_impl(self, team_name)

    def _ensure_team_record(self, team_id: Optional[int], team_name: str) -> Optional[int]:
        """
        确保给定的 team_id 在 teams 表中存在；若不存在则创建占位记录，避免 matches 插入时触发外键约束。
        - 优先使用传入的 team_id；如果没有，则按名称创建/获取。
        """
        return _ensure_team_record_impl(self, team_id, team_name)

    def _update_single_match(self, league_id: int, match_data: Dict[str, Any]) -> Dict[str, Any]:
        return _update_single_match_impl(self, league_id, match_data)

    # ------------------------------------------------------------------
    # Misc helpers
    # ------------------------------------------------------------------
    def _is_outdated(self, updated_at: Any, hours_threshold: int = 2) -> bool:
        if not updated_at:
            return True
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        return now() - updated_at > timedelta(hours=hours_threshold)

    def _merge_league_stats(self, league_stats: Dict[str, Any]) -> None:
        for key in ("matches_updated", "status_changes", "new_matches", "errors"):
            self.stats[key] += league_stats.get(key, 0)
        if "status_changes_detail" in league_stats:
            self.stats["status_changes_detail"].extend(league_stats["status_changes_detail"])
        if "new_match_ids" in league_stats:
            self.stats["new_match_ids"].extend(mid for mid in league_stats["new_match_ids"] if mid)

    def get_update_status(self) -> Dict[str, Any]:
        return {
            "service_name": "MatchStatusUpdater",
            "last_stats": self.stats,
            "is_healthy": (self.stats["errors"] == 0) if self.stats["last_update"] else None,
            "configuration": {
                "monitor_all_leagues": MONITOR_ALL_LEAGUES,
                "monitored_leagues_count": len(MONITORED_LEAGUES) if not MONITOR_ALL_LEAGUES else "ALL",
            },
        }


# ----------------------------------------------------------------------
# Factory helpers
# ----------------------------------------------------------------------

def create_match_status_updater(
    runtime: Optional[AppRuntime] = None,
    **kwargs: Any,
) -> MatchStatusUpdater:
    if runtime and "database" not in kwargs:
        kwargs["database"] = runtime.db
    return MatchStatusUpdater(runtime=runtime, **kwargs)


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.INFO)
    updater = create_match_status_updater()
    result = updater.update_all_match_status()

    print("更新完成:")
    print(f"  联赛处理: {result['leagues_processed']}")
    print(f"  比赛更新: {result['matches_updated']}")
    print(f"  状态变化: {result['status_changes']}")
    print(f"  新比赛: {result['new_matches']}")
    print(f"  错误: {result['errors']}")
