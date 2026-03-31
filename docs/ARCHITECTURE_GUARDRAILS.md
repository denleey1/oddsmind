# Architecture Guardrails

This project now includes lightweight guardrails to keep deep refactoring safe
while preserving runtime behavior.

## 1) Route Contract (static)

Purpose:
- Prevent accidental API route drift during architecture refactoring.
- Works without starting Flask app (no DB/Redis dependency required).

Generate/refresh baseline:

```bash
python scripts/generate_route_contract_baseline.py
```

Check current code against baseline:

```bash
python scripts/check_route_contract.py
```

Baseline file:
- `tests/architecture/baselines/route_contract_static_v1.json`

## 2) Runtime Slow-Init Guard (static test)

Purpose:
- Ensure runtime still contains one-shot deferred initialization guard APIs.

Run:

```bash
python -m unittest tests.architecture.test_runtime_slow_init_guard
```

## 3) Web Service Extraction Regression Tests

Purpose:
- Lock behavior of route-to-service extractions in `application/services/web_*`.
- Preserve known legacy response semantics while reducing route-layer complexity.

Run:

```bash
python -m unittest tests.architecture.test_web_service_extractions
```

Additional lazy-import guard for AI route orchestration:

```bash
python -m unittest tests.architecture.test_web_ai_lazy_imports
```

Mini-program auth extraction regression guard:

```bash
python -m unittest tests.architecture.test_miniprogram_service_extraction
```

Match-detail provider usage guard:

```bash
python -m unittest tests.architecture.test_match_detail_provider_usage
```

Legacy app_services facade compatibility guard:

```bash
python -m unittest tests.architecture.test_app_services_facade
```

Module size budget guard:

```bash
python scripts/check_module_size_budget.py
python -m unittest tests.architecture.test_module_size_budget
```

Duplicate method-name guard (prevents accidental in-class override by redefinition):

```bash
python -m unittest tests.architecture.test_no_duplicate_method_names
```

Scheduled updater orchestration guard (locks task lifecycle helper usage and centralized subprocess entry):

```bash
python -m unittest tests.architecture.test_scheduled_data_updater_structure
```

Monitoring odds-sync extraction guard:

```bash
python -m unittest tests.architecture.test_monitoring_odds_sync_extraction
```

Database manager extraction guard:

```bash
python -m unittest tests.architecture.test_database_manager_extractions
```

Database manager deep extraction guard (query/write helper split):

```bash
python -m unittest tests.architecture.test_database_manager_extractions_v2
```

Repository upsert extraction guard:

```bash
python -m unittest tests.architecture.test_repository_upsert_extraction
```

Monitoring change-detection extraction guard:

```bash
python -m unittest tests.architecture.test_monitoring_change_detection_extraction
```

Monitoring coordinator deep extraction guard (final-odds + unanalyzed-company flows):

```bash
python -m unittest tests.architecture.test_monitoring_coordinator_extractions_v2
```

Monitoring coordinator deep extraction guard (analysis execution split):

```bash
python -m unittest tests.architecture.test_monitoring_coordinator_extractions_v3
```

CLI heavy-handler extraction guard:

```bash
python -m unittest tests.architecture.test_cli_handler_extraction
```

Match-status match-ops extraction guard:

```bash
python -m unittest tests.architecture.test_match_status_ops_extraction
```

Web match-listing ops extraction guard:

```bash
python -m unittest tests.architecture.test_web_match_listing_extraction
```

Web match-listing ops deep extraction guard (query/format split):

```bash
python -m unittest tests.architecture.test_web_match_listing_ops_extraction_v2
```

Scheduled task-actions extraction guard:

```bash
python -m unittest tests.architecture.test_scheduled_task_actions_extraction
```

Auto rule-matcher extraction guard:

```bash
python -m unittest tests.architecture.test_auto_rule_matcher_extraction
```

Rule-match API payload extraction guard:

```bash
python -m unittest tests.architecture.test_rule_match_api_extraction
```

Web match-detail payload extraction guard:

```bash
python -m unittest tests.architecture.test_web_match_detail_payload_extraction
```

Match-detail service extraction guard:

```bash
python -m unittest tests.architecture.test_match_detail_service_extractions
```

Optimized repository extraction guard:

```bash
python -m unittest tests.architecture.test_optimized_repository_extraction
```

Enhanced manager extraction guard:

```bash
python -m unittest tests.architecture.test_enhanced_manager_extraction
```

Batch writer extraction guard:

```bash
python -m unittest tests.architecture.test_batch_writer_extraction
```

Split-model facade compatibility guard:

```bash
python -m unittest tests.architecture.test_models_split_compatibility
```

Task health tracker extraction guard:

```bash
python -m unittest tests.architecture.test_task_health_tracker_extraction
```

League-status monitor extraction guard:

```bash
python -m unittest tests.architecture.test_league_status_monitor_extraction
```

Optimized match-detail extraction guard:

```bash
python -m unittest tests.architecture.test_match_detail_optimized_extraction
```

Rule-engine extraction guard:

```bash
python -m unittest tests.architecture.test_rule_engine_extraction
```
