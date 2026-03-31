# Odds Final-Tick Freeze Cutover Package

Status: prepared, not executed.

This package is designed for deployment environments with real database access.
It prepares schema and indexes for the "freeze at kickoff" workflow.

## Goal

Enable a safe foundation for:

- freeze-by-match state tracking,
- deterministic final snapshot orchestration at kickoff,
- fast verification and rollback.

## Files

- `001_create_match_freeze_state.sql`
- `002_add_freeze_indexes.sql`
- `verify_freeze_state.sql`
- `900_rollback_odds_freeze.sql`

## Run Order

1. Run `001_create_match_freeze_state.sql`
2. Run `002_add_freeze_indexes.sql`
3. Run `verify_freeze_state.sql`

## Rollback Order

1. Run `900_rollback_odds_freeze.sql`
2. Run `verify_freeze_state.sql` again to confirm rollback result

## Suggested Command Pattern

```bash
mysql -u <user> -p <db_name> < migration_config/odds_freeze_final_tick/001_create_match_freeze_state.sql
mysql -u <user> -p <db_name> < migration_config/odds_freeze_final_tick/002_add_freeze_indexes.sql
mysql -u <user> -p <db_name> < migration_config/odds_freeze_final_tick/verify_freeze_state.sql
```

## What Is Not Included Yet

- No runtime code changes are applied in this package.
- No scheduler/job behavior is modified here.
- No lock/freeze decision logic is enabled yet.

Those changes should be deployed only after DB migration validation passes.
