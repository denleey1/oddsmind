#!/usr/bin/env python3
"""
Keycloak 用户管理脚本 - 自动创建带有效期的用户
用法：
  自动生成用户名密码：python create_user.py --auto
  指定用户名密码：    python create_user.py --username 张三 --password abc123
"""

import os
import sys
import argparse
import requests
import random
import string
from datetime import datetime, timedelta
from urllib.parse import urljoin
from dotenv import load_dotenv

# 加载环境变量
load_dotenv('oddsmind.env')

# Keycloak 配置
KEYCLOAK_BASE_URL = os.environ.get("KEYCLOAK_BASE_URL", "")
KEYCLOAK_REALM = os.environ.get("KEYCLOAK_REALM", "")
KEYCLOAK_CLIENT_ID = os.environ.get("KEYCLOAK_CLIENT_ID", "")
KEYCLOAK_CLIENT_SECRET = os.environ.get("KEYCLOAK_CLIENT_SECRET", "")

# 管理员账号（需要配置）
KEYCLOAK_ADMIN_USERNAME = os.environ.get("KEYCLOAK_ADMIN_USERNAME", "admin")
KEYCLOAK_ADMIN_PASSWORD = os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "")

# 用户默认有效期（天）
DEFAULT_VALIDITY_DAYS = 30


class KeycloakUserManager:
    """Keycloak 用户管理器"""
    
    def __init__(self):
        self.base_url = KEYCLOAK_BASE_URL.rstrip('/')
        self.realm = KEYCLOAK_REALM
        self.admin_token = None
        
    def _get_admin_token(self) -> str:
        """获取管理员访问令牌"""
        if not KEYCLOAK_ADMIN_PASSWORD:
            print("❌ 错误：未配置 KEYCLOAK_ADMIN_PASSWORD 环境变量")
            print("请在 oddsmind.env 中添加：")
            print("KEYCLOAK_ADMIN_USERNAME=admin")
            print("KEYCLOAK_ADMIN_PASSWORD=你的admin密码")
            sys.exit(1)
        
        token_url = f"{self.base_url}/realms/master/protocol/openid-connect/token"
        
        data = {
            'client_id': 'admin-cli',
            'username': KEYCLOAK_ADMIN_USERNAME,
            'password': KEYCLOAK_ADMIN_PASSWORD,
            'grant_type': 'password'
        }
        
        try:
            response = requests.post(token_url, data=data, verify=False, timeout=10)
            response.raise_for_status()
            self.admin_token = response.json()['access_token']
            return self.admin_token
        except requests.exceptions.RequestException as e:
            print(f"❌ 获取管理员令牌失败: {e}")
            print(f"请检查 KEYCLOAK_ADMIN_USERNAME 和 KEYCLOAK_ADMIN_PASSWORD 是否正确")
            sys.exit(1)
    
    def _get_headers(self) -> dict:
        """获取请求头"""
        if not self.admin_token:
            self._get_admin_token()
        return {
            'Authorization': f'Bearer {self.admin_token}',
            'Content-Type': 'application/json'
        }
    
    def check_user_exists(self, username: str) -> bool:
        """检查用户是否已存在"""
        url = f"{self.base_url}/admin/realms/{self.realm}/users?username={username}&exact=true"
        
        try:
            response = requests.get(url, headers=self._get_headers(), verify=False, timeout=10)
            response.raise_for_status()
            users = response.json()
            return len(users) > 0
        except requests.exceptions.RequestException as e:
            print(f"❌ 检查用户失败: {e}")
            return False
    
    def create_user(self, username: str, password: str, email: str = None, 
                    validity_days: int = DEFAULT_VALIDITY_DAYS) -> dict:
        """
        创建用户并设置有效期
        
        Args:
            username: 用户名
            password: 密码
            email: 邮箱（可选，默认为 username@oddsmind.local）
            validity_days: 有效期天数（默认30天）
        
        Returns:
            创建结果字典
        """
        # 检查用户是否已存在
        if self.check_user_exists(username):
            return {
                'success': False,
                'error': f'用户 {username} 已存在'
            }
        
        # 生成邮箱
        if not email:
            email = f"{username}@oddsmind.local"
        
        # 计算过期日期
        expiry_date = datetime.now() + timedelta(days=validity_days)
        expiry_date_str = expiry_date.strftime('%Y-%m-%d')
        
        # 创建用户
        url = f"{self.base_url}/admin/realms/{self.realm}/users"
        
        user_data = {
            'username': username,
            'email': email,
            'enabled': True,
            'emailVerified': True,
            'attributes': {
                'account_expiry_date': [expiry_date_str]  # 设置过期日期
            }
        }
        
        try:
            # 1. 创建用户
            response = requests.post(url, json=user_data, headers=self._get_headers(), 
                                    verify=False, timeout=10)
            response.raise_for_status()
            
            # 2. 获取新创建的用户ID
            user_id = self._get_user_id(username)
            if not user_id:
                return {
                    'success': False,
                    'error': '用户创建成功但无法获取用户ID'
                }
            
            # 3. 设置密码
            password_url = f"{self.base_url}/admin/realms/{self.realm}/users/{user_id}/reset-password"
            password_data = {
                'type': 'password',
                'value': password,
                'temporary': False  # 设置为永久密码，不需要首次登录修改
            }
            
            response = requests.put(password_url, json=password_data, headers=self._get_headers(), 
                                   verify=False, timeout=10)
            response.raise_for_status()
            
            return {
                'success': True,
                'username': username,
                'password': password,
                'email': email,
                'expiry_date': expiry_date_str,
                'user_id': user_id
            }
            
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'error': f'创建用户失败: {str(e)}'
            }
    
    def _get_user_id(self, username: str) -> str:
        """获取用户ID"""
        url = f"{self.base_url}/admin/realms/{self.realm}/users?username={username}&exact=true"
        
        try:
            response = requests.get(url, headers=self._get_headers(), verify=False, timeout=10)
            response.raise_for_status()
            users = response.json()
            
            if users and len(users) > 0:
                return users[0]['id']
            return None
        except requests.exceptions.RequestException:
            return None


