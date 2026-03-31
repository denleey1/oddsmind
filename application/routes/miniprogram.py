#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Mini-program auth routes.

Provides:
- WeChat login
- Invite code activation
- Current user profile
"""

from __future__ import annotations

from typing import Mapping, Optional

from flask import Blueprint, g, request

from application.context import get_logger_for
from application.services.miniprogram_auth import (
    activate_with_wechat_code,
    format_datetime_for_frontend as service_format_datetime_for_frontend,
    get_openid_from_wechat as service_get_openid_from_wechat,
    get_user_profile,
    login_with_wechat_code,
    renew_with_invite_code,
)
from auth import login_required
from utils.api import JsonValidationError, error as api_error, require_json, success as api_success
from utils.performance_monitor import performance_monitor
from utils.rate_limiter import check_and_mark_wechat_code_used, rate_limit

logger = get_logger_for(__name__)

miniprogram_bp = Blueprint("miniprogram", __name__)


def format_datetime_for_frontend(dt) -> Optional[str]:
    """Backward-compatible formatter export for legacy imports."""
    return service_format_datetime_for_frontend(dt)


def get_openid_from_wechat(code: str):
    """Backward-compatible helper export for legacy imports."""
    return service_get_openid_from_wechat(code, logger)


def _emit_service_result(result):
    """Convert normalized service result to legacy API envelope."""
    if result.get("success"):
        return api_success(result.get("data", {}))

    extra = result.get("extra", {})
    return api_error(
        result.get("message", "请求失败"),
        status=result.get("status", 400),
        error_code=result.get("error_code"),
        **extra,
    )


def _parse_json_payload(schema: Mapping[str, type]) -> dict:
    """Parse and validate request JSON using the shared lightweight validator."""
    try:
        return require_json(request, schema)
    except JsonValidationError as exc:
        raise ValueError(str(exc)) from exc


def _check_wechat_code_replay(code: str):
    """Reject duplicate WeChat login code usage."""
    if check_and_mark_wechat_code_used(code):
        return None

    logger.warning("检测到微信 code 重复使用: %s...", code[:10])
    return api_error("登录凭证已失效，请重新登录", status=400)


@miniprogram_bp.route("/api/miniprogram/login", methods=["POST"])
@rate_limit(limit=10, window=60)
@performance_monitor
def miniprogram_login():
    """Mini-program login endpoint."""
    try:
        payload = _parse_json_payload({"code": str})
        code = payload["code"]

        replay_error = _check_wechat_code_replay(code)
        if replay_error is not None:
            return replay_error

        result = login_with_wechat_code(code=code, logger=logger)
        return _emit_service_result(result)
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except Exception as exc:
        logger.error("登录失败: %s", exc, exc_info=True)
        return api_error("登录失败，请稍后重试", status=500)


@miniprogram_bp.route("/api/miniprogram/activate", methods=["POST"])
@rate_limit(limit=5, window=60)
@performance_monitor
def miniprogram_activate():
    """Activate mini-program account with invite code."""
    try:
        payload = _parse_json_payload({"code": str, "invite_code": str})
        code = payload["code"]
        invite_code = payload["invite_code"]

        logger.info("收到激活请求: code=%s..., invite_code=%s", code[:10], invite_code)

        replay_error = _check_wechat_code_replay(code)
        if replay_error is not None:
            return replay_error

        result = activate_with_wechat_code(code=code, invite_code=invite_code, logger=logger)
        return _emit_service_result(result)
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except Exception as exc:
        logger.error("激活失败: %s", exc, exc_info=True)
        return api_error("激活失败，请稍后重试", status=500)


@miniprogram_bp.route("/api/miniprogram/renew", methods=["POST"])
@login_required
@rate_limit(limit=5, window=60)
@performance_monitor
def miniprogram_renew():
    """Renew: extend expiry for already activated users with a new invite code."""
    try:
        payload = _parse_json_payload({"invite_code": str})
        invite_code = payload["invite_code"]

        if not hasattr(g, "current_user") or not g.current_user:
            return api_error("未登录", status=401)

        openid = g.current_user.get("openid")
        logger.info("收到续费请求: openid=%s..., invite_code=%s", openid[:10], invite_code)

        result = renew_with_invite_code(openid=openid, invite_code=invite_code, logger=logger)
        return _emit_service_result(result)
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except Exception as exc:
        logger.error("续费失败: %s", exc, exc_info=True)
        return api_error("续费失败，请稍后重试", status=500)


@miniprogram_bp.route("/api/miniprogram/user", methods=["GET"])
@login_required
@performance_monitor
def miniprogram_get_user():
    """Return the currently authenticated mini-program user profile."""
    try:
        if not hasattr(g, "current_user") or not g.current_user:
            return api_error("未登录", status=401)

        user_data = g.current_user
        openid = user_data.get("openid")
        result = get_user_profile(openid=openid)
        return _emit_service_result(result)
    except Exception as exc:
        logger.error("获取用户信息失败: %s", exc, exc_info=True)
        return api_error("获取用户信息失败", status=500)
