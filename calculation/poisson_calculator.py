"""
泊松分布计算模块 (增强版)
支持Dixon-Coles修正、时间衰减和市场融合
"""
import pandas as pd
import numpy as np
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, List, Optional, Any
from scipy.stats import poisson
import logging
import math
from datetime import datetime

# 导入数据库连接池
from database.pool import get_connection
from calculation.poisson_fusion import fuse_expected_goals

# 配置日志
logger = logging.getLogger(__name__)

# ------------------ Dixon-Coles 修正 ------------------

def dc_tau(home_goals: int, away_goals: int, rho: float, lambda_h: float, lambda_a: float) -> float:
    """Dixon-Coles修正因子"""
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

def estimate_league_rho_simple(league_avg_home: float, league_avg_away: float, 
                               low_score_freq: Dict = None) -> float:
    """
    简化的联赛ρ估计
    默认返回-0.13 (经验值)
    """
    # 如果提供了低比分频率，可以更精确估计
    if low_score_freq:
        obs_00 = low_score_freq.get((0,0), 0)
        exp_00 = math.exp(-league_avg_home) * math.exp(-league_avg_away)
        if exp_00 > 0 and league_avg_home * league_avg_away > 0:
            rho = (obs_00 / exp_00 - 1) / (league_avg_home * league_avg_away)
            return max(-0.3, min(0.2, rho))
    
    return -0.13  # 默认值

def round_to_2dp(value):
    """保留两位小数"""
    try:
        return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))
    except (ValueError, TypeError):
        return 0.0

def get_match_info(match_id, connection):
    """根据match_id获取比赛信息"""
    with connection.cursor() as cursor:
        query = """
        SELECT match_id, league_id, home_team_id, away_team_id,
               home_team_name, away_team_name, match_time, match_status
        FROM matches 
        WHERE match_id = %s
        """
        cursor.execute(query, (match_id,))
        return cursor.fetchone()

def load_league_matches(league_id, exclude_match_id, connection):
    """加载联赛所有已完成的比赛数据"""
    query = """
    SELECT home_team_name as HomeTeam, away_team_name as AwayTeam,
           home_score as FTHG, away_score as FTAG, match_time as match_date
    FROM matches 
    WHERE league_id = %s AND match_status = 'finished' 
          AND home_score IS NOT NULL AND away_score IS NOT NULL
          AND match_id != %s
    ORDER BY match_time DESC
    """
    
    # [修正] 弃用 pd.read_sql_query，改用标准的 cursor 执行来提高稳定性
    with connection.cursor() as cursor:
        cursor.execute(query, (league_id, exclude_match_id))
        results = cursor.fetchall()
    
    if not results:
        return pd.DataFrame() # 如果没有结果，返回一个空的DataFrame

    df = pd.DataFrame(results)
    
    df['FTHG'] = pd.to_numeric(df['FTHG'], errors='coerce')
    df['FTAG'] = pd.to_numeric(df['FTAG'], errors='coerce')
    df = df.dropna(subset=['FTHG', 'FTAG'])
    
    return df

def load_over_under_odds(match_id: int, connection) -> List[Dict[str, Any]]:
    """加载大小球即时赔率"""
    query = """
    SELECT
        company_id,
        market_line,
        over_open,
        under_open,
        over_current,
        under_current,
        last_updated
    FROM over_under_odds_changes
    WHERE match_id = %s
    """
    with connection.cursor() as cursor:
        cursor.execute(query, (match_id,))
        rows = cursor.fetchall() or []

    records: List[Dict[str, Any]] = []
    for row in rows:
        records.append({
            'company_id': row.get('company_id'),
            'market_line': float(row['market_line']) if row.get('market_line') is not None else None,
            'over_open': float(row['over_open']) if row.get('over_open') is not None else None,
            'under_open': float(row['under_open']) if row.get('under_open') is not None else None,
            'over_current': float(row['over_current']) if row.get('over_current') is not None else None,
            'under_current': float(row['under_current']) if row.get('under_current') is not None else None,
            'last_updated': row.get('last_updated'),
        })
    return records



def calculate_league_averages(match_data):
    """计算联赛平均值"""
    league_avg_home = match_data['FTHG'].mean()
    league_avg_away = match_data['FTAG'].mean()
    return round_to_2dp(league_avg_home), round_to_2dp(league_avg_away)

