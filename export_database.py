#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库导出工具
"""
import os
import sys
from pathlib import Path
from datetime import datetime
import subprocess

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

def get_db_config():
    """获取数据库配置"""
    # 从connection.py读取配置
    from database.connection import DB_CONFIG
    return DB_CONFIG

def export_database_structure():
    """导出数据库结构"""
    config = get_db_config()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"oddsmind_structure_{timestamp}.sql"
    
    # 构建mysqldump命令（只导出结构）
    cmd = [
        'mysqldump',
        '-h', config['host'],
        '-P', str(config['port']),
        '-u', config['user'],
        f'-p{config["password"]}',
        '--no-data',
        '--routines',
        '--triggers',
        config['database']
    ]
    
    print(f"正在导出数据库结构到 {output_file}...")
    
    try:
        with open(output_file, 'w', encoding='utf8') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            
        if result.returncode == 0:
            print(f"[SUCCESS] 数据库结构导出成功: {output_file}")
            return output_file
        else:
            print(f"[ERROR] 导出失败: {result.stderr}")
            return None
    except FileNotFoundError:
        print("✗ 未找到mysqldump命令，请确保MySQL已安装并添加到PATH")
        return None
    except Exception as e:
        print(f"✗ 导出错误: {e}")
        return None

def export_database_with_data():
    """导出完整数据库（包含数据）"""
    config = get_db_config()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"oddsmind_full_{timestamp}.sql"
    
    # 构建mysqldump命令
    cmd = [
        'mysqldump',
        '-h', config['host'],
        '-P', str(config['port']),
        '-u', config['user'],
        f'-p{config["password"]}',
        '--single-transaction',
        '--routines',
        '--triggers',
        '--complete-insert',
        config['database']
    ]
    
    print(f"正在导出完整数据库到 {output_file}...")
    
    try:
        with open(output_file, 'w', encoding='utf8') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            
        if result.returncode == 0:
            file_size = os.path.getsize(output_file) / (1024 * 1024)  # MB
            print(f"[SUCCESS] 数据库导出成功: {output_file} (大小: {file_size:.2f} MB)")
            return output_file
        else:
            print(f"[ERROR] 导出失败: {result.stderr}")
            return None
    except FileNotFoundError:
        print("✗ 未找到mysqldump命令，请确保MySQL已安装并添加到PATH")
        return None
    except Exception as e:
        print(f"✗ 导出错误: {e}")
        return None

def export_core_tables():
    """只导出核心表"""
    config = get_db_config()
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"oddsmind_core_{timestamp}.sql"
    
    # 核心表列表
    core_tables = [
        'leagues',
        'teams', 
        'companies',
        'standard_odds_win',
        'standard_odds_loss',
        'rule_conditions_home',
        'rule_conditions_away',
        'rule_outcomes'
    ]
    
    # 构建mysqldump命令
    cmd = [
        'mysqldump',
        '-h', config['host'],
        '-P', str(config['port']),
        '-u', config['user'],
        f'-p{config["password"]}',
        '--single-transaction',
        '--complete-insert',
        config['database']
    ] + core_tables
    
    print(f"正在导出核心表到 {output_file}...")
    print(f"包含的表: {', '.join(core_tables)}")
    
    try:
        with open(output_file, 'w', encoding='utf8') as f:
            result = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, text=True)
            
        if result.returncode == 0:
            file_size = os.path.getsize(output_file) / 1024  # KB
            print(f"[SUCCESS] 核心表导出成功: {output_file} (大小: {file_size:.2f} KB)")
            return output_file
        else:
            print(f"[ERROR] 导出失败: {result.stderr}")
            return None
    except FileNotFoundError:
        print("✗ 未找到mysqldump命令，请确保MySQL已安装并添加到PATH")
        return None
    except Exception as e:
        print(f"✗ 导出错误: {e}")
        return None

def export_using_python():
    """使用Python直接导出（当mysqldump不可用时）"""
    print("使用Python方法导出数据...")
    
    db = get_connection()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = f"oddsmind_python_export_{timestamp}.sql"
    
    try:
        # 获取所有表名
        tables_query = "SHOW TABLES"
        tables = db.execute_query(tables_query, fetch='all')
        
        with open(output_file, 'w', encoding='utf8') as f:
            f.write("-- OddsMind Database Export\n")
            f.write(f"-- Generated at {datetime.now()}\n")
            f.write("-- Using Python export method\n\n")
            
            f.write("SET FOREIGN_KEY_CHECKS=0;\n")
            f.write("SET SQL_MODE='NO_AUTO_VALUE_ON_ZERO';\n\n")
            
            # 导出每个表
            for table_row in tables:
                table_name = list(table_row.values())[0]
                print(f"  导出表: {table_name}")
                
                # 获取建表语句
                create_query = f"SHOW CREATE TABLE {table_name}"
                create_result = db.execute_query(create_query, fetch='one')
                create_sql = create_result['Create Table']
                
                f.write(f"-- Table: {table_name}\n")
                f.write(f"DROP TABLE IF EXISTS `{table_name}`;\n")
                f.write(f"{create_sql};\n\n")
                
                # 如果是核心表，导出数据
                core_tables = ['leagues', 'teams', 'companies', 'standard_odds_win', 
                              'standard_odds_loss', 'rule_conditions_home', 
                              'rule_conditions_away', 'rule_outcomes']
                
                if table_name in core_tables:
                    # 获取数据
                    data_query = f"SELECT * FROM {table_name}"
                    data = db.execute_query(data_query, fetch='all')
                    
                    if data:
                        f.write(f"-- Data for table {table_name}\n")
                        for row in data:
                            values = []
                            for v in row.values():
                                if v is None:
                                    values.append('NULL')
                                elif isinstance(v, (int, float)):
                                    values.append(str(v))
                                else:
                                    # 转义字符串
                                    v_str = str(v).replace("'", "''")
                                    values.append(f"'{v_str}'")
                            
                            insert_sql = f"INSERT INTO `{table_name}` VALUES ({','.join(values)});\n"
                            f.write(insert_sql)
                        f.write("\n")
            
            f.write("SET FOREIGN_KEY_CHECKS=1;\n")
        
        file_size = os.path.getsize(output_file) / 1024  # KB
        print(f"[SUCCESS] Python导出成功: {output_file} (大小: {file_size:.2f} KB)")
        return output_file
        
    except Exception as e:
        print(f"[ERROR] Python导出失败: {e}")
        return None
    finally:
        db.close()

def main():
    print("=" * 50)
    print("OddsMind 数据库导出工具")
    print("=" * 50)
    
    print("\n请选择导出方式：")
    print("1. 导出完整数据库（结构+所有数据）")
    print("2. 只导出数据库结构（无数据）")
    print("3. 只导出核心表（结构+核心数据）")
    print("4. 使用Python方法导出（mysqldump不可用时）")
    
    choice = input("\n请输入选项 (1-4): ").strip()
    
    if choice == '1':
        result = export_database_with_data()
    elif choice == '2':
        result = export_database_structure()
    elif choice == '3':
        result = export_core_tables()
    elif choice == '4':
        result = export_using_python()
    else:
        print("无效选项")
        return
    
    if result:
        print(f"\n导出完成！文件位置：")
        print(f"  {PROJECT_ROOT}\\{result}")
        print("\n部署步骤：")
        print("1. 将此SQL文件复制到新服务器")
        print("2. 在新服务器执行：mysql -u root -p oddsmind < " + result)
    else:
        print("\n导出失败，请检查错误信息")

if __name__ == "__main__":
    main()