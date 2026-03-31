#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量写入队列管理器 - [性能优化版]
将数据库写入操作从爬虫线程中分离，使用队列缓冲，由专门的写入线程批量处理

优化点：
1. 添加失败重试机制（最多3次）
2. 队列满时阻塞等待而非丢弃（可配置）
3. 优雅关闭等待队列清空
4. 详细的统计信息和监控
5. 写入确认回调（可选）
"""

import time
import threading
from datetime import datetime
from queue import Queue
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger
from database.models import OddsChangeModel, OverUnderOddsChangeModel
from .batch_writer_flush_ops import (
    flush_all_impl,
    get_stats_impl,
    process_retries_impl,
    write_batch_with_retry_impl,
)
from .batch_writer_queue_ops import (
    enqueue_odds_changes_impl,
    enqueue_odds_impl,
    enqueue_over_under_impl,
    get_queue_depths_impl,
    queues_empty,
    should_flush,
    wait_for_empty_impl,
    wait_for_queue_drain,
)

logger = get_logger(__name__)


class BatchWriter:
    """
    批量写入队列管理器

    [可靠性增强]
    - 失败重试：写入失败自动重试（最多3次）
    - 优雅关闭：stop()时等待队列清空
    - 队列监控：提供详细的统计信息
    """

    def __init__(
        self,
        db_manager,
        batch_size: int = 500,
        flush_interval: float = 2.0,
        max_queue_size: int = 10000,
        max_retries: int = 3,
        block_on_full: bool = False,
        on_write_complete: Optional[Callable[[int], None]] = None,
    ):
        self.db_manager = db_manager
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.max_queue_size = max_queue_size
        self.max_retries = max_retries
        self.block_on_full = block_on_full
        self.on_write_complete = on_write_complete

        self.odds_changes_queue: Queue = Queue(maxsize=max_queue_size)
        self.over_under_queue: Queue = Queue(maxsize=max_queue_size)
        self.odds_queue: Queue = Queue(maxsize=max_queue_size)

        self._retry_queue: Queue = Queue()

        self.writer_thread: Optional[threading.Thread] = None
        self.running = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        self.stats = {
            "total_written": 0,
            "total_failed": 0,
            "total_retried": 0,
            "queue_full_count": 0,
            "last_flush_time": None,
            "flush_count": 0,
            "retry_success": 0,
            "retry_failed": 0,
        }
        self._stats_lock = threading.Lock()

        logger.info(
            "BatchWriter initialized: batch_size=%s, flush_interval=%ss, max_queue_size=%s, max_retries=%s",
            batch_size,
            flush_interval,
            max_queue_size,
            max_retries,
        )

    def start(self):
        """启动写入线程"""
        if self.running:
            logger.warning("BatchWriter is already running")
            return

        self.running = True
        self._stop_event.clear()
        self.writer_thread = threading.Thread(target=self._writer_loop, daemon=True, name="BatchWriter")
        self.writer_thread.start()
        logger.info("BatchWriter started")

    def stop(self, timeout: float = 60.0):
        """
        停止写入线程，等待队列清空

        [可靠性增强] 优雅关闭：
        1. 设置停止标志
        2. 等待队列清空（最多timeout秒）
        3. 最后强制刷新一次
        """
        if not self.running:
            return

        logger.info("Stopping BatchWriter, waiting for queue to drain...")
        self._stop_event.set()
        self.running = False

        wait_for_queue_drain(self, timeout)

        if self.writer_thread:
            self.writer_thread.join(timeout=5.0)

        remaining = self._flush_all()
        if remaining > 0:
            logger.warning("BatchWriter stopped with %s records still pending", remaining)
        else:
            logger.info("BatchWriter stopped gracefully, all data written")

    def enqueue_odds_changes(self, odds_changes: List[OddsChangeModel], block: bool = None) -> bool:
        """将赔率变化数据加入队列"""
        return enqueue_odds_changes_impl(self, odds_changes, block)

    def enqueue_over_under(self, changes: List[OverUnderOddsChangeModel], block: bool = None) -> bool:
        """将大小球赔率变化数据加入队列"""
        return enqueue_over_under_impl(self, changes, block)

    def enqueue_odds(self, match_id: int, odds_data: Dict[str, Any], block: bool = None) -> bool:
        """将赔率数据加入队列"""
        return enqueue_odds_impl(self, match_id, odds_data, block)

    def _writer_loop(self):
        """写入线程主循环"""
        logger.info("BatchWriter thread started")

        last_flush = time.time()

        while self.running or not self._stop_event.is_set():
            try:
                if self._stop_event.is_set() and queues_empty(self):
                    break

                current_time = time.time()
                if should_flush(self, last_flush, current_time):
                    self._flush_all()
                    self._process_retries()
                    last_flush = current_time
                else:
                    time.sleep(0.1)
            except Exception as exc:
                logger.error(f"Error in BatchWriter loop: {exc}", exc_info=True)
                time.sleep(1.0)

        logger.info("BatchWriter thread stopped")

    def _flush_all(self) -> int:
        """刷新所有队列，批量写入数据库"""
        return flush_all_impl(self)

    def _write_batch_with_retry(self, batch_type: str, batch: Any, retry_count: int = 0) -> bool:
        """写入批次数据，失败时加入重试队列"""
        return write_batch_with_retry_impl(self, batch_type, batch, retry_count)

    def _process_retries(self):
        """处理重试队列"""
        process_retries_impl(self)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return get_stats_impl(self)

    def wait_for_empty(self, timeout: float = 60.0) -> bool:
        """等待队列清空"""
        return wait_for_empty_impl(self, timeout)

    def get_queue_depths(self) -> Dict[str, int]:
        """获取各队列深度（用于监控告警）"""
        return get_queue_depths_impl(self)