def calculate_team_stats(match_data, teams, recent_matches=8):
    """计算球队统计数据"""
    stats = {}
    league_avg_home, league_avg_away = calculate_league_averages(match_data)
    
    if league_avg_home == 0 or league_avg_away == 0:
        return None # 避免除以零

    for team in teams:
        home_games = match_data[match_data['HomeTeam'] == team].head(recent_matches)
        away_games = match_data[match_data['AwayTeam'] == team].head(recent_matches)
        
        home_goals = home_games['FTHG'].sum()
        home_conceded = home_games['FTAG'].sum()
        away_goals = away_games['FTAG'].sum()
        away_conceded = away_games['FTHG'].sum()
        
        home_attack = round_to_2dp((home_goals / len(home_games)) / league_avg_home) if len(home_games) > 0 else 1.0
        home_defense = round_to_2dp((home_conceded / len(home_games)) / league_avg_away) if len(home_games) > 0 else 1.0
        away_attack = round_to_2dp((away_goals / len(away_games)) / league_avg_away) if len(away_games) > 0 else 1.0
        away_defense = round_to_2dp((away_conceded / len(away_games)) / league_avg_home) if len(away_games) > 0 else 1.0

        stats[team] = {
            'home_attack': home_attack, 'home_defense': home_defense,
            'away_attack': away_attack, 'away_defense': away_defense
        }
    
    return stats


def calculate_team_stats_with_decay(match_data, teams, recent_matches=8, half_life_days=150):
    """
    计算球队统计数据 (带时间衰减)
    近期比赛权重更高，使用指数衰减: weight = 2^(-days/half_life)
    """
    stats = {}
    league_avg_home, league_avg_away = calculate_league_averages(match_data)
    
    if league_avg_home == 0 or league_avg_away == 0:
        return None
    
    # 当前日期
    current_date = pd.Timestamp.now()
    
    for team in teams:
        home_games = match_data[match_data['HomeTeam'] == team].head(recent_matches).copy()
        away_games = match_data[match_data['AwayTeam'] == team].head(recent_matches).copy()
        
        # 主场统计 (带衰减)
        if len(home_games) > 0:
            home_games['days_ago'] = (current_date - pd.to_datetime(home_games['match_date'])).dt.days
            home_games['weight'] = np.power(2, -home_games['days_ago'] / half_life_days)
            
            total_weight = home_games['weight'].sum()
            weighted_goals = (home_games['FTHG'] * home_games['weight']).sum()
            weighted_conceded = (home_games['FTAG'] * home_games['weight']).sum()
            
            home_attack = round_to_2dp((weighted_goals / total_weight) / league_avg_home) if total_weight > 0 else 1.0
            home_defense = round_to_2dp((weighted_conceded / total_weight) / league_avg_away) if total_weight > 0 else 1.0
        else:
            home_attack = 1.0
            home_defense = 1.0
        
        # 客场统计 (带衰减)
        if len(away_games) > 0:
            away_games['days_ago'] = (current_date - pd.to_datetime(away_games['match_date'])).dt.days
            away_games['weight'] = np.power(2, -away_games['days_ago'] / half_life_days)
            
            total_weight = away_games['weight'].sum()
            weighted_goals = (away_games['FTAG'] * away_games['weight']).sum()
            weighted_conceded = (away_games['FTHG'] * away_games['weight']).sum()
            
            away_attack = round_to_2dp((weighted_goals / total_weight) / league_avg_away) if total_weight > 0 else 1.0
            away_defense = round_to_2dp((weighted_conceded / total_weight) / league_avg_home) if total_weight > 0 else 1.0
        else:
            away_attack = 1.0
            away_defense = 1.0
        
        stats[team] = {
            'home_attack': home_attack, 
            'home_defense': home_defense,
            'away_attack': away_attack, 
            'away_defense': away_defense
        }
    
    return stats

def calculate_poisson_probabilities(home_team, away_team, team_stats, league_avg_home, league_avg_away, max_goals=5):
    """计算泊松分布概率"""
    if not team_stats or home_team not in team_stats or away_team not in team_stats:
        return None
        
    home_stats = team_stats[home_team]
    away_stats = team_stats[away_team]
    
    home_exp_goals = round_to_2dp(home_stats['home_attack'] * away_stats['away_defense'] * league_avg_home)
    away_exp_goals = round_to_2dp(away_stats['away_attack'] * home_stats['home_defense'] * league_avg_away)
    
    result = _build_poisson_result(home_exp_goals, away_exp_goals, max_goals)
    return result

