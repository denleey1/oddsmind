#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Flush/retry helpers extracted from BatchWriter."""

from __future__ import annotations

import time
from datetime import datetime
from queue import Empty
from typing import TYPE_CHECKING, Any, Dict

from core.logger import get_logger

from .batch_writer_queue_ops import collect_flush_payload, total_pending_records
from .manager_write_helpers import (
    _direct_bulk_upsert_odds_changes,
    _direct_bulk_upsert_over_under_odds_changes,
)

if TYPE_CHECKING:
    from .batch_writer import BatchWriter

logger = get_logger(__name__)


def write_batch_with_retry_impl(
    writer: "BatchWriter",
    batch_type: str,
    batch: Any,
    retry_count: int = 0,
) -> bool:
    try:
        if batch_type == "odds_changes":
            _direct_bulk_upsert_odds_changes(writer.db_manager, batch)
        elif batch_type == "over_under":
            _direct_bulk_upsert_over_under_odds_changes(writer.db_manager, batch)
        elif batch_type == "odds":
            writer.db_manager.store_multiple_odds_data(batch, force_direct_write=True)
        return True
    except Exception as exc:
        logger.error("Failed to write %s batch (attempt %s): %s", batch_type, retry_count + 1, exc)

        if retry_count < writer.max_retries:
            writer._retry_queue.put((batch_type, batch, retry_count + 1))
            with writer._stats_lock:
                writer.stats["total_retried"] += 1
            logger.info(
                "Batch added to retry queue (attempt %s/%s)",
                retry_count + 1,
                writer.max_retries,
            )
        else:
            logger.error("Batch failed after %s retries, data lost", writer.max_retries)
            with writer._stats_lock:
                writer.stats["retry_failed"] += 1

        return False


def process_retries_impl(writer: "BatchWriter") -> None:
    processed = 0

    while not writer._retry_queue.empty():
        try:
            batch_type, batch, retry_count = writer._retry_queue.get_nowait()
            wait_time = min(2 ** retry_count, 30)
            time.sleep(wait_time)

            success = write_batch_with_retry_impl(writer, batch_type, batch, retry_count)
            if success:
                with writer._stats_lock:
                    writer.stats["retry_success"] += 1
            processed += 1
        except Empty:
            break
        except Exception as exc:
            logger.error(f"Error processing retry: {exc}")

    if processed > 0:
        logger.debug("Processed %s retry batches", processed)


def flush_all_impl(writer: "BatchWriter") -> int:
    try:
        all_odds_changes, all_over_under, odds_batch = collect_flush_payload(writer)

        written_count = 0
        failed_count = 0

        if all_odds_changes:
            for index in range(0, len(all_odds_changes), writer.batch_size):
                batch = all_odds_changes[index:index + writer.batch_size]
                success = write_batch_with_retry_impl(writer, "odds_changes", batch)
                if success:
                    written_count += len(batch)
                else:
                    failed_count += len(batch)

        if all_over_under:
            for index in range(0, len(all_over_under), writer.batch_size):
                batch = all_over_under[index:index + writer.batch_size]
                success = write_batch_with_retry_impl(writer, "over_under", batch)
                if success:
                    written_count += len(batch)
                else:
                    failed_count += len(batch)

        if odds_batch:
            success = write_batch_with_retry_impl(writer, "odds", odds_batch)
            if success:
                written_count += len(odds_batch)
            else:
                failed_count += len(odds_batch)

        if written_count > 0 or all_odds_changes or all_over_under or odds_batch:
            with writer._stats_lock:
                writer.stats["total_written"] += written_count
                writer.stats["total_failed"] += failed_count
                writer.stats["last_flush_time"] = datetime.now()
                writer.stats["flush_count"] += 1

            if writer.on_write_complete and written_count > 0:
                try:
                    writer.on_write_complete(written_count)
                except Exception as callback_err:
                    logger.warning(f"Write complete callback failed: {callback_err}")

            if written_count > 0:
                logger.debug(
                    "BatchWriter flushed: %s written, %s failed (odds_changes: %s, over_under: %s, odds: %s)",
                    written_count,
                    failed_count,
                    len(all_odds_changes),
                    len(all_over_under),
                    len(odds_batch),
                )

        return total_pending_records(writer)
    except Exception as exc:
        logger.error(f"Error flushing queues: {exc}", exc_info=True)
        return -1


def get_stats_impl(writer: "BatchWriter") -> Dict[str, Any]:
    with writer._stats_lock:
        stats = writer.stats.copy()

    stats.update(
        {
            "odds_changes_queue_size": writer.odds_changes_queue.qsize(),
            "over_under_queue_size": writer.over_under_queue.qsize(),
            "odds_queue_size": writer.odds_queue.qsize(),
            "retry_queue_size": writer._retry_queue.qsize(),
            "total_queue_size": (
                writer.odds_changes_queue.qsize()
                + writer.over_under_queue.qsize()
                + writer.odds_queue.qsize()
                + writer._retry_queue.qsize()
            ),
            "is_running": writer.running,
            "max_queue_size": writer.max_queue_size,
        }
    )

    total_attempted = stats["total_written"] + stats["total_failed"]
    stats["success_rate"] = round(
        (stats["total_written"] / total_attempted * 100) if total_attempted > 0 else 100,
        2,
    )

    return stats


__all__ = [
    "flush_all_impl",
    "get_stats_impl",
    "process_retries_impl",
    "write_batch_with_retry_impl",
]
