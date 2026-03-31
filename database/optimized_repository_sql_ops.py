#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""SQL builders extracted from optimized_repository."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Set

from core.exceptions import ValidationError


DEFAULT_PROTECTED_FIELDS: Set[str] = {"data_source", "created_at"}


def normalize_model_data(model: Any) -> Dict[str, Any]:
    """Convert model payload to an upsert-ready dict."""
    data = model.to_db_dict()
    data = {key: value for key, value in data.items() if value is not None}
    if data.get("id") is None and "id" in data:
        del data["id"]
    return data


def ensure_non_empty_data(data: Dict[str, Any]) -> None:
    if not data:
        raise ValidationError("No data to upsert")


def build_insert_with_upsert_sql(
    table_name: str,
    columns: Sequence[str],
    conflict_columns: Iterable[str],
    protected_fields: Optional[Set[str]] = None,
) -> str:
    """Build INSERT ... ON DUPLICATE KEY UPDATE SQL."""
    if protected_fields is None:
        protected_fields = set()

    placeholders = ", ".join(["%s"] * len(columns))
    columns_str = ", ".join([f"`{column}`" for column in columns])

    conflict_columns_set = set(conflict_columns)
    update_clauses = []
    for column in columns:
        if column not in conflict_columns_set and column not in protected_fields:
            update_clauses.append(f"`{column}` = VALUES(`{column}`)")

    query = f"""
        INSERT INTO {table_name} ({columns_str})
        VALUES ({placeholders})
    """
    if update_clauses:
        query += f" ON DUPLICATE KEY UPDATE {', '.join(update_clauses)}"
    return query


def build_single_upsert_sql(
    table_name: str,
    data: Dict[str, Any],
    conflict_columns: Iterable[str],
) -> Tuple[str, List[Any]]:
    columns = list(data.keys())
    query = build_insert_with_upsert_sql(table_name, columns, conflict_columns)
    return query, list(data.values())


def build_batch_upsert_sql(
    table_name: str,
    records_data: List[Dict[str, Any]],
    conflict_columns: Iterable[str],
    protected_fields: Optional[Set[str]] = None,
) -> Tuple[str, List[str]]:
    columns = list(records_data[0].keys())
    query = build_insert_with_upsert_sql(table_name, columns, conflict_columns, protected_fields)
    return query, columns


def align_batch_values(records_data: List[Dict[str, Any]], columns: Sequence[str]) -> List[List[Any]]:
    return [[record.get(column) for column in columns] for record in records_data]


def build_unique_lookup(
    table_name: str,
    data: Dict[str, Any],
    unique_columns: Iterable[str],
) -> Tuple[str, List[Any]]:
    conditions = []
    values: List[Any] = []

    for column in unique_columns:
        if column in data and data[column] is not None:
            conditions.append(f"`{column}` = %s")
            values.append(data[column])

    if not conditions:
        raise ValidationError("No unique columns provided for find_or_create")

    query = f"SELECT * FROM {table_name} WHERE {' AND '.join(conditions)}"
    return query, values


def build_find_by_criteria_sql(
    table_name: str,
    criteria: Dict[str, Any],
    limit: Optional[int] = None,
    order_by: Optional[str] = None,
    use_index_hint: Optional[str] = None,
) -> Tuple[str, List[Any]]:
    where_clauses = []
    values: List[Any] = []

    for column, value in criteria.items():
        if isinstance(value, tuple) and len(value) == 2:
            operator, operator_value = value
            where_clauses.append(f"`{column}` {operator} %s")
            values.append(operator_value)
        elif isinstance(value, (list, tuple)):
            placeholders = ", ".join(["%s"] * len(value))
            where_clauses.append(f"`{column}` IN ({placeholders})")
            values.extend(value)
        elif value is None:
            where_clauses.append(f"`{column}` IS NULL")
        else:
            where_clauses.append(f"`{column}` = %s")
            values.append(value)

    query = f"SELECT * FROM {table_name}"
    if use_index_hint:
        query += f" USE INDEX ({use_index_hint})"
    query += f" WHERE {' AND '.join(where_clauses)}"

    if order_by:
        query += f" ORDER BY {order_by}"
    if limit:
        query += f" LIMIT {limit}"

    return query, values


__all__ = [
    "DEFAULT_PROTECTED_FIELDS",
    "align_batch_values",
    "build_batch_upsert_sql",
    "build_find_by_criteria_sql",
    "build_single_upsert_sql",
    "build_unique_lookup",
    "ensure_non_empty_data",
    "normalize_model_data",
]
