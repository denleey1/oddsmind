#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Business orchestration for mini-program authentication APIs."""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests

from utils.timezone_utils import now, to_timezone_aware
from utils.jwt_helper import issue_jwt_token
from utils.miniprogram_db import (
    activate_user_with_invite_code_atomic,
    create_user,
    get_invite_code_expires_days,
    get_user_by_openid,
    update_user_login_time,
)


WECHAT_APPID = os.environ.get("WECHAT_APPID", "")
WECHAT_APPSECRET = os.environ.get("WECHAT_APPSECRET", "")


def format_datetime_for_frontend(dt) -> Optional[str]:
    """Format datetime into frontend-friendly local ISO string without timezone marker."""
    if dt is None:
        return None
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo:
            return dt.replace(tzinfo=None).isoformat()
        return dt.isoformat()
    return str(dt)


def get_openid_from_wechat(code: str, logger: Any) -> Dict[str, Any]:
    """Exchange wx.login ``code`` for ``openid`` via WeChat API."""
    if not WECHAT_APPID or not WECHAT_APPSECRET:
        raise ValueError("微信小程序 AppID 或 AppSecret 未配置")

    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {
        "appid": WECHAT_APPID,
        "secret": WECHAT_APPSECRET,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    try:
        logger.info("正在调用微信API获取openid，AppID: %s...", WECHAT_APPID[:10])
        response = requests.get(url, params=params, timeout=5)
        logger.info("微信API响应状态码: %s", response.status_code)

        data = response.json()
        logger.info("微信API返回数据: %s", list(data.keys()))

        if "errcode" in data:
            error_msg = data.get("errmsg", "未知错误")
            error_code = data.get("errcode")
            logger.error("微信API错误: %s - %s", error_code, error_msg)
            raise ValueError(f"微信登录失败: {error_msg} (错误码: {error_code})")

        openid = data.get("openid")
        if not openid:
            logger.error("微信API未返回openid")
            raise ValueError("无法从微信API获取openid")

        logger.info("成功获取openid: %s...", openid[:10])
        return {
            "openid": openid,
            "session_key": data.get("session_key"),
            "unionid": data.get("unionid"),
        }
    except requests.Timeout:
        logger.error("请求微信API超时（5秒）")
        raise ValueError("请求微信API超时，请稍后重试")
    except requests.RequestException as exc:
        logger.error("请求微信API失败: %s", exc, exc_info=True)
        raise ValueError(f"请求微信API失败: {str(exc)}")


def _service_success(data: Dict[str, Any]) -> Dict[str, Any]:
    return {"success": True, "status": 200, "data": data}


def _service_error(message: str, status: int, error_code: Optional[str] = None, **extra) -> Dict[str, Any]:
    payload = {"success": False, "status": status, "message": message}
    if error_code:
        payload["error_code"] = error_code
    if extra:
        payload["extra"] = extra
    return payload


def _normalize_expires_at(expires_at: Any):
    if not expires_at:
        return expires_at
    if isinstance(expires_at, str):
        try:
            expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        except ValueError:
            from dateutil import parser

            expires_at = parser.parse(expires_at)
    elif isinstance(expires_at, datetime) and expires_at.tzinfo is None:
        expires_at = to_timezone_aware(expires_at)
    return expires_at


def login_with_wechat_code(code: str, logger: Any) -> Dict[str, Any]:
    """Execute login flow and return normalized service response."""
    wechat_data = get_openid_from_wechat(code, logger)
    openid = wechat_data.get("openid")
    unionid = wechat_data.get("unionid")

    if not openid:
        return _service_error("无法获取 openid", status=400)

    user = get_user_by_openid(openid)
    if not user:
        user_id = create_user(openid, unionid)
        user = get_user_by_openid(openid)
    else:
        user_id = user["id"]
        if unionid and not user.get("unionid"):
            from app_database import execute_update

            execute_update(
                "UPDATE miniprogram_users SET unionid = %s, last_login_at = NOW() WHERE openid = %s",
                (unionid, openid),
            )
            user["unionid"] = unionid

    is_activated = bool(user.get("is_activated"))
    logger.info(
        "登录检查: openid=%s..., is_activated=%s (原始值: %s, 类型: %s)",
        openid[:10],
        is_activated,
        user.get("is_activated"),
        type(user.get("is_activated")),
    )

    if not is_activated:
        logger.info("用户未激活: openid=%s...", openid[:10])
        expires_at = user.get("expires_at")
        expires_at_str = format_datetime_for_frontend(expires_at)
        return _service_success(
            {
                "openid": openid,
                "is_activated": False,
                "status": "NOT_ACTIVATED",
                "expires_at": expires_at_str,
                "message": "需要激活账号",
            }
        )

    expires_at = _normalize_expires_at(user.get("expires_at"))
    if expires_at:
        now_local = now()
        if expires_at < now_local:
            logger.warning("账号已过期: openid=%s..., expires_at=%s, now=%s", openid[:10], expires_at, now_local)
            expires_at_str = format_datetime_for_frontend(expires_at)
            # 过期用户：先重置激活状态，然后返回"需要激活"，让用户可以输入新激活码
            from app_database import execute_update as _exec_update
            _exec_update(
                "UPDATE miniprogram_users SET is_activated = FALSE WHERE openid = %s",
                (openid,),
            )
            logger.info("已重置过期用户激活状态: openid=%s...", openid[:10])
            return _service_success(
                {
                    "openid": openid,
                    "is_activated": False,
                    "status": "EXPIRED",
                    "expires_at": expires_at_str,
                    "message": "账号已过期，请使用新的激活码续费",
                }
            )

    if not (unionid and not user.get("unionid")):
        update_user_login_time(openid)

    expires_at_str = format_datetime_for_frontend(expires_at)
    token = issue_jwt_token(
        {"user_id": user_id, "openid": openid, "is_activated": True, "expires_at": expires_at_str}
    )

    logger.info("登录成功: openid=%s..., user_id=%s, token_length=%s", openid[:10], user_id, len(token) if token else 0)
    logger.info("用户状态: is_activated=%s, expires_at=%s", user.get("is_activated"), expires_at_str)
    response_data = {
        "token": token,
        "user": {
            "id": user_id,
            "openid": openid,
            "nickname": user.get("nickname"),
            "avatar_url": user.get("avatar_url"),
            "is_activated": True,
            "expires_at": expires_at_str,
        },
    }
    logger.info("登录接口返回数据: token存在=%s, user存在=%s", bool(token), bool(response_data.get("user")))
    return _service_success(response_data)


def activate_with_wechat_code(code: str, invite_code: str, logger: Any) -> Dict[str, Any]:
    """Execute activation flow and return normalized service response."""
    logger.info("开始调用微信API获取openid")
    wechat_data = get_openid_from_wechat(code, logger)
    logger.info("微信API调用成功")
    openid = wechat_data.get("openid")
    unionid = wechat_data.get("unionid")

    if not openid:
        return _service_error("无法获取 openid", status=400)

    user = get_user_by_openid(openid)
    if not user:
        user_id = create_user(openid, unionid)
        user = get_user_by_openid(openid)
    else:
        user_id = user["id"]
        is_activated = bool(user.get("is_activated"))
        logger.info("用户状态检查: openid=%s..., is_activated=%s", openid[:10], is_activated)

        if is_activated:
            # 检查是否已过期 — 过期用户允许用新激活码续费
            expires_at = _normalize_expires_at(user.get("expires_at"))
            if expires_at and expires_at < now():
                logger.info("用户已过期，允许重新激活: openid=%s...", openid[:10])
                # 重置激活状态，允许后续流程继续
                from app_database import execute_update as _exec_update
                _exec_update(
                    "UPDATE miniprogram_users SET is_activated = FALSE WHERE openid = %s",
                    (openid,),
                )
            else:
                logger.warning("用户已激活且未过期，拒绝重复激活: openid=%s...", openid[:10])
                expires_at_str = format_datetime_for_frontend(expires_at)
                return _service_error(
                    "账号已激活，请直接登录",
                    status=400,
                    error_code="ALREADY_ACTIVATED",
                    expires_at=expires_at_str,
                )

    expires_days = get_invite_code_expires_days(invite_code)
    logger.info("邀请码有效期: %s -> %s天", invite_code, expires_days)

    logger.info("开始原子性激活: openid=%s..., invite_code=%s, user_id=%s", openid[:10], invite_code, user_id)
    success, error_msg = activate_user_with_invite_code_atomic(
        openid=openid, invite_code=invite_code, expires_days=expires_days, user_id=user_id
    )
    if not success:
        logger.warning("原子性激活失败: %s, 原因: %s", invite_code, error_msg)
        return _service_error("激活码无效或已失效", status=400, error_code="INVALID_INVITE_CODE")

    logger.info("原子性激活成功: openid=%s..., invite_code=%s", openid[:10], invite_code)
    user = get_user_by_openid(openid)
    expires_at = user.get("expires_at")
    expires_at_str = format_datetime_for_frontend(expires_at)

    token = issue_jwt_token(
        {"user_id": user_id, "openid": openid, "is_activated": True, "expires_at": expires_at_str}
    )
    logger.info("激活成功: openid=%s..., user_id=%s, token_length=%s", openid[:10], user_id, len(token) if token else 0)
    logger.info("用户状态: is_activated=%s, expires_at=%s", user.get("is_activated"), expires_at_str)

    response_data = {
        "token": token,
        "user": {
            "id": user_id,
            "openid": openid,
            "nickname": user.get("nickname"),
            "avatar_url": user.get("avatar_url"),
            "is_activated": True,
            "expires_at": expires_at_str,
        },
    }
    logger.info("激活接口返回数据: token存在=%s, user存在=%s", bool(token), bool(response_data.get("user")))
    return _service_success(response_data)


def renew_with_invite_code(openid: str, invite_code: str, logger: Any) -> Dict[str, Any]:
    """
    续费：已激活用户使用新的邀请码延长有效期。
    续费逻辑：新到期时间 = max(当前到期时间, 现在) + 邀请码天数
    这样用户提前续费不会浪费剩余时间。

    整个操作在单个数据库事务中完成，保证原子性：
    激活码消耗、用户到期时间更新、使用记录写入要么全部成功，要么全部回滚。
    """
    if not openid:
        return _service_error("用户信息无效", status=401)

    user = get_user_by_openid(openid)
    if not user:
        return _service_error("用户不存在", status=404)

    user_id = user["id"]

    expires_days = get_invite_code_expires_days(invite_code)
    logger.info("续费: openid=%s..., invite_code=%s, expires_days=%s", openid[:10], invite_code, expires_days)

    from database.pool import get_connection

    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("START TRANSACTION")

        # 1. 行锁获取邀请码并验证
        cursor.execute("""
            SELECT id, max_uses, used_count, is_active, expires_at, account_expires_days
            FROM invite_codes
            WHERE code = %s FOR UPDATE
        """, (invite_code,))
        invite_info = cursor.fetchone()

        if not invite_info:
            conn.rollback()
            return _service_error("激活码无效或已失效", status=400, error_code="INVALID_INVITE_CODE")

        if isinstance(invite_info, dict):
            invite_id = invite_info['id']
            max_uses = invite_info['max_uses']
            used_count = invite_info['used_count']
            is_active = invite_info['is_active']
            code_expires_at = invite_info['expires_at']
        else:
            invite_id, max_uses, used_count, is_active, code_expires_at, _ = invite_info

        if not is_active:
            conn.rollback()
            return _service_error("激活码无效或已失效", status=400, error_code="INVALID_INVITE_CODE")

        if used_count >= max_uses:
            conn.rollback()
            logger.warning("续费邀请码使用次数已达上限: %s, used=%s/%s", invite_code, used_count, max_uses)
            return _service_error("激活码无效或已失效", status=400, error_code="INVALID_INVITE_CODE")

        if code_expires_at:
            from utils.timezone_utils import to_timezone_aware
            if isinstance(code_expires_at, datetime) and code_expires_at.tzinfo is None:
                code_expires_at = to_timezone_aware(code_expires_at)
            if code_expires_at < now():
                conn.rollback()
                return _service_error("激活码无效或已失效", status=400, error_code="INVALID_INVITE_CODE")

        # 2. 消耗邀请码（在事务内）
        cursor.execute("""
            UPDATE invite_codes
            SET used_count = used_count + 1
            WHERE id = %s AND used_count < max_uses AND is_active = TRUE
        """, (invite_id,))
        if cursor.rowcount != 1:
            conn.rollback()
            return _service_error("激活码无效或已失效", status=400, error_code="INVALID_INVITE_CODE")

        # 3. 计算新到期时间
        current_expires = _normalize_expires_at(user.get("expires_at"))
        now_local = now()
        base_time = max(current_expires, now_local) if current_expires else now_local
        new_expires = base_time + timedelta(days=expires_days)

        # 4. 更新用户到期时间
        cursor.execute(
            "UPDATE miniprogram_users SET expires_at = %s, invite_code_used = %s WHERE openid = %s",
            (new_expires, invite_code, openid),
        )

        # 5. 记录使用历史
        try:
            cursor.execute("""
                INSERT INTO invite_code_usage
                (invite_code_id, invite_code, user_id, openid, account_expires_at)
                VALUES (%s, %s, %s, %s, %s)
            """, (invite_id, invite_code, user_id, openid, new_expires))
        except Exception as e:
            logger.warning("记录续费使用历史失败（不影响续费）: %s", e)

        # 6. 提交事务
        conn.commit()
        logger.info("续费成功: openid=%s..., 新到期时间=%s, 增加%s天", openid[:10], new_expires, expires_days)

    except Exception as e:
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        logger.error("续费事务失败: %s", e, exc_info=True)
        return _service_error("续费失败，请稍后重试", status=500)
    finally:
        if cursor:
            try:
                cursor.close()
            except Exception:
                pass
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    expires_at_str = format_datetime_for_frontend(new_expires)
    token = issue_jwt_token(
        {"user_id": user_id, "openid": openid, "is_activated": True, "expires_at": expires_at_str}
    )

    return _service_success({
        "token": token,
        "user": {
            "id": user_id,
            "openid": openid,
            "nickname": user.get("nickname"),
            "avatar_url": user.get("avatar_url"),
            "is_activated": True,
            "expires_at": expires_at_str,
        },
        "renewed_days": expires_days,
        "message": f"续费成功，增加{expires_days}天",
    })


def get_user_profile(openid: str) -> Dict[str, Any]:
    """Get full user profile by openid as normalized service response."""
    if not openid:
        return _service_error("用户信息无效", status=401)

    user = get_user_by_openid(openid)
    if not user:
        return _service_error("用户不存在", status=404)

    expires_at_str = format_datetime_for_frontend(user.get("expires_at"))
    last_login_at_str = format_datetime_for_frontend(user.get("last_login_at"))
    return _service_success(
        {
            "id": user["id"],
            "openid": user["openid"],
            "nickname": user.get("nickname"),
            "avatar_url": user.get("avatar_url"),
            "is_activated": user.get("is_activated", False),
            "expires_at": expires_at_str,
            "last_login_at": last_login_at_str,
        }
    )


__all__ = [
    "activate_with_wechat_code",
    "format_datetime_for_frontend",
    "get_openid_from_wechat",
    "get_user_profile",
    "login_with_wechat_code",
    "renew_with_invite_code",
]
