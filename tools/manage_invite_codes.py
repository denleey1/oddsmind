#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
邀请码管理脚本
用于生成、查看、禁用邀请码
"""

import os
import sys
import argparse
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

# 添加项目根目录到路径
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# 加载环境变量（重要！）
from dotenv import load_dotenv
env_path = os.path.join(ROOT, 'oddsmind.env')
if os.path.exists(env_path):
    load_dotenv(env_path)

from app_database import execute_query, execute_update
from core.logger import get_logger

logger = get_logger("manage_invite_codes")


def generate_invite_code(length: int = 8) -> str:
    """
    生成随机邀请码
    
    Args:
        length: 邀请码长度
    
    Returns:
        邀请码字符串
    """
    import random
    import string
    
    # 使用大写字母和数字，排除容易混淆的字符（0, O, I, 1）
    chars = string.ascii_uppercase.replace('O', '').replace('I', '') + \
            string.digits.replace('0', '').replace('1', '')
    
    code = ''.join(random.choice(chars) for _ in range(length))
    return code


def create_invite_code(
    code: Optional[str] = None,
    max_uses: int = 1,
    expires_days: Optional[int] = None,
    account_expires_days: int = 365,
    created_by: Optional[str] = None,
    notes: Optional[str] = None
) -> str:
    """
    创建邀请码
    
    Args:
        code: 邀请码（如果不提供则自动生成）
        max_uses: 最大使用次数
        expires_days: 过期天数（None 表示永不过期）
        created_by: 创建者
        notes: 备注
    
    Returns:
        创建的邀请码
    """
    if not code:
        # 生成唯一邀请码
        while True:
            code = generate_invite_code()
            existing = execute_query(
                "SELECT id FROM invite_codes WHERE code = %s",
                (code,)
            )
            if not existing:
                break
    
    # 检查邀请码是否已存在
    existing = execute_query(
        "SELECT id FROM invite_codes WHERE code = %s",
        (code,)
    )
    if existing:
        raise ValueError(f"邀请码 {code} 已存在")
    
    # 计算过期时间
    expires_at = None
    if expires_days:
        expires_at = datetime.now() + timedelta(days=expires_days)
    
    # 插入数据库
    sql = """
        INSERT INTO invite_codes 
        (code, created_by, max_uses, expires_at, account_expires_days, notes, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, TRUE)
    """
    execute_update(sql, (code, created_by, max_uses, expires_at, account_expires_days, notes))
    
    logger.info(f"创建邀请码成功: {code}")
    return code


def list_invite_codes(active_only: bool = False) -> List[Dict[str, Any]]:
    """
    列出所有邀请码
    
    Args:
        active_only: 是否只显示激活的邀请码
    
    Returns:
        邀请码列表
    """
    if active_only:
        sql = """
            SELECT id, code, created_by, max_uses, used_count, 
                   expires_at, account_expires_days, is_active, notes, created_at
            FROM invite_codes
            WHERE is_active = TRUE
            ORDER BY created_at DESC
        """
    else:
        sql = """
            SELECT id, code, created_by, max_uses, used_count, 
                   expires_at, account_expires_days, is_active, notes, created_at
            FROM invite_codes
            ORDER BY created_at DESC
        """
    
    results = execute_query(sql)
    return results


def disable_invite_code(code: str) -> bool:
    """
    禁用邀请码
    
    Args:
        code: 邀请码
    
    Returns:
        是否成功
    """
    sql = "UPDATE invite_codes SET is_active = FALSE WHERE code = %s"
    execute_update(sql, (code,))
    logger.info(f"禁用邀请码: {code}")
    return True


def enable_invite_code(code: str) -> bool:
    """
    启用邀请码
    
    Args:
        code: 邀请码
    
    Returns:
        是否成功
    """
    sql = "UPDATE invite_codes SET is_active = TRUE WHERE code = %s"
    execute_update(sql, (code,))
    logger.info(f"启用邀请码: {code}")
    return True


def get_invite_code_info(code: str) -> Optional[Dict[str, Any]]:
    """
    获取邀请码详细信息
    
    Args:
        code: 邀请码
    
    Returns:
        邀请码信息，如果不存在则返回 None
    """
    sql = """
        SELECT id, code, created_by, max_uses, used_count, 
               expires_at, account_expires_days, is_active, notes, created_at, updated_at
        FROM invite_codes
        WHERE code = %s
    """
    results = execute_query(sql, (code,))
    if results:
        return results[0]
    return None


def format_invite_code_info(info: Dict[str, Any]) -> str:
    """格式化邀请码信息用于显示"""
    expires_str = info['expires_at'].strftime('%Y-%m-%d %H:%M:%S') if info['expires_at'] else '永不过期'
    status = '激活' if info['is_active'] else '禁用'
    remaining = info['max_uses'] - info['used_count']
    
    # 账号有效期显示
    account_expires_days = info.get('account_expires_days', 365)
    if account_expires_days == 1:
        account_expires_str = '1天'
    elif account_expires_days == 7:
        account_expires_str = '1周'
    elif account_expires_days == 30:
        account_expires_str = '1个月'
    elif account_expires_days == 365:
        account_expires_str = '1年'
    else:
        account_expires_str = f'{account_expires_days}天'
    
    return f"""
