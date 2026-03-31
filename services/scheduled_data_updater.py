#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
定时数据更新服务
每日定时执行联赛数据更新、赔率更新和广义实力计算
替代实时监控，减少服务器压力
"""

import os
import sys
import subprocess
from typing import Dict, Any, Optional, TYPE_CHECKING, List
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from core.logger import get_logger
from utils.timezone_utils import now, format_datetime
from application.services.task_health_tracker import get_task_tracker
from services.scheduled_task_actions import (
    run_calculate_strength_task,
    run_update_leagues_task,
    run_update_odds_task,
)

if TYPE_CHECKING:
    from core.runtime import AppRuntime


class ScheduledDataUpdater:
    """
    定时数据更新服务
    
    执行计划：
    - 23:59: 更新所有监控联赛的比赛数据
    - 00:59: 更新赔率数据 (间隔1小时)
    - 01:59: 计算广义实力 (再间隔1小时)
    """
    
    def __init__(self, runtime: Optional['AppRuntime'] = None):
        self.logger = get_logger(self.__class__.__name__)
        self.scheduler = BackgroundScheduler(timezone='Asia/Shanghai')
        self.is_running = False
        self.runtime = runtime
        self.coordinator = runtime.monitoring_coordinator if runtime else None
        
        # 任务状态跟踪
        self.task_status = {
            'leagues_update': {'last_run': None, 'status': 'pending', 'duration': None},
            'odds_update': {'last_run': None, 'status': 'pending', 'duration': None},
            'strength_calculation': {'last_run': None, 'status': 'pending', 'duration': None},
        }
        
        # 项目根目录
        self.project_root = PROJECT_ROOT
        
        # 设置调度器事件监听
        self.scheduler.add_listener(self._job_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
        
        # 注册任务到健康追踪器
        self._register_tasks_to_tracker()
        
        # 配置定时任务
        self._setup_scheduled_tasks()
    
    def _register_tasks_to_tracker(self):
        """注册任务到健康追踪器（供监控仪表板显示）"""
        try:
            tracker = get_task_tracker()
            # 每日联赛数据更新 - 23:59执行，预期24小时一次
            tracker.register_task('daily_leagues_update', '每日联赛数据更新', 
                                  expected_interval_minutes=24*60, max_allowed_delay_minutes=60)
            # 每日赔率更新 - 00:59执行
            tracker.register_task('daily_odds_update', '每日赔率数据更新',
                                  expected_interval_minutes=24*60, max_allowed_delay_minutes=60)
            # 广义实力计算 - 01:00执行
            tracker.register_task('daily_strength_calculation', '每日广义实力计算',
                                  expected_interval_minutes=24*60, max_allowed_delay_minutes=60)
            # daily_data_cleanup 已永久移除（用户选择保留所有历史数据）
            # 确保 Redis 中的残留记录也被清理
            self._cleanup_removed_tasks(tracker)
            self.logger.info("已注册3个定时任务到健康追踪器")
        except Exception as e:
            self.logger.warning(f"注册任务到健康追踪器失败: {e}")

    def _cleanup_removed_tasks(self, tracker):
        """清理已废弃任务在 Redis 中的残留记录"""
        removed_task_ids = ['daily_data_cleanup']
        try:
            import redis as _redis
            r = _redis.Redis(host='localhost', port=6379, decode_responses=True,
                             socket_connect_timeout=1, socket_timeout=1)
            r.ping()
            for task_id in removed_task_ids:
                key = f"oddsmind:task_health:{task_id}"
                if r.exists(key):
                    r.delete(key)
                    self.logger.info("已清理废弃任务 %s 的监控记录", task_id)
        except Exception as e:
            self.logger.debug("清理废弃任务记录时出错: %s", e)
    
    def _setup_scheduled_tasks(self):
        """配置定时任务"""
        try:
            # 任务1: 每日23:59更新联赛数据
            self.scheduler.add_job(
                func=self._update_leagues_task,
                trigger=CronTrigger(hour=23, minute=59, timezone='Asia/Shanghai'),
                id='daily_leagues_update',
                name='每日联赛数据更新',
                max_instances=1,
                coalesce=True
            )
            
            # 任务2: 每日00:59更新赔率数据 (联赛更新后1小时)
            self.scheduler.add_job(
                func=self._update_odds_task,
                trigger=CronTrigger(hour=0, minute=59, timezone='Asia/Shanghai'),
                id='daily_odds_update', 
                name='每日赔率数据更新',
                max_instances=1,
                coalesce=True
            )
            
            # 任务3: 每日01:00计算广义实力 (每天凌晨1点)
            self.scheduler.add_job(
                func=self._calculate_strength_task,
                trigger=CronTrigger(hour=1, minute=0, timezone='Asia/Shanghai'),
                id='daily_strength_calculation',
                name='每日广义实力计算',
                max_instances=1,
                coalesce=True
            )
            
            # 任务4: 每日数据清理 — 已禁用 (用户选择保留所有历史数据)
            # self.scheduler.add_job(
            #     func=self._cleanup_old_data_task,
            #     trigger=CronTrigger(hour=3, minute=0, timezone='Asia/Shanghai'),
            #     id='daily_data_cleanup',
            #     name='每日数据清理',
            #     max_instances=1,
            #     coalesce=True
            # )
            
            self.logger.info("定时任务配置完成")
            
        except Exception as e:
            self.logger.error(f"配置定时任务失败: {e}", exc_info=True)
            raise
    
    def start(self):
        """启动定时任务调度器"""
        if self.is_running:
            self.logger.warning("定时任务调度器已在运行")
            return
        
        try:
            self.scheduler.start()
            self.is_running = True
            self.logger.info("定时数据更新服务已启动")
            self.logger.info("任务计划:")
            self.logger.info("  23:59 - 联赛数据更新")
            self.logger.info("  00:59 - 赔率数据更新")
            self.logger.info("  01:00 - 广义实力计算")
            
            # 输出下次执行时间，便于调试
            jobs = self.scheduler.get_jobs()
            self.logger.info(f"已配置 {len(jobs)} 个定时任务")
            for job in jobs:
                next_run = job.next_run_time
                if next_run:
                    self.logger.info(f"  任务 '{job.name}' (ID: {job.id}) 下次执行: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
                else:
                    self.logger.warning(f"  任务 '{job.name}' (ID: {job.id}) 没有下次执行时间")
            
        except Exception as e:
            self.logger.error(f"启动定时任务调度器失败: {e}", exc_info=True)
            raise
    
    def stop(self):
        """停止定时任务调度器"""
        if not self.is_running:
            self.logger.warning("定时任务调度器未运行")
            return
        
        try:
            # 先检查调度器是否还在运行
            if not self.scheduler.running:
                self.logger.warning("调度器已经关闭")
                self.is_running = False
                return
            
            # 使用 wait=True 等待正在执行的任务完成
            # 但设置较短的超时时间，避免无限等待
            self.scheduler.shutdown(wait=True)
            self.is_running = False
            self.logger.info("定时数据更新服务已停止")
            
        except RuntimeError as e:
            # 如果调度器已经关闭，忽略这个错误
            if "shutdown" in str(e).lower() or "cannot schedule" in str(e).lower():
                self.logger.warning(f"调度器关闭时出现预期错误（可能已关闭）: {e}")
            else:
                self.logger.error(f"停止定时任务调度器失败: {e}", exc_info=True)
            self.is_running = False
        except Exception as e:
            self.logger.error(f"停止定时任务调度器失败: {e}", exc_info=True)
            self.is_running = False
    
    def get_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        try:
            # 检查调度器是否还在运行
            scheduler_running = self.scheduler.running if hasattr(self.scheduler, 'running') else False
            jobs_count = len(self.scheduler.get_jobs()) if scheduler_running else 0
        except (RuntimeError, AttributeError) as e:
            # 如果调度器已关闭，会出现 RuntimeError
            self.logger.warning(f"获取调度器状态时出错（可能已关闭）: {e}")
            scheduler_running = False
            jobs_count = 0
        
        return {
            'is_running': self.is_running and scheduler_running,
            'next_runs': self._get_next_runs() if scheduler_running else {},
            'task_status': self.task_status,
            'scheduler_info': {
                'jobs_count': jobs_count,
                'running': scheduler_running
            }
        }
    
    def _get_next_runs(self) -> Dict[str, str]:
        """获取下次执行时间"""
        next_runs = {}
        try:
            # 检查调度器是否还在运行
            if not self.scheduler.running:
                return next_runs
            
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time
                next_runs[job.id] = next_run.strftime('%Y-%m-%d %H:%M:%S') if next_run else 'N/A'
        except (RuntimeError, AttributeError) as e:
            # 如果调度器已关闭，会出现 RuntimeError
            self.logger.warning(f"获取下次执行时间失败（调度器可能已关闭）: {e}")
        except Exception as e:
            self.logger.error(f"获取下次执行时间失败: {e}")
        
        return next_runs
    
    def _job_listener(self, event):
        """任务执行事件监听器"""
        # 检查调度器是否还在运行，如果已关闭则不再处理事件
        try:
            if not self.scheduler.running:
                return
        except (RuntimeError, AttributeError):
            # 调度器已关闭，忽略事件
            return
        
        job_id = event.job_id
        
        try:
            tracker = get_task_tracker()
            task_name = self._get_task_name_by_job_id(job_id)
            
            if event.exception:
                self.logger.error(f"任务 {job_id} 执行失败: {event.exception}", exc_info=event.exception)
                # 更新任务状态为失败
                if task_name:
                    self.task_status[task_name]['status'] = 'failed'
                # 更新健康追踪器（如果还没有被更新）
                tracker.task_completed(job_id, success=False, error_message=str(event.exception))
            else:
                self.logger.info(f"✅ 任务 {job_id} 执行成功 (执行时间: {format_datetime(now())})")
                # 更新健康追踪器
                duration = self.task_status.get(task_name, {}).get('duration') if task_name else None
                tracker.task_completed(job_id, success=True, duration_seconds=duration)
        except RuntimeError as e:
            # 如果调度器在事件处理过程中关闭，忽略错误
            if "shutdown" in str(e).lower() or "cannot schedule" in str(e).lower():
                self.logger.warning(f"调度器已关闭，忽略任务事件: {job_id}")
            else:
                raise
    
    def _get_task_name_by_job_id(self, job_id: str) -> Optional[str]:
        """根据任务ID获取任务名称"""
        mapping = {
            'daily_leagues_update': 'leagues_update',
            'daily_odds_update': 'odds_update', 
            'daily_strength_calculation': 'strength_calculation',
        }
        return mapping.get(job_id)

    def _ensure_scheduler_running(self, closed_message: str) -> bool:
        """Return True when scheduler is available for task execution."""
        try:
            if not self.scheduler.running:
                self.logger.warning(closed_message)
                return False
        except (RuntimeError, AttributeError):
            self.logger.warning("调度器状态异常，取消执行任务")
            return False
        return True

    def _start_task(self, task_name: str, task_id: str, start_message: str):
        """Mark task as running and notify health tracker."""
        self.logger.info(start_message)
        start_time = now()
        self.task_status[task_name]['last_run'] = start_time
        self.task_status[task_name]['status'] = 'running'
        tracker = get_task_tracker()
        tracker.task_started(task_id)
        return start_time, tracker

    def _finish_task(self, task_name: str, start_time) -> float:
        """Mark task completion and return elapsed seconds."""
        duration = (now() - start_time).total_seconds()
        self.task_status[task_name]['status'] = 'completed'
        self.task_status[task_name]['duration'] = duration
        return duration

    def _mark_task_failed(self, task_name: str) -> None:
        self.task_status[task_name]['status'] = 'failed'

    def _mark_task_timeout(self, task_name: str) -> None:
        self.task_status[task_name]['status'] = 'timeout'

    def _resolve_league_group(self) -> str:
        from config.monitoring_config import MONITOR_ALL_LEAGUES
        return 'all' if MONITOR_ALL_LEAGUES else 'monitored'

    def _resolve_python_command(self, log_when_missing: bool = False) -> str:
        python_cmd = 'python3'
        venv_python = os.path.join(self.project_root, 'venv', 'bin', 'python')
        if os.path.exists(venv_python):
            return venv_python
        if log_when_missing:
            self.logger.info("venv Python不存在 (%s)，使用系统python3", venv_python)
        return python_cmd

    def _run_main_command(
        self,
        command_args: List[str],
        timeout: int,
        *,
        text: bool = True,
        log_when_missing_venv: bool = False,
    ):
        python_cmd = self._resolve_python_command(log_when_missing=log_when_missing_venv)
        cmd = [python_cmd, os.path.join(self.project_root, 'main.py'), *command_args]
        self.logger.info("执行命令: %s", ' '.join(cmd))
        return subprocess.run(
            cmd,
            cwd=self.project_root,
            capture_output=True,
            text=text,
            timeout=timeout,
        )
    
    def _update_leagues_task(self):
        """更新联赛数据任务"""
        return run_update_leagues_task(self)

    def _update_odds_task(self):
        """更新赔率数据任务"""
        return run_update_odds_task(self)

    def _calculate_strength_task(self):
        """计算广义实力任务"""
        return run_calculate_strength_task(self)

    def run_task_manually(self, task_name: str):
        """手动执行指定任务"""
        handlers = {
            'leagues_update': self._update_leagues_task,
            'odds_update': self._update_odds_task,
            'strength_calculation': self._calculate_strength_task,
        }
        if task_name not in handlers:
            raise ValueError(f"无效的任务名称: {task_name}")

        self.logger.info(f"手动执行任务: {task_name}")
        handlers[task_name]()


def get_scheduled_updater(runtime: Optional['AppRuntime'] = None) -> ScheduledDataUpdater:
    """创建定时数据更新器实例。"""
    return ScheduledDataUpdater(runtime=runtime)


def start_scheduled_data_updater(runtime: Optional['AppRuntime'] = None):
    """启动定时数据更新服务"""
    updater = get_scheduled_updater(runtime=runtime)
    updater.start()
    return updater


if __name__ == '__main__':
    # 测试定时任务
    import logging
    logging.basicConfig(level=logging.INFO)
    
    updater = ScheduledDataUpdater()
    updater.start()
    
    try:
        import time
        while True:
            time.sleep(60)
            status = updater.get_status()
            print(f"服务状态: {status}")
    except KeyboardInterrupt:
        print("停止定时任务服务...")
        updater.stop()
