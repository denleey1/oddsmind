#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Operational helpers extracted from optimized_repository."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from core.exceptions import DatabaseError

from .optimized_repository_sql_ops import (
    DEFAULT_PROTECTED_FIELDS,
    align_batch_values,
    build_batch_upsert_sql,
    build_find_by_criteria_sql,
    build_single_upsert_sql,
    build_unique_lookup,
    ensure_non_empty_data,
    normalize_model_data,
)

if TYPE_CHECKING:
    from .models import BaseModel
    from .optimized_repository import OptimizedBaseRepository


def atomic_upsert_impl(
    repository: "OptimizedBaseRepository",
    model: "BaseModel",
    conflict_columns: List[str],
) -> int:
    start_time = time.time()
    try:
        data = normalize_model_data(model)
        ensure_non_empty_data(data)
        query, values = build_single_upsert_sql(repository.table_name, data, conflict_columns)
        result = repository.db.execute_query(query, values)
        repository._update_operation_stats(True, time.time() - start_time)
        return result
    except Exception as exc:
        repository._update_operation_stats(False, time.time() - start_time)
        repository.logger.error(f"Atomic upsert failed for {repository.table_name}: {exc}")
        raise DatabaseError(f"Atomic upsert failed: {str(exc)}")


def execute_batch_upsert_impl(
    repository: "OptimizedBaseRepository",
    batch: List["BaseModel"],
    conflict_columns: List[str],
) -> int:
    if not batch:
        return 0

    records_data: List[Dict[str, Any]] = []
    for model in batch:
        data = normalize_model_data(model)
        if data:
            records_data.append(data)

    if not records_data:
        return 0

    query, columns = build_batch_upsert_sql(
        repository.table_name,
        records_data,
        conflict_columns,
        protected_fields=DEFAULT_PROTECTED_FIELDS,
    )
    values_list = align_batch_values(records_data, columns)
    return repository.db.execute_many(query, values_list)


def batch_atomic_upsert_impl(
    repository: "OptimizedBaseRepository",
    models: List["BaseModel"],
    conflict_columns: List[str],
    batch_size: int,
) -> int:
    if not models:
        return 0

    start_time = time.time()
    total_affected = 0

    try:
        for index in range(0, len(models), batch_size):
            batch = models[index:index + batch_size]
            total_affected += execute_batch_upsert_impl(repository, batch, conflict_columns)

        repository._update_operation_stats(True, time.time() - start_time)
        repository.logger.info(
            "Batch upsert completed: %s records affected from %s models",
            total_affected,
            len(models),
        )
        return total_affected
    except Exception as exc:
        repository._update_operation_stats(False, time.time() - start_time)
        repository.logger.error(f"Batch atomic upsert failed for {repository.table_name}: {exc}")
        raise DatabaseError(f"Batch atomic upsert failed: {str(exc)}")


def safe_find_or_create_impl(
    repository: "OptimizedBaseRepository",
    model: "BaseModel",
    unique_columns: List[str],
) -> Tuple["BaseModel", bool]:
    try:
        data = model.to_db_dict()
        query, values = build_unique_lookup(repository.table_name, data, unique_columns)

        existing = repository.db.execute_query(query, values, fetch="one")
        if existing:
            return repository.model_class.from_dict(existing), False

        affected = repository.atomic_upsert(model, unique_columns)
        if affected > 0:
            new_record = repository.db.execute_query(query, values, fetch="one")
            if new_record:
                return repository.model_class.from_dict(new_record), True

        raise DatabaseError("Failed to create record")
    except Exception as exc:
        repository.logger.error(f"Safe find_or_create failed for {repository.table_name}: {exc}")
        raise DatabaseError(f"Safe find_or_create failed: {str(exc)}")


def optimized_find_by_criteria_impl(
    repository: "OptimizedBaseRepository",
    criteria: Dict[str, Any],
    limit: Optional[int],
    order_by: Optional[str],
    use_index_hint: Optional[str],
) -> List["BaseModel"]:
    if not criteria:
        return []

    try:
        query, values = build_find_by_criteria_sql(
            repository.table_name,
            criteria,
            limit=limit,
            order_by=order_by,
            use_index_hint=use_index_hint,
        )
        results = repository.db.execute_query(query, values, fetch="all")
        return [repository.model_class.from_dict(row) for row in results] if results else []
    except Exception as exc:
        repository.logger.error(f"Optimized find by criteria failed for {repository.table_name}: {exc}")
        return []


__all__ = [
    "atomic_upsert_impl",
    "batch_atomic_upsert_impl",
    "execute_batch_upsert_impl",
    "optimized_find_by_criteria_impl",
    "safe_find_or_create_impl",
]
