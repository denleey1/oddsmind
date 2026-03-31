#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修正版验证器 - 正确的赔率过滤逻辑
只修改了关键的过滤逻辑，其他保持不变
"""

import sys
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime
import json
import time

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class ValidatorWithCorrectFilter:
    """修正过滤逻辑的验证器"""
    
    def __init__(self, min_odds: float = 1.4):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.min_odds = min_odds
        
        print(f"初始化完成，赔率过滤条件：整场比赛的所有公司初始赔率都 >= {min_odds}")
    
    def get_matches_to_filter(self, league_id: int, start_round: int, end_round: int) -> Set[int]:
        """
        获取需要过滤的比赛ID集合
        如果任何一家公司的主胜或客胜赔率 < min_odds，则过滤整场比赛
        """
        query = """
        SELECT DISTINCT m.match_id
        FROM matches m
        JOIN european_odds eo ON m.match_id = eo.match_id
        WHERE m.league_id = %s 
          AND m.round_number >= %s 
          AND m.round_number <= %s
          AND m.match_status = 'finished'
          AND eo.odds_type = '1x2'
          AND (eo.initial_home < %s OR eo.initial_away < %s)
        """
        
        results = self.db.execute_query(
            query, 
            [league_id, start_round, end_round, self.min_odds, self.min_odds], 
            fetch='all'
        )
        
        filtered_match_ids = {row['match_id'] for row in results} if results else set()
        
        print(f"发现 {len(filtered_match_ids)} 场比赛需要过滤（有公司赔率<{self.min_odds}）")
        
        return filtered_match_ids
    
    def validate_league_with_filter(self, league_id: int, league_name: str, start_round: int = 10, end_round: int = 38):
        """验证联赛并正确过滤"""
        
        print(f"\n开始验证 {league_name}")
        print("="*80)
        
        # 1. 获取所有完成的比赛
        match_query = """
        SELECT 
            match_id, round_number, home_team_id, away_team_id,
            home_team_name, away_team_name, home_score, away_score
        FROM matches
        WHERE league_id = %s 
          AND round_number >= %s 
          AND round_number <= %s
          AND match_status = 'finished'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        ORDER BY round_number
        """
        
        all_matches = self.db.execute_query(
            match_query, 
            [league_id, start_round, end_round], 
            fetch='all'
        )
        
        if not all_matches:
            print(f"没有找到符合条件的比赛")
            return
        
        total_matches = len(all_matches)
        print(f"总比赛数: {total_matches}")
        
        # 2. 获取需要过滤的比赛ID
        filtered_match_ids = self.get_matches_to_filter(league_id, start_round, end_round)
        
        # 3. 计算实际处理的比赛
        valid_match_ids = {m['match_id'] for m in all_matches} - filtered_match_ids
        processed_matches = len(valid_match_ids)
        filtered_count = len(filtered_match_ids)
        
        print(f"过滤比赛数: {filtered_count}")
        print(f"实际处理比赛数: {processed_matches}")
        print(f"过滤比例: {filtered_count/total_matches*100:.1f}%")
        
        if processed_matches == 0:
            print("所有比赛都被过滤，无法计算准确率")
            return
        
        # 4. 获取这些比赛的预测结果（从已有的验证表）
        # 这里假设已经有验证结果表，只需要过滤掉不符合条件的比赛
        
        # 创建临时的比赛ID列表用于查询
        if valid_match_ids:
            match_ids_str = ','.join(str(id) for id in valid_match_ids)
            
            # 从原始验证表获取数据，但只保留符合条件的比赛
            result_query = f"""
            SELECT 
                company_id,
                match_id,
                actual_home_score,
                actual_away_score,
                current_recommendation,
                current_rule_diff,
                initial_recommendation,
                initial_rule_diff
            FROM kleague_validation_results
            WHERE match_id IN ({match_ids_str})
            """
            
            valid_results = self.db.execute_query(result_query, fetch='all')
            
            if not valid_results:
                print("没有找到验证结果数据")
                return
            
            # 5. 计算准确率
            self._calculate_accuracy(valid_results, league_name)
    
    def _calculate_accuracy(self, results: List[Dict], league_name: str):
        """计算并显示准确率"""
        
        # 加载推荐映射
        try:
            mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                recommendation_mapping = mapping_data['recommendations']
        except:
            print("无法加载推荐映射文件")
            return
        
        # 统计每个公司的准确率
        company_stats = {}
        
        for row in results:
            company_id = row['company_id']
            
            if company_id not in company_stats:
                company_stats[company_id] = {
                    'total': 0,
                    'correct': 0
                }
            
            stats = company_stats[company_id]
            stats['total'] += 1
            
            # 判断实际结果
            if row['actual_home_score'] > row['actual_away_score']:
                actual_result = 'home_win'
            elif row['actual_home_score'] < row['actual_away_score']:
                actual_result = 'away_win'
            else:
                actual_result = 'draw'
            
            # 判断预测是否正确
            recommendation = row['current_recommendation']
            rule_diff = float(row.get('current_rule_diff', 0))
            
            if recommendation in recommendation_mapping:
                rule = recommendation_mapping[recommendation]
                predicted_result = rule.get('result', 'unknown')
                
                # 特殊处理双平偏让平
                if recommendation == "双平偏让平":
                    if rule_diff < 0:
                        predicted_result = "home_win"
                    elif rule_diff > 0:
                        predicted_result = "away_win"
                    else:
                        predicted_result = "draw"
                
                # 判断是否正确
                if isinstance(predicted_result, list):
                    if actual_result in predicted_result:
                        stats['correct'] += 1
                else:
                    if predicted_result == actual_result:
                        stats['correct'] += 1
        
        # 计算并显示准确率
        print(f"\n{league_name} 准确率统计（正确过滤后）:")
        print("-"*60)
        print(f"{'公司ID':<10} {'总预测':<10} {'正确数':<10} {'准确率':<10}")
        print("-"*60)
        
        # 按准确率排序
        sorted_companies = sorted(
            company_stats.items(), 
            key=lambda x: x[1]['correct']/x[1]['total'] if x[1]['total'] > 0 else 0,
            reverse=True
        )
        
        # 显示前10名
        for company_id, stats in sorted_companies[:10]:
            if stats['total'] > 50:  # 至少50个预测
                accuracy = stats['correct'] / stats['total'] * 100
                print(f"{company_id:<10} {stats['total']:<10} {stats['correct']:<10} {accuracy:.1f}%")
        
        # 显示总体统计
        total_predictions = sum(s['total'] for s in company_stats.values())
        total_correct = sum(s['correct'] for s in company_stats.values())
        overall_accuracy = total_correct / total_predictions * 100 if total_predictions > 0 else 0
        
        print("-"*60)
        print(f"总体准确率: {overall_accuracy:.1f}% ({total_correct}/{total_predictions})")
    
    def quick_test(self):
        """快速测试过滤逻辑是否正确"""
        
        # 测试韩K联赛
        league_id = 15
        league_name = "韩K联赛"
        
        print(f"测试 {league_name} 的过滤逻辑")
        print("="*80)
        
        # 检查原始数据
        query1 = """
        SELECT 
            COUNT(DISTINCT m.match_id) as total_matches
        FROM matches m
        WHERE m.league_id = %s 
          AND m.round_number >= 10 
          AND m.round_number <= 38
          AND m.match_status = 'finished'
        """
        
        result1 = self.db.execute_query(query1, [league_id], fetch='one')
        print(f"原始比赛总数: {result1['total_matches']}")
        
        # 使用正确的过滤逻辑
        filtered_matches = self.get_matches_to_filter(league_id, 10, 38)
        print(f"需要过滤的比赛数: {len(filtered_matches)}")
        print(f"剩余比赛数: {result1['total_matches'] - len(filtered_matches)}")
        print(f"过滤比例: {len(filtered_matches)/result1['total_matches']*100:.1f}%")
        
        # 验证过滤的比赛确实有赔率<1.4
        if filtered_matches:
            sample_match = list(filtered_matches)[0]
            query2 = """
            SELECT 
                company_id,
                initial_home,
                initial_away
            FROM european_odds
            WHERE match_id = %s AND odds_type = '1x2'
            ORDER BY initial_home
            LIMIT 5
            """
            
            sample_odds = self.db.execute_query(query2, [sample_match], fetch='all')
            print(f"\n被过滤比赛{sample_match}的部分赔率:")
            for odds in sample_odds:
                print(f"  公司{odds['company_id']}: 主胜{odds['initial_home']:.2f}, 客胜{odds['initial_away']:.2f}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="修正过滤逻辑的验证器")
    parser.add_argument('--min-odds', type=float, default=1.4,
                       help='最小赔率阈值（默认1.4）')
    parser.add_argument('--test', action='store_true',
                       help='运行快速测试')
    parser.add_argument('--league-id', type=int, default=15,
                       help='联赛ID（默认15-韩K）')
    
    args = parser.parse_args()
    
    validator = ValidatorWithCorrectFilter(min_odds=args.min_odds)
    
    if args.test:
        validator.quick_test()
    else:
        # 验证指定联赛
        league_map = {
            15: "韩K联赛",
            25: "日职联",
            36: "英超",
            31: "西甲",
            8: "德甲",
            11: "意甲",
            23: "法甲"
        }
        
        league_name = league_map.get(args.league_id, f"联赛{args.league_id}")
        validator.validate_league_with_filter(args.league_id, league_name)


if __name__ == "__main__":
    main()