def calculate_match_outcomes(probabilities):
    """计算比赛结果概率"""
    home_win, draw, away_win = 0, 0, 0
    for prob in probabilities:
        if prob['home_goals'] > prob['away_goals']: home_win += prob['probability']
        elif prob['home_goals'] == prob['away_goals']: draw += prob['probability']
        else: away_win += prob['probability']
    
    return {
        'home_win': round_to_2dp(home_win * 100),
        'draw': round_to_2dp(draw * 100),
        'away_win': round_to_2dp(away_win * 100),
    }

def calculate_over_under_probabilities(home_lambda, away_lambda):
    """计算大小球概率"""
    total_lambda = home_lambda + away_lambda
    ou_lines = [1.5, 2.5, 3.5]
    ou_probs = {}
    for line in ou_lines:
        under_prob = poisson.cdf(int(line - 0.5), total_lambda)
        over_prob = 1 - under_prob
        ou_probs[f"大{line}"] = round_to_2dp(over_prob * 100)
        ou_probs[f"小{line}"] = round_to_2dp(under_prob * 100)
    return ou_probs


def bivariate_poisson_pmf(x: int, y: int, lambda1: float, lambda2: float, lambda3: float) -> float:
    """
    双变量泊松分布PMF
    X = U + A, Y = U + B, 其中U~Pois(λ3)为共享成分
    λ1: X的独立成分, λ2: Y的独立成分, λ3: 共享成分(相关性)
    """
    prob = 0.0
    for k in range(min(x, y) + 1):
        if x - k < 0 or y - k < 0:
            continue
        term1 = math.exp(-(lambda1 + lambda2 + lambda3))
        term2 = (lambda1 ** (x - k)) / math.factorial(x - k) if x - k >= 0 else 0
        term3 = (lambda2 ** (y - k)) / math.factorial(y - k) if y - k >= 0 else 0
        term4 = (lambda3 ** k) / math.factorial(k) if k >= 0 else 0
        prob += term1 * term2 * term3 * term4
    return prob


