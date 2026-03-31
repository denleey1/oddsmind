#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
应用安全和错误处理模块
提供统一的安全验证、错误处理和日志记录功能
"""
import re
import traceback
from typing import Any, Dict, List, Optional, Callable, Union
from functools import wraps
from flask import request, jsonify
from datetime import datetime

from core.logger import get_logger

logger = get_logger(__name__)


class SecurityValidator:
    """安全验证器"""
    
    # SQL注入检测模式
    SQL_INJECTION_PATTERNS = [
        r"(\s*(union|select|insert|update|delete|drop|create|alter|exec|execute)\s+)",
        r"(\s*(or|and)\s+\d+\s*=\s*\d+)",
        r"(\s*;\s*(drop|delete|update|create|alter)\s+)",
        r"(\s*--\s*)",
        r"(\s*/\*.*?\*/\s*)",
        r"(\s*'\s*(or|and)\s*')",
    ]
    
    # XSS检测模式
    XSS_PATTERNS = [
        r"<script[^>]*>.*?</script>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
    ]
    
    @classmethod
    def validate_match_id(cls, match_id: Union[str, int]) -> bool:
        """验证比赛ID格式"""
        try:
            match_id_int = int(match_id)
            return 1000000 <= match_id_int <= 99999999  # 合理的比赛ID范围
        except (ValueError, TypeError):
            return False
    
    @classmethod
    def validate_company_id(cls, company_id: Union[str, int]) -> bool:
        """验证公司ID格式"""
        try:
            company_id_int = int(company_id)
            return 1 <= company_id_int <= 9999  # 合理的公司ID范围
        except (ValueError, TypeError):
            return False
    
    @classmethod
    def check_sql_injection(cls, value: str) -> bool:
        """检查SQL注入攻击"""
        if not isinstance(value, str):
            return False
            
        value_lower = value.lower()
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_lower, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def check_xss_attack(cls, value: str) -> bool:
        """检查XSS攻击"""
        if not isinstance(value, str):
            return False
            
        for pattern in cls.XSS_PATTERNS:
            if re.search(pattern, value, re.IGNORECASE):
                return True
        return False
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 255) -> str:
        """清理字符串输入"""
        if not isinstance(value, str):
            return ""
        
        # 移除危险字符
        value = re.sub(r'[<>"\';\\]', '', value)
        
        # 限制长度
        if len(value) > max_length:
            value = value[:max_length]
        
        return value.strip()
    
    @classmethod
    def validate_request_params(cls, params: Dict[str, Any]) -> Dict[str, Any]:
        """验证请求参数"""
        errors = []
        
        for key, value in params.items():
            if isinstance(value, str):
                # 检查SQL注入
                if cls.check_sql_injection(value):
                    errors.append(f"参数 {key} 包含可疑的SQL内容")
                
                # 检查XSS
                if cls.check_xss_attack(value):
                    errors.append(f"参数 {key} 包含可疑的脚本内容")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }


class ErrorHandler:
    """统一错误处理器"""
    
    @staticmethod
    def handle_database_error(error: Exception, operation: str = "数据库操作") -> Dict[str, Any]:
        """处理数据库错误"""
        error_msg = str(error)
        logger.error(f"{operation}失败: {error_msg}", exc_info=True)
        
        # 不向用户暴露详细的数据库错误信息
        if "foreign key constraint fails" in error_msg.lower():
            return {
                'success': False,
                'error': '数据引用约束错误，请检查相关数据是否存在',
                'error_code': 'FOREIGN_KEY_ERROR'
            }
        elif "duplicate entry" in error_msg.lower():
            return {
                'success': False,
                'error': '数据重复，该记录已存在',
                'error_code': 'DUPLICATE_ENTRY'
            }
        elif "doesn't exist" in error_msg.lower():
            return {
                'success': False,
                'error': '请求的数据不存在',
                'error_code': 'DATA_NOT_FOUND'
            }
        else:
            return {
                'success': False,
                'error': '数据库操作失败，请稍后重试',
                'error_code': 'DATABASE_ERROR'
            }
    
    @staticmethod
    def handle_validation_error(errors: List[str]) -> Dict[str, Any]:
        """处理验证错误"""
        logger.warning(f"参数验证失败: {errors}")
        return {
            'success': False,
            'error': '请求参数验证失败',
            'details': errors,
            'error_code': 'VALIDATION_ERROR'
        }
    
    @staticmethod
    def handle_generic_error(error: Exception, operation: str = "操作") -> Dict[str, Any]:
        """处理通用错误"""
        error_msg = str(error)
        logger.error(f"{operation}失败: {error_msg}", exc_info=True)
        
        return {
            'success': False,
            'error': f'{operation}失败，请稍后重试',
            'error_code': 'INTERNAL_ERROR'
        }
    
    @staticmethod
    def handle_not_found_error(resource: str = "资源") -> Dict[str, Any]:
        """处理未找到错误"""
        return {
            'success': False,
            'error': f'请求的{resource}不存在',
            'error_code': 'NOT_FOUND'
        }


class RequestLogger:
    """请求日志记录器"""
    
    @staticmethod
    def log_request(endpoint: str, params: Dict[str, Any] = None, 
                   user_info: Dict[str, Any] = None) -> None:
        """记录请求日志"""
        client_ip = request.environ.get('HTTP_X_FORWARDED_FOR', request.remote_addr)
        user_agent = request.headers.get('User-Agent', '')
        
        log_data = {
            'timestamp': datetime.now().isoformat(),
            'endpoint': endpoint,
            'method': request.method,
            'client_ip': client_ip,
            'user_agent': user_agent,
            'params': params or {},
            'user_info': user_info or {}
        }
        
        logger.info(f"API请求: {endpoint} - IP: {client_ip}")
        logger.debug(f"请求详情: {log_data}")
    
    @staticmethod
    def log_response(endpoint: str, success: bool, error: str = None, 
                    response_time: float = None) -> None:
        """记录响应日志"""
        status = "成功" if success else "失败"
        log_msg = f"API响应: {endpoint} - {status}"
        
        if response_time:
            log_msg += f" - 耗时: {response_time:.3f}s"
        
        if error:
            log_msg += f" - 错误: {error}"
            logger.warning(log_msg)
        else:
            logger.info(log_msg)


def security_required(validate_params: bool = True, 
                     log_requests: bool = True):
    """安全验证装饰器"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            start_time = datetime.now()
            endpoint = f.__name__
            
            try:
                # 记录请求日志
                if log_requests:
                    params = dict(request.args) if request.args else {}
                    RequestLogger.log_request(endpoint, params)
                
                # 验证请求参数
                if validate_params:
                    params = dict(request.args) if request.args else {}
                    validation_result = SecurityValidator.validate_request_params(params)
                    
                    if not validation_result['valid']:
                        error_response = ErrorHandler.handle_validation_error(validation_result['errors'])
                        
                        # 记录响应日志
                        if log_requests:
                            response_time = (datetime.now() - start_time).total_seconds()
                            RequestLogger.log_response(endpoint, False, 
                                                     error_response['error'], response_time)
                        
                        return jsonify(error_response), 400
                
                # 执行原函数
                result = f(*args, **kwargs)
                
                # 记录成功响应日志
                if log_requests:
                    response_time = (datetime.now() - start_time).total_seconds()
                    RequestLogger.log_response(endpoint, True, response_time=response_time)
                
                return result
                
            except Exception as e:
                # 统一错误处理
                error_response = ErrorHandler.handle_generic_error(e, f"执行{endpoint}")
                
                # 记录错误响应日志
                if log_requests:
                    response_time = (datetime.now() - start_time).total_seconds()
                    RequestLogger.log_response(endpoint, False, 
                                             error_response['error'], response_time)
                
                return jsonify(error_response), 500
        
        return wrapper
    return decorator


