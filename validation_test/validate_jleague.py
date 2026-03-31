#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
验证日职联赛的预测准确率
"""

import sys
from pathlib import Path
from typing import Dict, List, Set
from datetime import datetime
import json

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class JLeagueValidator:
    """日职联赛验证器"""
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.league_id = 25  # 日职联赛ID
        self.league_name = "日职联"
        
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
    
    def validate_full_season(self, start_round: int = 10, end_round: int = 38):
        """验证整个赛季"""
        
        print(f"\n开始验证 {self.league_name} (联赛ID: {self.league_id})")
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
            [self.league_id, start_round, end_round], 
            fetch='all'
        )
        
        if not all_matches:
            print(f"没有找到符合条件的比赛")
            return
        
        print(f"总比赛数: {len(all_matches)}")
        
        # 2. 检查是否有验证结果表
        check_table_query = """
        SELECT COUNT(*) as count
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
          AND table_name = 'jleague_validation_results'
        """
        
        table_exists = self.db.execute_query(check_table_query, fetch='one')
        
        if not table_exists or table_exists['count'] == 0:
            print(f"\n验证结果表 'jleague_validation_results' 不存在")
            print("需要先运行验证程序生成结果表")
            return
        
        # 3. 获取验证结果
        result_query = """
        SELECT 
            company_id,
            match_id,
            actual_home_score,
            actual_away_score,
            current_recommendation,
            current_rule_diff
        FROM jleague_validation_results
        WHERE match_id IN (%s)
        """ % ','.join(str(m['match_id']) for m in all_matches)
        
        results = self.db.execute_query(result_query, fetch='all')
        
        if not results:
            print("没有找到验证结果数据")
            return
        
        print(f"验证结果数: {len(results)}")
        
        # 4. 计算准确率
        self._calculate_accuracy(results)
        
        # 5. 分析赔率区间
        self._analyze_odds_ranges(start_round, end_round)
    
    def _calculate_accuracy(self, results: List[Dict]):
        """计算准确率"""
        
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
            
            if recommendation in self.recommendation_mapping:
                rule = self.recommendation_mapping[recommendation]
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
        
        # 显示准确率
        print(f"\n{self.league_name} 准确率统计:")
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
        
        # 总体统计
        total_predictions = sum(s['total'] for s in company_stats.values())
        total_correct = sum(s['correct'] for s in company_stats.values())
        overall_accuracy = total_correct / total_predictions * 100 if total_predictions > 0 else 0
        
        print("-"*60)
        print(f"总体准确率: {overall_accuracy:.1f}% ({total_correct}/{total_predictions})")
    
    def _analyze_odds_ranges(self, start_round: int, end_round: int):
        """分析不同赔率区间的准确率"""
        
        print(f"\n{self.league_name} 赔率区间分析:")
        print("="*60)
        
        # 定义赔率区间
        odds_ranges = [
            (0.0, 1.4, "极端明显"),
            (1.4, 1.8, "比较明显"),
            (1.8, 2.2, "适度偏向"),
            (2.2, 3.0, "相对均衡"),
            (3.0, float('inf'), "高赔率")
        ]
        
        # 获取每个区间的比赛
        for min_val, max_val, range_name in odds_ranges:
            if max_val == float('inf'):
                # 处理无穷大的情况
                query = """
                SELECT COUNT(DISTINCT m.match_id) as match_count
                FROM matches m
                JOIN european_odds eo ON m.match_id = eo.match_id
                WHERE m.league_id = %s 
                  AND m.round_number >= %s 
                  AND m.round_number <= %s
                  AND m.match_status = 'finished'
                  AND eo.odds_type = '1x2'
                  AND LEAST(eo.initial_home, eo.initial_away) >= %s
                """
                
                result = self.db.execute_query(
                    query,
                    [self.league_id, start_round, end_round, min_val],
                    fetch='one'
                )
            else:
                query = """
                SELECT COUNT(DISTINCT m.match_id) as match_count
                FROM matches m
                JOIN european_odds eo ON m.match_id = eo.match_id
                WHERE m.league_id = %s 
                  AND m.round_number >= %s 
                  AND m.round_number <= %s
                  AND m.match_status = 'finished'
                  AND eo.odds_type = '1x2'
                  AND LEAST(eo.initial_home, eo.initial_away) >= %s
                  AND LEAST(eo.initial_home, eo.initial_away) < %s
                """
                
                result = self.db.execute_query(
                    query,
                    [self.league_id, start_round, end_round, min_val, max_val],
                    fetch='one'
                )
            
            if result:
                print(f"{range_name:<15} 比赛数: {result['match_count']}")
        
        # 特别分析极端明显比赛
        self._analyze_obvious_matches(start_round, end_round)
    
    def _analyze_obvious_matches(self, start_round: int, end_round: int):
        """分析极端明显的比赛"""
        
        print(f"\n{self.league_name} 极端明显比赛(<1.4)详情:")
        print("-"*60)
        
        query = """
        SELECT DISTINCT 
            m.match_id,
            m.home_team_name,
            m.away_team_name,
            m.home_score,
            m.away_score,
            MIN(eo.initial_home) as min_home_odds,
            MIN(eo.initial_away) as min_away_odds
        FROM matches m
        JOIN european_odds eo ON m.match_id = eo.match_id
        WHERE m.league_id = %s 
          AND m.round_number >= %s 
          AND m.round_number <= %s
          AND m.match_status = 'finished'
          AND eo.odds_type = '1x2'
          AND (eo.initial_home < 1.4 OR eo.initial_away < 1.4)
        GROUP BY m.match_id, m.home_team_name, m.away_team_name, m.home_score, m.away_score
        LIMIT 5
        """
        
        obvious_matches = self.db.execute_query(
            query,
            [self.league_id, start_round, end_round],
            fetch='all'
        )
        
        if obvious_matches:
            for match in obvious_matches:
                home_score = match['home_score']
                away_score = match['away_score']
                
                if home_score > away_score:
                    result = "主胜"
                elif home_score < away_score:
                    result = "客胜"
                else:
                    result = "平局"
                
                print(f"{match['home_team_name']} vs {match['away_team_name']}")
                print(f"  比分: {home_score}-{away_score} ({result})")
                print(f"  赔率: 主{match['min_home_odds']:.2f} 客{match['min_away_odds']:.2f}")
        else:
            print("没有找到极端明显的比赛")


def main():
    """主函数"""
    validator = JLeagueValidator()
    
    # 验证整个赛季
    validator.validate_full_season(start_round=10, end_round=38)


if __name__ == "__main__":
    main()