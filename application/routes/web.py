#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Web-facing routes (HTML + legacy JSON endpoints)."""

from __future__ import annotations

import os
from functools import wraps

from flask import Blueprint, jsonify, render_template, request, session, redirect, g
from utils.timezone_utils import now
from utils.performance_monitor import performance_monitor
from utils.cache import cache_get, cache_set, get_cache_key

from application.bootstrap import ensure_initialized
from application.context import get_logger_for, get_runtime
from application.services.analytics import get_match_detail
from application.services.web_match_listing import (
    fetch_public_today_matches,
    fetch_today_matches,
    format_public_today_matches,
    format_today_matches,
    validate_match_status,
)
from application.services.web_match_detail_payloads import (
    build_public_match_detail_pagination_payload,
    build_public_match_detail_payload,
    build_public_match_summary_payload,
)
from application.services.web_ai_analysis import (
    build_ai_analysis_payload,
    build_ai_analysis_v2_payload,
)
from application.services.match_detail_service_provider import get_match_detail_service
from app_security import ErrorHandler, security_required
from auth import login_required

logger = get_logger_for(__name__)
runtime = get_runtime()

match_detail_service = get_match_detail_service()

web_bp = Blueprint('web', __name__)

# 网页访问密码（从环境变量读取，默认值：oddsmind2024）
WEB_ACCESS_PASSWORD = os.environ.get('WEB_ACCESS_PASSWORD', 'oddsmind2024')


