#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Upsert helper operations extracted from repository layer."""

from __future__ import annotations

from typing import List, TYPE_CHECKING

from core.exceptions import DatabaseError

if TYPE_CHECKING:
    from .models import BaseModel, OddsModel


def upsert_record(repo, model: "BaseModel", conflict_columns: List[str]) -> int:
    """Insert or update on conflict."""
    data = model.to_db_dict()
    data = {k: v for k, v in data.items() if v is not None}

    if 'id' in data and data['id'] is None:
        del data['id']

    columns = list(data.keys())
    placeholders = ', '.join(['%s'] * len(columns))
    columns_str = ', '.join(columns)
    values = list(data.values())

    conflict_conditions = []
    conflict_values = []
    for col in conflict_columns:
        if col in data:
            conflict_conditions.append(f"{col} = %s")
            conflict_values.append(data[col])

    if not conflict_conditions:
        query = f"INSERT INTO {repo.table_name} ({columns_str}) VALUES ({placeholders})"
        return repo.db.execute_query(query, values)

    check_query = f"SELECT COUNT(*) as count FROM {repo.table_name} WHERE {' AND '.join(conflict_conditions)}"
    result = repo.db.execute_query(check_query, conflict_values, fetch='one')

    if result and result['count'] > 0:
        update_clauses = []
        update_values = []
        for col in columns:
            if col not in conflict_columns:
                update_clauses.append(f"{col} = %s")
                update_values.append(data[col])

        if update_clauses:
            update_query = f"UPDATE {repo.table_name} SET {', '.join(update_clauses)} WHERE {' AND '.join(conflict_conditions)}"
            return repo.db.execute_query(update_query, update_values + conflict_values)
        return 0

    query = f"INSERT INTO {repo.table_name} ({columns_str}) VALUES ({placeholders})"
    try:
        return repo.db.execute_query(query, values)
    except Exception as e:
        if "foreign key constraint fails" in str(e).lower():
            error_msg = str(e)
            if "company_id" in error_msg:
                company_id = getattr(model, 'company_id', None) if hasattr(model, 'company_id') else None
                repo.logger.error(
                    f"外键约束失败：company_id={company_id} 在 companies 表中不存在。"
                    f"请确保在插入 {repo.table_name} 数据前，相关的公司记录已存在。"
                )
            else:
                repo.logger.error(f"外键约束失败：{error_msg}")
        raise


def batch_upsert_odds(repo, odds_batch: List["OddsModel"]) -> int:
    """
    OPTIMIZED batch upsert for odds data - Enhanced version.
    Uses improved MySQL syntax and error handling.
    """
    if not odds_batch:
        return 0

    try:
        records_data = []
        for odds in odds_batch:
            data = odds.to_db_dict()
            data = {k: v for k, v in data.items() if v is not None}
            if 'id' in data and data['id'] is None:
                del data['id']

            if not data.get('match_id') or data.get('company_id') is None:
                continue

            records_data.append(data)

        if not records_data:
            return 0

        columns = list(records_data[0].keys())
        columns_str = ', '.join([f'`{col}`' for col in columns])
        placeholders = ', '.join(['%s'] * len(columns))

        update_clauses = []
        for col in columns:
            if col not in ['match_id', 'company_id', 'id', 'created_at']:
                update_clauses.append(f'`{col}` = VALUES(`{col}`)')

        if 'updated_at' not in columns:
            update_clauses.append('`updated_at` = CURRENT_TIMESTAMP')

        query = f"""
            INSERT INTO {repo.table_name} ({columns_str}) 
            VALUES ({placeholders})
        """

        if update_clauses:
            query += f" ON DUPLICATE KEY UPDATE {', '.join(update_clauses)}"

        values_list = []
        for record in records_data:
            values = [record.get(col) for col in columns]
            values_list.append(values)

        affected_rows = repo.db.execute_many(query, values_list)
        repo.logger.debug(f"Batch upsert completed: {affected_rows} rows affected from {len(records_data)} records")
        return affected_rows

    except Exception as e:
        repo.logger.error(f"Batch upsert failed for {len(odds_batch)} odds records: {e}")
        raise DatabaseError(f"Batch upsert failed: {str(e)}")


__all__ = ["batch_upsert_odds", "upsert_record"]

