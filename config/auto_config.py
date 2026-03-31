#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Auto-configuration system for database and environment settings.
Supports environment variables and automatic database creation.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import pymysql
from pymysql import Connection


class AutoConfig:
    """自动配置系统，支持环境变量和配置文件"""
    
    def __init__(self):
        self.config_file = Path(__file__).parent / 'local_config.json'
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置，优先级：环境变量 > 配置文件 > 默认值"""
        
        # 默认配置
        default_config = {
            'mysql_host': 'localhost',
            'mysql_port': 3306,
            'mysql_user': 'root',
            'mysql_password': '',
            'mysql_database': 'oddsmind',
            'mysql_charset': 'utf8mb4'
        }
        
        # 尝试从配置文件加载
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    default_config.update(file_config)
            except Exception as e:
                print(f"Warning: Failed to load config file: {e}")
        
        # 环境变量覆盖（优先级最高）
        env_mapping = {
            'ODDSMIND_DB_HOST': 'mysql_host',
            'ODDSMIND_DB_PORT': 'mysql_port',
            'ODDSMIND_DB_USER': 'mysql_user',
            'ODDSMIND_DB_PASSWORD': 'mysql_password',
            'ODDSMIND_DB_NAME': 'mysql_database'
        }
        
        for env_key, config_key in env_mapping.items():
            env_value = os.getenv(env_key)
            if env_value is not None:
                if config_key == 'mysql_port':
                    default_config[config_key] = int(env_value)
                else:
                    default_config[config_key] = env_value
        
        return default_config
    
    def get_database_config(self) -> Dict[str, Any]:
        """获取数据库配置"""
        return {
            'host': self.config['mysql_host'],
            'port': self.config['mysql_port'],
            'user': self.config['mysql_user'],
            'password': self.config['mysql_password'],
            'database': self.config['mysql_database'],
            'charset': self.config['mysql_charset'],
            'cursorclass': pymysql.cursors.DictCursor
        }
    
    def ensure_database(self) -> bool:
        """确保数据库存在，如果不存在则创建"""
        config = self.get_database_config()
        db_name = config.pop('database')
        
        try:
            # 连接MySQL服务器（不指定数据库）
            conn = pymysql.connect(**config)
            cursor = conn.cursor()
            
            # 创建数据库（如果不存在）
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
                f"DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
            
            print(f"[SUCCESS] Database '{db_name}' is ready")
            
            cursor.close()
            conn.close()
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to ensure database: {e}")
            return False
    
    def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            config = self.get_database_config()
            conn = pymysql.connect(**config)
            conn.ping()
            conn.close()
            print("[SUCCESS] Database connection successful")
            return True
        except Exception as e:
            print(f"[ERROR] Database connection failed: {e}")
            return False
    
    def save_local_config(self, config: Optional[Dict[str, Any]] = None):
        """保存配置到本地文件"""
        if config is None:
            config = self.config
        
        # 不保存密码到文件
        safe_config = config.copy()
        if 'mysql_password' in safe_config:
            safe_config['mysql_password'] = '***'
        
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(safe_config, f, indent=2, ensure_ascii=False)
            print(f"[SUCCESS] Configuration saved to {self.config_file}")
        except Exception as e:
            print(f"[ERROR] Failed to save config: {e}")
    
    def setup_wizard(self):
        """交互式配置向导"""
        print("\n[SETUP] OddsMind Database Setup Wizard")
        print("-" * 40)
        
        # 询问数据库配置
        config = {}
        
        config['mysql_host'] = input(f"MySQL Host [{self.config['mysql_host']}]: ").strip() or self.config['mysql_host']
        
        port_input = input(f"MySQL Port [{self.config['mysql_port']}]: ").strip()
        config['mysql_port'] = int(port_input) if port_input else self.config['mysql_port']
        
        config['mysql_user'] = input(f"MySQL User [{self.config['mysql_user']}]: ").strip() or self.config['mysql_user']
        
        # 密码输入（不显示默认值）
        import getpass
        config['mysql_password'] = getpass.getpass("MySQL Password: ") or self.config['mysql_password']
        
        config['mysql_database'] = input(f"Database Name [{self.config['mysql_database']}]: ").strip() or self.config['mysql_database']
        
        config['mysql_charset'] = self.config['mysql_charset']
        
        # 更新配置
        self.config.update(config)
        
        # 测试连接
        print("\n[TEST] Testing connection...")
        if self.ensure_database() and self.test_connection():
            # 保存配置
            save = input("\n[SAVE] Save configuration? (y/n) [y]: ").strip().lower()
            if save != 'n':
                self.save_local_config()
            
            print("\n[SUCCESS] Setup completed successfully!")
            return True
        else:
            print("\n[ERROR] Setup failed. Please check your settings.")
            return False


# 全局配置实例
auto_config = AutoConfig()


def get_auto_database_config() -> Dict[str, Any]:
    """获取自动配置的数据库设置"""
    return auto_config.get_database_config()


def ensure_database_ready() -> bool:
    """确保数据库准备就绪"""
    return auto_config.ensure_database()


if __name__ == "__main__":
    # 运行配置向导
    auto_config.setup_wizard()