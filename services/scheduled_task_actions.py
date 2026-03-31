#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Task action implementations extracted from ScheduledDataUpdater."""

from __future__ import annotations

import subprocess


def run_update_leagues_task(updater) -> None:
    """Execute leagues update task."""
    if not updater._ensure_scheduler_running("调度器已关闭，取消执行联赛数据更新任务"):
        return

    task_name = 'leagues_update'
    task_id = 'daily_leagues_update'
    start_time, _ = updater._start_task(task_name, task_id, "开始执行每日联赛数据更新任务...")

    try:
        league_group = updater._resolve_league_group()

        if updater.coordinator:
            summary = updater.coordinator.update_match_statuses()
            duration = updater._finish_task(task_name, start_time)
            updater.logger.info(
                "联赛数据更新完成(协程) - 耗时: %.1fs, 摘要: %s",
                duration,
                summary,
            )
            return

        result = updater._run_main_command(
            ['scrape-leagues', '--league-group', league_group],
            timeout=3600,
            text=True,
        )
        if result.returncode == 0:
            duration = updater._finish_task(task_name, start_time)
            updater.logger.info("联赛数据更新完成，耗时: %.1f秒", duration)
            if result.stdout:
                updater.logger.debug("输出: %s", result.stdout)
            return

        updater._mark_task_failed(task_name)
        error_msg = f"联赛数据更新失败，返回码: {result.returncode}"
        if result.stderr:
            error_msg += f"，错误: {result.stderr}"
        updater.logger.error(error_msg)
        raise Exception(error_msg)

    except subprocess.TimeoutExpired:
        updater._mark_task_timeout(task_name)
        error_msg = "联赛数据更新超时（超过1小时）"
        updater.logger.error(error_msg)
        raise Exception(error_msg)

    except Exception as exc:
        updater._mark_task_failed(task_name)
        updater.logger.error("联赛数据更新任务执行失败: %s", exc, exc_info=True)
        raise


def run_update_odds_task(updater) -> None:
    """Execute odds update task."""
    if not updater._ensure_scheduler_running("调度器已关闭，取消执行赔率数据更新任务"):
        return

    task_name = 'odds_update'
    task_id = 'daily_odds_update'
    start_time, _ = updater._start_task(task_name, task_id, "开始执行每日赔率数据更新任务...")

    try:
        league_group = updater._resolve_league_group()

        if updater.coordinator:
            summary = updater.coordinator.initialize_monitoring(force=True)
            duration = updater._finish_task(task_name, start_time)
            updater.logger.info(
                "赔率数据更新完成(协程) - 耗时: %.1fs, 摘要: %s",
                duration,
                summary,
            )
            return

        result = updater._run_main_command(
            ['scrape-odds', '--league-group', league_group, '--company-filter', 'all'],
            timeout=7200,
            text=True,
        )
        if result.returncode == 0:
            duration = updater._finish_task(task_name, start_time)
            updater.logger.info("赔率数据更新完成，耗时: %.1f秒", duration)
            if result.stdout:
                updater.logger.debug("输出: %s", result.stdout)
            return

        updater._mark_task_failed(task_name)
        error_msg = f"赔率数据更新失败，返回码: {result.returncode}"
        if result.stderr:
            error_msg += f"，错误: {result.stderr}"
        updater.logger.error(error_msg)
        raise Exception(error_msg)

    except subprocess.TimeoutExpired:
        updater._mark_task_timeout(task_name)
        error_msg = "赔率数据更新超时（超过2小时）"
        updater.logger.error(error_msg)
        raise Exception(error_msg)

    except Exception as exc:
        updater._mark_task_failed(task_name)
        updater.logger.error("赔率数据更新任务执行失败: %s", exc, exc_info=True)
        raise


def run_calculate_strength_task(updater) -> None:
    """Execute generalized strength calculation task."""
    if not updater._ensure_scheduler_running("调度器已关闭，取消执行广义实力计算任务"):
        return

    task_name = 'strength_calculation'
    task_id = 'daily_strength_calculation'
    start_time, tracker = updater._start_task(task_name, task_id, "开始执行每日广义实力计算任务...")

    try:
        league_group = updater._resolve_league_group()

        result = updater._run_main_command(
            ['calculate-strength', '--league-group', league_group, '--max-workers', '4'],
            timeout=3600,
            text=False,
            log_when_missing_venv=True,
        )

        if result.returncode == 0:
            duration = updater._finish_task(task_name, start_time)
            updater.logger.info("广义实力计算完成，耗时: %.1f秒", duration)
            if result.stdout:
                try:
                    stdout_text = result.stdout.decode('utf-8', errors='replace')
                    updater.logger.debug("输出: %s", stdout_text[:2000])
                except Exception:
                    updater.logger.debug("输出内容无法解码")
            tracker.task_completed(task_id, success=True, duration_seconds=duration)
            return

        updater._mark_task_failed(task_name)
        error_msg = f"广义实力计算失败，返回码: {result.returncode}"
        if result.stderr:
            try:
                stderr_text = result.stderr.decode('utf-8', errors='replace')
                error_msg += f"，错误: {stderr_text[:1000]}"
            except Exception:
                error_msg += "，错误内容无法解码"
        updater.logger.error(error_msg)
        tracker.task_completed(task_id, success=False, error_message=error_msg)
        raise Exception(error_msg)

    except subprocess.TimeoutExpired:
        updater._mark_task_timeout(task_name)
        error_msg = "广义实力计算超时（超过1小时）"
        updater.logger.error(error_msg)
        tracker.task_completed(task_id, success=False, error_message=error_msg)
        raise Exception(error_msg)

    except Exception as exc:
        updater._mark_task_failed(task_name)
        updater.logger.error("广义实力计算任务执行失败: %s", exc, exc_info=True)
        tracker.task_completed(task_id, success=False, error_message=str(exc))
        raise


def run_cleanup_old_data_task(updater) -> None:
    """Execute old-data cleanup task."""
    if not updater._ensure_scheduler_running("调度器已关闭，取消执行数据清理任务"):
        return

    task_name = 'data_cleanup'
    task_id = 'daily_data_cleanup'
    start_time, _ = updater._start_task(task_name, task_id, "开始执行每日数据清理任务...")

    try:
        from services.data_cleanup_service import DataCleanupService

        cleanup_service = DataCleanupService()
        result = cleanup_service.cleanup_old_analysis_data(days=30)

        if result['success']:
            duration = updater._finish_task(task_name, start_time)
            updater.logger.info(
                "数据清理完成 - 耗时: %.1fs, "
                "赔率分析删除: %d 条, 基本面分析删除: %d 条, HTML快照删除: %d 个",
                duration,
                result['odds_analysis_deleted'],
                result['fundamental_analysis_deleted'],
                result['html_snapshots_deleted'],
            )
            return

        updater._mark_task_failed(task_name)
        error_msg = f"数据清理失败: {result.get('errors', [])}"
        updater.logger.error(error_msg)
        raise Exception(error_msg)

    except Exception as exc:
        updater._mark_task_failed(task_name)
        updater.logger.error("数据清理任务执行失败: %s", exc, exc_info=True)
        raise


__all__ = [
    "run_calculate_strength_task",
    "run_cleanup_old_data_task",
    "run_update_leagues_task",
    "run_update_odds_task",
]
