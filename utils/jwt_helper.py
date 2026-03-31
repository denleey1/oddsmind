#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
JWT Token 工具类
用于生成、验证和刷新 JWT Token
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import jwt
from utils.timezone_utils import now, to_timezone_aware, to_utc

logger = logging.getLogger(__name__)

# JWT 配置
JWT_SECRET = os.environ.get('JWT_SECRET', '')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRATION_DAYS = 7  # Token 有效期（天）


def get_jwt_secret() -> str:
    """获取 JWT 密钥"""
    if not JWT_SECRET:
        logger.warning("JWT_SECRET 未配置，使用默认密钥（仅用于开发环境）")
        return "default_secret_key_change_in_production"
    return JWT_SECRET


def issue_jwt_token(user_data: Dict[str, Any]) -> str:
    """
    生成 JWT Token
    
    Args:
        user_data: 用户数据字典，包含：
            - user_id: 用户ID
            - openid: 微信OpenID
            - is_activated: 是否已激活
            - expires_at: 账号过期时间（ISO格式字符串）
    
    Returns:
        JWT Token 字符串
    """
    secret = get_jwt_secret()
    
    # Token 过期时间应该取 min(账号过期时间, 7天后)
    # 使用 Asia/Shanghai 时间
    token_max_exp = now() + timedelta(days=JWT_EXPIRATION_DAYS)
    
    account_expires_at_str = user_data.get('expires_at')
    if account_expires_at_str:
        try:
            account_expires_at = datetime.fromisoformat(account_expires_at_str.replace('Z', '+00:00'))
            # 确保有时区信息，假设数据库存储的是本地时间（Asia/Shanghai）
            if account_expires_at.tzinfo is None:
                account_expires_at = to_timezone_aware(account_expires_at)
            else:
                # 如果有时区信息，转换为本地时区
                from utils.timezone_utils import to_local
                account_expires_at = to_local(account_expires_at)
            
            # Token 过期时间取两者最小值
            exp = min(account_expires_at, token_max_exp)
            logger.info(f"Token 过期时间: account_exp={account_expires_at}, token_max_exp={token_max_exp}, final_exp={exp}")
        except (ValueError, AttributeError) as e:
            logger.warning(f"解析账号过期时间失败: {e}，使用默认 Token 过期时间")
            exp = token_max_exp
    else:
        exp = token_max_exp
    
    # 构建 payload
    # JWT的exp和iat字段使用UTC时间戳（Unix时间戳），但我们在代码中使用本地时间
    current_time = now()
    payload = {
        'user_id': user_data.get('user_id'),
        'openid': user_data.get('openid'),
        'is_activated': user_data.get('is_activated', False),
        'expires_at': user_data.get('expires_at'),  # 账号过期时间（用于双重检查）
        'iat': int(to_utc(current_time).timestamp()),  # 签发时间（UTC时间戳）
        'exp': int(to_utc(exp).timestamp())  # Token 过期时间（UTC时间戳）
    }
    
    try:
        token = jwt.encode(payload, secret, algorithm=JWT_ALGORITHM)
        return token
    except Exception as e:
        logger.error(f"生成 JWT Token 失败: {e}")
        raise


def verify_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """
    验证 JWT Token
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        如果验证成功，返回用户数据字典；否则返回 None
    """
    secret = get_jwt_secret()
    
    try:
        # 解码 Token
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        
        # 检查账号是否过期（账号过期时间由邀请码决定，统一使用 Asia/Shanghai 时间）
        expires_at_str = payload.get('expires_at')
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str.replace('Z', '+00:00'))
                # 确保有时区信息，假设数据库存储的是本地时间（Asia/Shanghai）
                if expires_at.tzinfo is None:
                    expires_at = to_timezone_aware(expires_at)
                else:
                    # 如果有时区信息，转换为本地时区
                    from utils.timezone_utils import to_local
                    expires_at = to_local(expires_at)
                
                # 使用 Asia/Shanghai 时间进行比较
                now_local = now()
                if expires_at < now_local:
                    logger.warning(f"账号已过期: expires_at={expires_at}, now={now_local}")
                    return None
            except (ValueError, AttributeError) as e:
                logger.warning(f"解析账号过期时间失败: {e}")
        
        # 返回用户数据
        return {
            'user_id': payload.get('user_id'),
            'openid': payload.get('openid'),
            'is_activated': payload.get('is_activated', False),
            'expires_at': payload.get('expires_at'),
            'iat': payload.get('iat'),
            'exp': payload.get('exp')
        }
    
    except jwt.ExpiredSignatureError:
        logger.warning("JWT Token 已过期")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"JWT Token 无效: {e}")
        return None
    except Exception as e:
        logger.error(f"验证 JWT Token 时发生错误: {e}")
        return None


def refresh_jwt_token(token: str) -> Optional[str]:
    """
    刷新 JWT Token（如果 Token 仍然有效）
    
    Args:
        token: 当前的 JWT Token
    
    Returns:
        新的 JWT Token，如果原 Token 无效则返回 None
    """
    user_data = verify_jwt_token(token)
    if not user_data:
        return None
    
    # 重新生成 Token
    return issue_jwt_token(user_data)


def extract_token_from_header(auth_header: Optional[str]) -> Optional[str]:
    """
    从 Authorization header 中提取 Bearer Token
    
    Args:
        auth_header: Authorization header 值，格式: "Bearer <token>"
    
    Returns:
        Token 字符串，如果格式不正确则返回 None
    """
    if not auth_header:
        return None
    
    try:
        # 检查是否是 Bearer Token
        if auth_header.startswith('Bearer '):
            return auth_header[7:].strip()
        return None
    except Exception as e:
        logger.warning(f"提取 Token 失败: {e}")
        return None

