"""
负二项分布反演模块
从两条大小球盘口联合拟合(μ,k)参数，精确估计P(S=3)等关键概率
"""

import math
from typing import Dict, Optional, Tuple
from scipy.optimize import minimize
from scipy.stats import nbinom
import numpy as np
import logging

logger = logging.getLogger(__name__)


def negative_binomial_pmf(k_goals: int, mu: float, size: float) -> float:
    """
    负二项分布概率质量函数
    参数化: 均值mu, 离散度参数size (k)
    p = size/(size+mu)
    """
    if mu <= 0 or size <= 0:
        return 0.0
    p = size / (size + mu)
    return nbinom.pmf(k_goals, size, p)


def negative_binomial_cdf(k_goals: int, mu: float, size: float) -> float:
    """负二项分布累积分布函数"""
    if mu <= 0 or size <= 0:
        return 0.0
    p = size / (size + mu)
    return nbinom.cdf(k_goals, size, p)


def infer_nb_from_two_lines(
    p_over25: float, 
    p_over35: float,
    mu_bounds: Tuple[float, float] = (0.5, 6.0),
    k_bounds: Tuple[float, float] = (0.2, 50.0)
) -> Dict:
    """
    从2.5和3.5两条盘口的去水概率联合反演(μ,k)
    
    Args:
        p_over25: 大2.5的去水概率 P(S>=3)
        p_over35: 大3.5的去水概率 P(S>=4)
        mu_bounds: μ的搜索范围
        k_bounds: k的搜索范围
    
    Returns:
        包含mu, k, p_ge3, p_eq3, p_ge4等关键概率的字典
    """
    # 初值启发式: 用泊松近似给个mu0
    mu0 = 2.6 + 0.8 * (p_over25 - 0.5)
    mu0 = max(mu_bounds[0], min(mu_bounds[1], mu0))
    k0 = 5.0  # 默认离散度
    
    def loss(theta):
        mu, k = theta
        if mu <= 0 or k <= 0:
            return 1e10
        try:
            p = k / (k + mu)
            pge3 = 1 - nbinom.cdf(2, k, p)  # P(S>=3)
            pge4 = 1 - nbinom.cdf(3, k, p)  # P(S>=4)
            return (pge3 - p_over25)**2 + (pge4 - p_over35)**2
        except:
            return 1e10
    
    # 多起点优化以避免局部最优
    best_result = None
    best_loss = float('inf')
    
    for mu_init in [mu0, 2.0, 2.5, 3.0]:
        for k_init in [k0, 2.0, 10.0]:
            try:
                result = minimize(
                    loss, 
                    x0=(mu_init, k_init), 
                    bounds=[mu_bounds, k_bounds], 
                    method='L-BFGS-B'
                )
                if result.fun < best_loss:
                    best_loss = result.fun
                    best_result = result
            except:
                continue
    
    if best_result is None:
        # 降级到泊松
        logger.warning("NB拟合失败，降级到泊松分布")
        return fallback_to_poisson(p_over25)
    
    mu, k = best_result.x
    p = k / (k + mu)
    
    # 计算关键概率
    p_ge3 = 1 - nbinom.cdf(2, k, p)  # P(S>=3)
    p_ge4 = 1 - nbinom.cdf(3, k, p)  # P(S>=4)
    p_eq3 = p_ge3 - p_ge4              # P(S=3) - 关键！
    p_le2 = nbinom.cdf(2, k, p)        # P(S<=2)
    
    # 计算各进球数概率(0-7)
    probs_0_7 = [negative_binomial_pmf(i, mu, k) for i in range(8)]
    
    return {
        'mu': round(mu, 4),
        'k': round(k, 4),
        'p_ge3': round(p_ge3, 6),
        'p_eq3': round(p_eq3, 6),  # 3.0盘口的关键概率
        'p_ge4': round(p_ge4, 6),
        'p_le2': round(p_le2, 6),
        'distribution_type': 'negative_binomial',
        'fit_loss': round(best_loss, 8),
        'P0': round(probs_0_7[0], 6),
        'P1': round(probs_0_7[1], 6),
        'P2': round(probs_0_7[2], 6),
        'P3': round(probs_0_7[3], 6),
        'P4': round(probs_0_7[4], 6),
        'P5': round(probs_0_7[5], 6),
        'P6': round(probs_0_7[6], 6),
        'P7': round(probs_0_7[7], 6),
    }


def infer_nb_from_single_line(
    line: float,
    p_over: float,
    league_k_prior: float = 5.0
) -> Dict:
    """
    从单条盘口反演，k使用联赛先验
    
    Args:
        line: 盘口线(如2.5)
        p_over: 大球去水概率
        league_k_prior: 联赛级别的k先验
    """
    # 固定k，只求mu
    k = league_k_prior
    threshold = int(line + 0.5)  # 2.5->3, 3.5->4
    
    def loss(mu):
        if mu <= 0:
            return 1e10
        try:
            p = k / (k + mu)
            pge = 1 - nbinom.cdf(threshold - 1, k, p)
            return (pge - p_over)**2
        except:
            return 1e10
    
    result = minimize(loss, x0=2.5, bounds=[(0.5, 6.0)], method='L-BFGS-B')
    mu = result.x[0]
    p = k / (k + mu)
    
    # 计算概率
    p_ge3 = 1 - nbinom.cdf(2, k, p)
    p_ge4 = 1 - nbinom.cdf(3, k, p)
    p_eq3 = p_ge3 - p_ge4
    
    probs_0_7 = [negative_binomial_pmf(i, mu, k) for i in range(8)]
    
    return {
        'mu': round(mu, 4),
        'k': round(k, 4),
        'k_source': 'league_prior',
        'p_ge3': round(p_ge3, 6),
        'p_eq3': round(p_eq3, 6),
        'p_ge4': round(p_ge4, 6),
        'distribution_type': 'negative_binomial',
        'P0': round(probs_0_7[0], 6),
        'P1': round(probs_0_7[1], 6),
        'P2': round(probs_0_7[2], 6),
        'P3': round(probs_0_7[3], 6),
        'P4': round(probs_0_7[4], 6),
        'P5': round(probs_0_7[5], 6),
        'P6': round(probs_0_7[6], 6),
        'P7': round(probs_0_7[7], 6),
    }


