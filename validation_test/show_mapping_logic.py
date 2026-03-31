#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
详细展示推荐映射逻辑
"""

import sys
from pathlib import Path
import json

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

def show_mapping_logic():
    """展示完整的映射逻辑"""
    print("="*80)
    print("推荐术语映射逻辑详解")
    print("="*80)
    
    # 读取当前映射文件
    mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
    
    if not mapping_file.exists():
        print("❌ 映射文件不存在!")
        return
    
    try:
        with open(mapping_file, 'r', encoding='utf-8') as f:
            mapping_data = json.load(f)
        
        recommendations = mapping_data['recommendations']
        
        print(f"当前映射规则总数: {len(recommendations)}\n")
        
        # 按类型分组展示
        categories = {
            '主让球系列': [],
            '客让球系列': [],
            '主受球系列': [],
            '客受球系列': [],
            '平局系列': [],
            '双平系列': [],
            '其他': []
        }
        
        for rec, rule in recommendations.items():
            if '主让' in rec:
                categories['主让球系列'].append((rec, rule))
            elif '客让' in rec:
                categories['客让球系列'].append((rec, rule))
            elif '主受' in rec:
                categories['主受球系列'].append((rec, rule))
            elif '客受' in rec:
                categories['客受球系列'].append((rec, rule))
            elif rec == '平':
                categories['平局系列'].append((rec, rule))
            elif '双平' in rec:
                categories['双平系列'].append((rec, rule))
            else:
                categories['其他'].append((rec, rule))
        
        for category, items in categories.items():
            if items:
                print(f"{category}:")
                print("-" * 60)
                for rec, rule in sorted(items):
                    result = rule.get('result', 'unknown')
                    desc = rule.get('description', '')
                    
                    if isinstance(result, list):
                        result_str = f"{result} (任一成立)"
                    else:
                        result_str = result
                    
                    print(f"  {rec:<15} → {result_str:<25} ({desc})")
                print()
        
        # 特别说明动态判断逻辑
        print("特殊动态判断逻辑:")
        print("-" * 60)
        print("双平偏让平:")
        print("  - 如果 rule_diff < 0  → home_win  (主队规则值小，主队胜)")
        print("  - 如果 rule_diff > 0  → away_win  (客队规则值小，客队胜)")
        print("  - 如果 rule_diff = 0  → draw      (规则值相等，平局)")
        print("  注: rule_diff = 主队规则值 - 客队规则值")
        print()
        
        # 测试用例展示
        print("测试用例验证:")
        print("-" * 60)
        test_cases = [
            # (推荐, 实际比分, 实际结果, rule_diff, 期望判断)
            ("主让1胜", "2:0", "home_win", 0, "正确"),
            ("主让1平", "1:0", "home_win", 0, "正确"),
            ("主让1负", "0:0", "draw", 0, "正确"),
            ("主让1负", "0:1", "away_win", 0, "正确"),
            ("客让1胜", "0:2", "away_win", 0, "正确"),
            ("客让1平", "0:1", "away_win", 0, "正确"),
            ("主受1胜", "1:1", "draw", 0, "正确"),
            ("主受1胜", "2:0", "home_win", 0, "正确"),
            ("平", "1:1", "draw", 0, "正确"),
            ("双平偏让平", "2:0", "home_win", -0.5, "正确"),  # rule_diff < 0
            ("双平偏让平", "0:2", "away_win", 0.5, "正确"),   # rule_diff > 0
            ("双平偏让平", "1:1", "draw", 0.0, "正确"),       # rule_diff = 0
        ]
        
        print(f"{'推荐':<12} {'比分':<8} {'实际结果':<12} {'rule_diff':<12} {'预期映射':<12} {'判断'}")
        print("-" * 80)
        
        for rec, score, actual, rule_diff, expected_result in test_cases:
            # 获取映射结果
            if rec in recommendations:
                rule = recommendations[rec]
                predicted = rule.get('result', 'unknown')
                
                # 特殊处理双平偏让平
                if rec == "双平偏让平":
                    if rule_diff < 0:
                        predicted = "home_win"
                    elif rule_diff > 0:
                        predicted = "away_win"
                    else:
                        predicted = "draw"
                
                # 判断是否正确
                if isinstance(predicted, list):
                    is_correct = actual in predicted
                    predicted_str = str(predicted)
                else:
                    is_correct = predicted == actual
                    predicted_str = predicted
                
                result_str = "✅" if is_correct else "❌"
                
            else:
                predicted_str = "未找到"
                result_str = "❌"
            
            print(f"{rec:<12} {score:<8} {actual:<12} {rule_diff:<12} {predicted_str:<12} {result_str}")
        
        print("\n" + "="*80)
        print("映射逻辑检查完成!")
        
    except Exception as e:
        print(f"❌ 读取映射文件失败: {e}")

if __name__ == "__main__":
    show_mapping_logic()