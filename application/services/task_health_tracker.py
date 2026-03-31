#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时任务健康检查探针

功能：
1. 记录每个定时任务的执行状态
2. 检测任务是否超时未执行
3. 提供健康检查API数据
4. 支持告警通知
5. 通过 Redis 实现跨进程状态共享（支持 Web/Worker 分离架构）
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

from core.logger import get_logger
from utils.timezone_utils import now
from .task_health_tracker_health_ops import (
    build_tracker_snapshot,
    calculate_health_status,
    minutes_since_last_run,
    next_expected_run,
    task_status_to_dict,
)
from .task_health_tracker_redis_ops import (
    get_all_task_ids_from_redis_impl,
    get_redis_client,
    get_service_status_impl,
    load_task_from_redis_impl,
    save_task_to_redis_impl,
    update_service_status_impl,
)

_logger = get_logger("TaskHealthTracker")

REDIS_KEY_PREFIX = "oddsmind:task_health:"
REDIS_SERVICE_KEY = "oddsmind:service_status"
REDIS_TTL = 86400


def update_service_status(service_name: str, status: Dict[str, Any]) -> None:
    """更新服务状态到 Redis（供 Worker 进程调用）"""
    redis_client = _get_redis_client()
    update_service_status_impl(redis_client, service_name, status, REDIS_SERVICE_KEY, now, _logger)


def get_service_status(service_name: str) -> Optional[Dict[str, Any]]:
    """获取服务状态（供 Web 进程调用）"""
    redis_client = _get_redis_client()
    return get_service_status_impl(redis_client, service_name, REDIS_SERVICE_KEY, _logger)


@dataclass
class TaskStatus:
    """单个任务的状态"""

    task_id: str
    task_name: str
    last_run_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    last_error_time: Optional[datetime] = None
    last_error_message: Optional[str] = None
    last_duration_seconds: Optional[float] = None
    run_count: int = 0
    success_count: int = 0
    error_count: int = 0
    expected_interval_minutes: int = 60
    max_allowed_delay_minutes: int = 30
    is_running: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return task_status_to_dict(self, now())

    def _calculate_health_status(self, current: datetime) -> str:
        """计算健康状态: healthy, warning, critical, unknown"""
        return calculate_health_status(self, current)

    def _minutes_since_last_run(self, current: datetime) -> Optional[float]:
        """距离上次执行的分钟数"""
        return minutes_since_last_run(self, current)

    def _next_expected_run(self) -> Optional[str]:
        """预计下次执行时间"""
        return next_expected_run(self)


def _get_redis_client():
    """获取 Redis 客户端"""
    return get_redis_client(_logger)


