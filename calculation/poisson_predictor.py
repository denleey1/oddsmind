"""
泊松分布足球比赛预测模块
基于历史比赛数据预测进球数分布和各种比分概率
"""

import math
from typing import Dict, List, Tuple, Optional
from decimal import Decimal, ROUND_HALF_UP
import logging

from database.connection import get_connection

logger = logging.getLogger(__name__)

class PoissonPredictor:
    """泊松分布足球比赛预测器"""
    
    def __init__(self):
        self.db = get_connection()
        
    def round_to_2dp(self, value: float) -> float:
        """保留两位小数"""
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    def poisson_probability(self, lambda_val: float, k: int) -> float:
        """计算泊松分布概率 P(X=k) = e^(-λ) * λ^k / k!"""
        if lambda_val <= 0:
            return 0.0 if k > 0 else 1.0
        
        try:
            prob = (math.exp(-lambda_val) * (lambda_val ** k)) / math.factorial(k)
            return self.round_to_2dp(prob)
        except (OverflowError, ValueError):
            return 0.0
    
    def get_team_stats(self, team_id: int, league_id: int, is_home: bool, recent_games: int = 8) -> Dict:
        """获取球队近期主场/客场统计数据"""
        with self.db.connection_scope() as conn:
            cursor = conn.cursor()

            if is_home:
                where_condition = "home_team_id = %s"
                goals_for = "home_score"
                goals_against = "away_score"
            else:
                where_condition = "away_team_id = %s"
                goals_for = "away_score"
                goals_against = "home_score"

            sql = f"""
            SELECT 
                {goals_for} as goals_for,
                {goals_against} as goals_against,
                match_time
            FROM matches 
            WHERE {where_condition} 
                AND league_id = %s 
                AND match_status = 'finished'
                AND home_score IS NOT NULL 
                AND away_score IS NOT NULL
            ORDER BY match_time DESC 
            LIMIT %s
            """

            cursor.execute(sql, (team_id, league_id, recent_games))
            matches = cursor.fetchall()

        if not matches:
            return {
                'games_played': 0,
                'avg_goals_for': 0.0,
                'avg_goals_against': 0.0,
                'total_goals_for': 0,
                'total_goals_against': 0
            }

        total_goals_for = sum(match['goals_for'] for match in matches)
        total_goals_against = sum(match['goals_against'] for match in matches)
        games_played = len(matches)

        return {
            'games_played': games_played,
            'avg_goals_for': self.round_to_2dp(total_goals_for / games_played),
            'avg_goals_against': self.round_to_2dp(total_goals_against / games_played),
            'total_goals_for': total_goals_for,
            'total_goals_against': total_goals_against
        }
    
    def get_league_averages(self, league_id: int) -> Dict:
        """获取联赛平均数据"""
        with self.db.connection_scope() as conn:
            cursor = conn.cursor()

            sql = """
            SELECT 
                AVG(home_score) as avg_home_goals,
                AVG(away_score) as avg_away_goals,
                COUNT(*) as total_matches
            FROM matches 
            WHERE league_id = %s 
                AND match_status = 'finished'
                AND home_score IS NOT NULL 
                AND away_score IS NOT NULL
            """

            cursor.execute(sql, (league_id,))
            result = cursor.fetchone()

        if not result or result['total_matches'] == 0:
            return {
                'avg_home_goals': 1.5,
                'avg_away_goals': 1.2,
                'total_matches': 0
            }

        return {
            'avg_home_goals': self.round_to_2dp(float(result['avg_home_goals'])),
            'avg_away_goals': self.round_to_2dp(float(result['avg_away_goals'])),
            'total_matches': result['total_matches']
        }
    
    def calculate_attack_defense_strength(self, team_stats: Dict, league_avg: float, is_attack: bool) -> float:
        """计算攻击力或防守力系数"""
        if league_avg == 0:
            return 1.0
        
        if is_attack:
            # 攻击力 = 球队平均进球 / 联赛平均进球
            team_avg = team_stats['avg_goals_for']
        else:
            # 防守力 = 球队平均失球 / 联赛平均失球
            team_avg = team_stats['avg_goals_against']
        
        strength = team_avg / league_avg
        return self.round_to_2dp(strength)
    
    def predict_goals_expectation(self, home_team_id: int, away_team_id: int, league_id: int) -> Dict:
        """预测比赛的进球期望值"""
        # 获取球队数据
        home_stats = self.get_team_stats(home_team_id, league_id, is_home=True)
        away_stats = self.get_team_stats(away_team_id, league_id, is_home=False)
        league_stats = self.get_league_averages(league_id)
        
        # 计算攻防系数
        home_attack = self.calculate_attack_defense_strength(
            home_stats, league_stats['avg_home_goals'], is_attack=True)
        home_defense = self.calculate_attack_defense_strength(
            home_stats, league_stats['avg_home_goals'], is_attack=False)
        
        away_attack = self.calculate_attack_defense_strength(
            away_stats, league_stats['avg_away_goals'], is_attack=True)
        away_defense = self.calculate_attack_defense_strength(
            away_stats, league_stats['avg_away_goals'], is_attack=False)
        
        # 计算进球期望值
        home_expected = home_attack * away_defense * league_stats['avg_home_goals']
        away_expected = away_attack * home_defense * league_stats['avg_away_goals']
        
        return {
            'home_expected_goals': self.round_to_2dp(home_expected),
            'away_expected_goals': self.round_to_2dp(away_expected),
            'total_expected_goals': self.round_to_2dp(home_expected + away_expected),
            'team_stats': {
                'home': home_stats,
                'away': away_stats
            },
            'league_stats': league_stats,
            'strength_coefficients': {
                'home_attack': home_attack,
                'home_defense': home_defense,
                'away_attack': away_attack,
                'away_defense': away_defense
            }
        }
    
    def calculate_score_probabilities(self, home_lambda: float, away_lambda: float, max_goals: int = 5) -> Dict:
        """计算各种比分的概率"""
        score_probs = {}
        
        # 计算具体比分概率 (0-0 到 max_goals-max_goals)
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                prob = (self.poisson_probability(home_lambda, home_goals) * 
                       self.poisson_probability(away_lambda, away_goals))
                score_probs[f"{home_goals}-{away_goals}"] = self.round_to_2dp(prob)
        
        # 计算超过max_goals的概率
        home_over_prob = 1 - sum(self.poisson_probability(home_lambda, i) for i in range(max_goals + 1))
        away_over_prob = 1 - sum(self.poisson_probability(away_lambda, i) for i in range(max_goals + 1))
        
        # 添加"其他比分"的概率估计
        other_prob = self.round_to_2dp(home_over_prob + away_over_prob - home_over_prob * away_over_prob)
        if other_prob > 0:
            score_probs["其他比分"] = other_prob
        
        return score_probs
    
    def calculate_over_under_probabilities(self, home_lambda: float, away_lambda: float) -> Dict:
        """计算大小球概率"""
        total_lambda = home_lambda + away_lambda
        
        # 常见大小球盘口
        ou_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
        ou_probs = {}
        
        for line in ou_lines:
            # 计算小于等于line-0.5的概率（小球）
            under_prob = 0.0
            for goals in range(int(line) + 1):
                under_prob += self.poisson_probability(total_lambda, goals)
            
            over_prob = 1 - under_prob
            
            ou_probs[f"大{line}"] = self.round_to_2dp(over_prob)
            ou_probs[f"小{line}"] = self.round_to_2dp(under_prob)
        
        return ou_probs
    
    def calculate_confidence_intervals(self, lambda_val: float, confidence: float = 0.95) -> Dict:
        """计算泊松分布的置信区间"""
        # 使用正态近似计算置信区间（当λ较大时）
        if lambda_val >= 10:
            z_score = 1.96 if confidence == 0.95 else 2.58  # 95% or 99%
            margin = z_score * math.sqrt(lambda_val)
            lower = max(0, lambda_val - margin)
            upper = lambda_val + margin
        else:
            # 对于小λ值，使用更精确的方法
            # 这里简化为使用标准差
            std = math.sqrt(lambda_val)
            margin = 1.96 * std if confidence == 0.95 else 2.58 * std
            lower = max(0, lambda_val - margin)
            upper = lambda_val + margin
        
        return {
            'expected': self.round_to_2dp(lambda_val),
            'lower_bound': self.round_to_2dp(lower),
            'upper_bound': self.round_to_2dp(upper),
            'confidence_level': confidence
        }
    
    def predict_match(self, home_team_id: int, away_team_id: int, league_id: int) -> Dict:
        """完整的比赛预测"""
        try:
            # 1. 计算进球期望值
            prediction_base = self.predict_goals_expectation(home_team_id, away_team_id, league_id)
            
            home_lambda = prediction_base['home_expected_goals']
            away_lambda = prediction_base['away_expected_goals']
            
            # 2. 计算比分概率
            score_probabilities = self.calculate_score_probabilities(home_lambda, away_lambda)
            
            # 3. 计算大小球概率
            over_under_probabilities = self.calculate_over_under_probabilities(home_lambda, away_lambda)
            
            # 4. 计算置信区间
            home_confidence = self.calculate_confidence_intervals(home_lambda)
            away_confidence = self.calculate_confidence_intervals(away_lambda)
            
            # 5. 找出最可能的比分
            most_likely_score = max(score_probabilities.items(), 
                                  key=lambda x: x[1] if x[0] != "其他比分" else 0)
            
            return {
                'prediction_summary': {
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id,
                    'league_id': league_id,
                    'home_expected_goals': home_lambda,
                    'away_expected_goals': away_lambda,
                    'total_expected_goals': prediction_base['total_expected_goals'],
                    'most_likely_score': most_likely_score[0],
                    'most_likely_score_probability': most_likely_score[1]
                },
                'confidence_intervals': {
                    'home_goals': home_confidence,
                    'away_goals': away_confidence
                },
                'score_probabilities': score_probabilities,
                'over_under_probabilities': over_under_probabilities,
                'base_data': prediction_base,
                'model_info': {
                    'model_type': 'Poisson Distribution',
                    'recent_games_used': 8,
                    'precision': '2 decimal places'
                }
            }
            
        except Exception as e:
            logger.error(f"预测失败: {e}")
            return {
                'error': f"预测失败: {str(e)}",
                'prediction_summary': None
            }

