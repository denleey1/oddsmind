#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""性能监控工具：记录请求各阶段耗时"""

from __future__ import annotations

import time
import logging
from functools import wraps
from typing import Callable, Any, Dict
from flask import request, g, make_response

# 使用根logger确保日志能输出
logger = logging.getLogger('performance_monitor')
if not logger.handlers:
    # 如果没有配置handler，使用root logger
    logger = logging.getLogger()


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.timings: Dict[str, float] = {}
        self.start_time: float = 0
    
    def start(self):
        """开始计时"""
        self.timings = {}
        self.start_time = time.time()
        self.timings['t_start'] = self.start_time
    
    def mark(self, name: str):
        """记录时间点"""
        current = time.time()
        if self.timings:
            elapsed = current - self.start_time
            self.timings[name] = elapsed
    
    def get_timings(self) -> Dict[str, float]:
        """获取所有时间点"""
        if self.timings:
            total = time.time() - self.start_time
            self.timings['t_total'] = total
        return self.timings.copy()
    
    def log_timings(self, endpoint: str, status_code: int = 200):
        """记录性能日志"""
        timings = self.get_timings()
        if timings:
            # 计算各阶段耗时
            t_start = timings.get('t_start', 0)
            t_app_start = timings.get('t_app_start', t_start)
            t_app_end = timings.get('t_app_end', t_start)
            t_db = timings.get('t_db', 0)
            t_serialize_start = timings.get('t_serialize_start', t_app_end)
            t_serialize_end = timings.get('t_serialize_end', t_app_end)
            
            # 计算实际耗时（使用相对时间差，而不是绝对时间戳）
            t_total = timings.get('t_total', 0)
            t_app = t_app_end - t_app_start if t_app_end > t_app_start else 0
            t_serialize = t_serialize_end - t_serialize_start if t_serialize_end > t_serialize_start else 0
            
            # 修复：如果时间异常大（可能是时间戳而不是时间差），重新计算
            if t_app > 1000 or t_total > 1000:  # 如果超过1000秒，肯定是计算错误
                # 重新计算：使用当前时间减去开始时间
                current_time = time.time()
                t_total = current_time - self.start_time if self.start_time > 0 else 0
                # 如果t_app异常大，说明t_app_end和t_app_start可能是时间戳而不是相对时间
                if t_app > 1000:
                    t_app = t_total - t_db - t_serialize
                    if t_app < 0:
                        t_app = 0
            
            # 确保时间合理（如果总时间异常大，使用各阶段时间之和）
            if t_total > 100:  # 如果总时间超过100秒，可能计算错误
                t_total = t_app + t_db + t_serialize
            
            logger.info(
                f"PERF [{endpoint}] status={status_code} "
                f"total={t_total:.3f}s "
                f"app={t_app:.3f}s "
                f"db={t_db:.3f}s "
                f"serialize={t_serialize:.3f}s"
            )


def performance_monitor(f: Callable) -> Callable:
    """性能监控装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 初始化性能监控器
        monitor = PerformanceMonitor()
        monitor.start()
        g.performance_monitor = monitor
        
        # 记录应用处理开始时间
        monitor.mark('t_app_start')
        
        try:
            result = f(*args, **kwargs)
            
            # 记录应用处理结束时间
            monitor.mark('t_app_end')

            # 统一将 view 返回值转换为 Flask Response（兼容 (json, status) / (json, status, headers)）
            response = make_response(result)

            # 获取状态码
            status_code = getattr(response, 'status_code', 200) or 200

            # 记录性能日志
            endpoint = request.endpoint or request.path
            timings = monitor.get_timings()
            total_time = timings.get('t_total', 0)
            monitor.log_timings(endpoint, status_code)

            # [性能优化] 添加响应时间头（便于前端和Nginx对齐）
            response.headers['X-Response-Time'] = f"{total_time:.3f}"
            response.headers['X-DB-Time'] = f"{timings.get('t_db', 0):.3f}"

            # 添加响应大小头（对大响应有用）
            try:
                response_size = len(response.get_data())
                response.headers['X-Response-Size'] = str(response_size)
                response.headers['X-Response-Size-KB'] = f"{response_size/1024:.2f}"
            except Exception:
                response_size = None

            # [性能监控] 慢请求告警
            if total_time > 1.0:
                logger.warning(
                    f"⚠️ 慢请求: {endpoint} 耗时 {total_time:.2f}s (阈值: 1.0s) "
                    f"DB时间: {timings.get('t_db', 0):.2f}s "
                    + (f"响应大小: {response_size/1024:.2f}KB" if response_size is not None else "")
                )
            elif total_time > 0.5:
                logger.info(
                    f"🟡 中等请求: {endpoint} 耗时 {total_time:.2f}s "
                    + (f"响应大小: {response_size/1024:.2f}KB" if response_size is not None else "")
                )

            return response
        except Exception as e:
            monitor.mark('t_error')
            endpoint = request.endpoint or request.path
            monitor.log_timings(endpoint, 500)
            raise
    
    return decorated_function


def mark_db_time(func: Callable) -> Callable:
    """数据库查询耗时标记装饰器"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        if hasattr(g, 'performance_monitor'):
            monitor = g.performance_monitor
            db_start = time.time()
            monitor.mark('t_db_start')
            
            try:
                result = func(*args, **kwargs)
                db_end = time.time()
                db_time = db_end - db_start
                if 't_db' in monitor.timings:
                    monitor.timings['t_db'] += db_time
                else:
                    monitor.timings['t_db'] = db_time
                return result
            except Exception as e:
                db_end = time.time()
                db_time = db_end - db_start
                if 't_db' in monitor.timings:
                    monitor.timings['t_db'] += db_time
                else:
                    monitor.timings['t_db'] = db_time
                raise
        else:
            return func(*args, **kwargs)
    
    return wrapper

