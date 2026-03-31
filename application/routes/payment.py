#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
支付系统路由模块
提供：H5 支付页面渲染、订单创建/查询 API、微信支付回调接口
"""

from __future__ import annotations

import json
import os

from flask import Blueprint, render_template, request, jsonify, redirect, url_for

from application.context import get_logger_for
from application.services.payment_service import (
    PLAN_CONFIG,
    create_order,
    create_wxpay_order_h5,
    create_wxpay_order_jsapi,
    create_wxpay_order_native,
    get_order,
    get_orders_by_openid,
    get_plan_list,
    handle_payment_notify,
    simulate_payment_success,
    verify_callback_signature,
)
from utils.api import error as api_error, success as api_success
from utils.rate_limiter import rate_limit

logger = get_logger_for(__name__)

payment_bp = Blueprint("payment", __name__)

# 是否处于开发/测试模式（允许模拟支付）
DEV_MODE = os.environ.get("PAYMENT_DEV_MODE", "true").lower() in ("true", "1", "yes")


# ============================================================
# H5 页面路由
# ============================================================


@payment_bp.route("/pay/", methods=["GET"])
def payment_page():
    """H5 套餐选择与支付页面。"""
    plans = get_plan_list()
    return render_template(
        "payment/index.html",
        plans=plans,
        dev_mode=DEV_MODE,
    )


@payment_bp.route("/pay/result", methods=["GET"])
def payment_result_page():
    """支付结果页面（展示邀请码）。"""
    order_no = request.args.get("order_no", "")
    order = None
    if order_no:
        order = get_order(order_no)
    return render_template(
        "payment/result.html",
        order=order,
        order_no=order_no,
    )


@payment_bp.route("/pay/my-orders", methods=["GET"])
def my_orders_page():
    """订单查询页面（用户找回邀请码）。"""
    order_no = request.args.get("order_no", "")
    order = None
    if order_no:
        order = get_order(order_no)
    return render_template(
        "payment/my_orders.html",
        order=order,
        order_no=order_no,
    )


# ============================================================
# API 路由
# ============================================================


@payment_bp.route("/api/payment/plans", methods=["GET"])
def api_get_plans():
    """获取可购买的套餐列表。"""
    try:
        plans = get_plan_list()
        return api_success(plans)
    except Exception as e:
        logger.error("获取套餐列表失败: %s", e, exc_info=True)
        return api_error("获取套餐列表失败", status=500)


@payment_bp.route("/api/payment/create-order", methods=["POST"])
@rate_limit(limit=10, window=60)
def api_create_order():
    """
    创建支付订单。

    请求 Body:
        {
            "plan_type": "day|week|month|year"
        }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return api_error("请求缺少 JSON 数据", status=400)

        plan_type = data.get("plan_type")
        if not plan_type or plan_type not in PLAN_CONFIG:
            return api_error("无效的套餐类型", status=400)

        # 1. 创建内部订单
        order = create_order(plan_type=plan_type)
        order_no = order["order_no"]
        amount_cents = order["amount_cents"]
        description = order["plan_name"]

        # 2. 调用微信支付 Native 下单（扫码支付）
        wx_result = create_wxpay_order_native(
            order_no=order_no,
            amount_cents=amount_cents,
            description=description,
        )

        if not wx_result.get("success"):
            # 微信下单失败时仍返回订单信息（支持开发模式模拟支付）
            logger.warning("微信下单失败: %s, 订单号: %s", wx_result.get("error"), order_no)
            return api_success({
                **order,
                "wx_pay": wx_result,
                "dev_mode": DEV_MODE,
            })

        return api_success({
            **order,
            "wx_pay": wx_result,
        })

    except ValueError as e:
        return api_error(str(e), status=400)
    except Exception as e:
        logger.error("创建订单失败: %s", e, exc_info=True)
        return api_error("创建订单失败，请稍后重试", status=500)


@payment_bp.route("/api/payment/notify", methods=["POST"])
def api_payment_notify():
    """
    微信支付异步回调通知。
    微信服务器会 POST JSON 到此接口。
    包含签名验证防止伪造回调。
    """
    try:
        # 获取原始 body 用于签名验证
        raw_body = request.get_data(as_text=True)
        if not raw_body:
            logger.warning("支付回调无数据")
            return jsonify({"code": "FAIL", "message": "无效请求"}), 400

        # 验证微信支付回调签名
        wx_timestamp = request.headers.get("Wechatpay-Timestamp", "")
        wx_nonce = request.headers.get("Wechatpay-Nonce", "")
        wx_signature = request.headers.get("Wechatpay-Signature", "")
        wx_serial = request.headers.get("Wechatpay-Serial", "")

        if not verify_callback_signature(
            timestamp=wx_timestamp,
            nonce=wx_nonce,
            body=raw_body,
            signature=wx_signature,
            serial=wx_serial,
        ):
            logger.warning("支付回调签名验证失败，拒绝请求")
            return jsonify({"code": "FAIL", "message": "签名验证失败"}), 401

        body = request.get_json(silent=True)
        if not body:
            logger.warning("支付回调 JSON 解析失败")
            return jsonify({"code": "FAIL", "message": "无效请求"}), 400

        logger.info("收到支付回调: event_type=%s", body.get("event_type"))

        ok, msg = handle_payment_notify(body)
        if ok:
            return jsonify({"code": "SUCCESS", "message": "OK"}), 200
        else:
            return jsonify({"code": "FAIL", "message": msg}), 500

    except Exception as e:
        logger.error("处理支付回调异常: %s", e, exc_info=True)
        return jsonify({"code": "FAIL", "message": "处理失败"}), 500


@payment_bp.route("/api/payment/query/<order_no>", methods=["GET"])
def api_query_order(order_no):
    """查询订单状态（前端轮询用）。"""
    try:
        order = get_order(order_no)
        if not order:
            return api_error("订单不存在", status=404)

        # 格式化时间字段
        result = {
            "order_no": order["order_no"],
            "plan_type": order["plan_type"],
            "amount_cents": order["amount_cents"],
            "status": order["status"],
            "invite_code": order.get("invite_code"),
            "paid_at": order["paid_at"].isoformat() if order.get("paid_at") else None,
            "created_at": order["created_at"].isoformat() if order.get("created_at") else None,
        }
        return api_success(result)

    except Exception as e:
        logger.error("查询订单失败: %s", e, exc_info=True)
        return api_error("查询失败", status=500)


@payment_bp.route("/api/payment/simulate-pay", methods=["POST"])
@rate_limit(limit=5, window=60)
def api_simulate_pay():
    """
    模拟支付（仅开发模式可用）。
    直接将订单标记为已支付并生成邀请码。
    """
    if not DEV_MODE:
        return api_error("此接口仅在开发模式下可用", status=403)

    try:
        data = request.get_json(silent=True)
        if not data or not data.get("order_no"):
            return api_error("请提供 order_no", status=400)

        order_no = data["order_no"]
        result = simulate_payment_success(order_no)

        if result.get("success"):
            return api_success(result)
        else:
            return api_error(result.get("error", "模拟支付失败"), status=400)

    except Exception as e:
        logger.error("模拟支付失败: %s", e, exc_info=True)
        return api_error("模拟支付失败", status=500)
