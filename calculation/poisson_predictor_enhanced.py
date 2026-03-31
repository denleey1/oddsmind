"""
增强版泊松预测模块
支持Dixon-Coles修正、负二项分布、市场融合和概率校准
"""

import math
from typing import Dict, List, Tuple, Optional
from decimal import Decimal, ROUND_HALF_UP
import logging

from database.connection import get_connection

# 导入增强模块
from calculation.dixon_coles import (
    calculate_dc_score_distribution,
    apply_dc_correction_simple,
    estimate_league_rho
)
from calculation.nb_inverter import negative_binomial_pmf, negative_binomial_cdf
from calculation.market_fusion import cross_entropy_calibration, AdaptiveWeightFusion
from calculation.probability_calibrator import ProbabilityCalibrator, MultiClassCalibrator

logger = logging.getLogger(__name__)


class EnhancedPoissonPredictor:
    """增强版泊松预测器"""
    
    def __init__(self, use_dc: bool = True, use_market_fusion: bool = False):
        """
        Args:
            use_dc: 是否使用Dixon-Coles修正
            use_market_fusion: 是否融合市场赔率
        """
        self.db = get_connection()
        self.use_dc = use_dc
        self.use_market_fusion = use_market_fusion
        self.league_rho_cache = {}  # 缓存联赛ρ参数
    
    def round_to_2dp(self, value: float) -> float:
        """保留两位小数"""
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    
    def poisson_probability(self, lambda_val: float, k: int) -> float:
        """泊松概率"""
        if lambda_val <= 0:
            return 0.0 if k > 0 else 1.0
        try:
            prob = (math.exp(-lambda_val) * (lambda_val ** k)) / math.factorial(k)
            return self.round_to_2dp(prob)
        except (OverflowError, ValueError):
            return 0.0
    
    def get_team_stats(self, team_id: int, league_id: int, is_home: bool, 
                       recent_games: int = 8, time_decay: bool = False, 
                       half_life_days: int = 150) -> Dict:
        """
        获取球队统计(支持时间衰减)
        
        Args:
            time_decay: 是否应用时间衰减
            half_life_days: 半衰期(天)
        """
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
                match_time,
                DATEDIFF(NOW(), match_time) as days_ago
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
        
        if time_decay and half_life_days > 0:
            # 指数衰减权重: w = 2^(-days/half_life)
            total_weight = 0.0
            weighted_goals_for = 0.0
            weighted_goals_against = 0.0
            
            for match in matches:
                days = match.get('days_ago', 0) or 0
                weight = math.pow(2, -days / half_life_days)
                
                weighted_goals_for += match['goals_for'] * weight
                weighted_goals_against += match['goals_against'] * weight
                total_weight += weight
            
            if total_weight > 0:
                avg_for = weighted_goals_for / total_weight
                avg_against = weighted_goals_against / total_weight
            else:
                avg_for = sum(m['goals_for'] for m in matches) / len(matches)
                avg_against = sum(m['goals_against'] for m in matches) / len(matches)
        else:
            # 简单平均
            avg_for = sum(m['goals_for'] for m in matches) / len(matches)
            avg_against = sum(m['goals_against'] for m in matches) / len(matches)
        
        return {
            'games_played': len(matches),
            'avg_goals_for': self.round_to_2dp(avg_for),
            'avg_goals_against': self.round_to_2dp(avg_against),
            'total_goals_for': sum(m['goals_for'] for m in matches),
            'total_goals_against': sum(m['goals_against'] for m in matches)
        }
    
    def get_league_averages(self, league_id: int) -> Dict:
        """获取联赛平均"""
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
    
    def calculate_attack_defense_strength(self, team_stats: Dict, league_avg: float, 
                                         is_attack: bool, regularization: float = 0.0) -> float:
        """
        计算攻防系数(支持正则化)
        
        Args:
            regularization: 正则化强度(0-1)，0=无正则，1=完全收缩到1.0
        """
        if league_avg == 0:
            return 1.0
        
        team_avg = team_stats['avg_goals_for'] if is_attack else team_stats['avg_goals_against']
        strength = team_avg / league_avg
        
        # 正则化: 向1.0收缩
        if regularization > 0:
            strength = (1 - regularization) * strength + regularization * 1.0
        
        return self.round_to_2dp(strength)
    
    def predict_goals_expectation(self, home_team_id: int, away_team_id: int, league_id: int,
                                  time_decay: bool = False, regularization: float = 0.1) -> Dict:
        """
        预测进球期望(增强版)
        
        Args:
            time_decay: 是否应用时间衰减
            regularization: 正则化强度
        """
        home_stats = self.get_team_stats(home_team_id, league_id, is_home=True, 
                                         time_decay=time_decay)
        away_stats = self.get_team_stats(away_team_id, league_id, is_home=False, 
                                         time_decay=time_decay)
        league_stats = self.get_league_averages(league_id)
        
        # 攻防系数
        home_attack = self.calculate_attack_defense_strength(
            home_stats, league_stats['avg_home_goals'], is_attack=True, 
            regularization=regularization)
        home_defense = self.calculate_attack_defense_strength(
            home_stats, league_stats['avg_home_goals'], is_attack=False,
            regularization=regularization)
        
        away_attack = self.calculate_attack_defense_strength(
            away_stats, league_stats['avg_away_goals'], is_attack=True,
            regularization=regularization)
        away_defense = self.calculate_attack_defense_strength(
            away_stats, league_stats['avg_away_goals'], is_attack=False,
            regularization=regularization)
        
        # λ期望
        home_expected = home_attack * away_defense * league_stats['avg_home_goals']
        away_expected = away_attack * home_defense * league_stats['avg_away_goals']
        
        return {
            'home_expected_goals': self.round_to_2dp(home_expected),
            'away_expected_goals': self.round_to_2dp(away_expected),
            'total_expected_goals': self.round_to_2dp(home_expected + away_expected),
            'team_stats': {'home': home_stats, 'away': away_stats},
            'league_stats': league_stats,
            'strength_coefficients': {
                'home_attack': home_attack,
                'home_defense': home_defense,
                'away_attack': away_attack,
                'away_defense': away_defense
            }
        }
    
    def get_league_rho(self, league_id: int) -> float:
        """获取联赛DC相关系数(带缓存)"""
        if league_id not in self.league_rho_cache:
            with self.db.connection_scope() as conn:
                rho = estimate_league_rho(league_id, conn, lookback_days=180)
                self.league_rho_cache[league_id] = rho
        
        return self.league_rho_cache[league_id]
    
    def calculate_score_probabilities_enhanced(
        self, 
        home_lambda: float, 
        away_lambda: float,
        league_id: int = None,
        distribution: str = 'poisson',
        max_goals: int = 5
    ) -> Dict:
        """
        计算比分概率(支持多分布)
        
        Args:
            distribution: 'poisson', 'dc' (Dixon-Coles), 'nb' (负二项)
        """
        if distribution == 'dc' and league_id and self.use_dc:
            # Dixon-Coles修正
            rho = self.get_league_rho(league_id)
            return calculate_dc_score_distribution(home_lambda, away_lambda, rho, max_goals)
        
        elif distribution == 'nb':
            # 负二项分布(简化: 使用默认k=5)
            # 注意: 这里需要home/away分别的NB参数，暂时用泊松近似
            logger.warning("负二项分布需要独立的k参数，当前降级为泊松")
            distribution = 'poisson'
        
        # 默认: 独立泊松
        score_probs = {}
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                prob = (self.poisson_probability(home_lambda, home_goals) * 
                       self.poisson_probability(away_lambda, away_goals))
                score_probs[f"{home_goals}-{away_goals}"] = self.round_to_2dp(prob)
        
        # 计算总进球
        total_goals_dist = {}
        for total in range(2 * max_goals + 1):
            prob = 0.0
            for h in range(min(total + 1, max_goals + 1)):
                a = total - h
                if 0 <= a <= max_goals:
                    prob += score_probs.get(f"{h}-{a}", 0)
            total_goals_dist[total] = prob
        
        p_le3 = sum(total_goals_dist.get(s, 0) for s in range(4))  # ≤3球
        p_gt3 = sum(total_goals_dist.get(s, 0) for s in range(4, 2*max_goals + 1))  # >3球
        
        # 胜平负
        home_win = sum(score_probs.get(f"{h}-{a}", 0) 
                      for h in range(max_goals + 1) 
                      for a in range(h))
        draw = sum(score_probs.get(f"{x}-{x}", 0) for x in range(max_goals + 1))
        away_win = 1 - home_win - draw
        
        return {
            'score_probabilities': score_probs,
            'outcomes': {
                'home_win': self.round_to_2dp(home_win),
                'draw': self.round_to_2dp(draw),
                'away_win': self.round_to_2dp(away_win)
            },
            'total_goals': {
                'le3': self.round_to_2dp(p_le3),  # ≤3球
                'gt3': self.round_to_2dp(p_gt3)   # >3球
            },
            'distribution_type': distribution
        }
    
    def predict_match_enhanced(
        self,
        home_team_id: int,
        away_team_id: int,
        league_id: int,
        distribution: str = 'dc',
        time_decay: bool = True,
        regularization: float = 0.1,
        market_calibration: Optional[Dict] = None
    ) -> Dict:
        """
        完整增强预测
        
        Args:
            distribution: 'poisson', 'dc'
            time_decay: 是否时间衰减
            regularization: 正则化强度
            market_calibration: 可选的市场校准数据 {'p_ge3': x, 'p_ge4': y}
        """
        try:
            # 1. 计算基础λ
            prediction_base = self.predict_goals_expectation(
                home_team_id, away_team_id, league_id,
                time_decay=time_decay, regularization=regularization
            )
            
            home_lambda = prediction_base['home_expected_goals']
            away_lambda = prediction_base['away_expected_goals']
            
            # 2. 市场校准(如果提供)
            if market_calibration and self.use_market_fusion:
                p_market_ge3 = market_calibration.get('p_ge3')
                p_market_ge4 = market_calibration.get('p_ge4')
                
                if p_market_ge3 and p_market_ge4:
                    cal_result = cross_entropy_calibration(
                        home_lambda, away_lambda,
                        p_market_ge3, p_market_ge4
                    )
                    home_lambda = cal_result['lambda_h_calibrated']
                    away_lambda = cal_result['lambda_a_calibrated']
                    calibration_info = cal_result
                else:
                    calibration_info = None
            else:
                calibration_info = None
            
            # 3. 计算比分分布
            score_dist = self.calculate_score_probabilities_enhanced(
                home_lambda, away_lambda, league_id, distribution
            )
            
            # 4. 最可能比分
            scores_sorted = sorted(score_dist['score_probabilities'].items(), 
                                  key=lambda x: x[1], reverse=True)
            most_likely = scores_sorted[0] if scores_sorted else ('0-0', 0)
            
            return {
                'prediction_summary': {
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id,
                    'league_id': league_id,
                    'home_expected_goals': home_lambda,
                    'away_expected_goals': away_lambda,
                    'total_expected_goals': self.round_to_2dp(home_lambda + away_lambda),
                    'most_likely_score': most_likely[0],
                    'most_likely_prob': most_likely[1],
                    'distribution': distribution
                },
                'score_probabilities': score_dist['score_probabilities'],
                'outcomes': score_dist['outcomes'],
                'total_goals_probabilities': score_dist['total_goals'],
                'base_data': prediction_base,
                'market_calibration': calibration_info,
                'model_config': {
                    'use_dc': self.use_dc,
                    'time_decay': time_decay,
                    'regularization': regularization,
                    'distribution': distribution
                }
            }
        
        except Exception as e:
            logger.error(f"预测失败: {e}", exc_info=True)
            return {'error': str(e)}


