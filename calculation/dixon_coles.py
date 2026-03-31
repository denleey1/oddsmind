"""
Dixon-Coles 低比分修正模块
修正独立泊松模型在0-0, 1-0, 0-1, 1-1四个比分上的偏差
"""

import math
from typing import Dict, List, Tuple, Optional
from scipy.optimize import minimize
from scipy.stats import poisson
import numpy as np
import logging

logger = logging.getLogger(__name__)


def tau_dc(home_goals: int, away_goals: int, rho: float, lambda_h: float, lambda_a: float) -> float:
    """
    Dixon-Coles 修正因子
    
    对低比分(0-0, 1-0, 0-1, 1-1)应用修正，其他比分返回1.0
    
    Args:
        home_goals: 主队进球数
        away_goals: 客队进球数
        rho: 相关性参数(典型范围-0.2到0.2)
        lambda_h: 主队进球期望
        lambda_a: 客队进球期望
    
    Returns:
        修正因子τ
    """
    if home_goals == 0 and away_goals == 0:
        return 1 - lambda_h * lambda_a * rho
    elif home_goals == 1 and away_goals == 0:
        return 1 + lambda_a * rho
    elif home_goals == 0 and away_goals == 1:
        return 1 + lambda_h * rho
    elif home_goals == 1 and away_goals == 1:
        return 1 - rho
    else:
        return 1.0


def dc_probability(home_goals: int, away_goals: int, lambda_h: float, lambda_a: float, rho: float) -> float:
    """
    计算Dixon-Coles修正后的比分概率
    
    P_DC(x,y) = P_Poisson(x,y) * τ(x,y; ρ, λ_h, λ_a)
    """
    # 基础泊松概率
    p_base = poisson.pmf(home_goals, lambda_h) * poisson.pmf(away_goals, lambda_a)
    
    # 应用DC修正
    tau = tau_dc(home_goals, away_goals, rho, lambda_h, lambda_a)
    
    return p_base * tau


def estimate_rho_from_matches(matches: List[Dict], lambda_h_dict: Dict, lambda_a_dict: Dict) -> float:
    """
    从历史比赛数据估计ρ参数
    
    Args:
        matches: 比赛列表，每项包含 {'home_team', 'away_team', 'home_score', 'away_score'}
        lambda_h_dict: {team: 主场进球期望} 字典
        lambda_a_dict: {team: 客场进球期望} 字典
    
    Returns:
        估计的ρ值
    """
    def neg_log_likelihood(rho_array):
        rho = rho_array[0]
        nll = 0.0
        
        for match in matches:
            home_team = match['home_team']
            away_team = match['away_team']
            home_score = match['home_score']
            away_score = match['away_score']
            
            lambda_h = lambda_h_dict.get(home_team, 1.5)
            lambda_a = lambda_a_dict.get(away_team, 1.2)
            
            # DC概率
            p = dc_probability(home_score, away_score, lambda_h, lambda_a, rho)
            
            if p > 0:
                nll -= math.log(p)
            else:
                nll += 100  # 惩罚
        
        return nll
    
    # 优化求ρ (典型范围-0.2到0.2)
    result = minimize(neg_log_likelihood, x0=[0.0], bounds=[(-0.3, 0.3)], method='L-BFGS-B')
    
    return result.x[0]


def calculate_dc_score_distribution(
    lambda_h: float, 
    lambda_a: float, 
    rho: float = 0.0, 
    max_goals: int = 5
) -> Dict:
    """
    计算DC修正后的比分分布
    
    Args:
        lambda_h: 主队进球期望
        lambda_a: 客队进球期望
        rho: DC相关性参数
        max_goals: 最大进球数
    
    Returns:
        包含比分概率、结果概率、大小球概率等的字典
    """
    # 计算所有比分概率
    score_probs = {}
    total_prob = 0.0
    
    for h in range(max_goals + 1):
        for a in range(max_goals + 1):
            prob = dc_probability(h, a, lambda_h, lambda_a, rho)
            score_probs[f"{h}-{a}"] = prob
            total_prob += prob
    
    # 归一化(处理截断误差)
    if total_prob > 0:
        score_probs = {k: v/total_prob for k, v in score_probs.items()}
    
    # 计算胜平负概率
    home_win = sum(score_probs.get(f"{h}-{a}", 0) 
                   for h in range(max_goals + 1) 
                   for a in range(h))
    draw = sum(score_probs.get(f"{x}-{x}", 0) for x in range(max_goals + 1))
    away_win = sum(score_probs.get(f"{h}-{a}", 0) 
                   for h in range(max_goals + 1) 
                   for a in range(h + 1, max_goals + 1))
    
    # 计算总进球分布 P(S=s)
    total_goals_dist = {}
    for total in range(2 * max_goals + 1):
        prob = 0.0
        for h in range(min(total + 1, max_goals + 1)):
            a = total - h
            if 0 <= a <= max_goals:
                prob += score_probs.get(f"{h}-{a}", 0)
        total_goals_dist[total] = prob
    
    # 关键大小球概率
    p_le3 = sum(total_goals_dist.get(s, 0) for s in range(4))  # ≤3球
    p_gt3 = sum(total_goals_dist.get(s, 0) for s in range(4, 2 * max_goals + 1))  # >3球
    
    # 最可能比分
    most_likely_score = max(score_probs.items(), key=lambda x: x[1])
    
    return {
        'score_probabilities': score_probs,
        'outcomes': {
            'home_win': round(home_win, 6),
            'draw': round(draw, 6),
            'away_win': round(away_win, 6)
        },
        'total_goals': {
            'le3': round(p_le3, 6),  # ≤3球
            'gt3': round(p_gt3, 6),  # >3球
        },
        'most_likely_score': most_likely_score[0],
        'most_likely_prob': round(most_likely_score[1], 6),
        'rho': round(rho, 6),
        'lambda_h': round(lambda_h, 4),
        'lambda_a': round(lambda_a, 4),
    }


