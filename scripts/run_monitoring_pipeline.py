#!/usr/bin/env python3
import os, sys, csv, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)) + '/..')
from core.runtime import AppRuntime
from application.services.monitoring_initialization_service import MonitoringInitializationService

match_ids = [os.environ.get("TEST_MATCH_ID","2701884")]
print("Using match_ids:", match_ids)

runtime = AppRuntime()
svc = MonitoringInitializationService(runtime.scraper)

snap, odds_models, ou_models = svc.scrape_initial_odds(match_ids)
print("snapshot keys:", list(snap.keys()))
print("odds_models:", len(odds_models), "ou_models:", len(ou_models))

saved_odds = runtime.db_manager.bulk_upsert_odds_changes(odds_models) if odds_models else 0
saved_ou   = runtime.db_manager.bulk_upsert_over_under_odds_changes(ou_models) if ou_models else 0
print("saved:", {"odds": saved_odds, "over_under": saved_ou})

print("OK")
