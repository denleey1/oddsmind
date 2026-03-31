#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Core odds-change monitoring module."""

from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set

from concurrent.futures import ThreadPoolExecutor

from core.logger import get_logger
from core.runtime import AppRuntime
from database.manager import DatabaseManager
from database.models import OddsChangeModel
from scrapers.all_companies_scraper import AllCompaniesOddsScraper

# Keep importing via app_database for compatibility with existing query pathways.
from app_database import execute_query


class OddsChangeMonitor:
    """Active monitor for odds changes of a set of matches."""

    def __init__(
        self,
        match_ids: List[int],
        monitor_interval: int = 15,
        initial_snapshot: Dict = None,
        executor: ThreadPoolExecutor = None,
        runtime: Optional[AppRuntime] = None,
        db_manager: Optional[DatabaseManager] = None,
        scraper: Optional[AllCompaniesOddsScraper] = None,
        query_fn=None,
    ):
        self.match_ids = list(match_ids or [])
        self.monitor_interval = monitor_interval
        self.logger = get_logger(self.__class__.__name__)
        self._runtime = runtime

        if runtime:
            self.db_manager = db_manager or runtime.db_manager
            self.executor = executor or runtime.executor
            self.scraper = scraper or runtime.scraper

            if query_fn is None:

                def _runtime_query(sql, params=None):
                    return runtime.db.execute_query(sql, params, fetch='all')

                self._query_fn = _runtime_query
            else:
                self._query_fn = query_fn
        else:
            self.db_manager = db_manager or DatabaseManager()
            self.executor = executor or ThreadPoolExecutor(max_workers=5)
            self.scraper = scraper or AllCompaniesOddsScraper(executor=self.executor)
            self._query_fn = query_fn or (lambda sql, params=None: execute_query(sql, params))

        self.is_running = False
        self._thread = None
        self._lock = threading.Lock()
        self._wake_event = threading.Event()
        self._last_loop_started_at: Optional[datetime] = None
        self._last_loop_completed_at: Optional[datetime] = None
        self._last_loop_duration_seconds: Optional[float] = None
        self._last_loop_error: Optional[str] = None

        # {match_id: {company_id: {odds fields}}}
        self._odds_snapshot: Dict[int, Dict[int, Dict[str, Any]]] = (
            initial_snapshot if initial_snapshot is not None else {}
        )

        self._matches_to_analyze: Set[int] = set()
        self._analysis_lock = threading.Lock()

    def start(self):
        """Start monitoring service."""
        if self.is_running:
            self.logger.warning("Monitor is already running")
            return

        self.is_running = True
        self._wake_event.clear()
        self.logger.info(
            "Monitor initialized with %s matches in initial snapshot",
            len(self._odds_snapshot),
        )

        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.logger.info("Odds monitor started for %s matches", len(self.match_ids))

    def stop(self):
        """Stop monitoring service."""
        self.is_running = False
        self._wake_event.set()
        if self._thread and self._thread.is_alive():
            join_timeout = max(5, min(int(self.monitor_interval or 0) + 10, 120))
            self._thread.join(timeout=join_timeout)
            if self._thread.is_alive():
                self.logger.warning(
                    "Odds monitor thread did not stop within %ss; continuing shutdown",
                    join_timeout,
                )
        self.logger.info("Odds monitor stopped")

        if self._runtime is None and hasattr(self, 'executor') and self.executor:
            try:
                self.executor.shutdown(wait=False)
            except Exception:
                self.logger.exception("Failed to shutdown local monitor executor")

    def update_monitor_interval(self, new_interval: int):
        """Update polling interval dynamically."""
        old_interval = self.monitor_interval
        self.monitor_interval = new_interval
        self.logger.info("Monitor interval changed: %s -> %s seconds", old_interval, new_interval)
        self._wake_event.set()

    def get_monitoring_status(self) -> Dict[str, Any]:
        """Get current monitor status."""
        with self._lock:
            total_matches = len(self._odds_snapshot)
            total_companies = sum(len(companies) for companies in self._odds_snapshot.values())

            match_details = {
                match_id: {
                    'company_count': len(companies),
                    'company_ids': list(companies.keys()),
                }
                for match_id, companies in self._odds_snapshot.items()
            }

            return {
                'is_running': self.is_running,
                'monitor_interval': self.monitor_interval,
                'total_matches': total_matches,
                'total_companies': total_companies,
                'match_details': match_details,
                'last_loop_started_at': self._last_loop_started_at.isoformat() if self._last_loop_started_at else None,
                'last_loop_completed_at': self._last_loop_completed_at.isoformat() if self._last_loop_completed_at else None,
                'last_loop_duration_seconds': self._last_loop_duration_seconds,
                'last_loop_error': self._last_loop_error,
            }

    def _get_match_ids_snapshot(self) -> List[int]:
        """Return a stable snapshot of monitored match ids."""
        with self._lock:
            return list(self.match_ids)

    def _monitor_loop(self):
        """Main monitor loop."""
        loop_count = 0
        while self.is_running:
            loop_start = time.time()
            try:
                self._last_loop_started_at = datetime.now()
                self._last_loop_error = None
                loop_count += 1
                self.logger.debug("Starting monitor loop #%s", loop_count)

                monitored_match_ids = self._get_match_ids_snapshot()
                if not monitored_match_ids:
                    self.logger.debug("No monitored matches in current loop")
                else:
                    status_before = self.get_monitoring_status()
                    companies_before = status_before['total_companies']

                    priority_groups = self._group_matches_by_priority()
                    if self.monitor_interval <= 180:
                        batches_to_scrape = [('high', priority_groups.get('high', []))]
                    elif self.monitor_interval <= 1800:
                        batches_to_scrape = [
                            ('high', priority_groups.get('high', [])),
                            ('medium', priority_groups.get('medium', [])),
                        ]
                    else:
                        batches_to_scrape = [
                            ('high', priority_groups.get('high', [])),
                            ('medium', priority_groups.get('medium', [])),
                            ('low', priority_groups.get('low', [])),
                        ]

                    all_odds_data: Dict[int, Any] = {}
                    total_matches_scraped = 0

                    for priority, batch_match_ids in batches_to_scrape:
                        if not batch_match_ids:
                            continue

                        self.logger.info(
                            "Scraping %s priority batch with %s matches",
                            priority,
                            len(batch_match_ids),
                        )

                        batch_start = time.time()
                        batch_odds_data = self.scraper.scrape_with_all_companies(batch_match_ids)
                        batch_elapsed = time.time() - batch_start

                        if batch_odds_data and getattr(batch_odds_data, 'success', False) and getattr(batch_odds_data, 'data', None):
                            all_odds_data.update(batch_odds_data.data)
                            total_matches_scraped += len(batch_match_ids)
                            self.logger.info(
                                "Batch %s scrape completed in %.2fs with %s matches",
                                priority,
                                batch_elapsed,
                                len(batch_odds_data.data),
                            )
                        else:
                            self.logger.warning("Batch %s scrape returned no data", priority)

                        elapsed_so_far = time.time() - loop_start
                        remaining_time = self.monitor_interval - elapsed_so_far
                        if remaining_time < 10:
                            self.logger.warning(
                                "Monitor cycle near interval budget (remaining %.2fs), skipping later batches",
                                remaining_time,
                            )
                            break

                    from core.base_scraper import ScrapingResult

                    latest_odds_data = ScrapingResult(
                        success=len(all_odds_data) > 0,
                        data=all_odds_data,
                        metadata={
                            'total_matches': total_matches_scraped,
                            'message': f"batch scrape completed: {total_matches_scraped} matches",
                        },
                    )

                    scrape_elapsed = time.time() - loop_start
                    if latest_odds_data.success:
                        self.logger.info(
                            "Scrape stage completed in %.2fs (%s matches)",
                            scrape_elapsed,
                            total_matches_scraped,
                        )
                        if scrape_elapsed > self.monitor_interval * 0.6:
                            self.logger.warning(
                                "Scrape time high: %.2fs (interval=%ss)",
                                scrape_elapsed,
                                self.monitor_interval,
                            )
                    else:
                        self.logger.error("Scrape failed or returned empty result")

                    compare_start = time.time()
                    changes_detected = self._compare_and_record_changes(latest_odds_data)
                    compare_elapsed = time.time() - compare_start

                    status_after = self.get_monitoring_status()
                    companies_after = status_after['total_companies']
                    if companies_after > companies_before:
                        self.logger.info(
                            "New monitored companies discovered: +%s",
                            companies_after - companies_before,
                        )

                    total_elapsed = time.time() - loop_start
                    if changes_detected:
                        self.logger.info(
                            "Loop #%s detected %s odds updates (total %.2fs: scrape %.2fs, compare %.2fs)",
                            loop_count,
                            changes_detected,
                            total_elapsed,
                            scrape_elapsed,
                            compare_elapsed,
                        )
                    else:
                        self.logger.debug(
                            "Loop #%s no odds updates (total %.2fs)",
                            loop_count,
                            total_elapsed,
                        )

                    if total_elapsed > self.monitor_interval:
                        self.logger.error(
                            "Monitor loop exceeded interval: %.2fs > %ss",
                            total_elapsed,
                            self.monitor_interval,
                        )

                self._cleanup_finished_matches()
                self._trigger_analysis_for_new_companies()

            except Exception as exc:
                self._last_loop_error = str(exc)
                self.logger.error("Monitor loop #%s failed: %s", loop_count, exc, exc_info=True)

            finally:
                self._last_loop_completed_at = datetime.now()
                self._last_loop_duration_seconds = time.time() - loop_start
                interval = max(int(self.monitor_interval or 0), 1)
                self._wake_event.wait(timeout=interval)
                self._wake_event.clear()

    def _group_matches_by_priority(self) -> Dict[str, List[int]]:
        """Group monitored matches by kickoff urgency."""
        from dateutil import parser

        now = datetime.now()
        high_priority: List[int] = []
        medium_priority: List[int] = []
        low_priority: List[int] = []

        match_ids = self._get_match_ids_snapshot()
        if not match_ids:
            return {'high': [], 'medium': [], 'low': []}

        placeholders = ','.join(['%s'] * len(match_ids))
        sql = f"""
        SELECT match_id, match_time, match_status
        FROM matches
        WHERE match_id IN ({placeholders})
          AND match_status IN ('scheduled', 'live')
        """

        try:
            results = self._query_fn(sql, tuple(match_ids))
            for row in results:
                match_id = row.get('match_id')
                match_time = row.get('match_time')
                match_status = row.get('match_status')
                if not match_time or match_status not in ('scheduled', 'live'):
                    continue

                if isinstance(match_time, str):
                    match_time = parser.parse(match_time)

                time_to_match = (match_time - now).total_seconds() / 60
                if time_to_match <= 40:
                    high_priority.append(match_id)
                elif time_to_match <= 120:
                    medium_priority.append(match_id)
                else:
                    low_priority.append(match_id)

        except Exception as exc:
            self.logger.error("Failed to group matches by priority: %s", exc, exc_info=True)
            return {'high': match_ids, 'medium': [], 'low': []}

        return {'high': high_priority, 'medium': medium_priority, 'low': low_priority}

    def _cleanup_finished_matches(self):
        """Remove finished matches from monitor state to avoid stale growth."""
        match_ids = self._get_match_ids_snapshot()
        if not match_ids:
            return

        try:
            placeholders = ','.join(['%s'] * len(match_ids))
            sql = f"SELECT match_id, match_status FROM matches WHERE match_id IN ({placeholders})"
            results = self._query_fn(sql, tuple(match_ids))

            finished_match_ids = {
                row['match_id'] for row in results if row.get('match_status') == 'finished'
            }
            if not finished_match_ids:
                return

            with self._lock:
                for match_id in finished_match_ids:
                    self._odds_snapshot.pop(match_id, None)
                original_count = len(self.match_ids)
                self.match_ids = [mid for mid in self.match_ids if mid not in finished_match_ids]
                new_count = len(self.match_ids)

            with self._analysis_lock:
                self._matches_to_analyze.difference_update(finished_match_ids)

            self.logger.info(
                "Removed %s finished matches from monitor; remaining=%s",
                original_count - new_count,
                new_count,
            )

        except Exception as exc:
            self.logger.error("Failed to cleanup finished matches: %s", exc, exc_info=True)

    def _compare_and_record_changes(self, latest_odds_result: Any) -> int:
        """Compare latest odds with snapshot and persist changed records."""
        if not latest_odds_result.success or not latest_odds_result.data:
            return 0

        changes_to_upsert: List[OddsChangeModel] = []
        now = datetime.now()

        for match_id, new_data in latest_odds_result.data.items():
            if hasattr(new_data, 'data'):
                if not new_data.success:
                    continue
                odds_data = new_data.data
            else:
                odds_data = new_data

            if not isinstance(odds_data, dict) or 'odds' not in odds_data:
                continue

            with self._lock:
                if match_id not in self._odds_snapshot:
                    self._odds_snapshot[match_id] = {}
                current_match_snapshot = self._odds_snapshot[match_id]

            for new_record in odds_data['odds']:
                company_id = new_record.get('company_id')
                if not company_id:
                    continue

                previous_record = current_match_snapshot.get(company_id)
                should_update = False
                is_new_company = False
                is_missing_in_db = False

                if not previous_record:
                    if not self._has_valid_odds(new_record):
                        continue
                    should_update = True
                    is_new_company = True
                    with self._analysis_lock:
                        self._matches_to_analyze.add(match_id)
                elif self._has_odds_changed(previous_record, new_record):
                    should_update = True
                    with self._analysis_lock:
                        self._matches_to_analyze.add(match_id)
                else:
                    db_written = previous_record.get('_db_written')
                    if db_written is None or db_written is False:
                        should_update = True
                        is_missing_in_db = True
                        if previous_record.get('initial_home') is not None and previous_record.get('initial_away') is not None:
                            with self._analysis_lock:
                                self._matches_to_analyze.add(match_id)
                    else:
                        last_updated = previous_record.get('_last_updated')
                        if isinstance(last_updated, str):
                            from dateutil import parser

                            last_updated = parser.parse(last_updated)
                        if last_updated and (now - last_updated) > timedelta(hours=1):
                            should_update = True
                            if previous_record.get('initial_home') is not None and previous_record.get('initial_away') is not None:
                                with self._analysis_lock:
                                    self._matches_to_analyze.add(match_id)

                if not should_update:
                    continue

                if is_new_company:
                    change_model = OddsChangeModel(
                        match_id=match_id,
                        company_id=company_id,
                        initial_home=new_record.get('initial_home'),
                        initial_draw=new_record.get('initial_draw'),
                        initial_away=new_record.get('initial_away'),
                        initial_return_rate=new_record.get('initial_return_rate'),
                        current_home=new_record.get('current_home'),
                        current_draw=new_record.get('current_draw'),
                        current_away=new_record.get('current_away'),
                        current_return_rate=new_record.get('current_return_rate'),
                        last_updated=now,
                    )
                else:
                    change_model = OddsChangeModel(
                        match_id=match_id,
                        company_id=company_id,
                        initial_home=previous_record.get('initial_home'),
                        initial_draw=previous_record.get('initial_draw'),
                        initial_away=previous_record.get('initial_away'),
                        initial_return_rate=previous_record.get('initial_return_rate'),
                        current_home=new_record.get('current_home'),
                        current_draw=new_record.get('current_draw'),
                        current_away=new_record.get('current_away'),
                        current_return_rate=new_record.get('current_return_rate'),
                        last_updated=now,
                    )
                changes_to_upsert.append(change_model)

                with self._lock:
                    if is_new_company:
                        self._odds_snapshot[match_id][company_id] = {
                            'initial_home': new_record.get('initial_home'),
                            'initial_draw': new_record.get('initial_draw'),
                            'initial_away': new_record.get('initial_away'),
                            'initial_return_rate': new_record.get('initial_return_rate'),
                            'current_home': new_record.get('current_home'),
                            'current_draw': new_record.get('current_draw'),
                            'current_away': new_record.get('current_away'),
                            'current_return_rate': new_record.get('current_return_rate'),
                            '_db_written': False,
                            '_last_updated': None,
                        }
                    else:
                        self._odds_snapshot[match_id][company_id].update(
                            {
                                'current_home': new_record.get('current_home'),
                                'current_draw': new_record.get('current_draw'),
                                'current_away': new_record.get('current_away'),
                                'current_return_rate': new_record.get('current_return_rate'),
                                '_last_updated': now,
                            }
                        )
                        if is_missing_in_db:
                            self._odds_snapshot[match_id][company_id]['_db_written'] = False

        if changes_to_upsert:
            try:
                saved_count = self.db_manager.upsert_odds_changes(changes_to_upsert)
                self.logger.info(
                    "Persisted %s odds change records (affected rows=%s)",
                    len(changes_to_upsert),
                    saved_count,
                )
                if saved_count > 0:
                    with self._lock:
                        for change_model in changes_to_upsert:
                            mid = change_model.match_id
                            cid = change_model.company_id
                            if mid in self._odds_snapshot and cid in self._odds_snapshot[mid]:
                                self._odds_snapshot[mid][cid]['_db_written'] = True
                                self._odds_snapshot[mid][cid]['_last_updated'] = now
            except Exception as exc:
                self.logger.error("Failed to persist odds changes: %s", exc, exc_info=True)

        return len(changes_to_upsert)

    def _has_odds_changed(self, old: Dict, new: Dict) -> bool:
        """Return True if current odds values changed."""
        return (
            old.get('current_home') != new.get('current_home')
            or old.get('current_draw') != new.get('current_draw')
            or old.get('current_away') != new.get('current_away')
        )

    def _has_valid_odds(self, record: Dict) -> bool:
        """Check whether required current odds fields are present."""
        return all(
            [
                record.get('current_home') is not None,
                record.get('current_draw') is not None,
                record.get('current_away') is not None,
            ]
        )

    def _trigger_analysis_for_new_companies(self):
        """Trigger asynchronous re-analysis when monitored companies need recalculation."""
        self._check_unanalyzed_companies_in_db()

        with self._analysis_lock:
            if not self._matches_to_analyze:
                return
            matches_to_analyze = list(self._matches_to_analyze)
            self._matches_to_analyze.clear()

        if not matches_to_analyze:
            return

        self.logger.info(
            "Submitting analysis for %s matches with new or missing company analysis",
            len(matches_to_analyze),
        )

        submitted = self._submit_analysis_job(matches_to_analyze)
        if not submitted:
            with self._analysis_lock:
                self._matches_to_analyze.update(matches_to_analyze)

    def _submit_analysis_job(self, match_ids: List[int]) -> bool:
        """Submit analysis work safely; do not lose tasks when executor is shutting down."""
        try:
            if self._runtime and self._runtime.executor:
                self._runtime.executor.submit(self._analyze_matches_async, match_ids)
                return True
            if self.executor:
                self.executor.submit(self._analyze_matches_async, match_ids)
                return True

            self.logger.warning("No executor available, running analysis inline")
            self._analyze_matches_async(match_ids)
            return True
        except RuntimeError as exc:
            self.logger.warning("Analysis submission skipped because executor is unavailable: %s", exc)
            return False
        except Exception as exc:
            self.logger.error("Failed to submit analysis task: %s", exc, exc_info=True)
            return False

    def _check_unanalyzed_companies_in_db(self):
        """Detect matches that have odds rows but still lack analysis rows."""
        match_ids = self._get_match_ids_snapshot()
        if not match_ids:
            return

        try:
            now = datetime.now()
            last_check = getattr(self, '_last_unanalyzed_check', None)
            if last_check and (now - last_check) < timedelta(minutes=15):
                return
            self._last_unanalyzed_check = now

            match_ids_to_check = match_ids[:200]
            if not match_ids_to_check:
                return

            placeholders = ','.join(['%s'] * len(match_ids_to_check))
            query = f"""
                SELECT DISTINCT oc.match_id, COUNT(DISTINCT oc.company_id) as unanalyzed_count
                FROM odds_changes oc
                JOIN matches m ON m.match_id = oc.match_id
                LEFT JOIN odds_analysis_results oar
                    ON oar.match_id = oc.match_id AND oar.company_id = oc.company_id
                WHERE oc.match_id IN ({placeholders})
                  AND m.match_status IN ('scheduled', 'live')
                  AND oc.initial_home IS NOT NULL
                  AND oc.initial_draw IS NOT NULL
                  AND oc.initial_away IS NOT NULL
                  AND oar.match_id IS NULL
                GROUP BY oc.match_id
                LIMIT 20
            """

            results = self._query_fn(query, tuple(match_ids_to_check))
            if not results:
                return

            matches_needing_analysis = []
            for row in results:
                match_id = row.get('match_id')
                unanalyzed_count = row.get('unanalyzed_count', 0)
                if match_id and unanalyzed_count > 0:
                    matches_needing_analysis.append(match_id)
                    if len(matches_needing_analysis) >= 10:
                        break

            if matches_needing_analysis:
                self.logger.info(
                    "Found %s matches with missing company analysis; queued for re-analysis",
                    len(matches_needing_analysis),
                )
                with self._analysis_lock:
                    self._matches_to_analyze.update(matches_needing_analysis)

        except Exception as exc:
            self.logger.error("Failed checking unanalyzed companies: %s", exc, exc_info=True)

    def _sort_by_kickoff(self, match_ids: List[int]) -> List[int]:
        """Sort match IDs by kickoff time ascending (nearest first)."""
        if not match_ids:
            return match_ids
        try:
            placeholders = ','.join(['%s'] * len(match_ids))
            sql = f"SELECT match_id, match_time FROM matches WHERE match_id IN ({placeholders})"
            rows = self._query_fn(sql, tuple(match_ids))
            time_map = {r['match_id']: r['match_time'] for r in rows}
            far_future = datetime(2099, 1, 1)
            return sorted(match_ids, key=lambda mid: time_map.get(mid, far_future))
        except Exception:
            self.logger.debug("Failed to sort by kickoff, using original order", exc_info=True)
            return match_ids

    def _analyze_matches_async(self, match_ids: List[int]):
        """Run realtime analysis in background and always release analyzer resources."""
        if not match_ids:
            return

        analyzer = None
        try:
            from odds_analysis.realtime_analyzer import RealtimeOddsAnalyzer

            # Sort by kickoff time so near-kickoff matches are analyzed first
            match_ids = self._sort_by_kickoff(match_ids)

            max_batch = 50
            if len(match_ids) > max_batch:
                self.logger.warning(
                    "Analysis queue too large (%s), trimming to first %s matches",
                    len(match_ids),
                    max_batch,
                )
                match_ids = match_ids[:max_batch]

            self.logger.info("Starting analysis for %s matches", len(match_ids))
            analyzer = RealtimeOddsAnalyzer(max_workers=min(5, len(match_ids)))

            results = analyzer.batch_analyze_matches(match_ids)
            success_count = sum(1 for r in results if r.get('success', False))
            self.logger.info("Background analysis completed: %s/%s successful", success_count, len(match_ids))

        except ImportError:
            self.logger.warning("RealtimeOddsAnalyzer unavailable, skipping async analysis")
        except Exception as exc:
            self.logger.error("Async analysis failed: %s", exc, exc_info=True)
        finally:
            if analyzer is not None:
                try:
                    analyzer.shutdown()
                except Exception:
                    self.logger.debug("Analyzer shutdown after async analysis failed", exc_info=True)


if __name__ == '__main__':
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger(__name__)

    test_match_ids = [2702229]
    monitor = OddsChangeMonitor(match_ids=test_match_ids, monitor_interval=10, initial_snapshot={})
    monitor.start()

    try:
        while True:
            time.sleep(60)
            logger.info("Main thread heartbeat")
    except KeyboardInterrupt:
        logger.info("Stopping monitor...")
        monitor.stop()
        logger.info("Monitor stopped")