def fallback_to_poisson(p_over25: float) -> Dict:
    """降级到泊松分布的回退方案"""
    from scipy.stats import poisson
    
    # 简单二分搜索找到mu
    def find_mu(p_target):
        lo, hi = 0.5, 6.0
        for _ in range(100):
            mid = (lo + hi) / 2
            p_calc = 1 - poisson.cdf(2, mid)
            if p_calc > p_target:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2
    
    mu = find_mu(p_over25)
    
    p_ge3 = 1 - poisson.cdf(2, mu)
    p_ge4 = 1 - poisson.cdf(3, mu)
    p_eq3 = p_ge3 - p_ge4
    
    probs_0_7 = [poisson.pmf(i, mu) for i in range(8)]
    
    return {
        'mu': round(mu, 4),
        'k': None,
        'p_ge3': round(p_ge3, 6),
        'p_eq3': round(p_eq3, 6),
        'p_ge4': round(p_ge4, 6),
        'distribution_type': 'poisson',
        'P0': round(probs_0_7[0], 6),
        'P1': round(probs_0_7[1], 6),
        'P2': round(probs_0_7[2], 6),
        'P3': round(probs_0_7[3], 6),
        'P4': round(probs_0_7[4], 6),
        'P5': round(probs_0_7[5], 6),
        'P6': round(probs_0_7[6], 6),
        'P7': round(probs_0_7[7], 6),
    }


def robust_consensus(
    records: list,
    trim_pct: float = 0.15,
    margin_weight: bool = True
) -> Tuple[float, float]:
    """
    鲁棒的赔率共识聚合
    
    Args:
        records: 包含over/under赔率的记录列表
        trim_pct: 截尾比例(去掉极端值)
        margin_weight: 是否按水位倒数加权
    
    Returns:
        (p_over_consensus, margin_avg)
    """
    if not records:
        return None, None
    
    # 计算去水概率和margin
    processed = []
    for rec in records:
        over_odds = rec.get('over_odds')
        under_odds = rec.get('under_odds')
        
        if over_odds and under_odds and over_odds > 1.0 and under_odds > 1.0:
            margin = (1/over_odds + 1/under_odds - 1)
            p_over_raw = 1 / over_odds
            p_under_raw = 1 / under_odds
            # 去水
            p_over = p_over_raw / (p_over_raw + p_under_raw)
            
            processed.append({
                'p_over': p_over,
                'margin': margin,
                'weight': 1/(margin + 0.01) if margin_weight else 1.0
            })
    
    if not processed:
        return None, None
    
    # 按p_over排序并截尾
    processed.sort(key=lambda x: x['p_over'])
    n = len(processed)
    trim_count = int(n * trim_pct)
    
    if n > 4:
        trimmed = processed[trim_count:n-trim_count]
    else:
        trimmed = processed
    
    # 加权平均
    total_weight = sum(r['weight'] for r in trimmed)
    p_over_consensus = sum(r['p_over'] * r['weight'] for r in trimmed) / total_weight
    margin_avg = sum(r['margin'] for r in processed) / len(processed)
    
    return p_over_consensus, margin_avg


if __name__ == "__main__":
    # 测试用例
    print("=== 负二项反演模块测试 ===\n")
    
    # 测试1: 从两条盘口反演
    print("测试1: 从2.5(55%)和3.5(35%)反演")
    result1 = infer_nb_from_two_lines(0.55, 0.35)
    print(f"μ={result1['mu']}, k={result1['k']}")
    print(f"P(S>=3)={result1['p_ge3']:.4f}, P(S=3)={result1['p_eq3']:.4f}, P(S>=4)={result1['p_ge4']:.4f}")
    print(f"拟合误差: {result1['fit_loss']:.8f}\n")
    
    # 测试2: 单盘口降级
    print("测试2: 从单盘2.5(50%)反演(使用先验k=5)")
    result2 = infer_nb_from_single_line(2.5, 0.50, league_k_prior=5.0)
    print(f"μ={result2['mu']}, k={result2['k']} (先验)")
    print(f"P(S=3)={result2['p_eq3']:.4f}\n")
    
    # 测试3: 鲁棒共识
    print("测试3: 鲁棒赔率共识")
    test_records = [
        {'over_odds': 1.90, 'under_odds': 1.95},
        {'over_odds': 1.85, 'under_odds': 2.00},
        {'over_odds': 1.88, 'under_odds': 1.97},
        {'over_odds': 2.10, 'under_odds': 1.75},  # 异常值
    ]
    p_consensus, margin = robust_consensus(test_records, trim_pct=0.15)
    print(f"共识概率: {p_consensus:.4f}, 平均水位: {margin:.4f}")







