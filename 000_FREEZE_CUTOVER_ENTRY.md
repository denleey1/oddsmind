# Freeze Cutover Entry

Status: prepared only, not applied yet.

Use this file as the single entry point after migration/deployment.

## Primary Package

- `migration_config/odds_freeze_final_tick/README.md`

## SQL Files (Run In Order)

1. `migration_config/odds_freeze_final_tick/001_create_match_freeze_state.sql`
2. `migration_config/odds_freeze_final_tick/002_add_freeze_indexes.sql`
3. `migration_config/odds_freeze_final_tick/verify_freeze_state.sql`

Rollback:

1. `migration_config/odds_freeze_final_tick/900_rollback_odds_freeze.sql`

## Quick Commands

```bash
mysql -u <user> -p <db_name> < migration_config/odds_freeze_final_tick/001_create_match_freeze_state.sql
mysql -u <user> -p <db_name> < migration_config/odds_freeze_final_tick/002_add_freeze_indexes.sql
mysql -u <user> -p <db_name> < migration_config/odds_freeze_final_tick/verify_freeze_state.sql
```

Rollback:

```bash
mysql -u <user> -p <db_name> < migration_config/odds_freeze_final_tick/900_rollback_odds_freeze.sql
```

## Scope Note

This package only prepares database structures for final-tick freeze cutover.
Business logic changes are intentionally deferred until deployment environment validation.
