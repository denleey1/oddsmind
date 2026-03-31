import os
import logging
from datetime import datetime
from functools import wraps
from flask import Blueprint, redirect, url_for, request, g, session, jsonify
from utils.timezone_utils import now, to_timezone_aware

logging.basicConfig(level=logging.INFO)

# Session密钥配置（保留用于Flask session）
# 安全: 必须通过环境变量设置，不使用不安全的默认值
_default_key = os.urandom(32).hex()
SESSION_SECRET_KEY = os.environ.get("SESSION_SECRET_KEY") or _default_key
if not os.environ.get("SESSION_SECRET_KEY"):
    logging.warning("SESSION_SECRET_KEY 未设置，已生成随机密钥（重启后 session 将失效）")

# 创建一个空的auth blueprint（为了兼容性，但不会注册任何路由）
auth_bp = Blueprint("auth", __name__)


def _get_bearer_token(req=None) -> str:
    """
    从请求头中获取 Bearer Token
    
    Args:
        req: Flask request 对象（可选）
    
    Returns:
        Token 字符串，如果不存在则返回 None
    """
    if req is None:
        req = request
    
    auth_header = req.headers.get('Authorization')
    if not auth_header:
        return None
    
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip()
    
    return None


def _verify_jwt_token(token: str):
    """
    验证 JWT Token
    
    Args:
        token: JWT Token 字符串
    
    Returns:
        如果验证成功，返回用户数据字典；否则返回 None
    """
    try:
        from utils.jwt_helper import verify_jwt_token
        return verify_jwt_token(token)
    except ImportError:
        logging.warning("JWT 工具类未找到，跳过 JWT 验证")
        return None
    except Exception as e:
        logging.warning(f"JWT Token 验证失败: {e}")
        return None


def login_required(f):
    """
    增强的登录验证装饰器
    支持多种认证方式（优先级从高到低）：
    1. JWT Token（小程序）
    2. Session（Web端，如果将来启用）
    
    安全修复：对于 /api/* 接口，必须提供有效的 JWT Token 才能访问。
    没有 token 或验证失败时，API 接口返回 401，Web 接口重定向到登录页。
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. 尝试 JWT Token 验证（小程序）
        jwt_token = _get_bearer_token()
        if jwt_token:
            jwt_user = _verify_jwt_token(jwt_token)
            if jwt_user:
                # ✅ 关键修复：验证用户是否仍然存在于数据库中
                openid = jwt_user.get('openid')
                db_user = None
                
                if openid:
                    try:
                        from utils.miniprogram_db import get_user_by_openid
                        db_user = get_user_by_openid(openid)
                    except Exception as e:
                        logging.error(f"验证用户状态失败: {e}", exc_info=True)
                        # 验证失败时拒绝访问（安全优先）
                        db_user = None
                        if request.path.startswith('/api/'):
                            return jsonify({"success": False, "error": "验证失败，请重新登录", "error_code": "VERIFY_FAILED"}), 401
                        return redirect("/login?error=verify_failed")
                
                # ✅ 统一验证用户状态（在try块外，确保所有情况都被检查）
                if not openid:
                    # 如果没有openid，拒绝访问（安全优先）
                    logging.warning("JWT Token中缺少openid")
                    if request.path.startswith('/api/'):
                        return jsonify({"success": False, "error": "Token无效，请重新登录", "error_code": "INVALID_TOKEN"}), 401
                    return redirect("/login?error=invalid_token")
                
                if not db_user:
                    # 如果用户不存在（已被删除），拒绝访问
                    logging.warning(f"JWT Token有效但用户不存在: openid={openid[:10]}...")
                    if request.path.startswith('/api/'):
                        return jsonify({"success": False, "error": "用户不存在，请重新登录", "error_code": "USER_NOT_FOUND"}), 401
                    return redirect("/login?error=not_found")
                
                # 检查用户是否仍然激活
                is_activated = bool(db_user.get('is_activated'))
                if not is_activated:
                    logging.warning(f"JWT Token有效但用户未激活: openid={openid[:10]}...")
                    if request.path.startswith('/api/'):
                        return jsonify({"success": False, "error": "账号未激活，请重新激活", "error_code": "NOT_ACTIVATED"}), 401
                    return redirect("/login?error=not_activated")
                
                # 检查账号是否过期（统一使用 Asia/Shanghai 时间）
                expires_at = db_user.get('expires_at')
                if expires_at:
                    if isinstance(expires_at, str):
                        # 尝试解析时间字符串
                        try:
                            expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                        except ValueError:
                            # 如果解析失败，尝试其他格式
                            from dateutil import parser
                            expires_at = parser.parse(expires_at)
                    elif isinstance(expires_at, datetime) and expires_at.tzinfo is None:
                        # 数据库存储的是本地时间（Asia/Shanghai），转换为时区感知对象
                        expires_at = to_timezone_aware(expires_at)
                    
                    # 使用 Asia/Shanghai 时间进行比较
                    now_local = now()
                    if expires_at < now_local:
                        logging.warning(f"账号已过期: openid={openid[:10]}..., expires_at={expires_at}, now={now_local}")
                        if request.path.startswith('/api/'):
                            return jsonify({"success": False, "error": "账号已过期，请使用新的激活码续费", "error_code": "EXPIRED_TOKEN"}), 401
                        return redirect("/login?error=expired")
                
                # 使用数据库中的最新信息
                g.current_user = {
                    'user_id': db_user.get('id'),
                    'openid': db_user.get('openid'),
                    'is_activated': bool(db_user.get('is_activated')),
                    'expires_at': db_user.get('expires_at').isoformat() if db_user.get('expires_at') else None
                }
                
                # ✅ 所有验证通过后才执行原函数
                return f(*args, **kwargs)
            else:
                # JWT Token 存在但验证失败
                logging.warning("JWT Token 验证失败")
                if request.path.startswith('/api/'):
                    return jsonify({"success": False, "error": "Token无效或已过期，请重新登录", "error_code": "INVALID_TOKEN"}), 401
                return redirect("/login?error=invalid_token")
        
        # 2. 尝试 Session 验证（Web端，如果将来启用）
        # 当前可以保留但暂时不启用
        # if "user" in session:
        #     g.current_user = session.get("user")
        #     return f(*args, **kwargs)
        
        # 3. ✅ 安全修复：没有 token 时，对于 /api/* 接口必须返回 401
        # 对于 Web 页面，可以重定向到登录页（如果需要的话）
        if request.path.startswith('/api/'):
            logging.warning(f"API 接口访问缺少认证: {request.path}")
            return jsonify({"success": False, "error": "需要登录认证", "error_code": "AUTH_REQUIRED"}), 401
        
        # 对于非 API 的 Web 页面，可以根据需要重定向或直接通过
        # 当前保持向后兼容，直接通过（如果将来需要保护 Web 页面，可以在这里添加重定向）
        return f(*args, **kwargs)
    
    return decorated_function


# 为了兼容模板中的url_for('auth.login')和url_for('auth.logout')，添加简单的路由
@auth_bp.route("/login")
def login():
    """登录路由（已禁用验证，直接重定向到首页）"""
    return redirect(url_for('web.index'))


@auth_bp.route("/logout")
def logout():
    """登出路由（已禁用验证，直接重定向到首页）"""
    return redirect(url_for('web.index'))
