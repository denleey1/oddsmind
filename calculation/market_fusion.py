"""
市场融合模块
实现模型预测与市场赔率的融合，包括交叉熵校准和自适应权重
"""

import math
import numpy as np
from typing import Dict, List, Tuple, Optional
from scipy.optimize import minimize
from collections import deque
import logging

logger = logging.getLogger(__name__)


def cross_entropy_calibration(
    lambda_h_model: float,
    lambda_a_model: float,
    p_market_ge3: float,
    p_market_ge4: float,
    bounds: Tuple[float, float] = (0.5, 2.0)
) -> Dict:
    """
    交叉熵校准: 调整λ使模型概率与市场概率对齐
    
    最小化: CE = -[p1*log(q1) + (1-p1)*log(1-q1) + p2*log(q2) + (1-p2)*log(1-q2)]
    其中 p1, p2 是市场概率, q1, q2 是调整后的模型概率
    
    Args:
        lambda_h_model: 模型预测的主队λ
        lambda_a_model: 模型预测的客队λ
        p_market_ge3: 市场去水后的P(S≥3)
        p_market_ge4: 市场去水后的P(S≥4)
        bounds: 缩放因子的边界
    
    Returns:
        包含调整后λ和概率的字典
    """
    from scipy.stats import poisson
    
    def calculate_probs(alpha, beta):
        """计算调整后的λ对应的概率"""
        lh = alpha * lambda_h_model
        la = beta * lambda_a_model
        total_lambda = lh + la
        
        # P(S>=3) = 1 - P(S<=2)
        q_ge3 = 1 - poisson.cdf(2, total_lambda)
        q_ge4 = 1 - poisson.cdf(3, total_lambda)
        
        return q_ge3, q_ge4
    
    def cross_entropy_loss(params):
        alpha, beta = params
        
        if alpha <= 0 or beta <= 0:
            return 1e10
        
        try:
            q_ge3, q_ge4 = calculate_probs(alpha, beta)
            
            # 避免log(0)
            q_ge3 = np.clip(q_ge3, 1e-10, 1 - 1e-10)
            q_ge4 = np.clip(q_ge4, 1e-10, 1 - 1e-10)
            
            # 交叉熵
            ce = -(p_market_ge3 * np.log(q_ge3) + (1 - p_market_ge3) * np.log(1 - q_ge3) +
                   p_market_ge4 * np.log(q_ge4) + (1 - p_market_ge4) * np.log(1 - q_ge4))
            
            return ce
        except:
            return 1e10
    
    # 优化
    result = minimize(
        cross_entropy_loss,
        x0=[1.0, 1.0],
        bounds=[bounds, bounds],
        method='L-BFGS-B'
    )
    
    alpha_opt, beta_opt = result.x
    lambda_h_cal = alpha_opt * lambda_h_model
    lambda_a_cal = beta_opt * lambda_a_model
    
    q_ge3, q_ge4 = calculate_probs(alpha_opt, beta_opt)
    
    return {
        'lambda_h_calibrated': round(lambda_h_cal, 4),
        'lambda_a_calibrated': round(lambda_a_cal, 4),
        'alpha': round(alpha_opt, 4),
        'beta': round(beta_opt, 4),
        'p_ge3_calibrated': round(q_ge3, 6),
        'p_ge4_calibrated': round(q_ge4, 6),
        'ce_loss': round(result.fun, 6),
        'model_original': {
            'lambda_h': lambda_h_model,
            'lambda_a': lambda_a_model
        },
        'market_target': {
            'p_ge3': p_market_ge3,
            'p_ge4': p_market_ge4
        }
    }


