#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
赔率区间分析器 - 调查为什么过滤明显比赛反而降低准确率
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import json

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class OddsRangeAnalyzer:
    """分析不同赔率区间的准确率"""
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        
        # 定义赔率区间
        self.odds_ranges = [
            (0.0, 1.4, "极端明显"),
            (1.4, 1.8, "比较明显"),
            (1.8, 2.2, "适度偏向"),
            (2.2, 3.0, "相对均衡"),
            (3.0, float('inf'), "高赔率")
        ]
        
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
    
    def analyze_by_odds_range(self, league_id: int, start_round: int = 10, end_round: int = 38):
        """按赔率区间分析准确率"""
        
        print(f"\n开始分析联赛{league_id}的赔率区间准确率")
        print("="*80)
        
        # 获取所有比赛及其最低赔率
        query = """
        SELECT 
            m.match_id,
            m.home_score,
            m.away_score,
            MIN(LEAST(eo.initial_home, eo.initial_away)) as min_odds
        FROM matches m
        JOIN european_odds eo ON m.match_id = eo.match_id
        WHERE m.league_id = %s 
          AND m.round_number >= %s 
          AND m.round_number <= %s
          AND m.match_status = 'finished'
          AND eo.odds_type = '1x2'
        GROUP BY m.match_id, m.home_score, m.away_score
        """
        
        matches = self.db.execute_query(
            query, 
            [league_id, start_round, end_round], 
            fetch='all'
        )
        
        if not matches:
            print("没有找到比赛数据")
            return
        
        # 按赔率区间分类比赛
        range_matches = {i: [] for i in range(len(self.odds_ranges))}
        
        for match in matches:
            min_odds = float(match['min_odds'])
            match_id = match['match_id']
            
            for idx, (min_val, max_val, _) in enumerate(self.odds_ranges):
                if min_val <= min_odds < max_val:
                    range_matches[idx].append(match_id)
                    break
        
        # 分析每个区间的准确率
        print(f"\n{'赔率区间':<15} {'比赛数':<10} {'预测数':<10} {'正确数':<10} {'准确率':<10}")
        print("-"*65)
        
        total_stats = {'matches': 0, 'predictions': 0, 'correct': 0}
        
        for idx, (min_val, max_val, range_name) in enumerate(self.odds_ranges):
            match_ids = range_matches[idx]
            
            if not match_ids:
                print(f"{range_name:<15} {0:<10} {0:<10} {0:<10} {'N/A':<10}")
                continue
            
            # 获取这些比赛的预测结果
            match_ids_str = ','.join(str(id) for id in match_ids)
            
            result_query = f"""
            SELECT 
                vr.match_id,
                vr.company_id,
                vr.actual_home_score,
                vr.actual_away_score,
                vr.current_recommendation,
                vr.current_rule_diff
            FROM kleague_validation_results vr
            WHERE vr.match_id IN ({match_ids_str})
            """
            
            predictions = self.db.execute_query(result_query, fetch='all')
            
            if not predictions:
                print(f"{range_name:<15} {len(match_ids):<10} {0:<10} {0:<10} {'N/A':<10}")
                continue
            
            # 计算准确率
            correct_count = 0
            total_predictions = len(predictions)
            
            for pred in predictions:
                # 判断实际结果
                if pred['actual_home_score'] > pred['actual_away_score']:
                    actual_result = 'home_win'
                elif pred['actual_home_score'] < pred['actual_away_score']:
                    actual_result = 'away_win'
                else:
                    actual_result = 'draw'
                
                # 判断预测是否正确
                recommendation = pred['current_recommendation']
                if recommendation in self.recommendation_mapping:
                    rule = self.recommendation_mapping[recommendation]
                    predicted_result = rule.get('result', 'unknown')
                    
                    # 特殊处理双平偏让平
                    if recommendation == "双平偏让平":
                        rule_diff = float(pred.get('current_rule_diff', 0))
                        if rule_diff < 0:
                            predicted_result = "home_win"
                        elif rule_diff > 0:
                            predicted_result = "away_win"
                        else:
                            predicted_result = "draw"
                    
                    # 判断是否正确
                    if isinstance(predicted_result, list):
                        if actual_result in predicted_result:
                            correct_count += 1
                    else:
                        if predicted_result == actual_result:
                            correct_count += 1
            
            accuracy = correct_count / total_predictions * 100 if total_predictions > 0 else 0
            
            print(f"{range_name:<15} {len(match_ids):<10} {total_predictions:<10} {correct_count:<10} {accuracy:.1f}%")
            
            # 累计统计
            total_stats['matches'] += len(match_ids)
            total_stats['predictions'] += total_predictions
            total_stats['correct'] += correct_count
        
        # 显示总体统计
        print("-"*65)
        overall_accuracy = total_stats['correct'] / total_stats['predictions'] * 100 if total_stats['predictions'] > 0 else 0
        print(f"{'总计':<15} {total_stats['matches']:<10} {total_stats['predictions']:<10} {total_stats['correct']:<10} {overall_accuracy:.1f}%")
        
        # 分析结论
        self._analyze_conclusion(range_matches, total_stats)
    
    def _analyze_conclusion(self, range_matches: Dict, total_stats: Dict):
        """分析结论"""
        
        print("\n" + "="*80)
        print("分析结论:")
        print("-"*40)
        
        # 找出准确率最高的区间
        best_range = None
        best_accuracy = 0
        
        for idx, (min_val, max_val, range_name) in enumerate(self.odds_ranges):
            if range_matches[idx]:
                # 重新计算该区间的准确率
                match_ids = range_matches[idx]
                match_ids_str = ','.join(str(id) for id in match_ids)
                
                query = f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN 
                           (actual_home_score > actual_away_score AND current_recommendation IN ('主让1胜', '主让1平', '主让2胜', '主让2平')) OR
                           (actual_home_score < actual_away_score AND current_recommendation IN ('客让1胜', '客让1平', '客让2胜', '客让2平')) OR
                           (actual_home_score = actual_away_score AND current_recommendation IN ('平', '双平偏平'))
                       THEN 1 ELSE 0 END) as correct
                FROM kleague_validation_results
                WHERE match_id IN ({match_ids_str})
                """
                
                result = self.db.execute_query(query, fetch='one')
                if result and result['total'] > 0:
                    accuracy = result['correct'] / result['total'] * 100
                    if accuracy > best_accuracy:
                        best_accuracy = accuracy
                        best_range = range_name
        
        print(f"1. 准确率最高的赔率区间: {best_range} ({best_accuracy:.1f}%)")
        
        # 分析极端明显比赛的影响
        obvious_matches = len(range_matches[0])  # 极端明显 < 1.4
        obvious_percentage = obvious_matches / total_stats['matches'] * 100 if total_stats['matches'] > 0 else 0
        
        print(f"2. 极端明显比赛(<1.4)占比: {obvious_percentage:.1f}% ({obvious_matches}/{total_stats['matches']})")
        
        # 提供解释
        print("\n可能的原因分析:")
        print("- 如果极端明显比赛准确率反而低，说明模型可能过度依赖赔率特征")
        print("- 如果中等赔率区间准确率高，说明模型在均衡比赛中表现更好")
        print("- 需要检查推荐规则是否对极端赔率有特殊处理")
    
    def compare_with_without_filter(self, league_id: int):
        """对比过滤前后的准确率"""
        
        print(f"\n对比过滤前后的准确率")
        print("="*80)
        
        # 1. 不过滤的准确率
        query_all = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN 
                (actual_home_score > actual_away_score AND current_recommendation IN ('主让1胜', '主让1平', '主让2胜', '主让2平')) OR
                (actual_home_score < actual_away_score AND current_recommendation IN ('客让1胜', '客让1平', '客让2胜', '客让2平')) OR
                (actual_home_score = actual_away_score AND current_recommendation IN ('平', '双平偏平'))
            THEN 1 ELSE 0 END) as correct
        FROM kleague_validation_results vr
        JOIN matches m ON vr.match_id = m.match_id
        WHERE m.league_id = %s AND m.round_number >= 10 AND m.round_number <= 38
        """
        
        result_all = self.db.execute_query(query_all, [league_id], fetch='one')
        
        if result_all and result_all['total'] > 0:
            accuracy_all = result_all['correct'] / result_all['total'] * 100
            print(f"不过滤: 总预测{result_all['total']}, 正确{result_all['correct']}, 准确率{accuracy_all:.1f}%")
        
        # 2. 过滤后的准确率 (排除赔率<1.4的比赛)
        query_filtered = """
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN 
                (actual_home_score > actual_away_score AND current_recommendation IN ('主让1胜', '主让1平', '主让2胜', '主让2平')) OR
                (actual_home_score < actual_away_score AND current_recommendation IN ('客让1胜', '客让1平', '客让2胜', '客让2平')) OR
                (actual_home_score = actual_away_score AND current_recommendation IN ('平', '双平偏平'))
            THEN 1 ELSE 0 END) as correct
        FROM kleague_validation_results vr
        JOIN matches m ON vr.match_id = m.match_id
        WHERE m.league_id = %s 
          AND m.round_number >= 10 
          AND m.round_number <= 38
          AND vr.match_id NOT IN (
              SELECT DISTINCT m2.match_id
              FROM matches m2
              JOIN european_odds eo ON m2.match_id = eo.match_id
              WHERE m2.league_id = %s
                AND eo.odds_type = '1x2'
                AND (eo.initial_home < 1.4 OR eo.initial_away < 1.4)
          )
        """
        
        result_filtered = self.db.execute_query(query_filtered, [league_id, league_id], fetch='one')
        
        if result_filtered and result_filtered['total'] > 0:
            accuracy_filtered = result_filtered['correct'] / result_filtered['total'] * 100
            print(f"过滤后: 总预测{result_filtered['total']}, 正确{result_filtered['correct']}, 准确率{accuracy_filtered:.1f}%")
            
            # 分析差异
            print(f"\n准确率变化: {accuracy_filtered - accuracy_all:+.1f}%")
            print(f"预测数变化: {result_filtered['total'] - result_all['total']:+d}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="赔率区间分析器")
    parser.add_argument('--league-id', type=int, default=15,
                       help='联赛ID（15-韩K，25-日职）')
    
    args = parser.parse_args()
    
    analyzer = OddsRangeAnalyzer()
    
    # 按赔率区间分析
    analyzer.analyze_by_odds_range(args.league_id)
    
    # 对比过滤前后
    analyzer.compare_with_without_filter(args.league_id)


if __name__ == "__main__":
    main()