class TaskHealthTracker:
    """
    任务健康追踪器（单例）

    使用 Redis 实现跨进程状态共享，支持 Web/Worker 分离架构
    """

    _instance: Optional["TaskHealthTracker"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "TaskHealthTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._local_tasks: Dict[str, TaskStatus] = {}
        self._task_lock = threading.Lock()
        self._redis = _get_redis_client()
        self._initialized = True
        _logger.info("TaskHealthTracker 初始化完成 (Redis: %s)", "已连接" if self._redis else "未连接")

    def _save_to_redis(self, task: TaskStatus) -> None:
        """保存任务状态到 Redis"""
        save_task_to_redis_impl(self._redis, task, REDIS_KEY_PREFIX, REDIS_TTL, _logger)

    def _load_from_redis(self, task_id: str) -> Optional[TaskStatus]:
        """从 Redis 加载任务状态"""
        return load_task_from_redis_impl(self._redis, task_id, REDIS_KEY_PREFIX, TaskStatus, _logger)

    def _get_all_task_ids_from_redis(self) -> List[str]:
        """从 Redis 获取所有任务 ID"""
        return get_all_task_ids_from_redis_impl(self._redis, REDIS_KEY_PREFIX, _logger)

    def register_task(
        self,
        task_id: str,
        task_name: str,
        expected_interval_minutes: int = 60,
        max_allowed_delay_minutes: int = 30,
    ) -> None:
        """注册一个需要追踪的任务"""
        with self._task_lock:
            existing = self._load_from_redis(task_id)
            if existing:
                self._local_tasks[task_id] = existing
                return

            if task_id not in self._local_tasks:
                task = TaskStatus(
                    task_id=task_id,
                    task_name=task_name,
                    expected_interval_minutes=expected_interval_minutes,
                    max_allowed_delay_minutes=max_allowed_delay_minutes,
                )
                self._local_tasks[task_id] = task
                self._save_to_redis(task)
                _logger.info(f"注册任务追踪: {task_id} ({task_name})")

    def task_started(self, task_id: str) -> None:
        """标记任务开始执行"""
        with self._task_lock:
            task = self._local_tasks.get(task_id) or self._load_from_redis(task_id)
            if task:
                task.is_running = True
                task.last_run_time = now()
                self._local_tasks[task_id] = task
                self._save_to_redis(task)

    def task_completed(
        self,
        task_id: str,
        success: bool = True,
        duration_seconds: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """标记任务执行完成"""
        with self._task_lock:
            task = self._local_tasks.get(task_id) or self._load_from_redis(task_id)
            if not task:
                return

            task.is_running = False
            task.run_count += 1
            task.last_duration_seconds = duration_seconds

            if success:
                task.success_count += 1
                task.last_success_time = now()
                # 成功后清除旧错误信息，避免已恢复的错误一直挂在监控面板上
                task.last_error_message = None
                task.last_error_time = None
            else:
                task.error_count += 1
                task.last_error_time = now()
                task.last_error_message = error_message
                _logger.warning(f"任务 {task_id} 执行失败: {error_message}")

            self._local_tasks[task_id] = task
            self._save_to_redis(task)

    def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取单个任务状态（优先从 Redis 读取）"""
        with self._task_lock:
            task = self._load_from_redis(task_id)
            if task:
                return task.to_dict()
            if task_id in self._local_tasks:
                return self._local_tasks[task_id].to_dict()
            return None

    def get_all_status(self) -> Dict[str, Any]:
        """获取所有任务状态（从 Redis 读取，支持跨进程）"""
        with self._task_lock:
            current = now()
            tasks_status: Dict[str, Dict[str, Any]] = {}

            redis_task_ids = self._get_all_task_ids_from_redis()
            for task_id in redis_task_ids:
                task = self._load_from_redis(task_id)
                if task:
                    tasks_status[task_id] = task.to_dict()

            for task_id, task in self._local_tasks.items():
                if task_id not in tasks_status:
                    tasks_status[task_id] = task.to_dict()

            return build_tracker_snapshot(current, tasks_status)

    def get_health_summary(self) -> Dict[str, Any]:
        """获取简化的健康摘要（适合快速检查）"""
        status = self.get_all_status()
        return {
            "timestamp": status["timestamp"],
            "overall_health": status["overall_health"],
            "total_tasks": status["total_tasks"],
            "healthy": status["healthy_tasks"],
            "warning": status["warning_tasks"],
            "critical": status["critical_tasks"],
            "unhealthy_tasks": status["unhealthy_task_ids"],
        }


_tracker: Optional[TaskHealthTracker] = None


def get_task_tracker() -> TaskHealthTracker:
    """获取任务追踪器单例"""
    global _tracker
    if _tracker is None:
        _tracker = TaskHealthTracker()
    return _tracker


def track_task(
    task_id: str,
    task_name: str,
    expected_interval_minutes: int = 60,
    max_allowed_delay_minutes: int = 30,
):
    """
    装饰器：追踪任务执行状态

    用法:
        @track_task('odds_monitor', '赔率变化监控', expected_interval_minutes=5)
        def monitor_odds_changes():
            ...
    """

    def decorator(func: Callable) -> Callable:
        tracker = get_task_tracker()
        tracker.register_task(
            task_id=task_id,
            task_name=task_name,
            expected_interval_minutes=expected_interval_minutes,
            max_allowed_delay_minutes=max_allowed_delay_minutes,
        )

        @wraps(func)
        def wrapper(*args, **kwargs):
            tracker = get_task_tracker()
            start_time = now()
            tracker.task_started(task_id)

            try:
                result = func(*args, **kwargs)
                duration = (now() - start_time).total_seconds()

                success = True
                error_msg = None
                if isinstance(result, dict) and "error" in result:
                    success = False
                    error_msg = str(result.get("error"))

                tracker.task_completed(
                    task_id=task_id,
                    success=success,
                    duration_seconds=duration,
                    error_message=error_msg,
                )
                return result
            except Exception as exc:
                duration = (now() - start_time).total_seconds()
                tracker.task_completed(
                    task_id=task_id,
                    success=False,
                    duration_seconds=duration,
                    error_message=str(exc),
                )
                raise

        return wrapper

    return decorator


__all__ = [
    "TaskHealthTracker",
    "TaskStatus",
    "get_task_tracker",
    "track_task",
]
