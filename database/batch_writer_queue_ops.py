#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Queue protocol helpers extracted from BatchWriter."""

from __future__ import annotations

import time
from queue import Empty, Full
from typing import TYPE_CHECKING, Any, Dict, List, Tuple

from core.logger import get_logger

if TYPE_CHECKING:
    from .batch_writer import BatchWriter

logger = get_logger(__name__)


def queues_empty(writer: "BatchWriter") -> bool:
    return (
        writer.odds_changes_queue.empty()
        and writer.over_under_queue.empty()
        and writer.odds_queue.empty()
        and writer._retry_queue.empty()
    )


def wait_for_queue_drain(writer: "BatchWriter", timeout: float) -> None:
    start = time.time()
    while (time.time() - start) < timeout:
        if queues_empty(writer):
            break
        time.sleep(0.5)


def enqueue_odds_changes_impl(
    writer: "BatchWriter",
    odds_changes: List[Any],
    block: bool = None,
) -> bool:
    if not odds_changes:
        return True

    should_block = block if block is not None else writer.block_on_full

    try:
        if should_block:
            writer.odds_changes_queue.put(odds_changes, block=True, timeout=30.0)
        else:
            writer.odds_changes_queue.put_nowait(odds_changes)
        return True
    except Full:
        with writer._stats_lock:
            writer.stats["queue_full_count"] += 1
        logger.warning("Odds changes queue is full, dropping %s records", len(odds_changes))
        return False
    except Exception as exc:
        logger.error(f"Failed to enqueue odds changes: {exc}")
        return False


def enqueue_over_under_impl(
    writer: "BatchWriter",
    changes: List[Any],
    block: bool = None,
) -> bool:
    if not changes:
        return True

    should_block = block if block is not None else writer.block_on_full

    try:
        if should_block:
            writer.over_under_queue.put(changes, block=True, timeout=30.0)
        else:
            writer.over_under_queue.put_nowait(changes)
        return True
    except Full:
        with writer._stats_lock:
            writer.stats["queue_full_count"] += 1
        logger.warning("Over/under queue is full, dropping %s records", len(changes))
        return False
    except Exception as exc:
        logger.error(f"Failed to enqueue over_under changes: {exc}")
        return False


def enqueue_odds_impl(
    writer: "BatchWriter",
    match_id: int,
    odds_data: Dict[str, Any],
    block: bool = None,
) -> bool:
    should_block = block if block is not None else writer.block_on_full

    try:
        if should_block:
            writer.odds_queue.put((match_id, odds_data), block=True, timeout=30.0)
        else:
            writer.odds_queue.put_nowait((match_id, odds_data))
        return True
    except Full:
        with writer._stats_lock:
            writer.stats["queue_full_count"] += 1
        logger.warning("Odds queue is full, dropping match %s", match_id)
        return False
    except Exception as exc:
        logger.error(f"Failed to enqueue odds payload: {exc}")
        return False


def should_flush(writer: "BatchWriter", last_flush: float, current_time: float) -> bool:
    return (
        (current_time - last_flush) >= writer.flush_interval
        or writer.odds_changes_queue.qsize() >= writer.batch_size
        or writer.over_under_queue.qsize() >= writer.batch_size
        or writer.odds_queue.qsize() >= writer.batch_size
        or not writer._retry_queue.empty()
    )


def collect_flush_payload(writer: "BatchWriter") -> Tuple[List[Any], List[Any], Dict[int, Any]]:
    all_odds_changes: List[Any] = []
    all_over_under: List[Any] = []
    odds_batch: Dict[int, Any] = {}

    while True:
        try:
            odds_changes = writer.odds_changes_queue.get_nowait()
            if isinstance(odds_changes, list):
                all_odds_changes.extend(odds_changes)
        except Empty:
            break

    while True:
        try:
            over_under = writer.over_under_queue.get_nowait()
            if isinstance(over_under, list):
                all_over_under.extend(over_under)
        except Empty:
            break

    while True:
        try:
            match_id, odds_data = writer.odds_queue.get_nowait()
            odds_batch[match_id] = odds_data
        except Empty:
            break

    return all_odds_changes, all_over_under, odds_batch


def total_pending_records(writer: "BatchWriter") -> int:
    return writer.odds_changes_queue.qsize() + writer.over_under_queue.qsize() + writer.odds_queue.qsize()


def wait_for_empty_impl(writer: "BatchWriter", timeout: float = 60.0) -> bool:
    start_time = time.time()
    while time.time() - start_time < timeout:
        if queues_empty(writer):
            return True
        time.sleep(0.5)
    return False


def get_queue_depths_impl(writer: "BatchWriter") -> Dict[str, int]:
    return {
        "odds_changes": writer.odds_changes_queue.qsize(),
        "over_under": writer.over_under_queue.qsize(),
        "odds": writer.odds_queue.qsize(),
        "retry": writer._retry_queue.qsize(),
    }


__all__ = [
    "collect_flush_payload",
    "enqueue_odds_changes_impl",
    "enqueue_odds_impl",
    "enqueue_over_under_impl",
    "get_queue_depths_impl",
    "queues_empty",
    "should_flush",
    "total_pending_records",
    "wait_for_empty_impl",
    "wait_for_queue_drain",
]