def generate_random_username(prefix: str = "user") -> str:
    """
    生成随机用户名
    格式：prefix + 8位随机数字
    示例：user12345678
    """
    random_digits = ''.join(random.choices(string.digits, k=8))
    return f"{prefix}{random_digits}"


def generate_random_password(length: int = 12) -> str:
    """
    生成高强度随机密码
    包含：大写字母、小写字母、数字、特殊字符
    长度：默认12位
    示例：Xk9@mP2nQ5w!
    """
    # 确保至少包含每种字符类型
    password_chars = [
        random.choice(string.ascii_uppercase),  # 至少1个大写字母
        random.choice(string.ascii_lowercase),  # 至少1个小写字母
        random.choice(string.digits),           # 至少1个数字
        random.choice('!@#$%^&*'),             # 至少1个特殊字符
    ]
    
    # 剩余字符从所有类型中随机选择
    all_chars = string.ascii_letters + string.digits + '!@#$%^&*'
    password_chars += random.choices(all_chars, k=length - 4)
    
    # 打乱顺序
    random.shuffle(password_chars)
    
    return ''.join(password_chars)


def print_success(result: dict, is_auto: bool = False):
    """打印成功信息"""
    print("\n" + "=" * 60)
    print("✅ 用户创建成功！")
    print("-" * 60)
    print(f"用户名：    {result['username']}")
    print(f"密码：      {result['password']}")
    print(f"有效期至：  {result['expiry_date']}")
    
    if is_auto:
        print("\n⚠️  重要提示：")
        print("   - 请立即复制保存上述账号信息！")
        print("   - 密码为随机生成，丢失后需要重置！")
    
    print(f"\n登录地址：  {os.environ.get('APP_BASE_URL', 'http://119.29.112.18')}/login")
    print("=" * 60)
    print("\n💡 提示：请将上述信息发送给用户")
    print(f"💡 用户账号将在 {result['expiry_date']} 后自动过期\n")


def print_batch_summary(results: list):
    """打印批量创建汇总表"""
    success_count = sum(1 for r in results if r['success'])
    failed_count = len(results) - success_count
    
    print("\n" + "=" * 80)
    print(f"📊 批量创建汇总")
    print("-" * 80)
    print(f"总计: {len(results)} 个账号 | 成功: {success_count} | 失败: {failed_count}")
    print("=" * 80)
    
    if success_count > 0:
        print("\n✅ 成功创建的账号：")
        print("-" * 80)
        print(f"{'序号':<6} {'用户名':<20} {'密码':<20} {'有效期至':<15}")
        print("-" * 80)
        
        idx = 1
        for result in results:
            if result['success']:
                print(f"{idx:<6} {result['username']:<20} {result['password']:<20} {result['expiry_date']:<15}")
                idx += 1
        
        print("-" * 80)
        print("💡 提示：请保存上述账号信息并发送给对应用户")
        print(f"💡 登录地址：{os.environ.get('APP_BASE_URL', 'http://119.29.112.18')}/login")
    
    if failed_count > 0:
        print("\n❌ 创建失败的账号：")
        print("-" * 80)
        for result in results:
            if not result['success']:
                print(f"   {result.get('username', 'N/A')}: {result['error']}")
    
    print("=" * 80 + "\n")