邀请码: {info['code']}
状态: {status}
创建者: {info['created_by'] or 'N/A'}
最大使用次数: {info['max_uses']}
已使用次数: {info['used_count']}
剩余次数: {remaining}
邀请码过期时间: {expires_str}
账号有效期: {account_expires_str} ({account_expires_days}天)
备注: {info['notes'] or 'N/A'}
创建时间: {info['created_at'].strftime('%Y-%m-%d %H:%M:%S')}
"""


def main():
    parser = argparse.ArgumentParser(description='邀请码管理工具')
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 创建邀请码
    create_parser = subparsers.add_parser('create', help='创建邀请码')
    create_parser.add_argument('--code', type=str, help='指定邀请码（不指定则自动生成）')
    create_parser.add_argument('--max-uses', type=int, default=1, help='最大使用次数（默认：1）')
    create_parser.add_argument('--expires-days', type=int, help='邀请码过期天数（不指定则永不过期）')
    create_parser.add_argument('--account-expires-days', type=int, default=365, 
                               help='账号有效期（天数），1=1天，7=1周，30=1个月，365=1年（默认365）')
    create_parser.add_argument('--created-by', type=str, help='创建者')
    create_parser.add_argument('--notes', type=str, help='备注')
    
    # 列出邀请码
    list_parser = subparsers.add_parser('list', help='列出邀请码')
    list_parser.add_argument('--active-only', action='store_true', help='只显示激活的邀请码')
    
    # 查看邀请码信息
    info_parser = subparsers.add_parser('info', help='查看邀请码信息')
    info_parser.add_argument('code', type=str, help='邀请码')
    
    # 查看激活码使用记录
    usage_parser = subparsers.add_parser('usage', help='查看激活码使用记录')
    usage_parser.add_argument('code', type=str, help='邀请码')
    
    # 禁用邀请码
    disable_parser = subparsers.add_parser('disable', help='禁用邀请码')
    disable_parser.add_argument('code', type=str, help='邀请码')
    
    # 启用邀请码
    enable_parser = subparsers.add_parser('enable', help='启用邀请码')
    enable_parser.add_argument('code', type=str, help='邀请码')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == 'create':
            code = create_invite_code(
                code=args.code,
                max_uses=args.max_uses,
                expires_days=args.expires_days,
                account_expires_days=args.account_expires_days,
                created_by=args.created_by,
                notes=args.notes
            )
            print(f"✅ 创建邀请码成功: {code}")
            
            # 显示邀请码信息
            info = get_invite_code_info(code)
            if info:
                print(format_invite_code_info(info))
        
        elif args.command == 'list':
            codes = list_invite_codes(active_only=args.active_only)
            if not codes:
                print("没有找到邀请码")
                return
            
            print(f"\n找到 {len(codes)} 个邀请码:\n")
            for code_info in codes:
                status = '✅' if code_info['is_active'] else '❌'
                expires_str = code_info['expires_at'].strftime('%Y-%m-%d') if code_info['expires_at'] else '永不过期'
                account_expires_days = code_info.get('account_expires_days', 365)
                if account_expires_days == 1:
                    account_str = '1天'
                elif account_expires_days == 7:
                    account_str = '1周'
                elif account_expires_days == 30:
                    account_str = '1月'
                elif account_expires_days == 365:
                    account_str = '1年'
                else:
                    account_str = f'{account_expires_days}天'
                print(f"{status} {code_info['code']:10} | "
                      f"使用: {code_info['used_count']}/{code_info['max_uses']} | "
                      f"账号有效期: {account_str} | "
                      f"过期: {expires_str} | "
                      f"创建者: {code_info['created_by'] or 'N/A'}")
        
        elif args.command == 'info':
            info = get_invite_code_info(args.code)
            if info:
                print(format_invite_code_info(info))
            else:
                print(f"❌ 邀请码 {args.code} 不存在")
        
        elif args.command == 'usage':
            from utils.miniprogram_db import get_invite_code_usage_history
            usage_history = get_invite_code_usage_history(args.code)
            if not usage_history:
                print(f"❌ 邀请码 {args.code} 没有使用记录")
                return
            
            print(f"\n邀请码 {args.code} 使用记录（共 {len(usage_history)} 条）:\n")
            print(f"{'序号':<6} {'用户ID':<8} {'OpenID':<20} {'账号过期时间':<20} {'使用时间':<20} {'昵称':<15}")
            print("-" * 100)
            for idx, record in enumerate(usage_history, 1):
                openid_short = record['openid'][:15] + '...' if len(record['openid']) > 15 else record['openid']
                expires_at_str = record['account_expires_at'].strftime('%Y-%m-%d %H:%M:%S') if record['account_expires_at'] else 'N/A'
                used_at_str = record['used_at'].strftime('%Y-%m-%d %H:%M:%S') if record['used_at'] else 'N/A'
                nickname = record.get('nickname') or 'N/A'
                print(f"{idx:<6} {record['user_id']:<8} {openid_short:<20} {expires_at_str:<20} {used_at_str:<20} {nickname:<15}")
        
        elif args.command == 'disable':
            if disable_invite_code(args.code):
                print(f"✅ 已禁用邀请码: {args.code}")
        
        elif args.command == 'enable':
            if enable_invite_code(args.code):
                print(f"✅ 已启用邀请码: {args.code}")
    
    except Exception as e:
        logger.error(f"操作失败: {e}")
        print(f"❌ 错误: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()

