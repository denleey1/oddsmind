#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Central coordinator for match and odds monitoring workflows."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from core.runtime import AppRuntime

from app_business import MonitorIntervalCalculator
from app_database import (
    execute_query,
    get_matches_to_monitor,
    get_round_completion_status,
    is_round_complete,
)
from application.services.fundamental_analysis_service import FundamentalAnalysisService
from application.services.monitoring_initialization_service import MonitoringInitializationService
from application.services.odds_analysis_service import OddsAnalysisService
from database.manager import DatabaseManager
from database.models import AsianHandicapOddsModel, OddsChangeModel, OverUnderOddsChangeModel, OddsModel
from monitoring.odds_monitor import OddsChangeMonitor
from services.monitoring_change_detection import collect_matches_requiring_analysis
from services.monitoring_final_odds import sync_final_odds
from services.monitoring_odds_sync import sync_write_odds_changes, verify_odds_changes_in_db
from services.monitoring_unanalyzed_companies import (
    check_and_analyze_unanalyzed_companies,
    verify_priority_companies_analyzed,
)
from services.monitoring_analysis_execution import (
    analyse_matches_with_changes as _analyse_matches_with_changes_impl,
    calculate_strength as _calculate_strength_impl,
    find_completed_rounds as _find_completed_rounds_impl,
    reanalyse_league_matches as _reanalyse_league_matches_impl,
)
from services.match_status_updater import create_match_status_updater


