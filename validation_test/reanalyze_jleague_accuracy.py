#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
重新分析日职联验证结果的准确率
使用修复后的推荐结果映射功能
"""

import sys
from pathlib import Path
from typing import Dict, List

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection


def map_recommendation_to_result(recommendation: str) -> str:
    """
    将推荐结果映射为比赛结果
    使用已有的recommendation_mapping.json规则
    注意：这个函数只用于单一结果映射，多结果的准确性判断在另外处理
    """
    if not recommendation:
        return 'unknown'
    
    # 映射规则（基于recommendation_mapping.json）
    mapping = {
        "主让1胜": "home_win",
        "主让1平": "home_win", 
        "主让1负": "draw",  # 多结果中取第一个
        "主让2胜": "home_win",
        "主让2平": "home_win",
        "客让1胜": "away_win",
        "客让1平": "away_win",
        "客让2胜": "away_win",
        "客让2平": "away_win",
        "主受1胜": "home_win",  # 多结果中取第一个
        "客受1胜": "away_win",  # 多结果中取第一个
        "平": "draw",
        "双平": "draw",  # 任意结果都对，这里用draw代表
        "双平偏平": "draw",
        "双平偏让平": "draw",
        "双平偏客平": "draw"
    }
    
    return mapping.get(recommendation, 'unknown')


def is_recommendation_correct(recommendation: str, actual_result: str, rule_diff: float = None) -> bool:
    """
    判断推荐是否正确
    正确处理多结果和动态判断的情况
    """
    if not recommendation:
        return False
    
    # 特殊处理双平偏让平的动态判断
    if recommendation == "双平偏让平":
        if rule_diff is None:
            return False
        # 根据rule_diff动态判断
        if rule_diff < 0:
            expected_result = "home_win"  # 主队规则值小，预测主胜
        elif rule_diff > 0:
            expected_result = "away_win"  # 客队规则值小，预测客胜
        else:
            expected_result = "draw"      # 规则值相等，预测平局
        return actual_result == expected_result
    
    # 完整的映射规则（包含多结果）
    mapping = {
        "主让1胜": ["home_win"],
        "主让1平": ["home_win"], 
        "主让1负": ["draw", "away_win"],  # 两个结果都算正确
        "主让2胜": ["home_win"],
        "主让2平": ["home_win"],
        "客让1胜": ["away_win"],
        "客让1平": ["away_win"],
        "客让2胜": ["away_win"],
        "客让2平": ["away_win"],
        "主受1胜": ["home_win", "draw"],  # 两个结果都算正确
        "客受1胜": ["away_win", "draw"],  # 两个结果都算正确
        "平": ["draw"],
        "双平": ["home_win", "draw", "away_win"],  # 任意结果都算正确
        "双平偏平": ["draw"],
        "双平偏客平": ["draw"]
    }
    
    if recommendation in mapping:
        expected_results = mapping[recommendation]
        return actual_result in expected_results
    
    return False


def get_actual_result(home_score: int, away_score: int) -> str:
    """根据比分获取实际比赛结果"""
    if home_score > away_score:
        return 'home_win'
    elif home_score < away_score:
        return 'away_win'
    else:
        return 'draw'


def reanalyze_accuracy():
    """重新分析准确率"""
    db = get_connection()
    
    # 获取所有验证结果
    query = """
        SELECT 
            match_id, company_id, round_number,
            home_team_name, away_team_name,
            actual_home_score, actual_away_score,
            initial_recommendation, current_recommendation,
            initial_rule_diff, current_rule_diff
        FROM jleague_validation_results
        ORDER BY round_number, match_id, company_id
    """
    
    results = db.execute_query(query, fetch='all')
    print(f"加载了 {len(results)} 条验证结果")
    
    # 处理每条结果
    processed_results = []
    for result in results:
        # 计算实际结果
        actual_result = get_actual_result(
            result['actual_home_score'], 
            result['actual_away_score']
        )
        
        # 映射推荐结果
        initial_pred = map_recommendation_to_result(result['initial_recommendation'])
        current_pred = map_recommendation_to_result(result['current_recommendation'])
        
        processed_result = {
            'match_id': result['match_id'],
            'company_id': result['company_id'],
            'round_number': result['round_number'],
            'home_team_name': result['home_team_name'],
            'away_team_name': result['away_team_name'],
            'actual_result': actual_result,
            'initial_recommendation': result['initial_recommendation'],
            'current_recommendation': result['current_recommendation'],
            'initial_pred': initial_pred,
            'current_pred': current_pred,
            'initial_correct': is_recommendation_correct(result['initial_recommendation'], actual_result, result['initial_rule_diff']),
            'current_correct': is_recommendation_correct(result['current_recommendation'], actual_result, result['current_rule_diff'])
        }
        
        processed_results.append(processed_result)
    
    # 显示准确率统计
    display_accuracy_statistics(processed_results)


def display_accuracy_statistics(results: List[Dict]):
    """显示准确率统计分析"""
    if not results:
        print("没有数据可供统计")
        return
    
    print("\n" + "="*80)
    print("日职联预测准确率分析报告 (修复后)")
    print("="*80)
    
    # 1. 整体统计
    total_predictions = len(results)
    companies = set(r['company_id'] for r in results)
    matches = set(r['match_id'] for r in results)
    rounds = set(r['round_number'] for r in results)
    
    print(f"基本信息:")
    print(f"   总预测数: {total_predictions:,} 次")
    print(f"   涉及比赛: {len(matches)} 场")
    print(f"   涉及公司: {len(companies)} 家") 
    print(f"   涉及轮次: 第{min(rounds)}-{max(rounds)}轮")
    
    # 2. 各公司准确率分析
    print(f"\n各公司预测准确率排名 (TOP 15):")
    print("-"*70)
    
    company_stats = {}
    for company_id in companies:
        company_results = [r for r in results if r['company_id'] == company_id]
        
        initial_correct = sum(1 for r in company_results if r['initial_correct'])
        current_correct = sum(1 for r in company_results if r['current_correct'])
        total = len(company_results)
        
        initial_accuracy = (initial_correct / total) * 100 if total > 0 else 0
        current_accuracy = (current_correct / total) * 100 if total > 0 else 0
        
        company_stats[company_id] = {
            'total': total,
            'initial_correct': initial_correct,
            'current_correct': current_correct,
            'initial_accuracy': initial_accuracy,
            'current_accuracy': current_accuracy
        }
    
    # 按初盘准确率排序，显示前15名
    sorted_companies = sorted(company_stats.items(), key=lambda x: x[1]['initial_accuracy'], reverse=True)[:15]
    
    print(f"{'公司ID':<8} {'总预测':<8} {'初盘正确':<10} {'初盘准确率':<12} {'即时正确':<10} {'即时准确率':<12}")
    print("-"*70)
    
    for company_id, stats in sorted_companies:
        print(f"{company_id:<8} {stats['total']:<8} {stats['initial_correct']:<10} "
              f"{stats['initial_accuracy']:.1f}%{'':<7} {stats['current_correct']:<10} "
              f"{stats['current_accuracy']:.1f}%")
    
    # 3. 最佳公司
    if sorted_companies:
        best_company = sorted_companies[0]
        print(f"\n最佳预测公司:")
        print(f"   公司ID: {best_company[0]}")
        print(f"   初盘准确率: {best_company[1]['initial_accuracy']:.1f}%")
        print(f"   即时准确率: {best_company[1]['current_accuracy']:.1f}%")
    
    # 4. 胜平负准确率分析
    print(f"\n胜平负预测准确率分析:")
    print("-"*60)
    
    result_types = ['home_win', 'draw', 'away_win'] 
    result_names = {'home_win': '主胜', 'draw': '平局', 'away_win': '客胜'}
    
    for result_type in result_types:
        # 实际该结果的比赛
        actual_results = [r for r in results if r['actual_result'] == result_type]
        if not actual_results:
            continue
        
        # 预测该结果且正确的
        initial_predicted_correct = sum(1 for r in actual_results if r['initial_pred'] == result_type)
        current_predicted_correct = sum(1 for r in actual_results if r['current_pred'] == result_type)
        
        # 预测该结果的总数(不论是否正确)
        initial_predicted_total = sum(1 for r in results if r['initial_pred'] == result_type)
        current_predicted_total = sum(1 for r in results if r['current_pred'] == result_type)
        
        total_actual = len(actual_results)
        recall_initial = (initial_predicted_correct / total_actual) * 100 if total_actual > 0 else 0
        recall_current = (current_predicted_correct / total_actual) * 100 if total_actual > 0 else 0
        
        precision_initial = (initial_predicted_correct / initial_predicted_total) * 100 if initial_predicted_total > 0 else 0
        precision_current = (current_predicted_correct / current_predicted_total) * 100 if current_predicted_total > 0 else 0
        
        print(f"{result_names[result_type]:<6} 实际{total_actual:>4}场")
        print(f"       召回率: 初盘{recall_initial:>5.1f}% 即时{recall_current:>5.1f}%")
        print(f"       精确率: 初盘{precision_initial:>5.1f}% 即时{precision_current:>5.1f}%")
        print(f"       预测量: 初盘{initial_predicted_total:>4}次 即时{current_predicted_total:>4}次")
        print()
    
    # 5. 整体准确率对比
    total_initial_correct = sum(1 for r in results if r['initial_correct'])
    total_current_correct = sum(1 for r in results if r['current_correct'])
    
    overall_initial_accuracy = (total_initial_correct / total_predictions) * 100
    overall_current_accuracy = (total_current_correct / total_predictions) * 100
    
    print(f"整体准确率:")
    print(f"   初盘整体准确率: {overall_initial_accuracy:.1f}% ({total_initial_correct}/{total_predictions})")
    print(f"   即时整体准确率: {overall_current_accuracy:.1f}% ({total_current_correct}/{total_predictions})")
    
    accuracy_diff = overall_current_accuracy - overall_initial_accuracy
    trend = "上升" if accuracy_diff > 0 else "下降" if accuracy_diff < 0 else "持平"
    print(f"   准确率变化: {trend} {accuracy_diff:+.1f}%")
    
    # 6. 未识别推荐结果统计
    unknown_initial = sum(1 for r in results if r['initial_pred'] == 'unknown')
    unknown_current = sum(1 for r in results if r['current_pred'] == 'unknown')
    
    if unknown_initial > 0 or unknown_current > 0:
        print(f"\n未识别推荐结果:")
        print(f"   初盘未识别: {unknown_initial} 次 ({unknown_initial/total_predictions*100:.1f}%)")
        print(f"   即时未识别: {unknown_current} 次 ({unknown_current/total_predictions*100:.1f}%)")
        
        # 显示一些未识别的例子
        unknown_examples = []
        for r in results:
            if r['initial_pred'] == 'unknown' and r['initial_recommendation'] not in unknown_examples:
                unknown_examples.append(r['initial_recommendation'])
            if len(unknown_examples) >= 5:
                break
        
        if unknown_examples:
            print(f"   未识别的推荐样例:")
            for example in unknown_examples:
                print(f"     '{example}'")
    
    print("="*80)


if __name__ == "__main__":
    reanalyze_accuracy()