def predict_match_enhanced(
    home_team_id: int,
    away_team_id: int,
    league_id: int,
    use_dc: bool = True,
    time_decay: bool = True,
    market_data: Optional[Dict] = None
) -> Dict:
    """快速预测接口"""
    predictor = EnhancedPoissonPredictor(use_dc=use_dc, use_market_fusion=bool(market_data))
    
    distribution = 'dc' if use_dc else 'poisson'
    
    return predictor.predict_match_enhanced(
        home_team_id, away_team_id, league_id,
        distribution=distribution,
        time_decay=time_decay,
        market_calibration=market_data
    )


if __name__ == "__main__":
    import json
    
    print("=== 增强版泊松预测测试 ===\n")
    
    test_home, test_away, test_league = 207, 193, 25
    
    # 测试1: 基础预测(DC修正)
    print("测试1: Dixon-Coles修正预测")
    result_dc = predict_match_enhanced(test_home, test_away, test_league, use_dc=True)
    
    if 'error' not in result_dc:
        summary = result_dc['prediction_summary']
        print(f"λ_h={summary['home_expected_goals']}, λ_a={summary['away_expected_goals']}")
        print(f"最可能比分: {summary['most_likely_score']} ({summary['most_likely_prob']:.4f})")
        total_goals = result_dc.get('total_goals_probabilities') or result_dc.get('total_goals', {})
        print(f"大小球: P(≤3)={total_goals.get('le3', 0):.4f}, "
              f"P(>3)={total_goals.get('gt3', 0):.4f}")
    
    # 测试2: 市场融合
    print("\n测试2: 市场融合预测")
    market_data = {'p_ge3': 0.55, 'p_ge4': 0.35}
    result_fusion = predict_match_enhanced(
        test_home, test_away, test_league,
        use_dc=True, market_data=market_data
    )
    
    if 'error' not in result_fusion and result_fusion.get('market_calibration'):
        cal = result_fusion['market_calibration']
        print(f"原始λ: ({cal['model_original']['lambda_h']}, {cal['model_original']['lambda_a']})")
        print(f"校准λ: ({cal['lambda_h_calibrated']}, {cal['lambda_a_calibrated']})")
        print(f"市场目标P(≥3)={cal['market_target']['p_ge3']:.4f}, "
              f"校准后={cal['p_ge3_calibrated']:.4f}")