class MonitoringCoordinator:
    """High level orchestrator that keeps match/odds monitoring in sync."""

    def __init__(self, runtime: AppRuntime) -> None:
        self.runtime = runtime
        self.logger = get_logger(self.__class__.__name__)
        self.db_manager: DatabaseManager = runtime.db_manager

        self._monitor_init_service = MonitoringInitializationService(runtime.scraper)
        self._fundamental_service = FundamentalAnalysisService()
        self._odds_analysis_service = OddsAnalysisService()
        self._match_status_updater = create_match_status_updater(runtime=runtime)

        self._latest_matches: List[Dict[str, Any]] = []
        self._latest_snapshot: Dict[int, Dict[int, Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._monitor_init_lock = threading.Lock()
        self._status_update_lock = threading.Lock()
        self._completed_match_lock = threading.Lock()
        self._slow_log_threshold_seconds = 10.0

    def _check_and_analyze_unanalyzed_companies(self, initial_snapshot: Dict, match_ids: List[int]) -> None:
        """Delegate missing-analysis company scan and asynchronous remediation."""
        check_and_analyze_unanalyzed_companies(
            execute_query=execute_query,
            logger=self.logger,
            runtime=self.runtime,
            match_ids=match_ids,
            verify_priority_callback=self._verify_priority_companies_analyzed,
        )
    
    def _verify_priority_companies_analyzed(self, match_ids: List[int], priority_companies: set) -> None:
        """Delegate verification of priority-company analysis completeness."""
        verify_priority_companies_analyzed(
            execute_query=execute_query,
            logger=self.logger,
            match_ids=match_ids,
            priority_companies=priority_companies,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    def refresh_monitor_targets(self) -> List[Dict[str, Any]]:
        """Pull latest match candidates that should be monitored."""
        matches = get_matches_to_monitor()
        with self._lock:
            self._latest_matches = matches
        return matches

    def initialize_monitoring(self, force: bool = False) -> Dict[str, Any]:
        """
        Prepare odds monitoring by fetching initial odds snapshot and ensuring
        the odds-change monitor runs with the freshest data.
        """
        start_ts = time.monotonic()
        if not self._monitor_init_lock.acquire(blocking=False):
            monitor_running = bool(self.runtime.monitor and self.runtime.monitor.is_running)
            self.logger.warning("Monitoring initialisation already in progress, skipping duplicate request")
            return {
                'matches': len(self._latest_matches),
                'odds_records': 0,
                'over_under_records': 0,
                'monitor_started': monitor_running,
                'skipped': True,
                'elapsed_seconds': round(time.monotonic() - start_ts, 3),
            }

        try:
            matches = self.refresh_monitor_targets()
            if not matches:
                self.logger.warning("Monitoring initialisation skipped: no matches found")
                return {
                    'matches': 0,
                    'odds_records': 0,
                    'over_under_records': 0,
                    'monitor_started': False,
                    'elapsed_seconds': round(time.monotonic() - start_ts, 3),
                }

            match_ids = [m['match_id'] for m in matches]
            initial_snapshot, odds_changes, ou_changes, ah_models = self._build_initial_snapshot(match_ids, force=force)

            saved_records = 0
            if odds_changes:
                saved_records = self._sync_write_odds_changes(odds_changes)

                if saved_records > 0:
                    verified_count = self._verify_odds_changes_in_db(odds_changes)
                    if verified_count > 0:
                        for match_id, companies in initial_snapshot.items():
                            for company_id in companies.keys():
                                initial_snapshot[match_id][company_id]['_db_written'] = True
                        self.logger.info(
                            "Initial snapshot write verified: %s/%s records confirmed",
                            verified_count,
                            len(odds_changes),
                        )
                    else:
                        self.logger.error(
                            "Initial snapshot write verification failed: no records found in database"
                        )

            ou_saved = 0
            if ou_changes:
                ou_saved = self.db_manager.bulk_upsert_over_under_odds_changes(ou_changes)

            ah_saved = 0
            if ah_models:
                ah_saved = self.db_manager.bulk_upsert_asian_handicap_odds(ah_models)

            monitor_started = self._start_or_reset_monitor(match_ids, initial_snapshot)

            # Keep heavy post-init analysis off the scheduler thread.
            self._submit_background_task(
                self._fundamental_service.batch_analyze_fundamental,
                [str(mid) for mid in match_ids],
                task_name="fundamental bootstrap analysis",
            )

            self._check_and_analyze_unanalyzed_companies(
                initial_snapshot,
                match_ids,
            )

            self.logger.info(
                "Monitoring initialised: %s matches, %s odds rows, %s over/under rows, %s asian handicap rows, monitor=%s",
                len(match_ids),
                saved_records,
                ou_saved,
                ah_saved,
                monitor_started,
            )

            return {
                'matches': len(match_ids),
                'odds_records': saved_records,
                'over_under_records': ou_saved,
                'asian_handicap_records': ah_saved,
                'monitor_started': monitor_started,
                'elapsed_seconds': round(time.monotonic() - start_ts, 3),
            }
        finally:
            elapsed = time.monotonic() - start_ts
            if elapsed > self._slow_log_threshold_seconds:
                self.logger.warning("Monitoring initialisation is slow: %.2fs", elapsed)
            self._monitor_init_lock.release()

    def update_match_statuses(self) -> Dict[str, Any]:
        """Refresh match meta data from league scrapers and re-sync monitoring."""
        start_ts = time.monotonic()
        if not self._status_update_lock.acquire(blocking=False):
            self.logger.warning("Match status update already in progress, skipping duplicate run")
            return {'skipped': True, 'reason': 'already_running', 'elapsed_seconds': round(time.monotonic() - start_ts, 3)}

        try:
            result = self._match_status_updater.update_all_match_status()
            self.logger.info("Match status updater summary: %s", result)

            status_changes_detail = result.get('status_changes_detail', [])
            finished_matches = [
                item['match_id']
                for item in status_changes_detail
                if item.get('new_status') == 'finished'
            ]
            if finished_matches:
                self.logger.info(
                    "Syncing final odds for %d newly finished matches (force update)",
                    len(finished_matches),
                )
                self._sync_final_odds(match_ids=finished_matches, force_update=True)

            new_match_ids = result.get('new_match_ids', [])
            scheduled_changes = [
                item['match_id']
                for item in status_changes_detail
                if item.get('new_status') in {'scheduled', 'live'}
            ]

            if finished_matches or new_match_ids or scheduled_changes or result.get('status_changes') or result.get('new_matches'):
                self.logger.info("Refreshing monitoring targets after match status update")
                self.initialize_monitoring(force=True)
            else:
                self.verify_odds_sync()

            if isinstance(result, dict):
                result['elapsed_seconds'] = round(time.monotonic() - start_ts, 3)
            return result
        finally:
            elapsed = time.monotonic() - start_ts
            if elapsed > self._slow_log_threshold_seconds:
                self.logger.warning("Match status update is slow: %.2fs", elapsed)
            self._status_update_lock.release()

    def process_completed_matches(self) -> Dict[str, Any]:
        """Handle post-match workflows: final odds, strength calculation, re-analysis."""
        start_ts = time.monotonic()
        if not self._completed_match_lock.acquire(blocking=False):
            self.logger.warning("Completed-match processing already in progress, skipping duplicate run")
            return {
                'skipped': True,
                'reason': 'already_running',
                'elapsed_seconds': round(time.monotonic() - start_ts, 3),
            }

        try:
            odds_saved = self._sync_final_odds()
            # Skip broad strength recalculation while keeping odds sync intact.
            summary = {
                'final_odds_saved': odds_saved,
                'strength_recalculated': [],
                'elapsed_seconds': round(time.monotonic() - start_ts, 3),
            }

            # After processing completions ensure monitored odds are still in sync
            self.verify_odds_sync()

            return summary
        except Exception as exc:
            self.logger.error("process_completed_matches failed: %s", exc, exc_info=True)
            return {
                'error': str(exc),
                'elapsed_seconds': round(time.monotonic() - start_ts, 3),
            }
        finally:
            elapsed = time.monotonic() - start_ts
            if elapsed > self._slow_log_threshold_seconds:
                self.logger.warning("Completed-match processing is slow: %.2fs", elapsed)
            self._completed_match_lock.release()

    def monitor_odds_changes(self) -> Dict[str, Any]:
        """
        Inspect odds tables and trigger downstream analysis when updates occur.
        淇敼閫昏緫锛氫笉浠呮煡璇㈡湁鍙樺寲鐨勮褰曪紝杩樿鏌ヨ鏈夎禂鐜囨暟鎹絾浠庢湭琚垎鏋愯繃鐨勮褰曪紙鍗充娇璧旂巼娌″彉鍖栵級
        """
        start_ts = time.monotonic()
        changes_list = collect_matches_requiring_analysis(execute_query)
        if not changes_list:
            self.logger.debug("No odds changes requiring analysis in current window")
            return {'processed': 0, 'elapsed_seconds': round(time.monotonic() - start_ts, 3)}

        self.logger.info(
            "Found %d matches with fresh odds changes (1x2/over-under)",
            len(changes_list),
        )
        self._analyse_matches_with_changes(changes_list)
        elapsed = time.monotonic() - start_ts
        if elapsed > self._slow_log_threshold_seconds:
            self.logger.warning("Odds change monitoring cycle is slow: %.2fs", elapsed)
        return {'processed': len(changes_list), 'elapsed_seconds': round(elapsed, 3)}


    def verify_odds_sync(self) -> Dict[str, Any]:
        """Check whether match metadata updates have corresponding odds updates."""
        sql = """
        SELECT 
            m.match_id,
            m.updated_at AS match_updated_at,
            MAX(oc.last_updated) AS odds_last_updated,
            MAX(ou.last_updated) AS ou_last_updated
        FROM matches m
        LEFT JOIN odds_changes oc ON oc.match_id = m.match_id
        LEFT JOIN over_under_odds_changes ou ON ou.match_id = m.match_id
        WHERE m.match_status IN ('scheduled', 'live')
          AND m.match_time BETWEEN DATE_SUB(NOW(), INTERVAL 1 DAY) AND DATE_ADD(NOW(), INTERVAL 3 DAY)
        GROUP BY m.match_id, m.updated_at
        HAVING (odds_last_updated IS NULL OR TIMESTAMPDIFF(MINUTE, odds_last_updated, m.updated_at) > 15)
           OR (ou_last_updated IS NOT NULL AND TIMESTAMPDIFF(MINUTE, ou_last_updated, m.updated_at) > 15)
        """

        mismatches = execute_query(sql)
        if mismatches:
            for item in mismatches[:10]:
                self.logger.warning(
                    "Match %s updated at %s lacks fresh odds (1x2=%s, ou=%s)",
                    item['match_id'],
                    item['match_updated_at'],
                    item.get('odds_last_updated'),
                    item.get('ou_last_updated'),
                )
        return {'out_of_sync': len(mismatches)}

    def _submit_background_task(self, task, *args, task_name: str) -> bool:
        """Submit non-critical background work without breaking the caller on executor errors."""
        try:
            self.runtime.executor.submit(task, *args)
            return True
        except RuntimeError as exc:
            self.logger.warning("Skipped %s because executor is unavailable: %s", task_name, exc)
            return False
        except Exception as exc:
            self.logger.error("Failed to submit %s: %s", task_name, exc, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    
    def _sync_write_odds_changes(self, odds_changes: List) -> int:
        """
        鍚屾鍐欏叆璧旂巼鍙樺寲鏁版嵁锛岀粫杩嘊atchWriter闃熷垪
        
        Args:
            odds_changes: OddsChangeModel 鍒楄〃
            
        Returns:
            瀹為檯鍐欏叆鐨勮褰曟暟
        """
        return sync_write_odds_changes(self.db_manager, odds_changes, self.logger)
    
    def _verify_odds_changes_in_db(self, odds_changes: List) -> int:
        """
        楠岃瘉璧旂巼鍙樺寲鏁版嵁鏄惁鐪熸鍐欏叆鏁版嵁搴?        
        Args:
            odds_changes: OddsChangeModel 鍒楄〃
            
        Returns:
            鏁版嵁搴撲腑瀛樺湪鐨勮褰曟暟
        """
        return verify_odds_changes_in_db(odds_changes, self.logger)

    def _build_initial_snapshot(
        self,
        match_ids: List[int],
        force: bool = False,
    ) -> tuple[
        Dict[int, Dict[int, Dict[str, Any]]],
        List[OddsChangeModel],
        List[OverUnderOddsChangeModel],
        List[AsianHandicapOddsModel],
    ]:
        initial_snapshot: Dict[int, Dict[int, Dict[str, Any]]] = {}
        odds_changes: List[OddsChangeModel] = []
        ou_changes: List[OverUnderOddsChangeModel] = []

        snapshot, odds_records, ou_records, ah_models = self._monitor_init_service.scrape_initial_odds(match_ids)
        initial_snapshot.update(snapshot)
        odds_changes.extend(odds_records)
        ou_changes.extend(ou_records)

        if force and not odds_changes and not ou_changes:
            self.logger.warning("Forced refresh returned no odds data")

        with self._lock:
            self._latest_snapshot = initial_snapshot

        return initial_snapshot, odds_changes, ou_changes, ah_models

    def _start_or_reset_monitor(
        self,
        match_ids: List[int],
        initial_snapshot: Dict[int, Dict[int, Dict[str, Any]]],
    ) -> bool:
        if not match_ids:
            return False

        current_monitor: Optional[OddsChangeMonitor] = self.runtime.monitor
        if current_monitor and current_monitor.is_running:
            current_monitor.stop()
            self.logger.info("Stopped previous odds change monitor instance")
            self.runtime.monitor = None

        earliest_match_time = min(
            (m.get('match_time') for m in self._latest_matches if m.get('match_time')),
            default=None,
        )
        initial_interval = (
            MonitorIntervalCalculator.get_monitor_interval(earliest_match_time)
            if earliest_match_time
            else 1800
        )

        monitor = OddsChangeMonitor(
            match_ids=match_ids,
            monitor_interval=initial_interval,
            initial_snapshot=initial_snapshot,
            executor=self.runtime.executor,
            runtime=self.runtime,
        )
        monitor.start()
        self.runtime.monitor = monitor
        return True

    def _sync_final_odds(self, lookback_hours: int = 24, match_ids: Optional[List[int]] = None, force_update: bool = False) -> int:
        """Sync final odds for finished matches into european_odds."""
        return sync_final_odds(
            execute_query=execute_query,
            logger=self.logger,
            runtime=self.runtime,
            db_manager=self.db_manager,
            odds_record_to_model=self._odds_record_to_model,
            lookback_hours=lookback_hours,
            match_ids=match_ids,
            force_update=force_update,
        )

    def _odds_record_to_model(self, match_id: int, record: Dict[str, Any]) -> Optional[OddsModel]:
        company_id = record.get('company_id')
        if not company_id:
            return None

        return OddsModel(
            match_id=match_id,
            company_id=int(company_id),
            initial_home=record.get('initial_home'),
            initial_draw=record.get('initial_draw'),
            initial_away=record.get('initial_away'),
            initial_home_prob=record.get('initial_home_prob'),
            initial_draw_prob=record.get('initial_draw_prob'),
            initial_away_prob=record.get('initial_away_prob'),
            initial_return_rate=record.get('initial_return_rate'),
            current_home=record.get('current_home'),
            current_draw=record.get('current_draw'),
            current_away=record.get('current_away'),
            current_home_prob=record.get('current_home_prob'),
            current_draw_prob=record.get('current_draw_prob'),
            current_away_prob=record.get('current_away_prob'),
            current_return_rate=record.get('current_return_rate'),
            kelly_home=record.get('kelly_home'),
            kelly_draw=record.get('kelly_draw'),
            kelly_away=record.get('kelly_away'),
            update_time=record.get('update_time'),
            data_source='titan007',
        )

    def _find_completed_rounds(self) -> List[Dict[str, Any]]:
        return _find_completed_rounds_impl(execute_query_fn=execute_query, logger=self.logger)

    def _calculate_strength(self, league_id: int, round_number: int) -> tuple[bool, Optional[str]]:
        return _calculate_strength_impl(
            execute_query_fn=execute_query,
            logger=self.logger,
            league_id=league_id,
            round_number=round_number,
        )

    def _reanalyse_league_matches(self, league_id: int) -> None:
        """Re-run odds analysis so stored results use the latest power ratings."""
        return _reanalyse_league_matches_impl(
            execute_query_fn=execute_query,
            logger=self.logger,
            league_id=league_id,
        )

    def _analyse_matches_with_changes(self, changed_matches: List[Dict[str, Any]]) -> None:
        return _analyse_matches_with_changes_impl(
            fundamental_service=self._fundamental_service,
            logger=self.logger,
            changed_matches=changed_matches,
        )


def get_monitoring_coordinator(runtime: AppRuntime) -> MonitoringCoordinator:
    """Convenience factory."""
    return MonitoringCoordinator(runtime)


