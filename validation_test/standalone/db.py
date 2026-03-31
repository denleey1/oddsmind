#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
独立数据库连接模块（无项目依赖）
通过环境变量配置连接参数
"""
import os
import pymysql
from pymysql.cursors import DictCursor


def get_db_config():
    return {
        'host': os.environ.get('MYSQL_HOST', 'localhost'),
        'port': int(os.environ.get('MYSQL_PORT', '3306')),
        'user': os.environ.get('MYSQL_USER', 'root'),
        'password': os.environ.get('MYSQL_PASSWORD', ''),
        'database': os.environ.get('MYSQL_DATABASE', 'oddsmind'),
        'charset': 'utf8mb4',
    }


class SimpleDB:
    """简单数据库连接（用完即关）"""

    def __init__(self):
        self._config = get_db_config()

    def execute_query(self, sql, params=None, fetch='all'):
        conn = pymysql.connect(**self._config, cursorclass=DictCursor)
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or ())
                if fetch == 'all':
                    return cur.fetchall()
                elif fetch == 'one':
                    return cur.fetchone()
                else:
                    return cur.fetchall()
        finally:
            conn.close()


def get_connection():
    return SimpleDB()
