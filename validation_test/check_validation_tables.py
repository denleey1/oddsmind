#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查验证结果表状态
"""

import sys
from pathlib import Path

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

def check_validation_tables():
    """检查验证结果表状态"""
    db = get_connection()
    
    # 查找所有验证结果表
    query = """
    SELECT 
        TABLE_NAME as table_name,
        TABLE_COMMENT as table_comment
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() 
    AND TABLE_NAME LIKE '%validation_results'
    ORDER BY TABLE_NAME
    """
    
    tables = db.execute_query(query, fetch='all')
    
    print("现有验证结果表:")
    print("=" * 60)
    
    if not tables:
        print("❌ 没有找到任何验证结果表")
        return
    
    for table in tables:
        table_name = table['table_name']
        comment = table['table_comment'] or ''
        
        # 获取记录数
        count_query = f"SELECT COUNT(*) as cnt FROM `{table_name}`"
        count_result = db.execute_query(count_query, fetch='one')
        count = count_result['cnt']
        
        # 获取轮次范围
        if count > 0:
            range_query = f"""
            SELECT 
                MIN(round_number) as min_round,
                MAX(round_number) as max_round,
                COUNT(DISTINCT company_id) as companies,
                COUNT(DISTINCT match_id) as matches
            FROM `{table_name}`
            """
            range_result = db.execute_query(range_query, fetch='one')
            
            print(f"✅ {table_name}")
            print(f"   记录数: {count}")
            print(f"   轮次: 第{range_result['min_round']}-{range_result['max_round']}轮")
            print(f"   比赛: {range_result['matches']} 场")
            print(f"   公司: {range_result['companies']} 家")
            if comment:
                print(f"   备注: {comment}")
        else:
            print(f"⚠️ {table_name} (空表)")
        
        print()

if __name__ == "__main__":
    check_validation_tables()