class AdaptiveWeightFusion:
    """自适应权重融合器"""
    
    def __init__(self, window_size: int = 50, initial_weight: float = 0.5):
        """
        Args:
            window_size: 滚动窗口大小(用于计算性能)
            initial_weight: 初始模型权重
        """
        self.window_size = window_size
        self.model_weight = initial_weight
        
        # 历史记录: (model_prob, market_prob, actual)
        self.history_ge3 = deque(maxlen=window_size)
        self.history_ge4 = deque(maxlen=window_size)
    
    def update(self, model_probs: Dict, market_probs: Dict, actual_goals: int):
        """
        更新历史记录
        
        Args:
            model_probs: {'p_ge3': x, 'p_ge4': y}
            market_probs: {'p_ge3': x, 'p_ge4': y}
            actual_goals: 实际总进球数
        """
        actual_ge3 = 1 if actual_goals >= 3 else 0
        actual_ge4 = 1 if actual_goals >= 4 else 0
        
        self.history_ge3.append({
            'model': model_probs.get('p_ge3', 0),
            'market': market_probs.get('p_ge3', 0),
            'actual': actual_ge3
        })
        
        self.history_ge4.append({
            'model': model_probs.get('p_ge4', 0),
            'market': market_probs.get('p_ge4', 0),
            'actual': actual_ge4
        })
    
    def calculate_log_loss(self, predictions: List[Dict], key: str) -> float:
        """计算log loss"""
        if not predictions:
            return float('inf')
        
        loss = 0.0
        for pred in predictions:
            p = np.clip(pred[key], 1e-10, 1 - 1e-10)
            loss -= pred['actual'] * np.log(p) + (1 - pred['actual']) * np.log(1 - p)
        
        return loss / len(predictions)
    
    def update_weight(self) -> float:
        """
        根据历史表现更新模型权重
        
        Returns:
            更新后的模型权重
        """
        if len(self.history_ge3) < 20:  # 样本不足，保持初始权重
            return self.model_weight
        
        # 计算模型和市场的log loss
        model_loss_ge3 = self.calculate_log_loss(list(self.history_ge3), 'model')
        market_loss_ge3 = self.calculate_log_loss(list(self.history_ge3), 'market')
        
        model_loss_ge4 = self.calculate_log_loss(list(self.history_ge4), 'model')
        market_loss_ge4 = self.calculate_log_loss(list(self.history_ge4), 'market')
        
        # 综合两个指标
        model_loss_avg = (model_loss_ge3 + model_loss_ge4) / 2
        market_loss_avg = (market_loss_ge3 + market_loss_ge4) / 2
        
        # 使用softmax归一化来计算权重
        # 损失越低，权重越高
        total = np.exp(-model_loss_avg) + np.exp(-market_loss_avg)
        new_weight = np.exp(-model_loss_avg) / total
        
        # 平滑更新(避免剧烈波动)
        self.model_weight = 0.7 * self.model_weight + 0.3 * new_weight
        
        logger.info(f"权重更新: 模型={self.model_weight:.3f}, 市场={1-self.model_weight:.3f} "
                   f"(模型loss={model_loss_avg:.4f}, 市场loss={market_loss_avg:.4f})")
        
        return self.model_weight
    
    def fuse(self, model_probs: Dict, market_probs: Dict) -> Dict:
        """
        融合模型和市场概率
        
        Args:
            model_probs: 模型预测概率
            market_probs: 市场隐含概率
        
        Returns:
            融合后的概率
        """
        w = self.model_weight
        
        fused = {}
        for key in ['p_ge3', 'p_ge4', 'p_eq3', 'p_le2']:
            if key in model_probs and key in market_probs:
                fused[key] = w * model_probs[key] + (1 - w) * market_probs[key]
            elif key in model_probs:
                fused[key] = model_probs[key]
            elif key in market_probs:
                fused[key] = market_probs[key]
        
        return {
            'probabilities': fused,
            'model_weight': round(w, 4),
            'market_weight': round(1 - w, 4),
            'model_probs': model_probs,
            'market_probs': market_probs
        }


def betting_threshold_strategy(
    p_model: float,
    p_market: float,
    threshold: float = 0.05,
    min_edge: float = 0.02
) -> Dict:
    """
    基于概率差异的下注策略
    
    Args:
        p_model: 模型预测概率
        p_market: 市场隐含概率
        threshold: 最小差异阈值(绝对值)
        min_edge: 最小优势(EV正向要求)
    
    Returns:
        下注建议
    """
    diff = p_model - p_market
    abs_diff = abs(diff)
    
    # 计算期望值(假设1单位投注)
    if diff > 0:  # 模型认为大球概率更高
        odds_implied = 1 / p_market if p_market > 0 else 999
        ev = p_model * (odds_implied - 1) - (1 - p_model)
    else:  # 模型认为小球概率更高
        p_under_market = 1 - p_market
        odds_under = 1 / p_under_market if p_under_market > 0 else 999
        p_under_model = 1 - p_model
        ev = p_under_model * (odds_under - 1) - (1 - p_under_model)
    
    # 决策
    should_bet = abs_diff >= threshold and ev >= min_edge
    
    return {
        'should_bet': should_bet,
        'direction': 'over' if diff > 0 else 'under',
        'probability_diff': round(diff, 6),
        'abs_diff': round(abs_diff, 6),
        'expected_value': round(ev, 6),
        'confidence': 'high' if abs_diff >= 2 * threshold else 'medium' if abs_diff >= threshold else 'low'
    }