def estimate_lambda3_from_draw_prob(lambda_h: float, lambda_a: float, p_draw_target: float = None) -> float:
    """
    从平局概率估计λ3（共享成分）
    如果没有目标平局概率，使用默认相关系数
    """
    if p_draw_target is None:
        # 默认: λ3 = 平均λ的10-15%（经验值）
        return (lambda_h + lambda_a) * 0.12
    
    # 用二分搜索找到合适的λ3
    def calc_draw_prob(lam3):
        p_draw = 0.0
        for s in range(6):  # 0-0到5-5
            p_draw += bivariate_poisson_pmf(s, s, lambda_h - lam3, lambda_a - lam3, lam3)
        return p_draw
    
    lo, hi = 0.0, min(lambda_h, lambda_a) * 0.8
    for _ in range(30):
        mid = (lo + hi) / 2
        p_calc = calc_draw_prob(mid)
        if abs(p_calc - p_draw_target) < 0.001:
            return mid
        if p_calc < p_draw_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def _build_poisson_result(home_lambda: float, away_lambda: float, max_goals: int = 5, 
                          use_dc: bool = False, rho: float = -0.13,
                          use_bivariate: bool = False, lambda3: float = None) -> Dict[str, Any]:
    """
    构建比分分布 (支持DC修正和双变量泊松)
    
    Args:
        use_dc: 是否使用Dixon-Coles修正
        rho: DC相关系数 (默认-0.13)
        use_bivariate: 是否使用双变量泊松（处理相关性）
        lambda3: 共享成分参数（用于双变量泊松）
    """
    flat_probs = []
    total_prob = 0.0
    
    # 如果使用双变量泊松
    if use_bivariate:
        if lambda3 is None:
            lambda3 = estimate_lambda3_from_draw_prob(home_lambda, away_lambda)
        lambda1 = max(0.1, home_lambda - lambda3)  # 主队独立成分
        lambda2 = max(0.1, away_lambda - lambda3)  # 客队独立成分
        
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                score_prob = bivariate_poisson_pmf(home_goals, away_goals, lambda1, lambda2, lambda3)
                total_prob += score_prob
                odds = round_to_2dp(1 / score_prob) if score_prob > 0 else 999999
                flat_probs.append({
                    'score': f"{home_goals}-{away_goals}",
                    'probability': score_prob,
                    'percentage': score_prob * 100,
                    'odds': odds,
                    'home_goals': home_goals,
                    'away_goals': away_goals,
                })
    else:
        # 原有逻辑: 独立泊松 + 可选DC修正
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                home_prob = poisson.pmf(home_goals, home_lambda)
                away_prob = poisson.pmf(away_goals, away_lambda)
                score_prob = home_prob * away_prob
                
                # Dixon-Coles修正
                if use_dc:
                    tau = dc_tau(home_goals, away_goals, rho, home_lambda, away_lambda)
                    score_prob *= tau
                
                total_prob += score_prob
                odds = round_to_2dp(1 / score_prob) if score_prob > 0 else 999999
                flat_probs.append({
                    'score': f"{home_goals}-{away_goals}",
                    'probability': score_prob,
                    'percentage': score_prob * 100,
                    'odds': odds,
                    'home_goals': home_goals,
                    'away_goals': away_goals,
                })
    
    # 归一化
    if total_prob > 0 and total_prob != 1.0:
        for prob in flat_probs:
            prob['probability'] = round_to_2dp(prob['probability'] / total_prob)
            prob['percentage'] = round_to_2dp(prob['probability'] * 100)
            prob['odds'] = round_to_2dp(1 / prob['probability']) if prob['probability'] > 0 else 999999
    else:
        for prob in flat_probs:
            prob['probability'] = round_to_2dp(prob['probability'])
            prob['percentage'] = round_to_2dp(prob['percentage'])

    flat_probs.sort(key=lambda x: x['probability'], reverse=True)

    outcomes = calculate_match_outcomes(flat_probs)
    over_under = calculate_over_under_probabilities(home_lambda, away_lambda)
    
    # 计算关键大小球概率 (3.0盘)
    total_goals_dist = {}
    for prob in flat_probs:
        total = prob['home_goals'] + prob['away_goals']
        if total not in total_goals_dist:
            total_goals_dist[total] = 0
        total_goals_dist[total] += prob['probability']
    
    p_le3 = sum(total_goals_dist.get(s, 0) for s in range(4))  # P(S≤3) 小于等于3球
    p_gt3 = sum(total_goals_dist.get(s, 0) for s in range(4, max_goals*2 + 1))  # P(S>3) 大于3球

    # 确定方法名称
    if use_bivariate:
        method_name = 'Bivariate Poisson'
    elif use_dc:
        method_name = 'Dixon-Coles'
    else:
        method_name = 'Independent Poisson'
    
    return {
        'expected_goals': {
            'home': round_to_2dp(home_lambda),
            'away': round_to_2dp(away_lambda),
            'total': round_to_2dp(home_lambda + away_lambda),
        },
        'probabilities': flat_probs[:10],
        'outcomes': outcomes,
        'over_under': over_under,
        'most_likely': flat_probs[0] if flat_probs else None,
        'full_distribution': flat_probs,
        'total_goals_probs': {
            'le3': round_to_2dp(p_le3 * 100),  # ≤3球 (小于等于3球)
            'gt3': round_to_2dp(p_gt3 * 100),  # >3球 (大于3球)
        },
        'method': method_name,
        'rho': round_to_2dp(rho) if use_dc else None,
        'lambda3': round_to_2dp(lambda3) if use_bivariate and lambda3 else None,
    }



