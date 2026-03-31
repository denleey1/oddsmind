#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Flask application factory for OddsMind."""

from __future__ import annotations

import os

from flask import Flask
from flask_cors import CORS

from auth import auth_bp, SESSION_SECRET_KEY
from application.bootstrap import (
    configure_app,
    register_after_request,
    auto_initialize,
)
from application.routes.web import web_bp
from application.routes.api import api_bp
from application.routes.miniprogram import miniprogram_bp
from application.routes.payment import payment_bp
from services.rule_match_api import rule_api


def create_app() -> Flask:
    """Construct and configure the Flask application instance."""
    app = Flask(__name__, template_folder='../../templates', static_folder='../../static', static_url_path='/static')
    app.secret_key = SESSION_SECRET_KEY

    configure_app(app)
    register_after_request(app)
    # CORS 安全限制: 只允许已知域名跨域访问
    allowed_origins = os.environ.get("CORS_ORIGINS", "https://oddsmind.top").split(",")
    CORS(app, origins=allowed_origins, supports_credentials=True)

    app.register_blueprint(auth_bp)
    app.register_blueprint(web_bp)
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(miniprogram_bp)
    app.register_blueprint(payment_bp)  # 支付系统
    app.register_blueprint(rule_api)  # 规则匹配API

    # 确保定时任务服务在应用创建时启动（无论是直接运行还是通过gunicorn）
    # auto_initialize()内部有检查机制，确保只初始化一次
    try:
        auto_initialize()
    except Exception as exc:
        # 如果初始化失败，记录日志但不阻止应用启动
        from application.context import get_logger_for
        logger = get_logger_for(__name__)
        logger.error("后台服务初始化失败（应用仍可启动）: %s", exc, exc_info=True)

    return app