def kelly_criterion(
    prob: float,
    odds: float,
    fraction: float = 0.25,
    max_stake: float = 0.05
) -> float:
    """
    凯利准则计算下注比例
    
    Args:
        prob: 预测概率
        odds: 赔率(欧洲盘)
        fraction: 凯利分数(保守起见用1/4或1/8)
        max_stake: 最大下注比例
    
    Returns:
        建议下注比例(相对于总资金)
    """
    if prob <= 0 or odds <= 1:
        return 0.0
    
    # 凯利公式: f = (bp - q) / b
    # 其中 b = odds - 1, p = prob, q = 1 - prob
    b = odds - 1
    kelly_full = (b * prob - (1 - prob)) / b
    
    # 应用分数和最大值限制
    kelly_fractional = max(0, kelly_full * fraction)
    kelly_final = min(kelly_fractional, max_stake)
    
    return round(kelly_final, 4)


if __name__ == "__main__":
    print("=== 市场融合模块测试 ===\n")
    
    # 测试1: 交叉熵校准
    print("测试1: 交叉熵校准\n")
    
    lambda_h, lambda_a = 1.5, 1.3
    p_market_ge3, p_market_ge4 = 0.55, 0.35
    
    result = cross_entropy_calibration(lambda_h, lambda_a, p_market_ge3, p_market_ge4)
    
    print(f"原始模型: λ_h={result['model_original']['lambda_h']}, λ_a={result['model_original']['lambda_a']}")
    print(f"校准后:   λ_h={result['lambda_h_calibrated']}, λ_a={result['lambda_a_calibrated']}")
    print(f"缩放因子: α={result['alpha']}, β={result['beta']}")
    print(f"\n市场目标: P(≥3)={result['market_target']['p_ge3']:.4f}, P(≥4)={result['market_target']['p_ge4']:.4f}")
    print(f"校准结果: P(≥3)={result['p_ge3_calibrated']:.4f}, P(≥4)={result['p_ge4_calibrated']:.4f}")
    print(f"交叉熵损失: {result['ce_loss']:.6f}")
    
    # 测试2: 自适应权重融合
    print("\n\n测试2: 自适应权重融合\n")
    
    fusion = AdaptiveWeightFusion(window_size=50, initial_weight=0.5)
    
    # 模拟一系列预测
    np.random.seed(42)
    for i in range(60):
        # 模拟模型和市场预测
        true_prob = 0.5
        model_prob = true_prob + np.random.normal(0, 0.1)
        market_prob = true_prob + np.random.normal(0, 0.08)  # 市场略准一些
        
        model_prob = np.clip(model_prob, 0.1, 0.9)
        market_prob = np.clip(market_prob, 0.1, 0.9)
        
        # 实际结果
        actual = np.random.binomial(1, true_prob)
        actual_goals = 3 if actual else 2
        
        # 更新
        fusion.update(
            {'p_ge3': model_prob, 'p_ge4': model_prob * 0.6},
            {'p_ge3': market_prob, 'p_ge4': market_prob * 0.6},
            actual_goals
        )
        
        # 每10步更新权重
        if (i + 1) % 10 == 0:
            new_weight = fusion.update_weight()
            print(f"第{i+1}步后: 模型权重={new_weight:.3f}")
    
    # 测试3: 下注策略
    print("\n\n测试3: 下注策略与凯利准则\n")
    
    p_model, p_market = 0.58, 0.50
    odds_over = 1 / p_market
    
    strategy = betting_threshold_strategy(p_model, p_market, threshold=0.05, min_edge=0.02)
    
    print(f"模型概率: {p_model:.4f}, 市场概率: {p_market:.4f}")
    print(f"概率差异: {strategy['probability_diff']:.4f}")
    print(f"期望值:   {strategy['expected_value']:.4f}")
    print(f"是否下注: {'是' if strategy['should_bet'] else '否'} ({strategy['confidence']})")
    
    if strategy['should_bet']:
        kelly = kelly_criterion(p_model, odds_over, fraction=0.25, max_stake=0.05)
        print(f"\n凯利下注比例: {kelly*100:.2f}% (1/4凯利)")







