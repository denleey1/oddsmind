#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
规则匹配API接口
================
提供规则匹配结果的查询接口

接口列表:
- GET /api/rule-alerts              获取所有规则匹配（可筛选日期）
- GET /api/rule-alerts/today        获取今日规则匹配
- GET /api/rule-alerts/match/<id>   获取指定比赛的规则匹配
- GET /api/rules                    获取所有规则列表
"""
from flask import Blueprint, jsonify, request
from services.rule_match_payload_ops import (
    build_match_alerts_payload,
    build_rule_alerts_payload,
    build_rules_payload,
    build_today_alerts_payload,
)

rule_api = Blueprint('rule_api', __name__)


def _get_db():
    """延迟导入数据库连接，避免在模块加载时初始化"""
    from database.connection import get_connection
    return get_connection()


@rule_api.route('/api/rule-alerts', methods=['GET'])
def get_rule_alerts():
    """获取规则匹配结果
    
    Query params:
        date: 日期过滤 (YYYY-MM-DD)
        prediction: 预测类型过滤 (让方必赢/受让方不输)
        limit: 返回数量限制
    """
    db = _get_db()
    payload = build_rule_alerts_payload(
        db=db,
        date_filter=request.args.get('date'),
        prediction=request.args.get('prediction'),
        limit=request.args.get('limit', 50, type=int),
    )
    return jsonify(payload)


@rule_api.route('/api/rule-alerts/today', methods=['GET'])
def get_today_alerts():
    """获取今日规则匹配（含历史命中率和联赛类型）"""
    db = _get_db()
    return jsonify(build_today_alerts_payload(db))


@rule_api.route('/api/rule-alerts/match/<int:match_id>', methods=['GET'])
def get_match_alerts(match_id):
    """获取指定比赛的规则匹配"""
    db = _get_db()
    return jsonify(build_match_alerts_payload(db, match_id))


@rule_api.route('/api/rules', methods=['GET'])
def get_rules():
    """获取所有精准规则列表（含历史命中率详情）
    
    2026-01-31 更新：基于702场历史比赛验证，去除过拟合规则
    """
    return jsonify(build_rules_payload())


def register_rule_api(app):
    """注册规则API到Flask应用"""
    app.register_blueprint(rule_api)
