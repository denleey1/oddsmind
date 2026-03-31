#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查所有推荐术语的映射准确性
"""

import sys
from pathlib import Path

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection


def get_all_recommendations():
    """获取数据库中所有出现过的推荐术语"""
    db = get_connection()
    
    print("检查所有联赛验证结果中出现过的推荐术语...")
    
    # 查找所有验证结果表
    tables_query = """
    SELECT TABLE_NAME 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() 
    AND TABLE_NAME LIKE '%validation_results'
    """
    
    tables = db.execute_query(tables_query, fetch='all')
    
    all_recommendations = set()
    
    for table in tables:
        table_name = table['TABLE_NAME']
        
        try:
            # 获取该表中所有推荐术语
            rec_query = f"""
            SELECT DISTINCT initial_recommendation, current_recommendation
            FROM `{table_name}`
            WHERE initial_recommendation IS NOT NULL
            AND current_recommendation IS NOT NULL
            """
            
            results = db.execute_query(rec_query, fetch='all')
            
            for row in results:
                if row['initial_recommendation']:
                    all_recommendations.add(row['initial_recommendation'])
                if row['current_recommendation']:
                    all_recommendations.add(row['current_recommendation'])
            
            print(f"✅ {table_name}: 已检查")
            
        except Exception as e:
            print(f"❌ {table_name}: 查询失败 - {e}")
    
    return sorted(all_recommendations)


def check_mapping_completeness():
    """检查映射文件的完整性"""
    import json
    
    # 获取实际使用的推荐术语
    actual_recommendations = get_all_recommendations()
    
    print(f"\n数据库中发现的推荐术语总数: {len(actual_recommendations)}")
    print("-" * 60)
    
    for i, rec in enumerate(actual_recommendations, 1):
        print(f"{i:2d}. {rec}")
    
    # 检查映射文件
    mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
    
    if not mapping_file.exists():
        print("\n❌ 映射文件不存在!")
        return
    
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        mapped_recommendations = set(mapping_data['recommendations'].keys())
        
        print(f"\n映射文件中的推荐术语总数: {len(mapped_recommendations)}")
        print("-" * 60)
        
        # 检查缺失的映射
        missing_in_mapping = set(actual_recommendations) - mapped_recommendations
        extra_in_mapping = mapped_recommendations - set(actual_recommendations)
        
        if missing_in_mapping:
            print(f"\n❌ 映射文件中缺失的推荐术语 ({len(missing_in_mapping)}个):")
            for rec in sorted(missing_in_mapping):
                print(f"   - {rec}")
        
        if extra_in_mapping:
            print(f"\n⚠️ 映射文件中多余的推荐术语 ({len(extra_in_mapping)}个):")
            for rec in sorted(extra_in_mapping):
                print(f"   - {rec}")
        
        if not missing_in_mapping and not extra_in_mapping:
            print("\n✅ 映射文件完整，所有推荐术语都有对应的映射")
        
        # 显示所有映射
        print(f"\n当前映射规则:")
        print("-" * 80)
        print(f"{'推荐术语':<20} {'映射结果':<25} {'描述'}")
        print("-" * 80)
        
        for rec in sorted(actual_recommendations):
            if rec in mapping_data['recommendations']:
                rule = mapping_data['recommendations'][rec]
                result = rule.get('result', 'unknown')
                desc = rule.get('description', '')
                print(f"{rec:<20} {str(result):<25} {desc}")
            else:
                print(f"{rec:<20} {'❌ 缺失':<25} {'需要添加映射'}")
        
        return missing_in_mapping, extra_in_mapping, mapping_data
        
    except Exception as e:
        print(f"❌ 读取映射文件失败: {e}")
        return None, None, None


def analyze_recommendation_patterns():
    """分析推荐术语的规律"""
    actual_recommendations = get_all_recommendations()
    
    print(f"\n推荐术语分析:")
    print("-" * 60)
    
    patterns = {
        '让球胜': [rec for rec in actual_recommendations if '让' in rec and '胜' in rec],
        '让球平': [rec for rec in actual_recommendations if '让' in rec and '平' in rec],
        '让球负': [rec for rec in actual_recommendations if '让' in rec and '负' in rec],
        '受球胜': [rec for rec in actual_recommendations if '受' in rec and '胜' in rec],
        '受球平': [rec for rec in actual_recommendations if '受' in rec and '平' in rec],
        '受球负': [rec for rec in actual_recommendations if '受' in rec and '负' in rec],
        '双平系列': [rec for rec in actual_recommendations if '双平' in rec],
        '纯平局': [rec for rec in actual_recommendations if rec == '平'],
        '其他': []
    }
    
    categorized = set()
    for category, recs in patterns.items():
        categorized.update(recs)
    
    patterns['其他'] = [rec for rec in actual_recommendations if rec not in categorized]
    
    for category, recs in patterns.items():
        if recs:
            print(f"\n{category} ({len(recs)}个):")
            for rec in sorted(recs):
                print(f"   - {rec}")


def main():
    """主函数"""
    print("="*80)
    print("推荐术语映射完整性检查")
    print("="*80)
    
    missing, extra, mapping_data = check_mapping_completeness()
    
    analyze_recommendation_patterns()
    
    if missing:
        print(f"\n⚠️ 发现 {len(missing)} 个缺失的映射，需要手动添加!")
    
    print("\n" + "="*80)
    print("检查完成!")


if __name__ == "__main__":
    main()