#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys
import json
from pathlib import Path
from typing import Dict, List, Set, Any
import time

# Set encoding
sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.append(str(PROJECT_ROOT))

# Add parent directory to path to import local modules
sys.path.append(str(Path(__file__).parent.parent))

from core.logger import get_logger
from optimal_combination_analysis.combination_finder import CombinationFinder
from optimal_combination_analysis.coverage_analyzer import CoverageAnalyzer
from optimal_combination_analysis.db_connector import get_direct_connection
# Removed FastLeagueValidator dependency

class CombinationAnalysisRunner:
    """
    Runner for Optimal Combination Analysis.
    Fetches data from validation tables and runs the CombinationFinder.
    """
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
        self.finder = CombinationFinder()
        self.analyzer = CoverageAnalyzer()
        self.league_codes = [
            'bundesliga', 'ligue1', 'kleague', 'jleague', 
            'laliga', 'seriea', 'premier'
        ]
        
        # Load recommendation mapping directly from JSON
        self.recommendation_mapping = {}
        self._load_recommendation_mapping()
        
        try:
            self.db = get_direct_connection() # Use our direct connection
            self.db_available = True
        except Exception as e:
            print(f"⚠️ Critical: Direct Database connection failed: {e}")
            self.db = None
            self.db_available = False

    def _load_recommendation_mapping(self):
        """Loads recommendation mapping rules from the JSON file in the parent directory."""
        try:
            # Look for mapping file in the parent directory (validation_test/)
            mapping_file = Path(__file__).parent.parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                self.recommendation_mapping = mapping_data['recommendations']
            print(f"✅ Loaded {len(self.recommendation_mapping)} recommendation rules from {mapping_file.name}")
        except Exception as e:
            print(f"❌ Failed to load recommendation mapping: {e}")
            self.recommendation_mapping = {}

    def _is_recommendation_correct(self, recommendation: str, actual_result: str, rule_diff: float = 0) -> int:
        """
        Determines if a recommendation is correct based on the loaded mapping rules.
        Logic replicated exactly from FastLeagueValidator.
        """
        if recommendation not in self.recommendation_mapping:
            return 0
        
        rule = self.recommendation_mapping[recommendation]
        predicted_result = rule.get('result', 'unknown')
        
        # Special handling for "双平偏让平"
        if recommendation == "双平偏让平":
            if rule_diff < 0:
                predicted_result = "home_win"
            elif rule_diff > 0:
                predicted_result = "away_win"
            else:
                predicted_result = "draw"
        
        # Handle list results (multiple correct outcomes)
        if isinstance(predicted_result, list):
            return 1 if actual_result in predicted_result else 0
        else:
            return 1 if predicted_result == actual_result else 0

    def fetch_data(self, limit_matches: int = None) -> (List[int], Dict[int, Dict[int, bool]]):
        """
        Fetches validation results from all league tables.
        """
        if not self.db_available:
            print("❌ DB not available for data fetching. Cannot proceed.")
            return [], {}

        print("Fetching data from validation tables using direct connection...")
        
        matches_set = set()
        predictions = {}
        
        total_rows = 0
        
        for code in self.league_codes:
            table_name = f"{code}_validation_results"
            
            # Check if table exists
            check_sql = f"SHOW TABLES LIKE '{table_name}'"
            if not self.db.execute_query(check_sql, fetch='one'):
                print(f"Table {table_name} not found, skipping.")
                continue
                
            print(f"Reading from {table_name}...")
            
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
                
            total_rows += len(rows)
            
            for row in rows:
                match_id = row['match_id']
                company_id = row['company_id']
                
                matches_set.add(match_id)
                
                # Determine actual result
                if row['actual_home_score'] > row['actual_away_score']:
                    actual_result = 'home_win'
                elif row['actual_home_score'] < row['actual_away_score']:
                    actual_result = 'away_win'
                else:
                    actual_result = 'draw'
                
                # Check correctness using our local method with full logic
                is_correct = self._is_recommendation_correct(
                    row['current_recommendation'], 
                    actual_result, 
                    float(row['current_rule_diff'] if row['current_rule_diff'] is not None else 0)
                )

                if match_id not in predictions:
                    predictions[match_id] = {}
                
                predictions[match_id][company_id] = bool(is_correct)
        
        matches = list(matches_set)
        if limit_matches:
            matches = matches[-limit_matches:] # Take recent matches if limited
            
        print(f"Loaded {len(matches)} unique matches and {total_rows} predictions.")
        return matches, predictions

    def save_combination_to_db(self, name: str, result: Dict):
        """
        Saves the combination result to the database.
        """
        if not self.db_available:
            print("⚠️ DB not available. Skipping save to database.")
            return

        table_name = "company_combinations"
        
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            id INT AUTO_INCREMENT PRIMARY KEY,
            combination_name VARCHAR(50),
            company_ids JSON,
            total_matches INT,
            covered_matches INT,
            coverage_rate DECIMAL(5, 2),
            details JSON,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
        self.db.execute_query(create_sql)
        
        insert_sql = f"""
        INSERT INTO `{table_name}` 
        (combination_name, company_ids, total_matches, covered_matches, coverage_rate, details)
        VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        self.db.execute_query(insert_sql, [
            name,
            json.dumps(result['selected_companies']),
            result['total_matches'],
            result['covered_matches'],
            result['coverage_rate'],
            json.dumps(result['details'])
        ])
        print(f"Results saved to table `{table_name}`.")



    def run(self):
        # 1. Fetch Data
        matches, predictions = self.fetch_data()
        
        if not matches:
            print("No data found to analyze.")
            return

        # 2. Run Algorithm
        print(f"\nRunning Optimal Combination Analysis on {len(matches)} matches...")
        start_time = time.time()
        
        # We can try different K or strategies here. 
        # Let's find the Top 15 Golden Combination to aim for higher coverage.
        k = 15
        result = self.finder.find_best_combination(matches, predictions, k=k)
        
        end_time = time.time()
        
        # 3. Output Report
        print(f"\n{'='*60}")
        print(f"GOLDEN COMBINATION (Top {k})")
        print(f"{'='*60}")
        print(f"Total Matches Analyzed: {result['total_matches']}")
        print(f"Covered Matches:        {result['covered_matches']}")
        print(f"Coverage Rate:          {result['coverage_rate']}%")
        print(f"Selected Companies:     {result['selected_companies']}")
        print("-" * 60)
        print("Selection Steps:")
        for step in result['details']:
            print(f"  Step {step['step']}: Added Company {step['company_id']}")
            print(f"    - Marginal Gain: {step['marginal_gain']} matches")
            print(f"    - Overall Accuracy: {step['total_accuracy']:.2%}")
        print("-" * 60)
        
        # Verify with Analyzer
        verification = self.analyzer.analyze_coverage(matches, predictions, result['selected_companies'])
        print(f"Verification Check: Calculated Coverage {verification['coverage_rate']}% (Matches: {verification['covered_matches']}/{verification['total_matches']})")
        
        # 4. Save to DB
        self.save_combination_to_db(f"Global Golden {k}", result)

if __name__ == "__main__":
    runner = CombinationAnalysisRunner()
    runner.run()
