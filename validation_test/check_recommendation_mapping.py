#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查推荐结果的映射规则
分析推荐结果的含义
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection


def analyze_recommendations():
    """分析推荐结果"""
    
    recommendations = [
        '看好1胜', '看好1平', '看好1负',  # 这里1代表什么？
        '看好2平', '看好2胜',           # 这里2代表什么？
        '双平', '双平偏平', '双平偏客平',
        '平'
    ]
    
    print("推荐结果分析:")
    print("="*50)
    
    # 根据足球投注的常识：
    # 1 = 主队, 2 = 客队, X = 平局
    # 1x2是标准的欧洲赔率格式
    
    print("基于1X2标准:")
    print("1 = 主队(Home)")
    print("X = 平局(Draw)") 
    print("2 = 客队(Away)")
    print()
    
    mapping_rules = {
        # 明确的主队胜
        '看好1胜': 'home_win',      # 1胜 = 主队胜
        '看好1让': 'home_win',      # 1让 = 主队让球胜(主队胜)
        
        # 明确的客队胜  
        '看好1负': 'away_win',      # 1负 = 主队负(客队胜)
        '看好2胜': 'away_win',      # 2胜 = 客队胜
        '看好2让': 'away_win',      # 2让 = 客队让球胜(客队胜)
        
        # 明确的平局
        '看好1平': 'draw',          # 1平 = 平局
        '看好2平': 'draw',          # 2平 = 平局  
        '双平': 'draw',             # 双平 = 平局
        '双平偏平': 'draw',         # 双平偏平 = 倾向平局
        '双平偏客平': 'draw',       # 双平偏客平 = 倾向平局
        '平': 'draw'                # 平 = 平局
    }
    
    print("推荐结果 → 比赛结果 映射:")
    print("-" * 40)
    for rec, result in mapping_rules.items():
        print(f"{rec:<15} → {result}")
    
    return mapping_rules


def test_current_mapping():
    """测试当前映射的问题"""
    
    def current_map_recommendation_to_result(recommendation: str) -> str:
        """当前的映射函数"""
        if not recommendation:
            return 'unknown'
            
        rec = recommendation.lower()
        
        # 主胜相关 (包括看好1胜、看好1让、看好2胜等)
        if any(keyword in rec for keyword in ['1胜', '2胜', '1让', '2让', '主胜', '主让', '主队', 'home']):
            return 'home_win'
        
        # 客胜相关 (包括看好1负、看好2负等)
        if any(keyword in rec for keyword in ['1负', '2负', '客胜', '客让', '客队', 'away']):
            return 'away_win'
            
        # 平局相关 (包括看好1平、看好2平、双平等)
        if any(keyword in rec for keyword in ['1平', '2平', '平局', '平', 'draw', '双平']):
            return 'draw'
            
        return 'unknown'
    
    print("\n当前映射函数测试结果:")
    print("="*50)
    
    test_cases = [
        '看好1胜', '看好1平', '看好1负',
        '看好2胜', '看好2平', 
        '双平', '双平偏平', '双平偏客平', '平'
    ]
    
    print("推荐结果        当前映射      问题分析")
    print("-" * 50)
    
    for rec in test_cases:
        current_result = current_map_recommendation_to_result(rec)
        
        # 分析问题
        problem = ""
        if rec == '看好1负' and current_result == 'away_win':
            problem = "正确"
        elif rec == '看好2胜' and current_result == 'home_win':
            problem = "错误! 2胜应该是客队胜"
        elif rec in ['看好1平', '看好2平'] and current_result == 'draw':
            problem = "正确"
        elif rec == '看好1胜' and current_result == 'home_win':
            problem = "正确"
        else:
            problem = "正确"
            
        print(f"{rec:<15} {current_result:<12} {problem}")


def get_correct_mapping_function():
    """返回正确的映射函数"""
    
    def correct_map_recommendation_to_result(recommendation: str) -> str:
        """正确的推荐结果映射函数"""
        if not recommendation:
            return 'unknown'
            
        rec = recommendation.lower()
        
        # 主胜相关: 1胜(主队胜)、1让(主队让球胜)
        if any(keyword in rec for keyword in ['1胜', '1让', '主胜', '主让', '主队', 'home']):
            return 'home_win'
        
        # 客胜相关: 1负(主队负=客队胜)、2胜(客队胜)、2让(客队让球胜)
        if any(keyword in rec for keyword in ['1负', '2胜', '2让', '客胜', '客让', '客队', 'away']):
            return 'away_win'
            
        # 平局相关: 1平、2平、双平等
        if any(keyword in rec for keyword in ['1平', '2平', '平局', '平', 'draw', '双平']):
            return 'draw'
            
        return 'unknown'
    
    return correct_map_recommendation_to_result


if __name__ == "__main__":
    # 分析推荐结果含义
    mapping_rules = analyze_recommendations()
    
    # 测试当前映射的问题
    test_current_mapping()
    
    # 测试正确的映射函数
    print("\n修复后的映射函数测试:")
    print("="*50)
    
    correct_map = get_correct_mapping_function()
    
    test_cases = [
        '看好1胜', '看好1平', '看好1负',
        '看好2胜', '看好2平', 
        '双平', '双平偏平', '双平偏客平', '平'
    ]
    
    print("推荐结果        修复后映射")
    print("-" * 30)
    
    for rec in test_cases:
        result = correct_map(rec)
        print(f"{rec:<15} → {result}")