def get_poisson_prediction(match_id: int, recent_matches: int = 8, max_goals: int = 5,
                          use_dc: bool = True, time_decay: bool = True, 
                          half_life_days: int = 150, use_bivariate: bool = False,
                          apply_calibration: bool = False):
    """
    完全增强版泊松预测: 支持DC修正、时间衰减、双变量泊松、市场融合和后验校准
    
    Args:
        match_id: 比赛ID
        recent_matches: 近期比赛数
        max_goals: 最大进球数
        use_dc: 是否使用Dixon-Coles修正
        time_decay: 是否使用时间衰减
        half_life_days: 时间衰减半衰期(天)
        use_bivariate: 是否使用双变量泊松(处理相关性)
        apply_calibration: 是否应用后验概率校准(需要历史数据)
    """
    logger.info(f"-[泊松预测]- 开始为比赛ID {match_id} 计算预测 (DC={use_dc}, 衰减={time_decay}, 双变量={use_bivariate}, 校准={apply_calibration})...")
    try:
        with get_connection() as connection:
            match_info = get_match_info(match_id, connection)
            if not match_info:
                logger.warning(f"-[泊松预测]- 未找到比赛ID {match_id} 的信息，预测终止")
                return {'error': f'未找到比赛ID: {match_id}'}

            logger.info(f"-[泊松预测]- 成功获取比赛信息: {match_info['home_team_name']} vs {match_info['away_team_name']}")

            league_id = match_info['league_id']
            match_data = load_league_matches(league_id, match_id, connection)

            logger.info(f"-[泊松预测]- 为联赛 {league_id} 捕获 {len(match_data)} 条历史记录")

            if len(match_data) < 10:
                msg = f"联赛 {league_id} 历史数据不足 ({len(match_data)}条/要求10条)，无法完成预测"
                logger.warning(f"-[泊松预测]- {msg}")
                return {'error': msg}

            league_avg_home, league_avg_away = calculate_league_averages(match_data)
            logger.info(f"-[泊松预测]- 联赛平均进球: 主队={league_avg_home}, 客队={league_avg_away}")

            teams = [match_info['home_team_name'], match_info['away_team_name']]
            
            # 应用时间衰减 (如果启用)
            if time_decay:
                team_stats = calculate_team_stats_with_decay(match_data, teams, recent_matches, half_life_days)
                logger.info(f"-[泊松预测]- 使用时间衰减 (半衰期={half_life_days}天)")
            else:
                team_stats = calculate_team_stats(match_data, teams, recent_matches)

            if not team_stats:
                msg = "无法计算球队统计，可能因为联赛平均进球为0或历史数据不足"
                logger.warning(f"-[泊松预测]- {msg}")
                return {'error': msg}

            home_stats = team_stats[teams[0]]
            away_stats = team_stats[teams[1]]

            home_lambda = round_to_2dp(home_stats['home_attack'] * away_stats['away_defense'] * league_avg_home)
            away_lambda = round_to_2dp(away_stats['away_attack'] * home_stats['home_defense'] * league_avg_away)

            # 估计联赛ρ (如果使用DC)
            rho = -0.13
            if use_dc:
                rho = estimate_league_rho_simple(league_avg_home, league_avg_away)
                logger.info(f"-[泊松预测]- Dixon-Coles ρ={rho:.4f}")

            historical_metrics = _build_poisson_result(
                home_lambda, away_lambda, max_goals, 
                use_dc=use_dc, rho=rho, use_bivariate=use_bivariate
            )

            over_under_records = load_over_under_odds(match_id, connection)
            fusion = fuse_expected_goals(
                hist_home=home_lambda,
                hist_away=away_lambda,
                records=over_under_records,
                match_time=match_info.get('match_time'),
            )

            if fusion.get('applied'):
                # 融合后也应用所有增强算法
                final_metrics = _build_poisson_result(
                    fusion['home_final'], fusion['away_final'], max_goals,
                    use_dc=use_dc, rho=rho, use_bivariate=use_bivariate
                )
                expected_home = fusion['home_final']
                expected_away = fusion['away_final']
                logger.info(f"-[泊松预测]- 应用市场融合: λ_h {home_lambda}->{expected_home}, λ_a {away_lambda}->{expected_away}")
            else:
                final_metrics = historical_metrics
                expected_home = home_lambda
                expected_away = away_lambda

            result = {
                'expected_goals': final_metrics['expected_goals'],
                'probabilities': final_metrics['probabilities'],
                'outcomes': final_metrics['outcomes'],
                'over_under': final_metrics['over_under'],
                'most_likely': final_metrics['most_likely'],
                'total_goals_probs': final_metrics.get('total_goals_probs', {}),  # 包含P(S=3)
                'fusion': fusion,
                'historical_baseline': historical_metrics,
                'over_under_records': len(over_under_records),
                'method': final_metrics.get('method', 'Poisson'),
                'dc_rho': rho if use_dc else None,
                'time_decay_applied': time_decay,
                'expected_goals_components': {
                    'historical': {
                        'home': home_lambda,
                        'away': away_lambda,
                    },
                    'final': {
                        'home': round_to_2dp(expected_home),
                        'away': round_to_2dp(expected_away),
                    },
                },
            }

            return result

    except Exception as e:
        logger.error(f"-[泊松预测]- 计算 {match_id} 时发生异常: {e}", exc_info=True)
        return {'error': str(e)}