def web_password_required(f):
    """网页密码保护装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 检查是否已通过密码验证
        if session.get('web_access_granted'):
            return f(*args, **kwargs)
        
        # 如果是POST请求，验证密码
        if request.method == 'POST':
            password = request.form.get('password', '')
            # 简单的密码验证（可以改为更安全的方式）
            if password == WEB_ACCESS_PASSWORD:
                session['web_access_granted'] = True
                session.permanent = True
                return redirect(request.url)
            else:
                # 密码错误，显示错误信息
                return render_template('password_protected.html', error='密码错误，请重试')
        
        # GET请求，显示密码输入页面
        return render_template('password_protected.html')
    
    return decorated_function


@web_bp.route('/', methods=['GET', 'POST'])
@ensure_initialized
@web_password_required
def index():
    """首页（需要密码验证）"""
    return render_template('index_modern.html')


@web_bp.route('/old', methods=['GET', 'POST'])
@ensure_initialized
@web_password_required
def old_index():
    """旧版首页（需要密码验证）"""
    return render_template('index_new.html')


@web_bp.route('/health', methods=['GET'])
@ensure_initialized
def health_check():
    # 获取任务健康状态（从 Redis 读取，支持跨进程）
    from application.services.task_health_tracker import get_task_tracker, get_service_status
    task_tracker = get_task_tracker()
    task_health = task_tracker.get_health_summary()
    
    # 从 Redis 读取 Worker 服务状态（跨进程共享）
    scheduler_status = get_service_status('scheduler') or {}
    monitor_status = get_service_status('odds_monitor') or {}
    league_monitor_status = get_service_status('league_status_monitor') or {}

    payload = {
        'timestamp': now().isoformat(),
        'services': {
            'web_server': True,
            'scheduler_running': scheduler_status.get('running', False),
            'monitor_running': monitor_status.get('running', False),
            'monitor_matches': monitor_status.get('match_count', 0),
            'league_status_monitor_running': league_monitor_status.get('running', False),
            'league_status_monitor_stats': league_monitor_status.get('stats'),
        },
        'app_initialized': runtime.is_initialised,
        'scheduled_tasks': task_health,
    }
    return jsonify({'success': True, 'data': payload, 'message': 'OK'})


@web_bp.route('/health/tasks', methods=['GET'])
@ensure_initialized
def health_check_tasks():
    """详细的定时任务健康检查接口"""
    from application.services.task_health_tracker import get_task_tracker
    task_tracker = get_task_tracker()
    
    # 获取完整的任务状态
    full_status = task_tracker.get_all_status()
    
    return jsonify({
        'success': True, 
        'data': full_status, 
        'message': 'OK' if full_status['overall_health'] == 'healthy' else f"状态: {full_status['overall_health']}"
    })


@web_bp.route('/monitor', methods=['GET'])
@ensure_initialized
def monitor_dashboard():
    """监控仪表板页面"""
    return render_template('monitor_dashboard.html')


@web_bp.route('/api/matches/today', methods=['GET'])
@performance_monitor
@login_required
@ensure_initialized
def get_today_matches():
    try:
        from config.monitoring_config import (
            MONITORED_LEAGUES,
            MONITORING_DAYS,
            MONITOR_ALL_LEAGUES,
        )

        status_filter = validate_match_status(request.args.get('status', ''), logger)
        logger.debug(f"查询比赛列表（无分页），状态: {status_filter or '全部'}")

        fields_param = request.args.get('fields', '')
        requested_fields = set(fields_param.split(',')) if fields_param else set()

        matches = fetch_today_matches(
            status_filter=status_filter,
            monitored_leagues=MONITORED_LEAGUES,
            monitoring_days=MONITORING_DAYS,
            monitor_all_leagues=MONITOR_ALL_LEAGUES,
        )
        
        # 性能监控：记录数据库查询结束
        if hasattr(g, 'performance_monitor'):
            g.performance_monitor.mark('t_db_end')

        total_count = len(matches)
        logger.debug(f"返回所有 {total_count} 场比赛（无分页）")

        # 性能监控：记录序列化开始
        if hasattr(g, 'performance_monitor'):
            g.performance_monitor.mark('t_serialize_start')

        formatted_matches = format_today_matches(
            matches,
            requested_fields=requested_fields if requested_fields else None,
        )

        # 性能监控：记录序列化结束
        if hasattr(g, 'performance_monitor'):
            g.performance_monitor.mark('t_serialize_end')
        
        return jsonify({
            'success': True, 
            'data': formatted_matches, 
            'total': total_count
        })
    except Exception as exc:
        logger.error("获取今日比赛失败: %s", exc, exc_info=True)
        return jsonify({'success': False, 'error': str(exc)}), 500


@web_bp.route('/api/matches/<int:match_id>', methods=['GET'])
@performance_monitor
@login_required
@security_required(validate_params=True, log_requests=True)
@ensure_initialized
def get_match_detail_route(match_id: int):
    try:
        result = get_match_detail(str(match_id))
        if result['success']:
            return jsonify(result)
        return jsonify(ErrorHandler.handle_not_found_error("比赛")), 404
    except Exception as exc:  # pragma: no cover
        logger.error("获取比赛详情失败: %s", exc, exc_info=True)
        return jsonify(ErrorHandler.handle_generic_error(exc, "获取比赛详情")), 500


@web_bp.route('/api/matches/<int:match_id>/all_analyses', methods=['GET'])
@performance_monitor
@login_required
@security_required(validate_params=True, log_requests=True)
@ensure_initialized
def get_all_match_analyses(match_id: int):
    try:
        analyses = match_detail_service.get_odds_analyses(str(match_id)) or []
        analyses = match_detail_service.sort_analyses_by_priority(list(analyses))
        formatted_results = [
            match_detail_service.format_analysis_data(analysis)
            for analysis in analyses
        ]
        return jsonify({'success': True, 'data': formatted_results})
    except Exception as exc:  # pragma: no cover
        logger.error("获取比赛赔率分析失败: %s", exc, exc_info=True)
        return jsonify({'error': str(exc), 'success': False}), 500



@web_bp.route('/api/public/matches/today', methods=['GET'])
@performance_monitor
@ensure_initialized
def get_public_today_matches():
    """公共今日比赛接口（无需鉴权），用于前端无认证时的回退。"""
    try:
        from config.monitoring_config import (
            MONITORED_LEAGUES,
            MONITORING_DAYS,
            MONITOR_ALL_LEAGUES,
        )

        status_filter = validate_match_status(request.args.get('status', ''), logger)
        logger.debug(f"查询比赛列表（公共API，无分页），状态: {status_filter or '全部'}")
        
        # 构建缓存key（不再包含分页参数）
        cache_key = get_cache_key(
            'matches_today',
            status=status_filter,
            leagues=tuple(MONITORED_LEAGUES) if MONITORED_LEAGUES else 'all'
        )
        
        # 尝试从缓存获取
        cached_result = cache_get(cache_key)
        if cached_result is not None:
            logger.debug("缓存命中: %s", cache_key)
            return jsonify(cached_result)
        
        logger.debug("查询所有比赛（无分页限制）")

        matches = fetch_public_today_matches(
            status_filter=status_filter,
            monitored_leagues=MONITORED_LEAGUES,
            monitoring_days=MONITORING_DAYS,
            monitor_all_leagues=MONITOR_ALL_LEAGUES,
        )
        formatted_matches = format_public_today_matches(matches)

        result = {'success': True, 'data': formatted_matches, 'total': len(formatted_matches)}
        
        # [性能优化] 缓存结果（120秒TTL，提升缓存命中率，减少数据库压力）
        # 今日比赛列表变化不频繁，120秒延迟可接受，显著提升响应速度
        cache_set(cache_key, result, expire=120)
        
        return jsonify(result)
    except Exception as exc:
        logger.error("获取公共今日比赛失败: %s", exc, exc_info=True)
        return jsonify({'success': False, 'error': str(exc)}), 500


@web_bp.route('/api/public/matches/<int:match_id>/pagination', methods=['GET'])
@performance_monitor
@ensure_initialized
def get_public_match_detail_pagination(match_id: int):
    """
    比赛详情分页接口（优化版）
    
    查询参数：
    - type: 加载类型
      * basic: 只返回基本信息 + top公司（默认10家，<15KB）
      * full: 返回全部公司（原有逻辑，~213KB）
    - page: 页码（从1开始，默认1）
    - page_size: 每页公司数量（默认10，最大50）
    - fields: 要返回的字段（可选，逗号分隔）
    
    使用示例：
    1. 首次加载10家公司：?type=basic
    2. 分页加载全部：?type=full&page=1&page_size=50
    3. 字段筛选：?type=basic&fields=matchId,matchTime,oddsAnalysis
    """
    load_type = request.args.get('type', 'basic').lower()  # 默认basic
    try:
        page = max(1, int(request.args.get('page', 1)))
        page_size = min(int(request.args.get('page_size', 10)), 50)  # 默认10，最大50
    except (ValueError, TypeError):
        page = 1
        page_size = 10
    
    fields_param = request.args.get('fields', '')
    requested_fields = set(fields_param.split(',')) if fields_param else None
    
    try:
        payload, status_code = build_public_match_detail_pagination_payload(
            match_id=match_id,
            load_type=load_type,
            page=page,
            page_size=page_size,
            requested_fields=requested_fields,
            match_detail_service=match_detail_service,
        )
        if status_code != 200:
            return jsonify(payload), status_code
        return jsonify(payload)
    
    except Exception as exc:
        logger.error("获取公共比赛详情分页失败: %s", exc, exc_info=True)
        return jsonify(ErrorHandler.handle_generic_error(exc, "获取公共比赛详情分页")), 500


@web_bp.route('/api/public/matches/<int:match_id>', methods=['GET'])
@performance_monitor
@ensure_initialized
def get_public_match_detail_route(match_id: int):
    """
    公共比赛详情接口（无需鉴权）
    
    [已恢复] 返回全部公司数据、泊松预测、态度总结
    
    查询参数:
    - no_cache: 是否跳过缓存（默认false）
    """
    try:
        no_cache = request.args.get('no_cache', 'false').lower() == 'true'
        payload, status_code, headers = build_public_match_detail_payload(
            match_id=match_id,
            no_cache=no_cache,
            match_detail_service=match_detail_service,
            logger=logger,
        )
        response = jsonify(payload)
        for key, value in headers.items():
            response.headers[key] = value
        if status_code != 200:
            return response, status_code
        return response
    except Exception as exc:
        logger.error("获取公共比赛详情失败: %s", exc, exc_info=True)
        return jsonify(ErrorHandler.handle_generic_error(exc, "获取公共比赛详情")), 500


@web_bp.route('/api/public/matches/<int:match_id>/summary', methods=['GET'])
@performance_monitor
@ensure_initialized
def get_public_match_summary(match_id: int):
    """
    公司统计摘要接口（延迟加载）
    用于首屏加载后异步获取公司统计数据
    """
    try:
        payload, headers = build_public_match_summary_payload(
            match_id=match_id,
            match_detail_service=match_detail_service,
        )
        response = jsonify(payload)
        for key, value in headers.items():
            response.headers[key] = value
        return response
    except Exception as exc:
        logger.error("获取公司统计摘要失败: %s", exc, exc_info=True)
        return jsonify({'error': str(exc), 'success': False}), 500


@web_bp.route('/api/matches/<int:match_id>/poisson', methods=['GET'])
@performance_monitor
@login_required
@security_required(validate_params=True, log_requests=True)
@ensure_initialized
def get_match_poisson_prediction(match_id: int):
    """获取比赛的泊松分布预测（延迟加载接口，用于性能优化）"""
    try:
        from application.services.analytics import get_poisson_prediction
        result = get_poisson_prediction(str(match_id))
        if result['success']:
            return jsonify(result)
        return jsonify(ErrorHandler.handle_generic_error(None, "获取泊松预测失败")), 500
    except Exception as exc:
        logger.error("获取泊松预测失败: %s", exc, exc_info=True)
        return jsonify(ErrorHandler.handle_generic_error(exc, "获取泊松预测")), 500


@web_bp.route('/api/public/matches/<int:match_id>/poisson', methods=['GET'])
@performance_monitor
@ensure_initialized
def get_public_match_poisson_prediction(match_id: int):
    """公共泊松预测接口（无需鉴权）"""
    try:
        from application.services.analytics import get_poisson_prediction
        result = get_poisson_prediction(str(match_id))
        if result['success']:
            return jsonify(result)
        return jsonify(ErrorHandler.handle_generic_error(None, "获取泊松预测失败")), 500
    except Exception as exc:
        logger.error("获取公共泊松预测失败: %s", exc, exc_info=True)
        return jsonify(ErrorHandler.handle_generic_error(exc, "获取泊松预测")), 500


@web_bp.route('/api/matches/<int:match_id>/analysis', methods=['GET'])
@security_required(validate_params=True, log_requests=True)
@ensure_initialized
def get_match_analysis(match_id: int):
    """获取比赛分析数据（用于AI推理）"""
    try:
        from application.services.match_analysis_service import get_match_analysis_data
        result = get_match_analysis_data(str(match_id))
        if result['success']:
            return jsonify(result)
        return jsonify(result), 404
    except Exception as exc:
        logger.error("获取比赛分析数据失败: %s", exc, exc_info=True)
        return jsonify({'error': str(exc), 'success': False}), 500


@web_bp.route('/api/matches/<int:match_id>/ai-analysis/check', methods=['GET'])
@security_required(validate_params=True, log_requests=True)
@ensure_initialized
def check_ai_analysis_exists(match_id: int):
    """检查比赛是否已有AI分析结果（不再存储，总是返回不存在）"""
    # 由于不再存储AI分析结果，总是返回不存在，允许每次重新分析
    return jsonify({
        'success': True,
        'exists': False
    })


@web_bp.route('/api/matches/<int:match_id>/ai-analysis', methods=['POST'])
@security_required(validate_params=True, log_requests=True)
@ensure_initialized
def get_ai_analysis(match_id: int):
    """欧赔意图分析（自动化规则引擎）- 不存储结果，每次直接返回"""
    try:
        payload, status_code = build_ai_analysis_payload(
            match_id=match_id,
            request_json=request.json,
            logger=logger,
        )
        if status_code != 200:
            return jsonify(payload), status_code
        return jsonify(payload)
            
    except Exception as exc:
        logger.error("欧赔意图分析失败: %s", exc, exc_info=True)
        return jsonify({'error': str(exc), 'success': False}), 500


@web_bp.route('/api/v2/matches/<int:match_id>/analyze', methods=['POST'])
@security_required(validate_params=True, log_requests=True)
@ensure_initialized
def analyze_odds_intent_v2(match_id: int):
    """欧赔意图分析 v2（增强版）- 不存储结果，每次直接返回"""
    try:
        payload, status_code = build_ai_analysis_v2_payload(
            match_id=match_id,
            request_json=request.json,
        )
        if status_code != 200:
            return jsonify(payload), status_code
        return jsonify(payload)
        
    except Exception as exc:
        logger.error("欧赔意图分析v2失败: %s", exc, exc_info=True)
        return jsonify({'error': str(exc), 'success': False}), 500
__all__ = ['web_bp']
