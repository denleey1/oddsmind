#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
英超验证结果准确率分析器
分析即时盘推荐准确率排名和初盘即时盘一致性
"""

import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import pandas as pd

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class AccuracyAnalyzer:
    """准确率分析器"""
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        
        # 加载映射规则
        mapping_file = Path(__file__).parent / "recommendation_mapping.json"
        with open(mapping_file, 'r', encoding='utf-8') as f:
            self.mapping_config = json.load(f)
        
        self.mapping_rules = self.mapping_config['mapping_rules']['rules']
        
    def get_match_results(self) -> Dict[int, str]:
        """获取比赛实际结果"""
        query = """
            SELECT match_id, actual_home_score, actual_away_score
            FROM premier_league_validation_results
            GROUP BY match_id, actual_home_score, actual_away_score
        """
        
        results = self.db.execute_query(query, fetch='all')
        match_results = {}
        
        for result in results:
            match_id = result['match_id']
            home_score = result['actual_home_score'] 
            away_score = result['actual_away_score']
            
            if home_score > away_score:
                match_results[match_id] = '主胜'
            elif home_score == away_score:
                match_results[match_id] = '平'
            else:
                match_results[match_id] = '负'
        
        return match_results
    
    def check_prediction_accuracy(self, recommendation: str, actual_result: str, 
                                  home_rule_value: float = None, away_rule_value: float = None) -> bool:
        """检查推荐是否准确"""
        if recommendation not in self.mapping_rules:
            return False
        
        rule = self.mapping_rules[recommendation]
        expected_results = rule['result']
        
        # 处理动态判断的双平偏让平
        if expected_results == "dynamic":
            if home_rule_value is None or away_rule_value is None:
                return False
            
            # 规则值小的一方获胜
            if home_rule_value < away_rule_value:
                expected_results = "主胜"
            elif away_rule_value < home_rule_value:
                expected_results = "负"
            else:
                expected_results = "平"  # 规则值相等时默认平局
        
        # 处理数组形式的结果
        if isinstance(expected_results, list):
            return actual_result in expected_results
        else:
            return actual_result == expected_results
    
    def analyze_company_accuracy(self) -> List[Dict]:
        """分析各公司的准确率"""
        self.logger.info("开始分析公司准确率...")
        
        # 获取比赛实际结果
        match_results = self.get_match_results()
        
        # 获取所有验证数据
        query = """
            SELECT 
                company_id,
                match_id,
                initial_recommendation,
                current_recommendation,
                initial_rule_diff,
                current_rule_diff
            FROM premier_league_validation_results
        """
        
        validation_data = self.db.execute_query(query, fetch='all')
        
        # 按公司统计准确率
        company_stats = defaultdict(lambda: {
            'initial_total': 0,
            'initial_correct': 0, 
            'current_total': 0,
            'current_correct': 0,
            'consistency_total': 0,
            'consistency_match': 0
        })
        
        for row in validation_data:
            company_id = row['company_id']
            match_id = row['match_id']
            
            if match_id not in match_results:
                continue
            
            actual_result = match_results[match_id]
            
            # 计算主客队规则值（用于双平偏让平的动态判断）
            initial_rule_diff = float(row['initial_rule_diff'])
            current_rule_diff = float(row['current_rule_diff'])
            
            # 假设主队规则值 = (规则差 + 客队规则值)，这里简化处理
            # 实际应该从数据库获取具体的主客队规则值
            initial_home_rule = initial_rule_diff / 2
            initial_away_rule = -initial_rule_diff / 2
            current_home_rule = current_rule_diff / 2  
            current_away_rule = -current_rule_diff / 2
            
            stats = company_stats[company_id]
            
            # 初盘准确率
            initial_rec = row['initial_recommendation']
            if self.check_prediction_accuracy(initial_rec, actual_result, 
                                            initial_home_rule, initial_away_rule):
                stats['initial_correct'] += 1
            stats['initial_total'] += 1
            
            # 即时盘准确率
            current_rec = row['current_recommendation']
            if self.check_prediction_accuracy(current_rec, actual_result,
                                            current_home_rule, current_away_rule):
                stats['current_correct'] += 1
            stats['current_total'] += 1
            
            # 一致性统计
            if initial_rec == current_rec:
                stats['consistency_match'] += 1
            stats['consistency_total'] += 1
        
        # 计算最终统计结果
        company_results = []
        for company_id, stats in company_stats.items():
            if stats['current_total'] == 0:
                continue
                
            initial_accuracy = stats['initial_correct'] / stats['initial_total'] if stats['initial_total'] > 0 else 0
            current_accuracy = stats['current_correct'] / stats['current_total'] if stats['current_total'] > 0 else 0
            consistency = stats['consistency_match'] / stats['consistency_total'] if stats['consistency_total'] > 0 else 0
            
            company_results.append({
                'company_id': company_id,
                'initial_accuracy': initial_accuracy,
                'current_accuracy': current_accuracy,  
                'consistency': consistency,
                'total_predictions': stats['current_total'],
                'initial_correct': stats['initial_correct'],
                'current_correct': stats['current_correct'],
                'consistency_matches': stats['consistency_match']
            })
        
        self.logger.info(f"分析完成，共{len(company_results)}家公司")
        return company_results
    
    def generate_reports(self) -> Tuple[List[Dict], List[Dict]]:
        """生成报告"""
        company_results = self.analyze_company_accuracy()
        
        # 1. 即时盘准确率前15名
        top_current_accuracy = sorted(
            company_results, 
            key=lambda x: x['current_accuracy'], 
            reverse=True
        )[:15]
        
        # 2. 在准确率前15名中，找出初盘即时盘一致性前10名
        top_15_companies = {result['company_id'] for result in top_current_accuracy}
        
        consistency_candidates = [
            result for result in company_results 
            if result['company_id'] in top_15_companies
        ]
        
        top_consistency = sorted(
            consistency_candidates,
            key=lambda x: x['consistency'],
            reverse=True
        )[:10]
        
        return top_current_accuracy, top_consistency
    
    def print_reports(self):
        """打印报告"""
        top_accuracy, top_consistency = self.generate_reports()
        
        print("="*80)
        print("英超验证结果分析报告")
        print("="*80)
        
        print(f"\n[即时盘推荐准确率排名] (前15名)")
        print("-" * 80)
        print(f"{'排名':<4} {'公司ID':<8} {'即时准确率':<12} {'初盘准确率':<12} {'预测总数':<8} {'一致性':<8}")
        print("-" * 80)
        
        for i, result in enumerate(top_accuracy, 1):
            print(f"{i:<4} {result['company_id']:<8} "
                  f"{result['current_accuracy']:<12.3f} {result['initial_accuracy']:<12.3f} "
                  f"{result['total_predictions']:<8} {result['consistency']:<8.3f}")
        
        print(f"\n[初盘即时盘一致性排名] (准确率前15名中的前10名)")
        print("-" * 80)
        print(f"{'排名':<4} {'公司ID':<8} {'一致性':<10} {'即时准确率':<12} {'初盘准确率':<12} {'预测总数':<8}")
        print("-" * 80)
        
        for i, result in enumerate(top_consistency, 1):
            print(f"{i:<4} {result['company_id']:<8} "
                  f"{result['consistency']:<10.3f} {result['current_accuracy']:<12.3f} "
                  f"{result['initial_accuracy']:<12.3f} {result['total_predictions']:<8}")
        
        print(f"\n总结:")
        print(f"- 即时盘准确率最高: 公司{top_accuracy[0]['company_id']} ({top_accuracy[0]['current_accuracy']:.3f})")
        print(f"- 一致性最高: 公司{top_consistency[0]['company_id']} ({top_consistency[0]['consistency']:.3f})")


def main():
    """主函数"""
    analyzer = AccuracyAnalyzer()
    analyzer.print_reports()


if __name__ == "__main__":
    main()