#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Health aggregation helpers extracted from task_health_tracker."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict


def minutes_since_last_run(task, current):
    if task.last_run_time is None:
        return None
    return (current - task.last_run_time).total_seconds() / 60


def next_expected_run(task):
    if task.last_run_time is None:
        return None
    next_run = task.last_run_time + timedelta(minutes=task.expected_interval_minutes)
    return next_run.isoformat()


def calculate_health_status(task, current) -> str:
    if task.last_run_time is None:
        return "unknown"

    minutes_since = minutes_since_last_run(task, current)
    threshold = task.expected_interval_minutes + task.max_allowed_delay_minutes

    if minutes_since > threshold * 2:
        return "critical"
    if minutes_since > threshold:
        return "warning"
    if task.last_error_time and task.last_error_time > task.last_success_time:
        return "warning"
    return "healthy"


def task_status_to_dict(task, current) -> Dict[str, Any]:
    health_status = calculate_health_status(task, current)

    return {
        "task_id": task.task_id,
        "task_name": task.task_name,
        "last_run_time": task.last_run_time.isoformat() if task.last_run_time else None,
        "last_success_time": task.last_success_time.isoformat() if task.last_success_time else None,
        "last_error_time": task.last_error_time.isoformat() if task.last_error_time else None,
        "last_error_message": task.last_error_message,
        "last_duration_seconds": task.last_duration_seconds,
        "run_count": task.run_count,
        "success_count": task.success_count,
        "error_count": task.error_count,
        "expected_interval_minutes": task.expected_interval_minutes,
        "is_running": task.is_running,
        "health_status": health_status,
        "minutes_since_last_run": minutes_since_last_run(task, current),
        "next_expected_run": next_expected_run(task),
    }


def build_tracker_snapshot(current, tasks_status: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    health_statuses = [status["health_status"] for status in tasks_status.values()]

    if not health_statuses:
        overall_health = "unknown"
    elif "critical" in health_statuses:
        overall_health = "critical"
    elif "warning" in health_statuses:
        overall_health = "warning"
    elif "unknown" in health_statuses and len(health_statuses) == health_statuses.count("unknown"):
        overall_health = "unknown"
    else:
        overall_health = "healthy"

    unhealthy_tasks = [
        task_id
        for task_id, status in tasks_status.items()
        if status["health_status"] in ("warning", "critical")
    ]

    return {
        "timestamp": current.isoformat(),
        "overall_health": overall_health,
        "total_tasks": len(tasks_status),
        "healthy_tasks": sum(1 for status in tasks_status.values() if status["health_status"] == "healthy"),
        "warning_tasks": sum(1 for status in tasks_status.values() if status["health_status"] == "warning"),
        "critical_tasks": sum(1 for status in tasks_status.values() if status["health_status"] == "critical"),
        "unhealthy_task_ids": unhealthy_tasks,
        "tasks": tasks_status,
    }


__all__ = [
    "build_tracker_snapshot",
    "calculate_health_status",
    "minutes_since_last_run",
    "next_expected_run",
    "task_status_to_dict",
]
