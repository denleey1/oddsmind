#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
计算各联赛验证结果的准确率
"""

import sys
from pathlib import Path

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
import json

def load_recommendation_mapping():
    """加载推荐映射规则"""
    mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
    with open(mapping_file, 'r', encoding='utf-8') as f:
        return json.load(f)

def judge_match_result(home_score, away_score, recommendation, mapping):
    """判断推荐是否正确"""
    # 计算实际结果
    if home_score > away_score:
        actual_result = 'home_win'
    elif home_score < away_score:
        actual_result = 'away_win'
    else:
        actual_result = 'draw'
    
    # 获取推荐对应的预测结果
    if recommendation in mapping:
        rule = mapping[recommendation]
        
        # 特殊处理双平偏让平（需要根据盘口动态判断）
        if recommendation == "双平偏让平":
            # 这里简化处理，实际应该根据盘口判断
            predicted_result = 'draw'
        else:
            predicted_result = rule['result']
        
        # 判断是否正确
        return 1 if predicted_result == actual_result else 0
    else:
        return 0  # 未知推荐视为错误

def calculate_league_accuracy(league_code, league_name):
    """计算单个联赛的准确率"""
    db = get_connection()
    mapping = load_recommendation_mapping()
    
    table_name = f"{league_code}_validation_results"
    
    # 检查表是否存在
    check_sql = f"""
    SELECT COUNT(*) as cnt 
    FROM information_schema.tables 
    WHERE table_schema = DATABASE() 
    AND table_name = '{table_name}'
    """
    
    result = db.execute_query(check_sql, fetch='one')
    if result['cnt'] == 0:
        print(f"❌ {league_name}验证结果表 {table_name} 不存在")
        return None
    
    # 获取所有验证结果
    query = f"""
    SELECT 
        match_id, company_id, round_number,
        home_team_name, away_team_name,
        actual_home_score, actual_away_score,
        initial_recommendation, current_recommendation,
        initial_rule_diff, current_rule_diff,
        power_diff
    FROM `{table_name}`
    """
    
    results = db.execute_query(query, fetch='all')
    
    if not results:
        print(f"⚠️ {league_name}没有验证数据")
        return None
    
    # 计算每个公司的准确率
    company_stats = {}
    
    for row in results:
        company_id = row['company_id']
        
        if company_id not in company_stats:
            company_stats[company_id] = {
                'total': 0,
                'initial_correct': 0,
                'current_correct': 0,
                'consistent': 0  # 初盘和即时盘推荐一致的次数
            }
        
        stats = company_stats[company_id]
        stats['total'] += 1
        
        # 判断初盘推荐是否正确
        initial_correct = judge_match_result(
            row['actual_home_score'], 
            row['actual_away_score'],
            row['initial_recommendation'],
            mapping['recommendations']
        )
        stats['initial_correct'] += initial_correct
        
        # 判断即时盘推荐是否正确
        current_correct = judge_match_result(
            row['actual_home_score'],
            row['actual_away_score'], 
            row['current_recommendation'],
            mapping['recommendations']
        )
        stats['current_correct'] += current_correct
        
        # 检查一致性
        if row['initial_recommendation'] == row['current_recommendation']:
            stats['consistent'] += 1
    
    # 计算准确率并排序
    company_accuracies = []
    for company_id, stats in company_stats.items():
        if stats['total'] > 0:
            company_accuracies.append({
                'company_id': company_id,
                'total': stats['total'],
                'initial_accuracy': stats['initial_correct'] / stats['total'],
                'current_accuracy': stats['current_correct'] / stats['total'],
                'consistency': stats['consistent'] / stats['total'],
                'initial_correct': stats['initial_correct'],
                'current_correct': stats['current_correct']
            })
    
    # 按即时盘准确率排序
    company_accuracies.sort(key=lambda x: x['current_accuracy'], reverse=True)
    
    print(f"\n{'='*80}")
    print(f"{league_name} 验证准确率分析")
    print(f"{'='*80}")
    print(f"总预测数: {len(results)}")
    print(f"参与公司: {len(company_accuracies)}")
    
    # 整体统计
    total_predictions = len(results)
    total_initial_correct = sum(c['initial_correct'] for c in company_accuracies)
    total_current_correct = sum(c['current_correct'] for c in company_accuracies)
    
    print(f"整体初盘准确率: {total_initial_correct/total_predictions:.2%}")
    print(f"整体即时盘准确率: {total_current_correct/total_predictions:.2%}")
    
    # 显示前20名公司
    print(f"\n{'='*80}")
    print(f"即时盘准确率TOP20公司")
    print(f"{'='*80}")
    print(f"{'排名':<6} {'公司ID':<10} {'预测数':<10} {'初盘准确率':<12} {'即时准确率':<12} {'一致性':<10}")
    print(f"{'-'*80}")
    
    for i, company in enumerate(company_accuracies[:20], 1):
        print(f"{i:<6} {company['company_id']:<10} {company['total']:<10} "
              f"{company['initial_accuracy']:.2%}{'':6} "
              f"{company['current_accuracy']:.2%}{'':6} "
              f"{company['consistency']:.2%}")
    
    # 保存准确率到新表
    save_accuracy_to_db(db, league_code, league_name, company_accuracies)
    
    return company_accuracies

def save_accuracy_to_db(db, league_code, league_name, accuracies):
    """保存准确率到数据库"""
    table_name = f"{league_code}_accuracy_analysis"
    
    # 创建准确率表
    create_sql = f"""
    CREATE TABLE IF NOT EXISTS `{table_name}` (
        `company_id` int PRIMARY KEY,
        `total_predictions` int,
        `initial_correct` int,
        `current_correct` int,
        `initial_accuracy` decimal(5,4),
        `current_accuracy` decimal(5,4),
        `consistency` decimal(5,4),
        `rank` int,
        `analysis_time` datetime DEFAULT CURRENT_TIMESTAMP,
        INDEX `idx_accuracy` (`current_accuracy` DESC, `initial_accuracy` DESC)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{league_name}准确率分析表'
    """
    
    db.execute_query(create_sql)
    db.execute_query(f"TRUNCATE TABLE `{table_name}`")
    
    # 插入数据
    insert_sql = f"""
    INSERT INTO `{table_name}` (
        company_id, total_predictions, initial_correct, current_correct,
        initial_accuracy, current_accuracy, consistency, `rank`
    ) VALUES (
        %(company_id)s, %(total)s, %(initial_correct)s, %(current_correct)s,
        %(initial_accuracy)s, %(current_accuracy)s, %(consistency)s, %(rank)s
    )
    """
    
    for i, acc in enumerate(accuracies, 1):
        acc['rank'] = i
    
    db.execute_many(insert_sql, accuracies)
    print(f"\n✅ 准确率分析已保存到表 {table_name}")

def main():
    """主函数"""
    leagues = [
        {'code': 'bundesliga', 'name': '德甲'},
        {'code': 'ligue1', 'name': '法甲'},
        {'code': 'kleague', 'name': '韩国K联赛'},
        {'code': 'jleague', 'name': '日职联'},
        {'code': 'laliga', 'name': '西甲'},
        {'code': 'seriea', 'name': '意甲'},
        {'code': 'premier', 'name': '英超'}
    ]
    
    print("开始计算各联赛验证准确率...")
    
    all_results = []
    for league in leagues:
        result = calculate_league_accuracy(league['code'], league['name'])
        if result:
            all_results.append({
                'league': league['name'],
                'companies': len(result),
                'best_accuracy': result[0]['current_accuracy'] if result else 0,
                'best_company': result[0]['company_id'] if result else 0
            })
    
    # 汇总报告
    if all_results:
        print(f"\n{'='*80}")
        print("所有联赛最佳准确率汇总")
        print(f"{'='*80}")
        print(f"{'联赛':<15} {'公司数':<10} {'最佳公司':<10} {'最佳准确率':<12}")
        print(f"{'-'*80}")
        
        for result in all_results:
            print(f"{result['league']:<15} {result['companies']:<10} "
                  f"{result['best_company']:<10} {result['best_accuracy']:.2%}")

if __name__ == "__main__":
    main()