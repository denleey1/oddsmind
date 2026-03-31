#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据库索引检查脚本
检查比赛详情接口相关的表是否有必要的索引
"""

import sys
from app_database import execute_query

def check_indexes():
    """检查必要的索引是否存在"""
    
    print("=" * 80)
    print("数据库索引检查报告")
    print("=" * 80)
    print()
    
    # 需要检查的索引
    required_indexes = [
        {
            'table': 'odds_analysis_results',
            'columns': ['match_id', 'analyzed_at'],
            'name': 'idx_oar_match_analyzed',
            'description': '赔率分析结果表 - 用于查询和排序'
        },
        {
            'table': 'odds_analysis_results',
            'columns': ['match_id'],
            'name': 'idx_oar_match_id',
            'description': '赔率分析结果表 - 用于查询比赛的所有分析'
        },
        {
            'table': 'standings',
            'columns': ['team_id', 'league_id', 'standing_type'],
            'name': 'idx_standings_team_league_type',
            'description': '积分榜表 - 用于批量查询球队积分榜'
        },
        {
            'table': 'fundamental_analysis',
            'columns': ['match_id'],
            'name': 'idx_fa_match_id',
            'description': '基本面分析表 - 用于JOIN查询'
        },
        {
            'table': 'odds_changes',
            'columns': ['match_id', 'company_id'],
            'name': 'idx_oc_match_company',
            'description': '赔率变化表 - 用于JOIN查询'
        },
        {
            'table': 'team_power_ratings',
            'columns': ['team_id', 'company_id', 'league_id'],
            'name': 'idx_tpr_team_company_league',
            'description': '球队实力评级表 - 用于JOIN查询'
        },
        {
            'table': 'matches',
            'columns': ['league_id', 'match_time', 'home_team_id', 'away_team_id'],
            'name': 'idx_matches_league_time_teams',
            'description': '比赛表 - 用于规范比赛ID解析'
        }
    ]
    
    # 检查每个索引
    missing_indexes = []
    existing_indexes = []
    
    for idx_info in required_indexes:
        table = idx_info['table']
        columns = idx_info['columns']
        index_name = idx_info['name']
        description = idx_info['description']
        
        # 检查索引是否存在
        check_sql = """
        SELECT COUNT(*) as cnt
        FROM information_schema.statistics
        WHERE table_schema = DATABASE()
          AND table_name = %s
          AND index_name = %s
        """
        
        try:
            result = execute_query(check_sql, (table, index_name))
            exists = result[0]['cnt'] > 0 if result else False
            
            if exists:
                existing_indexes.append(idx_info)
                print(f"✅ {index_name} 存在")
            else:
                missing_indexes.append(idx_info)
                print(f"❌ {index_name} 缺失")
                print(f"   表: {table}")
                print(f"   列: {', '.join(columns)}")
                print(f"   说明: {description}")
                
                # 生成创建索引的SQL
                columns_str = ', '.join(columns)
                create_sql = f"CREATE INDEX {index_name} ON {table} ({columns_str});"
                print(f"   建议SQL: {create_sql}")
                print()
        except Exception as e:
            print(f"⚠️  检查索引 {index_name} 时出错: {e}")
            print()
    
    print()
    print("=" * 80)
    print("总结")
    print("=" * 80)
    print(f"✅ 已存在的索引: {len(existing_indexes)}")
    print(f"❌ 缺失的索引: {len(missing_indexes)}")
    print()
    
    if missing_indexes:
        print("建议执行的SQL:")
        print()
        for idx_info in missing_indexes:
            columns_str = ', '.join(idx_info['columns'])
            create_sql = f"CREATE INDEX {idx_info['name']} ON {idx_info['table']} ({columns_str});"
            print(create_sql)
        print()
    else:
        print("✅ 所有必要的索引都已存在！")
    
    return len(missing_indexes) == 0

if __name__ == '__main__':
    try:
        success = check_indexes()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"❌ 检查失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)














