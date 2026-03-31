#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Any

# Set encoding
sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Add parent directory to path to import local modules
sys.path.append(str(Path(__file__).parent.parent))

from core.logger import get_logger
from optimal_combination_analysis.coverage_analyzer import CoverageAnalyzer
from optimal_combination_analysis.db_connector import get_direct_connection

class CustomCombinationEvaluator:
    """
    Evaluates a specific list of companies.
    """
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.analyzer = CoverageAnalyzer()
        self.league_codes = [
            'bundesliga', 'ligue1', 'kleague', 'jleague', 
            'laliga', 'seriea', 'premier'
        ]
        
        # Load recommendation mapping directly from JSON
        self.recommendation_mapping = {}
        self._load_recommendation_mapping()
        
        try:
            self.db = get_direct_connection() 
            self.db_available = True
        except Exception as e:
            print(f"⚠️ Critical: Direct Database connection failed: {e}")
            self.db = None
            self.db_available = False

    def _load_recommendation_mapping(self):
        """Loads recommendation mapping rules."""
        try:
            mapping_file = Path(__file__).parent.parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                self.recommendation_mapping = mapping_data['recommendations']
        except Exception as e:
            print(f"❌ Failed to load recommendation mapping: {e}")
            self.recommendation_mapping = {}

    def _is_recommendation_correct(self, recommendation: str, actual_result: str, rule_diff: float = 0) -> int:
        if recommendation not in self.recommendation_mapping:
            return 0
        
        rule = self.recommendation_mapping[recommendation]
        predicted_result = rule.get('result', 'unknown')
        
        if recommendation == "双平偏让平":
            if rule_diff < 0:
                predicted_result = "home_win"
            elif rule_diff > 0:
                predicted_result = "away_win"
            else:
                predicted_result = "draw"
        
        if isinstance(predicted_result, list):
            return 1 if actual_result in predicted_result else 0
        else:
            return 1 if predicted_result == actual_result else 0

    def fetch_data(self) -> (List[int], Dict[int, Dict[int, bool]]):
        if not self.db_available:
            return [], {}
        
        matches_set = set()
        predictions = {}
        
        for code in self.league_codes:
            table_name = f"{code}_validation_results"
            
            check_sql = f"SHOW TABLES LIKE '{table_name}'"
            if not self.db.execute_query(check_sql, fetch='one'):
                continue
                
            query = f"""
                SELECT 
                    match_id, company_id, 
                    actual_home_score, actual_away_score,
                    current_recommendation, current_rule_diff
                FROM `{table_name}`
            """
            
            rows = self.db.execute_query(query, fetch='all')
            if not rows:
                continue
                
            for row in rows:
                match_id = row['match_id']
                company_id = row['company_id']
                
                matches_set.add(match_id)
                
                if row['actual_home_score'] > row['actual_away_score']:
                    actual_result = 'home_win'
                elif row['actual_home_score'] < row['actual_away_score']:
                    actual_result = 'away_win'
                else:
                    actual_result = 'draw'
                
                is_correct = self._is_recommendation_correct(
                    row['current_recommendation'], 
                    actual_result, 
                    float(row['current_rule_diff'] if row['current_rule_diff'] is not None else 0)
                )

                if match_id not in predictions:
                    predictions[match_id] = {}
                
                predictions[match_id][company_id] = bool(is_correct)
        
        matches = list(matches_set)
        return matches, predictions

    def run(self, company_ids: List[int]):
        matches, predictions = self.fetch_data()
        
        if not matches:
            print("No data found to analyze.")
            return

        print(f"\nEvaluating Custom Combination: {company_ids}")
        print(f"Total Matches: {len(matches)}")
        
        result = self.analyzer.analyze_coverage(matches, predictions, company_ids)
        
        print(f"\n{'='*60}")
        print(f"CUSTOM COMBINATION RESULTS")
        print(f"{ '='*60}")
        print(f"Covered Matches:        {result['covered_matches']}")
        print(f"Coverage Rate:          {result['coverage_rate']}%")
        print("-" * 60)

if __name__ == "__main__":
    evaluator = CustomCombinationEvaluator()
    # Combined list: Golden 5 + User's 6
    # Golden 5: [1243, 649, 943, 974, 1129]
    # User's 6: [115, 432, 80, 81, 281, 104]
    combined_ids = [1243, 649, 943, 974, 1129, 115, 432, 80, 81, 281, 104]
    evaluator.run(combined_ids)