def apply_dc_correction_simple(
    poisson_dist: Dict,
    lambda_h: float,
    lambda_a: float,
    league_rho: float = -0.13
) -> Dict:
    """
    对已有的泊松分布应用DC修正(简化版)
    
    适用于预测阶段，使用联赛级别的ρ先验
    
    Args:
        poisson_dist: 泊松分布概率字典 {'0-0': prob, '1-0': prob, ...}
        lambda_h: 主队λ
        lambda_a: 客队λ  
        league_rho: 联赛级别的ρ先验(默认-0.13，表示低比分略被高估)
    
    Returns:
        DC修正后的分布
    """
    corrected = {}
    
    for score, p_poisson in poisson_dist.items():
        try:
            h, a = map(int, score.split('-'))
            tau = tau_dc(h, a, league_rho, lambda_h, lambda_a)
            corrected[score] = p_poisson * tau
        except:
            corrected[score] = p_poisson
    
    # 归一化
    total = sum(corrected.values())
    if total > 0:
        corrected = {k: v/total for k, v in corrected.items()}
    
    return corrected


def estimate_league_rho(league_id: int, connection, lookback_days: int = 180) -> float:
    """
    估计联赛级别的ρ参数
    
    从数据库读取历史数据，使用简化方法估计
    """
    from datetime import datetime, timedelta
    
    cutoff_date = datetime.now() - timedelta(days=lookback_days)
    
    with connection.cursor() as cursor:
        query = """
        SELECT home_team_name, away_team_name, home_score, away_score
        FROM matches
        WHERE league_id = %s 
          AND match_status = 'finished'
          AND match_time >= %s
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        """
        cursor.execute(query, (league_id, cutoff_date))
        matches = cursor.fetchall()
    
    if len(matches) < 30:
        logger.warning(f"联赛{league_id}历史数据不足，使用默认ρ=-0.13")
        return -0.13
    
    # 简化估计: 比较低比分的观察频率与泊松期望
    # 统计0-0, 1-0, 0-1, 1-1的观察频率
    low_score_counts = {(0,0): 0, (1,0): 0, (0,1): 0, (1,1): 0}
    total = len(matches)
    
    # 计算联赛平均λ
    avg_home = sum(m['home_score'] for m in matches) / total
    avg_away = sum(m['away_score'] for m in matches) / total
    
    for m in matches:
        key = (m['home_score'], m['away_score'])
        if key in low_score_counts:
            low_score_counts[key] += 1
    
    # 计算ρ的简化估计
    # 0-0的观察频率与泊松期望之比
    obs_00 = low_score_counts[(0,0)] / total
    exp_00 = math.exp(-avg_home) * math.exp(-avg_away)
    
    if exp_00 > 0:
        # ρ ≈ (obs/exp - 1) / (λ_h * λ_a)
        rho_est = (obs_00 / exp_00 - 1) / (avg_home * avg_away) if avg_home * avg_away > 0 else -0.13
        rho_est = max(-0.3, min(0.2, rho_est))  # 限制范围
    else:
        rho_est = -0.13
    
    logger.info(f"联赛{league_id} 估计ρ={rho_est:.4f} (基于{total}场比赛)")
    
    return rho_est


if __name__ == "__main__":
    print("=== Dixon-Coles 修正模块测试 ===\n")
    
    # 测试1: DC概率计算
    lambda_h, lambda_a, rho = 1.5, 1.2, -0.13
    
    print(f"测试1: λ_h={lambda_h}, λ_a={lambda_a}, ρ={rho}")
    print("低比分概率 (泊松 vs DC):\n")
    
    for h, a in [(0,0), (1,0), (0,1), (1,1)]:
        p_poisson = poisson.pmf(h, lambda_h) * poisson.pmf(a, lambda_a)
        p_dc = dc_probability(h, a, lambda_h, lambda_a, rho)
        tau = tau_dc(h, a, rho, lambda_h, lambda_a)
        print(f"{h}-{a}: 泊松={p_poisson:.6f}, DC={p_dc:.6f}, τ={tau:.4f}")
    
    # 测试2: 完整分布
    print("\n测试2: 完整DC分布")
    dist = calculate_dc_score_distribution(lambda_h, lambda_a, rho, max_goals=5)
    
    print(f"\n胜平负: 主胜={dist['outcomes']['home_win']:.4f}, "
          f"平={dist['outcomes']['draw']:.4f}, "
          f"客胜={dist['outcomes']['away_win']:.4f}")
    
    print(f"\n大小球关键概率:")
    print(f"P(S≤3) = {dist['total_goals']['le3']:.4f}  <- 小于等于3球")
    print(f"P(S>3) = {dist['total_goals']['gt3']:.4f}  <- 大于3球")
    
    print(f"\n最可能比分: {dist['most_likely_score']} (概率={dist['most_likely_prob']:.4f})")


