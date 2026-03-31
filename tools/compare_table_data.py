#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
比较两个数据库中同一个表的数据是否完全一致

使用方法：
1. 直接连接两个数据库比较（推荐，适合小表）
   python tools/compare_table_data.py --table team_power_ratings --host1 server1 --host2 server2

2. 导出后本地比较（适合大表或网络不稳定）
   python tools/compare_table_data.py --table team_power_ratings --export-only
   # 然后手动导入到本地数据库，再比较
   
3. 从导出的SQL文件比较
   python tools/compare_table_data.py --table team_power_ratings --file1 dump1.sql --file2 dump2.sql
"""

import sys
import os
import argparse
import hashlib
from typing import Dict, List, Tuple, Optional, Any
from pathlib import Path
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    print("错误: 需要安装 pymysql")
    print("运行: pip install pymysql")
    sys.exit(1)


class DatabaseComparator:
    """数据库表数据比较工具"""
    
    def __init__(self, 
                 host1: str = None, 
                 port1: int = 3306,
                 user1: str = None,
                 password1: str = None,
                 database1: str = None,
                 host2: str = None,
                 port2: int = 3306,
                 user2: str = None,
                 password2: str = None,
                 database2: str = None):
        """初始化两个数据库连接"""
        self.conn1 = None
        self.conn2 = None
        
        if host1:
            self.conn1 = self._connect(host1, port1, user1, password1, database1, "数据库1")
        if host2:
            self.conn2 = self._connect(host2, port2, user2, password2, database2, "数据库2")
    
    def _connect(self, host: str, port: int, user: str, password: str, database: str, label: str):
        """连接数据库"""
        try:
            conn = pymysql.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                database=database,
                charset='utf8mb4',
                cursorclass=DictCursor
            )
            print(f"✅ {label} 连接成功: {host}:{port}/{database}")
            return conn
        except Exception as e:
            print(f"❌ {label} 连接失败: {e}")
            return None
    
    def close(self):
        """关闭数据库连接"""
        if self.conn1:
            self.conn1.close()
        if self.conn2:
            self.conn2.close()
    
    def get_table_data(self, conn, table_name: str) -> List[Dict[str, Any]]:
        """获取表的所有数据"""
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name} ORDER BY {self._get_primary_key(table_name, conn)}")
        return cursor.fetchall()
    
    def _get_primary_key(self, table_name: str, conn) -> str:
        """获取表的主键，用于排序"""
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT COLUMN_NAME 
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE 
            WHERE TABLE_SCHEMA = DATABASE() 
            AND TABLE_NAME = %s 
            AND CONSTRAINT_NAME = 'PRIMARY'
            ORDER BY ORDINAL_POSITION
        """, (table_name,))
        pk_columns = [row['COLUMN_NAME'] for row in cursor.fetchall()]
        if pk_columns:
            return ', '.join(pk_columns)
        # 如果没有主键，尝试使用第一个列
        cursor.execute(f"SHOW COLUMNS FROM {table_name}")
        columns = cursor.fetchall()
        if columns:
            return columns[0]['Field']
        return '1'  # 默认
    
    def calculate_row_hash(self, row: Dict[str, Any]) -> str:
        """计算行的哈希值（用于快速比较）"""
        # 将字典转换为排序后的JSON字符串
        row_str = json.dumps(row, sort_keys=True, default=str)
        return hashlib.md5(row_str.encode('utf-8')).hexdigest()
    
    def compare_tables(self, table_name: str, 
                      detailed: bool = False,
                      ignore_columns: List[str] = None) -> Dict[str, Any]:
        """
        比较两个数据库中的表数据
        
        Args:
            table_name: 表名
            detailed: 是否显示详细差异
            ignore_columns: 忽略比较的列（如 updated_at）
        
        Returns:
            比较结果字典
        """
        if not self.conn1 or not self.conn2:
            return {'error': '数据库连接未建立'}
        
        print(f"\n📊 开始比较表: {table_name}")
        print("=" * 60)
        
        # 获取数据
        print("正在从数据库1读取数据...")
        data1 = self.get_table_data(self.conn1, table_name)
        print(f"数据库1: {len(data1)} 行")
        
        print("正在从数据库2读取数据...")
        data2 = self.get_table_data(self.conn2, table_name)
        print(f"数据库2: {len(data2)} 行")
        
        # 计算哈希值
        print("\n正在计算哈希值...")
        hash1_map = {}
        hash2_map = {}
        
        for row in data1:
            # 忽略指定列
            if ignore_columns:
                row_filtered = {k: v for k, v in row.items() if k not in ignore_columns}
            else:
                row_filtered = row
            row_hash = self.calculate_row_hash(row_filtered)
            hash1_map[row_hash] = row
        
        for row in data2:
            if ignore_columns:
                row_filtered = {k: v for k, v in row.items() if k not in ignore_columns}
            else:
                row_filtered = row
            row_hash = self.calculate_row_hash(row_filtered)
            hash2_map[row_hash] = row
        
        # 比较
        hash1_set = set(hash1_map.keys())
        hash2_set = set(hash2_map.keys())
        
        only_in_1 = hash1_set - hash2_set
        only_in_2 = hash2_set - hash1_set
        common = hash1_set & hash2_set
        
        result = {
            'table_name': table_name,
            'count1': len(data1),
            'count2': len(data2),
            'count_diff': len(data1) - len(data2),
            'only_in_db1': len(only_in_1),
            'only_in_db2': len(only_in_2),
            'common_rows': len(common),
            'is_identical': len(only_in_1) == 0 and len(only_in_2) == 0,
            'detailed_diff': {}
        }
        
        # 详细差异
        if detailed and (only_in_1 or only_in_2):
            result['detailed_diff'] = {
                'only_in_db1': [hash1_map[h] for h in list(only_in_1)[:10]],  # 只显示前10条
                'only_in_db2': [hash2_map[h] for h in list(only_in_2)[:10]]
            }
        
        return result
    
    def export_table_to_sql(self, conn, table_name: str, output_file: str):
        """导出表数据到SQL文件"""
        print(f"正在导出表 {table_name} 到 {output_file}...")
        
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        rows = cursor.fetchall()
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"-- 表 {table_name} 的数据导出\n")
            f.write(f"-- 导出时间: {datetime.now().isoformat()}\n")
            f.write(f"-- 总行数: {len(rows)}\n\n")
            
            for row in rows:
                # 生成INSERT语句
                columns = ', '.join([f"`{k}`" for k in row.keys()])
                values = ', '.join([self._escape_value(v) for v in row.values()])
                f.write(f"INSERT INTO `{table_name}` ({columns}) VALUES ({values});\n")
        
        print(f"✅ 导出完成: {len(rows)} 行")
    
    def _escape_value(self, value):
        """转义SQL值"""
        if value is None:
            return 'NULL'
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, bool):
            return '1' if value else '0'
        else:
            # 转义字符串
            value_str = str(value).replace('\\', '\\\\').replace("'", "\\'")
            return f"'{value_str}'"
    
    def compare_from_files(self, file1: str, file2: str) -> Dict[str, Any]:
        """从SQL文件比较数据"""
        print("从SQL文件比较功能待实现...")
        return {'error': '从SQL文件比较功能待实现'}


