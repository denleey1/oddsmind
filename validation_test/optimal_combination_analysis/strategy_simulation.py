#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
from pathlib import Path
from typing import Dict, List, Counter

# Set encoding
sys.stdout.reconfigure(encoding='utf-8')

# Add project root
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from optimal_combination_analysis.db_connector import get_direct_connection

class StrategySimulator:
    def __init__(self):
        self.db = get_direct_connection()
        self.companies = [1243, 649, 943, 974, 1129, 115, 432, 80, 81, 281, 104]
        # Golden 5: 1243, 649, 943, 974, 1129 (Weights: 1.5)
        # Famous 6: 115, 432, 80, 81, 281, 104 (Weights: 1.0)
        self.weights = {
            1243: 1.5, 649: 1.5, 943: 1.5, 974: 1.5, 1129: 1.5,
            115: 1.0, 432: 1.0, 80: 1.0, 81: 1.0, 281: 1.0, 104: 1.0
        }
        self._load_mapping()
        self.league_codes = ['bundesliga', 'ligue1', 'kleague', 'jleague', 'laliga', 'seriea', 'premier']

    def _load_mapping(self):
        try:
            mapping_file = Path(__file__).parent.parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                self.mapping = json.load(f)['recommendations']
        except:
            self.mapping = {}

    def get_predicted_result(self, recommendation, rule_diff):
        if recommendation not in self.mapping:
            return None
        
        rule = self.mapping[recommendation]
        pred = rule.get('result', None)
        
        if recommendation == "双平偏让平":
            if rule_diff < 0: return "home_win"
            elif rule_diff > 0: return "away_win"
            else: return "draw"
            
        if isinstance(pred, list):
            return pred[0] # Simplify for voting: take primary prediction
        return pred

    def run(self):
        print("正在加载数据并模拟决策策略...")
        
        matches_data = {}
        
        # 1. Fetch Data
        for code in self.league_codes:
            table = f"{code}_validation_results"
            check = self.db.execute_query(f"SHOW TABLES LIKE '{table}'", fetch='one')
            if not check: continue
            
            rows = self.db.execute_query(f"""
                SELECT match_id, company_id, actual_home_score, actual_away_score, 
                       current_recommendation, current_rule_diff 
                FROM {table} 
                WHERE company_id IN ({','.join(map(str, self.companies))})
            """, fetch='all')
            
            if not rows: continue
            
            for row in rows:
                mid = row['match_id']
                if mid not in matches_data:
                    # Determine actual result
                    h, a = row['actual_home_score'], row['actual_away_score']
                    act = 'home_win' if h > a else ('away_win' if a > h else 'draw')
                    matches_data[mid] = {'actual': act, 'predictions': {}}
                
                pred = self.get_predicted_result(row['current_recommendation'], float(row['current_rule_diff'] or 0))
                if pred:
                    matches_data[mid]['predictions'][row['company_id']] = pred

        total_matches = len(matches_data)
        print(f"共分析 {total_matches} 场比赛，涉及11家公司。\n")
        
        # 2. Simulate Strategies
        
        # Strategy 1: Simple Majority (Vote Count)
        self._evaluate_strategy("民主投票 (多数决)", matches_data, lambda preds: self._strategy_majority(preds))
        
        # Strategy 2: Weighted (Golden 5 have 1.5x weight)
        self._evaluate_strategy("精英加权 (黄金公司1.5倍权重)", matches_data, lambda preds: self._strategy_weighted(preds))
        
        # Strategy 3: High Confidence (Threshold >= 6 votes)
        self._evaluate_strategy("高置信度 (>=6家公司一致)", matches_data, lambda preds: self._strategy_threshold(preds, 6))

        # Strategy 4: Very High Confidence (Threshold >= 8 votes)
        self._evaluate_strategy("超高置信度 (>=8家公司一致)", matches_data, lambda preds: self._strategy_threshold(preds, 8))

    def _strategy_majority(self, predictions):
        if not predictions: return None
        votes = Counter(predictions.values())
        return votes.most_common(1)[0][0]

    def _strategy_weighted(self, predictions):
        if not predictions: return None
        scores = {'home_win': 0, 'draw': 0, 'away_win': 0}
        for cid, pred in predictions.items():
            if pred in scores:
                scores[pred] += self.weights.get(cid, 1.0)
        return max(scores, key=scores.get)

    def _strategy_threshold(self, predictions, threshold):
        if not predictions: return None
        votes = Counter(predictions.values())
        top_choice, count = votes.most_common(1)[0]
        if count >= threshold:
            return top_choice
        return None # Skip bet

    def _evaluate_strategy(self, name, data, strategy_func):
        correct = 0
        betted = 0
        
        for mid, info in data.items():
            final_decision = strategy_func(info['predictions'])
            if final_decision:
                betted += 1
                if final_decision == info['actual']:
                    correct += 1
        
        accuracy = (correct / betted * 100) if betted > 0 else 0
        coverage = (betted / len(data) * 100) if len(data) > 0 else 0
        
        print(f"=== {name} ===")
        print(f"  出手场次: {betted} / {len(data)} (覆盖率 {coverage:.1f}%)")
        print(f"  命中场次: {correct}")
        print(f"  实际胜率: {accuracy:.1f}%")
        print("-" * 40)

if __name__ == "__main__":
    StrategySimulator().run()
