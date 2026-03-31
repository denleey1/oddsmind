#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查小程序路由是否正确配置
用于诊断 502 错误
"""

import os
import sys

# 添加项目根目录到路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def check_imports():
    """检查所有必要的导入"""
    print("=" * 60)
    print("检查导入...")
    print("=" * 60)
    
    errors = []
    
    # 检查基础模块
    try:
        import flask
        print("✅ Flask 导入成功")
    except ImportError as e:
        errors.append(f"❌ Flask 导入失败: {e}")
    
    try:
        from utils.jwt_helper import issue_jwt_token, verify_jwt_token
        print("✅ JWT 工具类导入成功")
    except ImportError as e:
        errors.append(f"❌ JWT 工具类导入失败: {e}")
    
    try:
        from utils.miniprogram_db import get_user_by_openid, validate_invite_code
        print("✅ 数据库操作函数导入成功")
    except ImportError as e:
        errors.append(f"❌ 数据库操作函数导入失败: {e}")
    
    try:
        from utils.api import success, error
        print("✅ API 工具函数导入成功")
    except ImportError as e:
        errors.append(f"❌ API 工具函数导入失败: {e}")
    
    try:
        from auth import login_required
        print("✅ 认证装饰器导入成功")
    except ImportError as e:
        errors.append(f"❌ 认证装饰器导入失败: {e}")
    
    try:
        from application.context import get_logger_for
        print("✅ Logger 导入成功")
    except ImportError as e:
        errors.append(f"❌ Logger 导入失败: {e}")
    
    # 检查小程序路由
    try:
        from application.routes.miniprogram import miniprogram_bp
        print("✅ 小程序路由 Blueprint 导入成功")
        print(f"   Blueprint 名称: {miniprogram_bp.name}")
        print(f"   路由数量: {len(miniprogram_bp.deferred_functions)}")
    except Exception as e:
        errors.append(f"❌ 小程序路由导入失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 检查应用工厂
    try:
        from application.web.factory import create_app
        print("✅ 应用工厂导入成功")
    except Exception as e:
        errors.append(f"❌ 应用工厂导入失败: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    if errors:
        print("发现以下错误:")
        for error in errors:
            print(f"  {error}")
        return False
    else:
        print("✅ 所有导入检查通过！")
        return True


def check_route_registration():
    """检查路由注册"""
    print("\n" + "=" * 60)
    print("检查路由注册...")
    print("=" * 60)
    
    try:
        from application.web.factory import create_app
        app = create_app()
        
        # 检查路由
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'endpoint': rule.endpoint,
                'methods': list(rule.methods),
                'path': rule.rule
            })
        
        # 查找小程序路由
        miniprogram_routes = [r for r in routes if 'miniprogram' in r['endpoint']]
        
        print(f"✅ 应用创建成功")
        print(f"   总路由数: {len(routes)}")
        print(f"   小程序路由数: {len(miniprogram_routes)}")
        
        if miniprogram_routes:
            print("\n小程序路由列表:")
            for route in miniprogram_routes:
                print(f"  {route['path']} [{', '.join(route['methods'])}] -> {route['endpoint']}")
        else:
            print("⚠️  未找到小程序路由！")
            return False
        
        return True
    except Exception as e:
        print(f"❌ 路由注册检查失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def check_environment():
    """检查环境变量"""
    print("\n" + "=" * 60)
    print("检查环境变量...")
    print("=" * 60)
    
    required_vars = ['JWT_SECRET', 'WECHAT_APPID', 'WECHAT_APPSECRET']
    missing = []
    
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            # 只显示前4个字符，隐藏敏感信息
            masked = value[:4] + '...' if len(value) > 4 else value
            print(f"✅ {var}: {masked}")
        else:
            print(f"❌ {var}: 未设置")
            missing.append(var)
    
    if missing:
        print(f"\n⚠️  缺少环境变量: {', '.join(missing)}")
        print("   这可能导致功能异常，但不影响路由注册")
        return False
    else:
        print("\n✅ 所有必需的环境变量已设置")
        return True


def check_database_tables():
    """检查数据库表是否存在"""
    print("\n" + "=" * 60)
    print("检查数据库表...")
    print("=" * 60)
    
    try:
        from app_database import execute_query
        
        tables = ['miniprogram_users', 'invite_codes']
        for table in tables:
            try:
                result = execute_query(f"SHOW TABLES LIKE '{table}'")
                if result:
                    print(f"✅ 表 {table} 存在")
                else:
                    print(f"❌ 表 {table} 不存在")
                    print(f"   需要运行数据库初始化脚本创建表")
            except Exception as e:
                print(f"⚠️  检查表 {table} 时出错: {e}")
        
        return True
    except Exception as e:
        print(f"⚠️  数据库检查失败: {e}")
        print("   可能是数据库连接问题，但不影响路由注册")
        return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("小程序路由诊断工具")
    print("=" * 60)
    
    results = []
    
    # 检查导入
    results.append(("导入检查", check_imports()))
    
    # 检查路由注册
    if results[0][1]:  # 如果导入成功，才检查路由
        results.append(("路由注册", check_route_registration()))
    
    # 检查环境变量
    results.append(("环境变量", check_environment()))
    
    # 检查数据库表
    results.append(("数据库表", check_database_tables()))
    
    # 总结
    print("\n" + "=" * 60)
    print("诊断总结")
    print("=" * 60)
    
    for name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{name}: {status}")
    
    # 502 错误的可能原因
    print("\n" + "=" * 60)
    print("502 错误的可能原因:")
    print("=" * 60)
    print("1. 后端服务未运行 - 检查服务状态")
    print("2. 后端代码有错误 - 查看后端日志")
    print("3. 导入错误 - 检查 Python 模块导入")
    print("4. 数据库连接失败 - 检查数据库配置")
    print("5. Nginx 配置问题 - 检查反向代理配置")
    print("\n建议:")
    print("- 查看后端日志: tail -f logs/app.log")
    print("- 检查服务状态: systemctl status oddsmind")
    print("- 测试路由: curl http://localhost:8889/api/miniprogram/login")


if __name__ == '__main__':
    main()