def print_comparison_result(result: Dict[str, Any]):
    """打印比较结果"""
    print("\n" + "=" * 60)
    print("📋 比较结果")
    print("=" * 60)
    print(f"表名: {result['table_name']}")
    print(f"数据库1行数: {result['count1']}")
    print(f"数据库2行数: {result['count2']}")
    print(f"行数差异: {result['count_diff']}")
    print(f"\n仅在数据库1中: {result['only_in_db1']} 行")
    print(f"仅在数据库2中: {result['only_in_db2']} 行")
    print(f"共同行数: {result['common_rows']} 行")
    
    if result['is_identical']:
        print("\n✅ 两个表的数据完全一致！")
    else:
        print("\n❌ 两个表的数据不一致！")
        if result.get('detailed_diff'):
            print("\n详细差异（前10条）:")
            if result['detailed_diff'].get('only_in_db1'):
                print("\n仅在数据库1中的数据:")
                for row in result['detailed_diff']['only_in_db1'][:3]:
                    print(f"  {row}")
            if result['detailed_diff'].get('only_in_db2'):
                print("\n仅在数据库2中的数据:")
                for row in result['detailed_diff']['only_in_db2'][:3]:
                    print(f"  {row}")


def main():
    parser = argparse.ArgumentParser(description='比较两个数据库中同一个表的数据')
    
    # 表名
    parser.add_argument('--table', '-t', required=True, help='要比较的表名')
    
    # 数据库1配置
    parser.add_argument('--host1', help='数据库1主机')
    parser.add_argument('--port1', type=int, default=3306, help='数据库1端口')
    parser.add_argument('--user1', help='数据库1用户名')
    parser.add_argument('--password1', help='数据库1密码')
    parser.add_argument('--database1', help='数据库1名称')
    
    # 数据库2配置
    parser.add_argument('--host2', help='数据库2主机')
    parser.add_argument('--port2', type=int, default=3306, help='数据库2端口')
    parser.add_argument('--user2', help='数据库2用户名')
    parser.add_argument('--password2', help='数据库2密码')
    parser.add_argument('--database2', help='数据库2名称')
    
    # 其他选项
    parser.add_argument('--detailed', '-d', action='store_true', help='显示详细差异')
    parser.add_argument('--ignore-columns', '-i', nargs='+', help='忽略比较的列（如 updated_at）')
    parser.add_argument('--export-only', action='store_true', help='仅导出数据，不比较')
    parser.add_argument('--output1', help='数据库1导出文件路径')
    parser.add_argument('--output2', help='数据库2导出文件路径')
    
    # 从环境变量读取配置
    parser.add_argument('--use-env', action='store_true', help='从环境变量读取数据库配置')
    
    args = parser.parse_args()
    
    # 从环境变量读取配置
    if args.use_env:
        from app_environment import get_environment_manager
        env = get_environment_manager()
        db_config = env.config.database
        
        if not args.host1:
            args.host1 = db_config.host
            args.port1 = db_config.port
            args.user1 = db_config.user
            args.password1 = db_config.password
            args.database1 = db_config.name
        
        if not args.host2:
            args.host2 = db_config.host
            args.port2 = db_config.port
            args.user2 = db_config.user
            args.password2 = db_config.password
            args.database2 = db_config.name
    
    # 创建比较器
    comparator = DatabaseComparator(
        host1=args.host1, port1=args.port1, user1=args.user1, 
        password1=args.password1, database1=args.database1,
        host2=args.host2, port2=args.port2, user2=args.user2,
        password2=args.password2, database2=args.database2
    )
    
    try:
        if args.export_only:
            # 仅导出
            if comparator.conn1 and args.output1:
                comparator.export_table_to_sql(comparator.conn1, args.table, args.output1)
            if comparator.conn2 and args.output2:
                comparator.export_table_to_sql(comparator.conn2, args.table, args.output2)
        else:
            # 比较
            if not comparator.conn1 or not comparator.conn2:
                print("❌ 错误: 需要同时连接两个数据库")
                return
            
            result = comparator.compare_tables(
                args.table, 
                detailed=args.detailed,
                ignore_columns=args.ignore_columns
            )
            print_comparison_result(result)
            
            # 保存结果到文件
            output_file = f"comparison_result_{args.table}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n📄 详细结果已保存到: {output_file}")
    
    finally:
        comparator.close()


if __name__ == '__main__':
    main()


