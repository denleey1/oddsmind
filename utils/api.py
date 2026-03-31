#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Common helpers for API responses and request validation."""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Type

from flask import jsonify, Request


class JsonValidationError(ValueError):
    """Raised when JSON payload validation fails."""


def success(data: Any = None, message: str = "OK", status: int = 200):
    """Return a standard success response."""
    payload: Dict[str, Any] = {
        "success": True,
        "message": message,
        "data": data,
    }
    return jsonify(payload), status


def error(message: str, *, status: int = 400, data: Any = None, error_code: Optional[str] = None, **kwargs):
    """
    Return a standard error response.
    
    Args:
        message: 错误消息
        status: HTTP 状态码
        data: 额外的数据
        error_code: 错误代码（如 EXPIRED_TOKEN, NOT_ACTIVATED 等）
        **kwargs: 其他字段（如 expires_at 等）
    """
    payload: Dict[str, Any] = {
        "success": False,
        "message": message,
    }
    if data is not None:
        payload["data"] = data
    if error_code is not None:
        payload["error_code"] = error_code
    # 添加其他字段（如 expires_at）
    payload.update(kwargs)
    return jsonify(payload), status


def require_json(request: Request, schema: Mapping[str, Optional[Type]]):
    """Validate JSON payload against a simple {field: type} schema."""
    data = request.get_json(silent=True)
    if data is None:
        raise JsonValidationError("请求缺少有效的 JSON 数据")

    validated: Dict[str, Any] = {}
    for field, expected_type in schema.items():
        if field not in data:
            raise JsonValidationError(f"请求缺少字段 '{field}'")
        value = data[field]
        if expected_type is not None and value is not None and not isinstance(value, expected_type):
            raise JsonValidationError(f"字段 '{field}' 类型应为 {expected_type.__name__}")
        validated[field] = value
    return validated