def batch_create_users(count: int, prefix: str = 'user', validity_days: int = DEFAULT_VALIDITY_DAYS) -> list:
    """
    批量创建用户
    
    Args:
        count: 创建数量
        prefix: 用户名前缀
        validity_days: 有效期天数
    
    Returns:
        创建结果列表
    """
    manager = KeycloakUserManager()
    results = []
    
    print(f"\n🚀 开始批量创建 {count} 个账号...")
    print(f"   用户名前缀：{prefix}")
    print(f"   有效期：{validity_days} 天")
    print(f"   密码强度：高强度12位（含大小写字母、数字、特殊字符）")
    print()
    
    for i in range(count):
        username = generate_random_username(prefix=prefix)
        password = generate_random_password()
        
        print(f"[{i+1}/{count}] 创建用户 {username}...", end=' ')
        
        result = manager.create_user(
            username=username,
            password=password,
            validity_days=validity_days
        )
        
        if result['success']:
            print("✅ 成功")
        else:
            print(f"❌ 失败 - {result.get('error', '未知错误')}")
        
        results.append(result)
    
    return results


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='创建带有效期的Keycloak用户',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  # 自动生成用户名和密码（推荐）
  python create_user.py --auto
  
  # 批量创建10个账号
  python create_user.py --batch 10
  
  # 批量创建5个账号，有效期60天
  python create_user.py --batch 5 --days 60
  
  # 批量创建账号并自定义前缀
  python create_user.py --batch 10 --prefix student
  
  # 手动指定用户名和密码
  python create_user.py --username zhangsan --password abc123456
        """
    )
    
    # 添加互斥参数组
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--auto', '-a', action='store_true', 
                      help='自动生成随机用户名和密码（推荐）')
    group.add_argument('--batch', '-b', type=int, metavar='COUNT',
                      help='批量创建指定数量的账号（自动生成用户名和密码）')
    group.add_argument('--username', '-u', help='手动指定用户名')
    
    parser.add_argument('--password', '-p', help='手动指定密码（需与--username配合使用）')
    parser.add_argument('--email', '-e', help='邮箱（可选，默认为 username@oddsmind.local）')
    parser.add_argument('--days', '-d', type=int, default=DEFAULT_VALIDITY_DAYS, 
                       help=f'有效期天数（默认{DEFAULT_VALIDITY_DAYS}天）')
    parser.add_argument('--prefix', default='user', 
                       help='自动生成用户名的前缀（默认：user）')
    
    args = parser.parse_args()
    
    # 批量创建模式
    if args.batch:
        if args.batch < 1:
            print("❌ 错误：批量创建数量必须至少为1")
            sys.exit(1)
        
        if args.batch > 100:
            print("❌ 错误：单次批量创建最多100个账号")
            print("提示：如需创建更多账号，请分批执行")
            sys.exit(1)
        
        # 批量创建
        results = batch_create_users(
            count=args.batch,
            prefix=args.prefix,
            validity_days=args.days
        )
        
        # 显示汇总
        print_batch_summary(results)
        
        # 如果有失败的，退出码为1
        if any(not r['success'] for r in results):
            sys.exit(1)
    
    # 自动模式：生成随机用户名和密码
    elif args.auto:
        username = generate_random_username(prefix=args.prefix)
        password = generate_random_password()
        is_auto = True
        print("\n🎲 自动生成模式")
        print(f"   用户名前缀：{args.prefix}")
        print(f"   密码强度：  高强度12位（含大小写字母、数字、特殊字符）")
        
        # 创建用户管理器
        manager = KeycloakUserManager()
        
        print(f"\n🔄 正在创建用户 {username}...")
        
        # 创建用户
        result = manager.create_user(
            username=username,
            password=password,
            email=args.email,
            validity_days=args.days
        )
        
        # 显示结果
        if result['success']:
            print_success(result, is_auto=is_auto)
        else:
            print(f"\n❌ 创建失败: {result['error']}\n")
            sys.exit(1)
    
    # 手动模式：使用指定的用户名和密码
    else:
        if not args.password:
            print("❌ 错误：使用 --username 时必须同时提供 --password")
            print("提示：使用 --auto 可以自动生成用户名和密码")
            sys.exit(1)
        
        username = args.username
        password = args.password
        is_auto = False
        
        # 验证密码强度
        if len(password) < 6:
            print("❌ 错误：密码长度至少6位")
            sys.exit(1)
        
        # 创建用户管理器
        manager = KeycloakUserManager()
        
        print(f"\n🔄 正在创建用户 {username}...")
        
        # 创建用户
        result = manager.create_user(
            username=username,
            password=password,
            email=args.email,
            validity_days=args.days
        )
        
        # 显示结果
        if result['success']:
            print_success(result, is_auto=is_auto)
        else:
            print(f"\n❌ 创建失败: {result['error']}\n")
            sys.exit(1)


if __name__ == '__main__':
    # 禁用SSL警告
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    main()

