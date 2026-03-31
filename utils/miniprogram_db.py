#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
小程序用户和邀请码数据库操作辅助函数
"""

from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from app_database import execute_query, execute_update
from database.pool import get_connection
from utils.timezone_utils import now, to_timezone_aware
import logging

logger = logging.getLogger("miniprogram_db")


def get_user_by_openid(openid: str) -> Optional[Dict[str, Any]]:
    """
    根据 openid 获取用户信息
    
    Args:
        openid: 微信 OpenID
    
    Returns:
        用户信息字典，如果不存在则返回 None
    """
    sql = """
        SELECT id, openid, unionid, nickname, avatar_url, is_activated,
               activated_at, expires_at, invite_code_used, last_login_at,
               created_at, updated_at
        FROM miniprogram_users
        WHERE openid = %s
    """
    results = execute_query(sql, (openid,))
    if results:
        return results[0]
    return None


def create_user(openid: str, unionid: Optional[str] = None,
                nickname: Optional[str] = None, avatar_url: Optional[str] = None) -> int:
    """
    创建新用户
    
    Args:
        openid: 微信 OpenID
        unionid: 微信 UnionID（可选）
        nickname: 用户昵称（可选）
        avatar_url: 头像URL（可选）
    
    Returns:
        用户ID
    """
    sql = """
        INSERT INTO miniprogram_users 
        (openid, unionid, nickname, avatar_url, is_activated)
        VALUES (%s, %s, %s, %s, FALSE)
    """
    execute_update(sql, (openid, unionid, nickname, avatar_url))
    
    # 获取刚创建的用户ID
    user = get_user_by_openid(openid)
    if user:
        logger.info(f"创建用户成功: openid={openid}, id={user['id']}")
        return user['id']
    raise Exception("创建用户失败")


def update_user_login_time(openid: str) -> None:
    """更新用户最后登录时间"""
    sql = "UPDATE miniprogram_users SET last_login_at = NOW() WHERE openid = %s"
    execute_update(sql, (openid,))


def activate_user(openid: str, invite_code: str, expires_days: int = 365) -> bool:
    """
    激活用户账号
    
    Args:
        openid: 微信 OpenID
        invite_code: 使用的邀请码
        expires_days: 账号有效期（天数）
    
    Returns:
        是否成功
    """
    expires_at = now() + timedelta(days=expires_days)
    
    sql = """
        UPDATE miniprogram_users
        SET is_activated = TRUE,
            activated_at = NOW(),
            expires_at = %s,
            invite_code_used = %s
        WHERE openid = %s
    """
    execute_update(sql, (expires_at, invite_code, openid))
    
    logger.info(f"激活用户成功: openid={openid}, invite_code={invite_code}")
    return True


def update_user_info(openid: str, nickname: Optional[str] = None,
                     avatar_url: Optional[str] = None) -> None:
    """更新用户信息"""
    if nickname and avatar_url:
        sql = """
            UPDATE miniprogram_users
            SET nickname = %s, avatar_url = %s
            WHERE openid = %s
        """
        execute_update(sql, (nickname, avatar_url, openid))
    elif nickname:
        sql = "UPDATE miniprogram_users SET nickname = %s WHERE openid = %s"
        execute_update(sql, (nickname, openid))
    elif avatar_url:
        sql = "UPDATE miniprogram_users SET avatar_url = %s WHERE openid = %s"
        execute_update(sql, (avatar_url, openid))


def get_invite_code(code: str) -> Optional[Dict[str, Any]]:
    """
    获取邀请码信息
    
    Args:
        code: 邀请码
    
    Returns:
        邀请码信息，如果不存在或无效则返回 None
    """
    sql = """
        SELECT id, code, created_by, max_uses, used_count, expires_at, 
               account_expires_days, is_active, notes
        FROM invite_codes
        WHERE code = %s
    """
    results = execute_query(sql, (code,))
    if results:
        return results[0]
    return None


def validate_invite_code(code: str):
    """
    验证邀请码是否有效
    
    Args:
        code: 邀请码
    
    Returns:
        (是否有效, 错误信息)
    """
    invite_info = get_invite_code(code)
    
    if not invite_info:
        return False, "邀请码不存在"
    
    if not invite_info['is_active']:
        return False, "邀请码已被禁用"
    
    # 检查使用次数
    if invite_info['used_count'] >= invite_info['max_uses']:
        return False, "邀请码使用次数已达上限"
    
    # 检查过期时间
    if invite_info['expires_at']:
        if now() > to_timezone_aware(invite_info['expires_at']):
            return False, "邀请码已过期"
    
    return True, None


def use_invite_code(code: str) -> bool:
    """
    使用邀请码（增加使用次数）
    
    Args:
        code: 邀请码
    
    Returns:
        是否成功
    """
    conn = None
    cursor = None
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE invite_codes
            SET used_count = used_count + 1
            WHERE code = %s
              AND is_active = TRUE
              AND (expires_at IS NULL OR expires_at > NOW())
              AND used_count < max_uses
        """, (code,))
        if cursor.rowcount != 1:
            conn.rollback()
            logger.warning(f"邀请码不可用或使用次数已达上限: {code}")
            raise ValueError("邀请码不可用或使用次数已达上限")
        conn.commit()
        logger.info(f"使用邀请码成功: {code}")
        return True
    except Exception as exc:
        if conn:
            conn.rollback()
        logger.error(f"使用邀请码失败: {code}, error={exc}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def get_invite_code_expires_days(code: str) -> int:
    """
    获取邀请码对应的账号有效期（天数）
    从数据库中的 account_expires_days 字段读取
    
    Args:
        code: 邀请码
    
    Returns:
        有效期天数（默认365天）
    """
    invite_info = get_invite_code(code)
    if invite_info and invite_info.get('account_expires_days'):
        return int(invite_info['account_expires_days'])
    
    # 默认365天
    return 365


def activate_user_with_invite_code_atomic(
    openid: str,
    invite_code: str,
    expires_days: int,
    user_id: int
) -> tuple[bool, Optional[str]]:
    """
    原子性操作：验证、使用邀请码并激活用户
    使用数据库事务和行锁确保并发安全
    
    Args:
        openid: 微信 OpenID
        invite_code: 邀请码
        expires_days: 账号有效期（天数）
        user_id: 用户ID
    
    Returns:
        (是否成功, 错误信息)
    """
    conn = None
    cursor = None
    try:
        # 从连接池获取连接
        conn = get_connection()
        cursor = conn.cursor()
        
        # 开始事务（MySQL 默认是自动提交的，需要显式开始事务）
        cursor.execute("START TRANSACTION")
        
        # 1. 使用行锁获取邀请码信息（FOR UPDATE 锁定行，防止并发）
        cursor.execute("""
            SELECT id, max_uses, used_count, is_active, expires_at
            FROM invite_codes
            WHERE code = %s FOR UPDATE
        """, (invite_code,))
        
        invite_info = cursor.fetchone()
        if not invite_info:
            conn.rollback()
            return False, "邀请码不存在"
        
        # 转换为字典格式（如果使用 DictCursor）
        if isinstance(invite_info, dict):
            invite_id = invite_info['id']
            max_uses = invite_info['max_uses']
            used_count = invite_info['used_count']
            is_active = invite_info['is_active']
            expires_at = invite_info['expires_at']
        else:
            # 元组格式
            invite_id, max_uses, used_count, is_active, expires_at = invite_info
        
        # 2. 验证邀请码
        if not is_active:
            conn.rollback()
            return False, "邀请码已被禁用"
        
        if used_count >= max_uses:
            conn.rollback()
            logger.warning(f"邀请码使用次数已达上限: {invite_code}, used_count={used_count}, max_uses={max_uses}")
            return False, "邀请码使用次数已达上限"
        
        # 检查邀请码过期时间（使用 Asia/Shanghai 时间）
        if expires_at:
            # 确保有时区信息，假设数据库存储的是本地时间（Asia/Shanghai）
            if isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                expires_at = to_timezone_aware(expires_at)
            
            now_local = now()
            if expires_at < now_local:
                conn.rollback()
                logger.warning(f"邀请码已过期: code={invite_code}, expires_at={expires_at}, now={now_local}")
                return False, "邀请码已过期"
        
        # 3. 使用邀请码（在事务中）
        cursor.execute("""
            UPDATE invite_codes
            SET used_count = used_count + 1
            WHERE id = %s
              AND used_count < max_uses
              AND is_active = TRUE
        """, (invite_id,))
        if cursor.rowcount != 1:
            conn.rollback()
            logger.warning(
                "原子性激活更新邀请码失败: code=%s, invite_id=%s, rowcount=%s",
                invite_code,
                invite_id,
                cursor.rowcount,
            )
            return False, "邀请码使用次数已达上限或已失效"
        
        # 4. 激活用户（只激活未激活的用户，防止重复激活漏洞）
        account_expires_at = now() + timedelta(days=expires_days)
        cursor.execute("""
            UPDATE miniprogram_users
            SET is_activated = TRUE,
                activated_at = NOW(),
                expires_at = %s,
                invite_code_used = %s
            WHERE openid = %s
              AND is_activated = FALSE
        """, (account_expires_at, invite_code, openid))
        
        # 检查是否真的更新了用户
        affected_rows = cursor.rowcount
        if affected_rows == 0:
            # 检查用户是否已激活
            cursor.execute("""
                SELECT is_activated FROM miniprogram_users WHERE openid = %s
            """, (openid,))
            user_info = cursor.fetchone()
            
            conn.rollback()
            
            if user_info:
                if isinstance(user_info, dict):
                    is_activated = user_info.get('is_activated')
                else:
                    is_activated = user_info[0]
                
                if is_activated:
                    logger.warning(f"用户已激活，拒绝重复激活: openid={openid[:10]}...")
                    return False, "用户已激活，不能重复激活"
                else:
                    logger.error(f"激活用户失败: openid={openid[:10]}... 未知原因")
                    return False, "激活失败"
            else:
                logger.error(f"激活用户失败: openid={openid[:10]}... 用户不存在")
                return False, "用户不存在"
        
        logger.info(f"用户激活更新成功: openid={openid[:10]}..., affected_rows={affected_rows}")
        
        # 5. 记录激活码使用历史（在同一个事务内，确保原子性）
        cursor.execute("""
            INSERT INTO invite_code_usage 
            (invite_code_id, invite_code, user_id, openid, account_expires_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (invite_id, invite_code, user_id, openid, account_expires_at))
        
        logger.info(f"激活码使用记录已保存: code={invite_code}, user_id={user_id}, openid={openid[:10]}...")
            
        # 6. 提交事务
        conn.commit()
        logger.info(f"原子性激活成功: openid={openid[:10]}..., invite_code={invite_code}, used_count={used_count + 1}/{max_uses}")
        return True, None
        
    except Exception as e:
        # 回滚事务
        if conn:
            try:
                conn.rollback()
                logger.info("事务已回滚")
            except Exception as rb_e:
                logger.error(f"回滚事务失败: {rb_e}")
        
        logger.error(f"原子性激活失败: {e}", exc_info=True)
        return False, f"激活失败: {str(e)}"
        
    finally:
        # 清理资源
        if cursor:
            try:
                cursor.close()
            except Exception as e:
                logger.error(f"关闭游标失败: {e}")
        
        if conn:
            try:
                conn.close()  # 归还连接池
            except Exception as e:
                logger.error(f"关闭连接失败: {e}")


def record_invite_code_usage(
    invite_code: str,
    user_id: int,
    openid: str,
    account_expires_at: datetime
) -> bool:
    """
    记录激活码使用记录
    
    Args:
        invite_code: 邀请码
        user_id: 用户ID
        openid: 微信OpenID
        account_expires_at: 账号过期时间
    
    Returns:
        是否成功
    """
    # 获取邀请码ID
    invite_info = get_invite_code(invite_code)
    if not invite_info:
        logger.error(f"无法找到邀请码: {invite_code}")
        return False
    
    invite_code_id = invite_info['id']
    
    sql = """
        INSERT INTO invite_code_usage 
        (invite_code_id, invite_code, user_id, openid, account_expires_at)
        VALUES (%s, %s, %s, %s, %s)
    """
    execute_update(sql, (invite_code_id, invite_code, user_id, openid, account_expires_at))
    logger.info(f"记录激活码使用: code={invite_code}, user_id={user_id}, openid={openid[:10]}...")
    return True


def get_invite_code_usage_history(code: str) -> List[Dict[str, Any]]:
    """
    获取激活码使用记录
    
    Args:
        code: 邀请码
    
    Returns:
        使用记录列表
    """
    sql = """
        SELECT u.id, u.invite_code, u.user_id, u.openid, u.account_expires_at, u.used_at,
               mu.nickname, mu.is_activated
        FROM invite_code_usage u
        LEFT JOIN miniprogram_users mu ON u.user_id = mu.id
        WHERE u.invite_code = %s
        ORDER BY u.used_at DESC
    """
    return execute_query(sql, (code,))