def predict_match_result(home_team_id: int, away_team_id: int, league_id: int) -> Dict:
    """快速预测接口"""
    predictor = PoissonPredictor()
    return predictor.predict_match(home_team_id, away_team_id, league_id)

if __name__ == "__main__":
    # 测试代码
    import json
    
    # 使用示例数据进行测试
    test_home_team = 207  # 大阪钢巴
    test_away_team = 193  # 大阪樱花
    test_league = 25
    
    print("=== 泊松分布足球预测测试 ===")
    result = predict_match_result(test_home_team, test_away_team, test_league)
    
    if 'error' not in result:
        print(f"\n预测摘要:")
        summary = result['prediction_summary']
        print(f"主队期望进球: {summary['home_expected_goals']}")
        print(f"客队期望进球: {summary['away_expected_goals']}")
        print(f"总进球期望: {summary['total_expected_goals']}")
        print(f"最可能比分: {summary['most_likely_score']} (概率: {summary['most_likely_score_probability']})")
        
        print(f"\n置信区间 (95%):")
        print(f"主队进球: {result['confidence_intervals']['home_goals']['lower_bound']} - {result['confidence_intervals']['home_goals']['upper_bound']}")
        print(f"客队进球: {result['confidence_intervals']['away_goals']['lower_bound']} - {result['confidence_intervals']['away_goals']['upper_bound']}")
        
        print(f"\n主要比分概率:")
        scores = sorted(result['score_probabilities'].items(), key=lambda x: x[1], reverse=True)[:10]
        for score, prob in scores:
            print(f"{score}: {prob}")
        
        print(f"\n大小球概率:")
        ou_items = list(result['over_under_probabilities'].items())
        for i in range(0, len(ou_items), 2):  # 每行显示一对大小球
            if i+1 < len(ou_items):
                print(f"{ou_items[i][0]}: {ou_items[i][1]}, {ou_items[i+1][0]}: {ou_items[i+1][1]}")
    else:
        print(f"预测失败: {result['error']}")
