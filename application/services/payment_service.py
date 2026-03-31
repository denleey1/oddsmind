#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
微信支付服务模块
负责：微信支付 V3 API 对接、订单管理、支付成功后自动生成邀请码
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import time
import uuid
from base64 import b64decode, b64encode
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app_database import execute_query, execute_update
from tools.manage_invite_codes import create_invite_code
from utils.timezone_utils import now

logger = logging.getLogger("payment_service")

# ============================================================
# 套餐配置
# ============================================================

PLAN_CONFIG = {
    "day": {
        "name": "日卡",
        "account_expires_days": 1,
        "price_cents": int(os.environ.get("PLAN_PRICE_DAY", 900)),
        "description": "1天有效期",
    },
    "week": {
        "name": "周卡",
        "account_expires_days": 7,
        "price_cents": int(os.environ.get("PLAN_PRICE_WEEK", 2900)),
        "description": "7天有效期",
    },
    "month": {
        "name": "月卡",
        "account_expires_days": 30,
        "price_cents": int(os.environ.get("PLAN_PRICE_MONTH", 6900)),
        "description": "30天有效期",
    },
    "year": {
        "name": "年卡",
        "account_expires_days": 365,
        "price_cents": int(os.environ.get("PLAN_PRICE_YEAR", 19900)),
        "description": "365天有效期",
    },
}

# ============================================================
# 微信支付配置
# ============================================================

WXPAY_MCH_ID = os.environ.get("WXPAY_MCH_ID", "")
WXPAY_API_KEY_V3 = os.environ.get("WXPAY_API_KEY_V3", "")
WXPAY_SERIAL_NO = os.environ.get("WXPAY_SERIAL_NO", "")
WXPAY_PRIVATE_KEY_PATH = os.environ.get("WXPAY_PRIVATE_KEY_PATH", "")
WXPAY_NOTIFY_URL = os.environ.get(
    "WXPAY_NOTIFY_URL", "https://lvyinshuzhi.cn/api/payment/notify"
)
# 公众号 appid（用于 JSAPI 支付，与小程序 appid 可能不同）
WXPAY_APPID = os.environ.get("WXPAY_APPID", os.environ.get("WECHAT_APPID", ""))


def _load_private_key() -> Optional[str]:
    """加载商户 API 私钥 PEM 文件内容。"""
    path = WXPAY_PRIVATE_KEY_PATH
    if not path or not os.path.isfile(path):
        logger.warning("微信支付私钥文件未配置或不存在: %s", path)
        return None
    with open(path, "r") as f:
        return f.read()


