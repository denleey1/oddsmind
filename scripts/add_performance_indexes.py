#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
创建性能优化索引
执行sql脚本中的索引创建语句
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv('/home/ubuntu/oddsmind/oddsmind.env')

import pymysql

def create_indexes():
    """创建所有性能优化索引"""
    
    # 从环境变量获取数据库配置
    db_config = {
        'host': os.getenv('MYSQL_HOST', 'localhost'),
        'port': int(os.getenv('MYSQL_PORT', 3306)),
        'user': os.getenv('MYSQL_USER', 'root'),
        'password': os.getenv('MYSQL_PASSWORD', ''),
        'database': os.getenv('MYSQL_DATABASE', 'oddsmind'),
        'charset': 'utf8mb4',
        'cursorclass': pymysql.cursors.DictCursor
    }
    
    print("="*70)
    print("开始创建性能优化索引")
    print("="*70)
    print(f"数据库: {db_config['database']}")
    print(f"主机: {db_config['host']}:{db_config['port']}")
    print()
    
    connection = None
    try:
        # 连接数据库
        connection = pymysql.connect(**db_config)
        cursor = connection.cursor()
        
        # 索引定义
        indexes = [
            # matches表索引
            {
                'table': 'matches',
                'index_name': 'idx_matches_time_status',
                'columns': 'match_time, match_status',
                'description': '优化按时间和状态查询今日比赛'
            },
            {
                'table': 'matches',
                'index_name': 'idx_matches_league_time',
                'columns': 'league_id, match_time',
                'description': '优化按联赛和时间查询'
            },
            {
                'table': 'matches',
                'index_name': 'idx_matches_match_id',
                'columns': 'match_id',
                'description': '优化按比赛ID查询'
            },
            {
                'table': 'matches',
                'index_name': 'idx_matches_home_team_time',
                'columns': 'home_team_id, match_time',
                'description': '优化按主队ID查询'
            },
            {
                'table': 'matches',
                'index_name': 'idx_matches_away_team_time',
                'columns': 'away_team_id, match_time',
                'description': '优化按客队ID查询'
            },
            {
                'table': 'matches',
                'index_name': 'idx_matches_updated_at',
                'columns': 'updated_at',
                'description': '优化按updated_at查询（增量更新）'
            },
            {
                'table': 'matches',
                'index_name': 'idx_matches_unique_match',
                'columns': 'league_id, match_time, home_team_id, away_team_id',
                'description': '优化同时按主队、客队、联赛查询（去重）'
            },
            # odds_analysis_results表索引
            {
                'table': 'odds_analysis_results',
                'index_name': 'idx_odds_analysis_match_id',
                'columns': 'match_id',
                'description': '优化赔率分析结果查询'
            },
            # odds_changes表索引
            {
                'table': 'odds_changes',
                'index_name': 'idx_odds_changes_match_id',
                'columns': 'match_id',
                'description': '优化赔率变化查询'
            },
            # fundamental_analysis表索引
            {
                'table': 'fundamental_analysis',
                'index_name': 'idx_fundamental_analysis_match_id',
                'columns': 'match_id',
                'description': '优化基本面分析查询'
            },
        ]
        
        created_count = 0
        skipped_count = 0
        failed_count = 0
        
        for idx in indexes:
            table = idx['table']
            index_name = idx['index_name']
            columns = idx['columns']
            description = idx['description']
            
            # 检查索引是否已存在
            check_sql = f"""
                SELECT COUNT(*) as count
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                AND table_name = '{table}'
                AND index_name = '{index_name}'
            """
            
            try:
                cursor.execute(check_sql)
                result = cursor.fetchone()
                if result and result['count'] > 0:
                    print(f"\n✓ 索引已存在，跳过: {index_name}")
                    skipped_count += 1
                    continue
            except Exception as e:
                print(f"\n✗ 检查索引失败 {index_name}: {str(e)}")
                # 继续尝试创建
                pass
            
            # 创建索引
            create_sql = f"""
                CREATE INDEX {index_name}
                ON {table}({columns})
            """
            
            try:
                print(f"\n创建索引: {index_name}")
                print(f"  表: {table}")
                print(f"  字段: {columns}")
                print(f"  说明: {description}")
                
                cursor.execute(create_sql)
                connection.commit()
                print(f"  ✓ 创建成功")
                created_count += 1
                
            except Exception as e:
                error_msg = str(e)
                if "Duplicate key name" in error_msg:
                    print(f"  ⚠ 索引已存在（重复）")
                    skipped_count += 1
                else:
                    print(f"  ✗ 创建失败: {error_msg}")
                    failed_count += 1
        
        # 输出统计
        print("\n" + "="*70)
        print("索引创建完成")
        print("="*70)
        print(f"  成功创建: {created_count}")
        print(f"  跳过（已存在）: {skipped_count}")
        print(f"  失败: {failed_count}")
        print(f"  总计: {len(indexes)}")
        
        # 显示matches表的索引
        print("\nmatches表当前索引:")
        show_sql = "SHOW INDEX FROM matches"
        try:
            cursor.execute(show_sql)
            indexes_info = cursor.fetchall()
            if indexes_info:
                idx_dict = {}
                for idx_info in indexes_info:
                    idx_name = idx_info['Key_name']
                    if idx_name not in idx_dict:
                        idx_dict[idx_name] = {
                            'non_unique': idx_info['Non_unique'],
                            'columns': []
                        }
                    idx_dict[idx_name]['columns'].append(idx_info['Column_name'])
                
                for idx_name, idx_info in sorted(idx_dict.items()):
                    unique = "UNIQUE" if idx_info['non_unique'] == 0 else ""
                    columns = ", ".join(idx_info['columns'])
                    print(f"  - {idx_name} ({unique}): {columns}")
        except Exception as e:
            print(f"  获取索引列表失败: {str(e)}")
            
    except Exception as e:
        print(f"\n❌ 数据库连接或执行失败: {str(e)}")
        import traceback
        traceback.print_exc()
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    create_indexes()
