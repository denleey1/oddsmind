#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清空titan007_football.db数据库
可选择性清空所有数据或指定表
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import os
import sqlite3
import argparse
from datetime import datetime

def clear_database(db_path: str = "data/titan007_football.db", 
                   backup: bool = True,
                   tables: list = None):
    """清空数据库
    
    Args:
        db_path: 数据库路径
        backup: 是否备份
        tables: 要清空的表列表，None表示清空所有表
    """
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return False
    
    # 备份数据库
    if backup:
        backup_path = db_path.replace('.db', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')
        print(f"备份数据库到: {backup_path}")
        
        # 复制文件
        import shutil
        shutil.copy2(db_path, backup_path)
        print("备份完成")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 获取所有表名
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name NOT LIKE 'sqlite_%'
            """)
            all_tables = [row[0] for row in cursor.fetchall()]
            
            if not all_tables:
                print("数据库中没有表")
                return False
            
            # 确定要清空的表
            if tables:
                # 验证指定的表是否存在
                tables_to_clear = [t for t in tables if t in all_tables]
                invalid_tables = [t for t in tables if t not in all_tables]
                
                if invalid_tables:
                    print(f"警告：以下表不存在: {', '.join(invalid_tables)}")
                
                if not tables_to_clear:
                    print("没有有效的表可以清空")
                    return False
            else:
                tables_to_clear = all_tables
            
            # 显示要清空的表
            print("\n将要清空以下表：")
            for table in tables_to_clear:
                # 获取表的记录数
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  - {table}: {count} 条记录")
            
            # 确认
            print(f"\n总计 {len(tables_to_clear)} 个表")
            answer = input("确定要清空这些表吗？(y/n): ").strip().lower()
            
            if answer != 'y':
                print("操作已取消")
                return False
            
            # 清空表
            print("\n开始清空表...")
            
            # 禁用外键约束
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            for table in tables_to_clear:
                try:
                    cursor.execute(f"DELETE FROM {table}")
                    deleted = cursor.rowcount
                    print(f"  清空 {table}: 删除 {deleted} 条记录")
                    
                    # 重置自增ID
                    cursor.execute(f"DELETE FROM sqlite_sequence WHERE name='{table}'")
                    
                except Exception as e:
                    print(f"  清空 {table} 失败: {e}")
            
            # 重新启用外键约束
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # 优化数据库
            print("\n优化数据库...")
            cursor.execute("VACUUM")
            
            conn.commit()
            print("\n清空完成！")
            
            # 显示清空后的状态
            print("\n清空后的数据库状态：")
            for table in tables_to_clear:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  - {table}: {count} 条记录")
            
            return True
            
    except Exception as e:
        print(f"清空数据库时出错: {e}")
        return False


def show_database_info(db_path: str = "data/titan007_football.db"):
    """显示数据库信息"""
    
    if not os.path.exists(db_path):
        print(f"数据库文件不存在: {db_path}")
        return
    
    # 获取文件大小
    file_size = os.path.getsize(db_path)
    size_mb = file_size / (1024 * 1024)
    
    print(f"\n数据库信息：")
    print(f"  文件路径: {db_path}")
    print(f"  文件大小: {size_mb:.2f} MB")
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # 获取所有表及其记录数
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                AND name NOT LIKE 'sqlite_%'
                ORDER BY name
            """)
            
            tables = cursor.fetchall()
            
            print(f"\n表信息（共 {len(tables)} 个表）：")
            total_records = 0
            
            for table_name in tables:
                table_name = table_name[0]
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                total_records += count
                
                if count > 0:
                    print(f"  {table_name:30} {count:>10,} 条记录")
            
            print(f"\n总记录数: {total_records:,}")
            
    except Exception as e:
        print(f"读取数据库信息时出错: {e}")


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='清空titan007_football.db数据库')
    parser.add_argument('--db', type=str, default='data/titan007_football.db', 
                       help='数据库文件路径')
    parser.add_argument('--no-backup', action='store_true', 
                       help='不备份数据库')
    parser.add_argument('--tables', type=str, 
                       help='要清空的表名，用逗号分隔。不指定则清空所有表')
    parser.add_argument('--info', action='store_true', 
                       help='只显示数据库信息，不清空')
    parser.add_argument('--force', action='store_true',
                       help='跳过确认，直接清空')
    
    args = parser.parse_args()
    
    # 如果只是查看信息
    if args.info:
        show_database_info(args.db)
        return
    
    # 解析要清空的表
    tables_to_clear = None
    if args.tables:
        tables_to_clear = [t.strip() for t in args.tables.split(',')]
    
    # 显示警告
    if not args.force:
        print("="*60)
        print("警告：此操作将清空数据库中的数据！")
        print("="*60)
        show_database_info(args.db)
    
    # 清空数据库
    success = clear_database(
        db_path=args.db,
        backup=not args.no_backup,
        tables=tables_to_clear
    )
    
    if success:
        print("\n操作成功完成！")
    else:
        print("\n操作失败或被取消")
        sys.exit(1)


if __name__ == '__main__':
    main()