def _rsa_sign(message: str) -> str:
    """使用商户私钥对消息进行 SHA256WithRSA 签名，返回 Base64 字符串。"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding

    pem = _load_private_key()
    if not pem:
        raise ValueError("私钥未配置，无法签名")
    private_key = serialization.load_pem_private_key(pem.encode(), password=None)
    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return b64encode(signature).decode("utf-8")


def _build_authorization_header(method: str, url_path: str, body: str = "") -> str:
    """构建微信支付 V3 Authorization 请求头。"""
    timestamp = str(int(time.time()))
    nonce_str = uuid.uuid4().hex
    message = f"{method}\n{url_path}\n{timestamp}\n{nonce_str}\n{body}\n"
    signature = _rsa_sign(message)
    return (
        f'WECHATPAY2-SHA256-RSA2048 mchid="{WXPAY_MCH_ID}",'
        f'nonce_str="{nonce_str}",'
        f'signature="{signature}",'
        f'timestamp="{timestamp}",'
        f'serial_no="{WXPAY_SERIAL_NO}"'
    )


# ============================================================
# 订单管理
# ============================================================


def generate_order_no() -> str:
    """生成唯一订单号：时间戳 + 随机串。"""
    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    rand = uuid.uuid4().hex[:8].upper()
    return f"OM{ts}{rand}"


def get_plan_list() -> List[Dict[str, Any]]:
    """返回可购买的套餐列表。"""
    plans = []
    for key, cfg in PLAN_CONFIG.items():
        plans.append(
            {
                "plan_type": key,
                "name": cfg["name"],
                "price_cents": cfg["price_cents"],
                "price_yuan": f"{cfg['price_cents'] / 100:.2f}",
                "description": cfg["description"],
                "account_expires_days": cfg["account_expires_days"],
            }
        )
    return plans


def create_order(plan_type: str, openid: Optional[str] = None) -> Dict[str, Any]:
    """
    创建支付订单。

    Args:
        plan_type: 套餐类型 (day/week/month/year)
        openid: 可选，付款人 openid

    Returns:
        订单信息字典
    """
    if plan_type not in PLAN_CONFIG:
        raise ValueError(f"无效的套餐类型: {plan_type}")

    cfg = PLAN_CONFIG[plan_type]
    order_no = generate_order_no()
    amount_cents = cfg["price_cents"]

    sql = """
        INSERT INTO payment_orders (order_no, openid, plan_type, amount_cents, status)
        VALUES (%s, %s, %s, %s, 'pending')
    """
    execute_update(sql, (order_no, openid, plan_type, amount_cents))
    logger.info("创建订单: order_no=%s, plan=%s, amount=%s分", order_no, plan_type, amount_cents)

    return {
        "order_no": order_no,
        "plan_type": plan_type,
        "plan_name": cfg["name"],
        "amount_cents": amount_cents,
        "amount_yuan": f"{amount_cents / 100:.2f}",
        "description": cfg["description"],
    }


def get_order(order_no: str) -> Optional[Dict[str, Any]]:
    """根据订单号查询订单。"""
    sql = """
        SELECT id, order_no, transaction_id, openid, plan_type,
               amount_cents, status, invite_code, paid_at,
               created_at, updated_at
        FROM payment_orders
        WHERE order_no = %s
    """
    results = execute_query(sql, (order_no,))
    if results:
        return results[0]
    return None


def get_orders_by_openid(openid: str) -> List[Dict[str, Any]]:
    """根据 openid 查询用户所有订单。"""
    sql = """
        SELECT id, order_no, plan_type, amount_cents, status,
               invite_code, paid_at, created_at
        FROM payment_orders
        WHERE openid = %s
        ORDER BY created_at DESC
        LIMIT 50
    """
    return execute_query(sql, (openid,))


def query_order_by_invite_code(invite_code: str) -> Optional[Dict[str, Any]]:
    """根据邀请码反查订单。"""
    sql = """
        SELECT id, order_no, plan_type, amount_cents, status,
               invite_code, paid_at, created_at
        FROM payment_orders
        WHERE invite_code = %s
    """
    results = execute_query(sql, (invite_code,))
    if results:
        return results[0]
    return None


# ============================================================
# 微信支付下单
# ============================================================


def create_wxpay_order_h5(order_no: str, amount_cents: int, description: str,
                          payer_ip: str = "127.0.0.1") -> Dict[str, Any]:
    """
    调用微信支付 H5 下单接口。

    Returns:
        {"h5_url": "...", "order_no": "..."} 或 错误信息
    """
    if not WXPAY_MCH_ID or not WXPAY_API_KEY_V3:
        raise ValueError("微信支付商户配置不完整")

    url_path = "/v3/pay/transactions/h5"
    full_url = f"https://api.mch.weixin.qq.com{url_path}"

    body = {
        "appid": WXPAY_APPID,
        "mchid": WXPAY_MCH_ID,
        "description": f"OddsMind {description}",
        "out_trade_no": order_no,
        "notify_url": WXPAY_NOTIFY_URL,
        "amount": {
            "total": amount_cents,
            "currency": "CNY",
        },
        "scene_info": {
            "payer_client_ip": payer_ip,
            "h5_info": {
                "type": "Wap",
            },
        },
    }

    body_str = json.dumps(body, ensure_ascii=False)
    auth_header = _build_authorization_header("POST", url_path, body_str)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": auth_header,
    }

    try:
        resp = requests.post(full_url, data=body_str.encode("utf-8"), headers=headers, timeout=10)
        logger.info("微信H5下单响应: status=%s", resp.status_code)

        if resp.status_code == 200:
            data = resp.json()
            return {"success": True, "h5_url": data.get("h5_url"), "order_no": order_no}
        else:
            error = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"message": resp.text}
            logger.error("微信H5下单失败: %s", error)
            return {"success": False, "error": error.get("message", "下单失败")}
    except Exception as e:
        logger.error("微信H5下单异常: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


def create_wxpay_order_native(order_no: str, amount_cents: int, description: str) -> Dict[str, Any]:
    """
    调用微信支付 Native 下单接口（扫码支付）。
    返回 code_url，前端生成二维码供用户扫码。

    Returns:
        {"code_url": "weixin://...", "order_no": "..."} 或 错误信息
    """
    if not WXPAY_MCH_ID or not WXPAY_API_KEY_V3:
        raise ValueError("微信支付商户配置不完整")

    url_path = "/v3/pay/transactions/native"
    full_url = f"https://api.mch.weixin.qq.com{url_path}"

    body = {
        "appid": WXPAY_APPID,
        "mchid": WXPAY_MCH_ID,
        "description": f"OddsMind {description}",
        "out_trade_no": order_no,
        "notify_url": WXPAY_NOTIFY_URL,
        "amount": {
            "total": amount_cents,
            "currency": "CNY",
        },
    }

    body_str = json.dumps(body, ensure_ascii=False)
    auth_header = _build_authorization_header("POST", url_path, body_str)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": auth_header,
    }

    try:
        resp = requests.post(full_url, data=body_str.encode("utf-8"), headers=headers, timeout=10)
        logger.info("微信Native下单响应: status=%s", resp.status_code)

        if resp.status_code in (200, 201):
            data = resp.json()
            code_url = data.get("code_url")
            logger.info("Native下单成功: order_no=%s, code_url=%s...", order_no, code_url[:30] if code_url else "None")
            return {"success": True, "code_url": code_url, "order_no": order_no}
        else:
            error = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"message": resp.text}
            logger.error("微信Native下单失败: %s", error)
            return {"success": False, "error": error.get("message", "下单失败"), "detail": error}
    except Exception as e:
        logger.error("微信Native下单异常: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


def create_wxpay_order_jsapi(order_no: str, amount_cents: int, description: str,
                             payer_openid: str) -> Dict[str, Any]:
    """
    调用微信支付 JSAPI 下单接口（公众号/web-view 内支付）。

    Returns:
        {"prepay_id": "...", "pay_params": {...}} 或 错误信息
    """
    if not WXPAY_MCH_ID or not WXPAY_API_KEY_V3:
        raise ValueError("微信支付商户配置不完整")

    url_path = "/v3/pay/transactions/jsapi"
    full_url = f"https://api.mch.weixin.qq.com{url_path}"

    body = {
        "appid": WXPAY_APPID,
        "mchid": WXPAY_MCH_ID,
        "description": f"OddsMind {description}",
        "out_trade_no": order_no,
        "notify_url": WXPAY_NOTIFY_URL,
        "amount": {
            "total": amount_cents,
            "currency": "CNY",
        },
        "payer": {
            "openid": payer_openid,
        },
    }

    body_str = json.dumps(body, ensure_ascii=False)
    auth_header = _build_authorization_header("POST", url_path, body_str)

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": auth_header,
    }

    try:
        resp = requests.post(full_url, data=body_str.encode("utf-8"), headers=headers, timeout=10)
        logger.info("微信JSAPI下单响应: status=%s", resp.status_code)

        if resp.status_code == 200:
            data = resp.json()
            prepay_id = data.get("prepay_id")
            # 构造前端调起支付所需的参数
            pay_params = _build_jsapi_pay_params(prepay_id)
            return {"success": True, "prepay_id": prepay_id, "pay_params": pay_params, "order_no": order_no}
        else:
            error = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {"message": resp.text}
            logger.error("微信JSAPI下单失败: %s", error)
            return {"success": False, "error": error.get("message", "下单失败")}
    except Exception as e:
        logger.error("微信JSAPI下单异常: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


def _build_jsapi_pay_params(prepay_id: str) -> Dict[str, str]:
    """构造 JSAPI 前端调起支付所需的参数（WeixinJSBridge.invoke 使用）。"""
    timestamp = str(int(time.time()))
    nonce_str = uuid.uuid4().hex
    package = f"prepay_id={prepay_id}"
    # 签名字符串
    sign_str = f"{WXPAY_APPID}\n{timestamp}\n{nonce_str}\n{package}\n"
    pay_sign = _rsa_sign(sign_str)

    return {
        "appId": WXPAY_APPID,
        "timeStamp": timestamp,
        "nonceStr": nonce_str,
        "package": package,
        "signType": "RSA",
        "paySign": pay_sign,
    }


# ============================================================
# 微信支付回调签名验证 + 解密
# ============================================================

# 微信支付平台公钥路径（用于验证回调签名）
WXPAY_PLATFORM_CERT_PATH = os.environ.get("WXPAY_PLATFORM_CERT_PATH", "")


def verify_callback_signature(timestamp: str, nonce: str, body: str, signature: str, serial: str) -> bool:
    """
    验证微信支付回调通知的 HTTP 请求头签名，防止伪造回调。

    Args:
        timestamp: Wechatpay-Timestamp 请求头
        nonce: Wechatpay-Nonce 请求头
        body: 请求 body 原文
        signature: Wechatpay-Signature 请求头 (Base64)
        serial: Wechatpay-Serial 请求头 (平台证书序列号)

    Returns:
        签名是否有效
    """
    if not all([timestamp, nonce, body, signature]):
        logger.warning("回调签名验证: 缺少必要参数")
        return False

    # 构造验签字符串
    sign_str = f"{timestamp}\n{nonce}\n{body}\n"

    # 尝试加载微信支付平台证书公钥
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
        from cryptography import x509

        cert_path = WXPAY_PLATFORM_CERT_PATH
        if not cert_path or not os.path.isfile(cert_path):
            # 平台证书未配置，降级为仅依赖 AES-GCM 解密验证
            logger.warning("微信支付平台证书未配置，跳过签名验证（依赖 AES-GCM 解密验证）")
            return True

        with open(cert_path, "rb") as f:
            cert = x509.load_pem_x509_certificate(f.read())
        public_key = cert.public_key()

        sig_bytes = b64decode(signature)
        public_key.verify(
            sig_bytes,
            sign_str.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        logger.info("回调签名验证通过")
        return True

    except Exception as e:
        logger.error("回调签名验证失败: %s", e, exc_info=True)
        return False


def decrypt_callback_resource(nonce: str, ciphertext: str, associated_data: str) -> Dict[str, Any]:
    """
    解密微信支付回调通知中的 resource 字段。
    使用 AEAD_AES_256_GCM 算法。
    """
    key = WXPAY_API_KEY_V3.encode("utf-8")
    nonce_bytes = nonce.encode("utf-8")
    ad = associated_data.encode("utf-8") if associated_data else b""
    data = b64decode(ciphertext)

    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce_bytes, data, ad)
    return json.loads(plaintext.decode("utf-8"))


def handle_payment_notify(body: Dict[str, Any]) -> Tuple[bool, str]:
    """
    处理微信支付回调通知。

    Args:
        body: 回调 JSON body

    Returns:
        (是否成功, 消息)
    """
    event_type = body.get("event_type")
    if event_type != "TRANSACTION.SUCCESS":
        logger.info("收到非成功事件: %s", event_type)
        return True, "OK"

    resource = body.get("resource", {})
    try:
        decrypted = decrypt_callback_resource(
            nonce=resource.get("nonce", ""),
            ciphertext=resource.get("ciphertext", ""),
            associated_data=resource.get("associated_data", ""),
        )
    except Exception as e:
        logger.error("解密回调数据失败: %s", e, exc_info=True)
        return False, "解密失败"

    order_no = decrypted.get("out_trade_no")
    transaction_id = decrypted.get("transaction_id")
    trade_state = decrypted.get("trade_state")

    logger.info("回调解密数据: order_no=%s, transaction_id=%s, state=%s",
                order_no, transaction_id, trade_state)

    if trade_state != "SUCCESS":
        logger.warning("交易状态非SUCCESS: %s", trade_state)
        return True, "OK"

    # 查询订单
    order = get_order(order_no)
    if not order:
        logger.error("回调订单不存在: %s", order_no)
        return False, "订单不存在"

    if order["status"] == "paid":
        logger.info("订单已处理，跳过: %s", order_no)
        return True, "OK"

    # 更新订单状态 + 生成邀请码
    try:
        invite_code = _generate_invite_code_for_order(order)

        sql = """
            UPDATE payment_orders
            SET status = 'paid',
                transaction_id = %s,
                invite_code = %s,
                notify_data = %s,
                paid_at = NOW()
            WHERE order_no = %s AND status = 'pending'
        """
        affected = execute_update(
            sql, (transaction_id, invite_code, json.dumps(decrypted, ensure_ascii=False), order_no)
        )

        if affected == 0:
            logger.warning("订单状态更新失败(可能已被处理): %s", order_no)
            return True, "OK"

        logger.info("支付成功处理完成: order_no=%s, invite_code=%s", order_no, invite_code)
        return True, "OK"

    except Exception as e:
        logger.error("处理支付回调失败: %s", e, exc_info=True)
        return False, str(e)


def _generate_invite_code_for_order(order: Dict[str, Any]) -> str:
    """
    根据订单信息生成对应的邀请码。
    复用现有的 create_invite_code() 逻辑。
    """
    plan_type = order["plan_type"]
    cfg = PLAN_CONFIG.get(plan_type)
    if not cfg:
        raise ValueError(f"未知套餐类型: {plan_type}")

    account_expires_days = cfg["account_expires_days"]

    code = create_invite_code(
        code=None,  # 自动生成
        max_uses=1,
        expires_days=30,  # 邀请码本身 30 天内有效
        account_expires_days=account_expires_days,
        created_by="payment_system",
        notes=f"自动生成-{cfg['name']}-订单{order['order_no']}",
    )

    logger.info("为订单 %s 生成邀请码: %s (有效期 %s 天)",
                order["order_no"], code, account_expires_days)
    return code


# ============================================================
# 模拟支付（开发/测试环境用）
# ============================================================


def simulate_payment_success(order_no: str) -> Dict[str, Any]:
    """
    模拟支付成功（仅用于开发测试）。
    直接将订单标记为已支付并生成邀请码。

    Args:
        order_no: 订单号

    Returns:
        包含邀请码的结果
    """
    order = get_order(order_no)
    if not order:
        return {"success": False, "error": "订单不存在"}

    if order["status"] == "paid":
        return {
            "success": True,
            "order_no": order_no,
            "invite_code": order["invite_code"],
            "message": "订单已支付",
        }

    try:
        invite_code = _generate_invite_code_for_order(order)

        sql = """
            UPDATE payment_orders
            SET status = 'paid',
                transaction_id = %s,
                invite_code = %s,
                paid_at = NOW()
            WHERE order_no = %s AND status = 'pending'
        """
        execute_update(sql, (f"SIM_{order_no}", invite_code, order_no))

        logger.info("模拟支付成功: order_no=%s, invite_code=%s", order_no, invite_code)
        return {
            "success": True,
            "order_no": order_no,
            "invite_code": invite_code,
        }
    except Exception as e:
        logger.error("模拟支付失败: %s", e, exc_info=True)
        return {"success": False, "error": str(e)}


# ============================================================
# 导出
# ============================================================

__all__ = [
    "PLAN_CONFIG",
    "create_order",
    "create_wxpay_order_h5",
    "create_wxpay_order_jsapi",
    "create_wxpay_order_native",
    "decrypt_callback_resource",
    "generate_order_no",
    "get_order",
    "get_orders_by_openid",
    "get_plan_list",
    "handle_payment_notify",
    "query_order_by_invite_code",
    "simulate_payment_success",
]