def validate_match_id(match_id: Union[str, int]) -> Dict[str, Any]:
    """验证比赛ID的辅助函数"""
    if not SecurityValidator.validate_match_id(match_id):
        return ErrorHandler.handle_validation_error([f"无效的比赛ID: {match_id}"])
    return {'success': True}


def validate_company_id(company_id: Union[str, int]) -> Dict[str, Any]:
    """验证公司ID的辅助函数"""
    if not SecurityValidator.validate_company_id(company_id):
        return ErrorHandler.handle_validation_error([f"无效的公司ID: {company_id}"])
    return {'success': True}


class SafeDataAccess:
    """安全的数据访问包装器"""
    
    @staticmethod
    def safe_execute_query(query_func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """安全执行数据库查询"""
        try:
            result = query_func(*args, **kwargs)
            return {'success': True, 'data': result}
        except Exception as e:
            return ErrorHandler.handle_database_error(e, "数据查询")
    
    @staticmethod
    def safe_execute_update(update_func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """安全执行数据库更新"""
        try:
            result = update_func(*args, **kwargs)
            return {'success': True, 'affected_rows': result}
        except Exception as e:
            return ErrorHandler.handle_database_error(e, "数据更新")


class ConfigValidator:
    """配置验证器"""
    
    @staticmethod
    def validate_database_config(config: Dict[str, Any]) -> bool:
        """验证数据库配置"""
        required_fields = ['host', 'port', 'user', 'password', 'database']
        
        for field in required_fields:
            if field not in config or not config[field]:
                logger.error(f"数据库配置缺少必要字段: {field}")
                return False
        
        # 验证端口号
        try:
            port = int(config['port'])
            if not (1 <= port <= 65535):
                logger.error(f"数据库端口号无效: {port}")
                return False
        except (ValueError, TypeError):
            logger.error(f"数据库端口号格式错误: {config['port']}")
            return False
        
        return True
    
    @staticmethod
    def validate_security_config(config: Dict[str, Any]) -> bool:
        """验证安全配置"""
        if 'SECRET_KEY' in config:
            secret_key = config['SECRET_KEY']
            if len(secret_key) < 32:
                logger.warning("SECRET_KEY长度过短，建议使用至少32个字符")
                return False
        
        return True