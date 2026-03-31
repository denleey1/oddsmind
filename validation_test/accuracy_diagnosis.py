#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
准确率计算诊断工具
找出不同计算方法导致准确率差异的原因
"""

import sys
from pathlib import Path
import json

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class AccuracyDiagnosis:
    """准确率计算诊断"""
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        
        # 加载推荐映射
        self._load_recommendation_mapping()
    
    def _load_recommendation_mapping(self):
        """加载推荐映射"""
        try:
            mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                self.recommendation_mapping = mapping_data['recommendations']
        except Exception as e:
            self.logger.error(f"无法加载推荐映射: {e}")
            self.recommendation_mapping = {}
    
    def diagnose_calculation_methods(self):
        """诊断不同的计算方法"""
        
        print("\n准确率计算方法诊断")
        print("="*80)
        
        # 获取样本数据 - 韩K联赛，公司16
        query = """
        SELECT 
            match_id,
            company_id,
            actual_home_score,
            actual_away_score,
            current_recommendation,
            current_rule_diff,
            initial_recommendation,
            initial_rule_diff
        FROM kleague_validation_results
        WHERE company_id = 16
        LIMIT 10
        """
        
        samples = self.db.execute_query(query, fetch='all')
        
        if not samples:
            print("没有找到样本数据")
            return
        
        print(f"\n分析前10条记录的计算差异：")
        print("-"*80)
        
        # 三种不同的计算方法
        method1_correct = 0  # 简单的推荐映射
        method2_correct = 0  # SQL中的硬编码规则
        method3_correct = 0  # 考虑rule_diff的复杂规则
        
        for idx, sample in enumerate(samples, 1):
            print(f"\n记录{idx}: 比赛{sample['match_id']}")
            print(f"  实际比分: {sample['actual_home_score']}-{sample['actual_away_score']}")
            print(f"  推荐: {sample['current_recommendation']}")
            print(f"  规则差值: {sample['current_rule_diff']}")
            
            # 实际结果
            if sample['actual_home_score'] > sample['actual_away_score']:
                actual_result = 'home_win'
                actual_desc = "主胜"
            elif sample['actual_home_score'] < sample['actual_away_score']:
                actual_result = 'away_win'
                actual_desc = "客胜"
            else:
                actual_result = 'draw'
                actual_desc = "平局"
            
            print(f"  实际结果: {actual_desc}")
            
            # 方法1: 简单映射
            rec = sample['current_recommendation']
            correct1 = False
            if rec in self.recommendation_mapping:
                rule = self.recommendation_mapping[rec]
                predicted = rule.get('result', 'unknown')
                if isinstance(predicted, list):
                    correct1 = actual_result in predicted
                else:
                    correct1 = (predicted == actual_result)
            
            # 方法2: SQL硬编码（简化判断）
            correct2 = False
            if actual_result == 'home_win' and rec in ['主让1胜', '主让1平', '主让2胜', '主让2平']:
                correct2 = True
            elif actual_result == 'away_win' and rec in ['客让1胜', '客让1平', '客让2胜', '客让2平']:
                correct2 = True
            elif actual_result == 'draw' and rec in ['平', '双平偏平']:
                correct2 = True
            
            # 方法3: 考虑rule_diff
            correct3 = False
            if rec in self.recommendation_mapping:
                rule = self.recommendation_mapping[rec]
                predicted = rule.get('result', 'unknown')
                
                # 特殊处理双平偏让平
                if rec == "双平偏让平":
                    rule_diff = float(sample.get('current_rule_diff', 0))
                    if rule_diff < 0:
                        predicted = "home_win"
                    elif rule_diff > 0:
                        predicted = "away_win"
                    else:
                        predicted = "draw"
                
                if isinstance(predicted, list):
                    correct3 = actual_result in predicted
                else:
                    correct3 = (predicted == actual_result)
            
            print(f"  方法1(简单映射): {'✓' if correct1 else '✗'}")
            print(f"  方法2(SQL硬编码): {'✓' if correct2 else '✗'}")
            print(f"  方法3(考虑rule_diff): {'✓' if correct3 else '✗'}")
            
            if correct1: method1_correct += 1
            if correct2: method2_correct += 1
            if correct3: method3_correct += 1
        
        # 汇总
        print("\n" + "="*80)
        print("不同方法的准确率对比:")
        print(f"方法1(简单映射): {method1_correct}/10 = {method1_correct*10}%")
        print(f"方法2(SQL硬编码): {method2_correct}/10 = {method2_correct*10}%")
        print(f"方法3(考虑rule_diff): {method3_correct}/10 = {method3_correct*10}%")
    
    def compare_full_dataset(self):
        """对比完整数据集的不同计算方法"""
        
        print("\n\n完整数据集准确率对比")
        print("="*80)
        
        # 方法1: 原始SQL查询（可能是最初的58%）
        query1 = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN 
                (actual_home_score > actual_away_score AND current_recommendation LIKE '主%') OR
                (actual_home_score < actual_away_score AND current_recommendation LIKE '客%') OR
                (actual_home_score = actual_away_score AND current_recommendation IN ('平', '双平', '双平偏平'))
            THEN 1 ELSE 0 END) as correct
        FROM kleague_validation_results
        WHERE company_id = 16
        """
        
        result1 = self.db.execute_query(query1, fetch='one')
        if result1:
            acc1 = result1['correct'] / result1['total'] * 100
            print(f"\n方法1 (宽松匹配 - 主/客/平):")
            print(f"  总数: {result1['total']}, 正确: {result1['correct']}, 准确率: {acc1:.1f}%")
        
        # 方法2: 严格的推荐类型匹配
        query2 = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN 
                (actual_home_score > actual_away_score AND current_recommendation IN ('主让1胜', '主让1平', '主让2胜', '主让2平')) OR
                (actual_home_score < actual_away_score AND current_recommendation IN ('客让1胜', '客让1平', '客让2胜', '客让2平')) OR
                (actual_home_score = actual_away_score AND current_recommendation IN ('平', '双平偏平'))
            THEN 1 ELSE 0 END) as correct
        FROM kleague_validation_results
        WHERE company_id = 16
        """
        
        result2 = self.db.execute_query(query2, fetch='one')
        if result2:
            acc2 = result2['correct'] / result2['total'] * 100
            print(f"\n方法2 (严格匹配 - 特定推荐):")
            print(f"  总数: {result2['total']}, 正确: {result2['correct']}, 准确率: {acc2:.1f}%")
        
        # 方法3: 查看推荐分布
        query3 = """
        SELECT 
            current_recommendation,
            COUNT(*) as count,
            SUM(CASE 
                WHEN actual_home_score > actual_away_score THEN 1 
                ELSE 0 
            END) as home_wins,
            SUM(CASE 
                WHEN actual_home_score < actual_away_score THEN 1 
                ELSE 0 
            END) as away_wins,
            SUM(CASE 
                WHEN actual_home_score = actual_away_score THEN 1 
                ELSE 0 
            END) as draws
        FROM kleague_validation_results
        WHERE company_id = 16
        GROUP BY current_recommendation
        ORDER BY count DESC
        LIMIT 10
        """
        
        result3 = self.db.execute_query(query3, fetch='all')
        
        print(f"\n推荐类型分布（公司16）:")
        print(f"{'推荐类型':<20} {'总数':<8} {'主胜':<8} {'客胜':<8} {'平局':<8}")
        print("-"*60)
        
        for row in result3:
            print(f"{row['current_recommendation']:<20} {row['count']:<8} {row['home_wins']:<8} {row['away_wins']:<8} {row['draws']:<8}")
        
        # 分析主受1胜这类推荐
        self._analyze_special_recommendations()
    
    def _analyze_special_recommendations(self):
        """分析特殊推荐类型"""
        
        print("\n\n特殊推荐类型分析")
        print("="*80)
        
        # 分析"主受1胜"类推荐
        query = """
        SELECT 
            current_recommendation,
            COUNT(*) as total,
            SUM(CASE WHEN actual_home_score > actual_away_score THEN 1 ELSE 0 END) as home_wins,
            SUM(CASE WHEN actual_home_score = actual_away_score THEN 1 ELSE 0 END) as draws,
            SUM(CASE WHEN actual_home_score < actual_away_score THEN 1 ELSE 0 END) as away_wins
        FROM kleague_validation_results
        WHERE company_id = 16
          AND current_recommendation IN ('主受1胜', '客受1胜', '主让1负', '客让1负')
        GROUP BY current_recommendation
        """
        
        results = self.db.execute_query(query, fetch='all')
        
        if results:
            print("\n受让类推荐的实际结果分布:")
            for row in results:
                print(f"\n{row['current_recommendation']}:")
                print(f"  总数: {row['total']}")
                print(f"  主胜: {row['home_wins']} ({row['home_wins']/row['total']*100:.1f}%)")
                print(f"  平局: {row['draws']} ({row['draws']/row['total']*100:.1f}%)")
                print(f"  客胜: {row['away_wins']} ({row['away_wins']/row['total']*100:.1f}%)")
                
                # 根据recommendation_mapping判断应该的结果
                if row['current_recommendation'] in self.recommendation_mapping:
                    expected = self.recommendation_mapping[row['current_recommendation']]
                    print(f"  映射文件预期: {expected.get('result')}")
                    print(f"  说明: {expected.get('description')}")


def main():
    """主函数"""
    diagnosis = AccuracyDiagnosis()
    
    # 1. 诊断计算方法差异
    diagnosis.diagnose_calculation_methods()
    
    # 2. 对比完整数据集
    diagnosis.compare_full_dataset()


if __name__ == "__main__":
    main()