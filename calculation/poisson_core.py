"""
泊松分布分析模块 - 核心计算逻辑
从你的优秀框架基础上实现，专注于计算逻辑，无UI依赖
"""

import pandas as pd
import numpy as np
from scipy.stats import poisson
from decimal import Decimal, ROUND_HALF_UP

from database.connection import get_connection

DB = get_connection()

def round_to_2dp(value):
    """保留两位小数"""
    return float(Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

def load_match_data(league_id=None):
    """
    从MySQL数据库加载比赛数据
    
    Args:
        league_id: 联赛ID过滤
        
    Returns:
        DataFrame: 比赛数据
    """
    try:
        if league_id:
            query = """
            SELECT match_id, league_id, home_team_id, away_team_id, 
                   home_team_name as HomeTeam, away_team_name as AwayTeam,
                   home_score as FTHG, away_score as FTAG, match_time as match_date,
                   CAST(LEFT(half_score, LOCATE('-', half_score) - 1) AS UNSIGNED) as HTHG,
                   CAST(RIGHT(half_score, LENGTH(half_score) - LOCATE('-', half_score)) AS UNSIGNED) as HTAG
            FROM matches 
            WHERE league_id = %s AND match_status = 'finished' 
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
            ORDER BY match_time DESC
            """
            with DB.connection_scope() as connection:
                df = pd.read_sql_query(query, connection, params=[league_id])
        else:
            query = """
            SELECT match_id, league_id, home_team_id, away_team_id,
                   home_team_name as HomeTeam, away_team_name as AwayTeam,
                   home_score as FTHG, away_score as FTAG, match_time as match_date,
                   CAST(LEFT(half_score, LOCATE('-', half_score) - 1) AS UNSIGNED) as HTHG,
                   CAST(RIGHT(half_score, LENGTH(half_score) - LOCATE('-', half_score)) AS UNSIGNED) as HTAG
            FROM matches 
            WHERE match_status = 'finished' 
                  AND home_score IS NOT NULL AND away_score IS NOT NULL
            ORDER BY match_time DESC
            """
            with DB.connection_scope() as connection:
                df = pd.read_sql_query(query, connection)
        
        # 转换数据类型
        df['FTHG'] = pd.to_numeric(df['FTHG'], errors='coerce')
        df['FTAG'] = pd.to_numeric(df['FTAG'], errors='coerce')
        df['HTHG'] = pd.to_numeric(df['HTHG'], errors='coerce')
        df['HTAG'] = pd.to_numeric(df['HTAG'], errors='coerce')
        
        # 删除空值行
        df = df.dropna(subset=['FTHG', 'FTAG'])
        
        return df
        
    except Exception as e:
        print(f"加载比赛数据时出错: {str(e)}")
        return pd.DataFrame()

def get_available_leagues():
    """
    获取可用的联赛列表
    
    Returns:
        list: (联赛ID, 联赛名称) 元组列表
    """
    try:
        query = "SELECT DISTINCT league_id, name_cn FROM leagues ORDER BY league_id"
        with DB.connection_scope() as connection:
            df = pd.read_sql_query(query, connection)
        
        return [(row['league_id'], row['name_cn']) for _, row in df.iterrows()]
        
    except Exception as e:
        print(f"获取联赛列表时出错: {str(e)}")
        return []

def calculate_league_averages(match_data):
    """
    计算联赛平均值
    
    Args:
        match_data: 比赛数据DataFrame
        
    Returns:
        tuple: (主场平均进球数, 客场平均进球数)
    """
    league_avg_home = match_data['FTHG'].mean()
    league_avg_away = match_data['FTAG'].mean()
    return round_to_2dp(league_avg_home), round_to_2dp(league_avg_away)

def calculate_team_stats(match_data, teams, recent_matches=8):
    """
    计算球队统计数据
    
    Args:
        match_data: 比赛数据DataFrame
        teams: 球队名称列表
        recent_matches: 最近比赛数量
        
    Returns:
        dict: 球队统计数据
    """
    df = match_data
    stats = {}
    league_avg_home, league_avg_away = calculate_league_averages(match_data)
    
    for team in teams:
        # 获取该队所有比赛（主场和客场）
        home_games = df[df['HomeTeam'] == team].copy()
        away_games = df[df['AwayTeam'] == team].copy()
        
        # 为每场比赛添加是否为主场标记
        home_games['is_home'] = True
        away_games['is_home'] = False
        
        # 合并所有比赛
        all_games = pd.concat([home_games, away_games])
        
        # 按日期排序（最新的在前）
        if 'match_date' in df.columns and not all_games.empty:
            try:
                all_games['match_date'] = pd.to_datetime(all_games['match_date'])
                all_games = all_games.sort_values('match_date', ascending=False)
            except:
                pass
        
        # 只取最近N场比赛
        recent_games = all_games.head(recent_matches)
        
        # 分离主场和客场比赛
        recent_home = recent_games[recent_games['is_home'] == True]
        recent_away = recent_games[recent_games['is_home'] == False]
        
        # 基本统计
        home_goals = recent_home['FTHG'].sum() if not recent_home.empty else 0
        home_conceded = recent_home['FTAG'].sum() if not recent_home.empty else 0
        away_goals = recent_away['FTAG'].sum() if not recent_away.empty else 0
        away_conceded = recent_away['FTHG'].sum() if not recent_away.empty else 0
        
        # 计算攻防强度
        home_attack = round_to_2dp(home_goals / len(recent_home) / league_avg_home) if len(recent_home) > 0 and league_avg_home > 0 else 1.0
        home_defense = round_to_2dp(home_conceded / len(recent_home) / league_avg_away) if len(recent_home) > 0 and league_avg_away > 0 else 1.0
        away_attack = round_to_2dp(away_goals / len(recent_away) / league_avg_away) if len(recent_away) > 0 and league_avg_away > 0 else 1.0
        away_defense = round_to_2dp(away_conceded / len(recent_away) / league_avg_home) if len(recent_away) > 0 and league_avg_home > 0 else 1.0
        
        # 球队统计数据
        team_stats = {
            'home_games': len(recent_home),
            'away_games': len(recent_away),
            'home_goals': home_goals,
            'away_goals': away_goals,
            'home_conceded': home_conceded,
            'away_conceded': away_conceded,
            'home_attack': home_attack,
            'home_defense': home_defense,
            'away_attack': away_attack,
            'away_defense': away_defense,
            'total_games': len(recent_games),
            'avg_home_goals': round_to_2dp(home_goals / len(recent_home)) if len(recent_home) > 0 else 0.0,
            'avg_away_goals': round_to_2dp(away_goals / len(recent_away)) if len(recent_away) > 0 else 0.0,
            'avg_home_conceded': round_to_2dp(home_conceded / len(recent_home)) if len(recent_home) > 0 else 0.0,
            'avg_away_conceded': round_to_2dp(away_conceded / len(recent_away)) if len(recent_away) > 0 else 0.0
        }
        
        # 添加半场进球统计（如果有）
        if 'HTHG' in df.columns and 'HTAG' in df.columns:
            ht_home_goals = recent_home['HTHG'].sum() if not recent_home.empty else 0
            ht_home_conceded = recent_home['HTAG'].sum() if not recent_home.empty else 0
            ht_away_goals = recent_away['HTAG'].sum() if not recent_away.empty else 0
            ht_away_conceded = recent_away['HTHG'].sum() if not recent_away.empty else 0
            
            team_stats.update({
                'ht_home_goals': ht_home_goals,
                'ht_home_conceded': ht_home_conceded,
                'ht_away_goals': ht_away_goals,
                'ht_away_conceded': ht_away_conceded,
                'avg_ht_home_goals': round_to_2dp(ht_home_goals / len(recent_home)) if len(recent_home) > 0 else 0.0,
                'avg_ht_away_goals': round_to_2dp(ht_away_goals / len(recent_away)) if len(recent_away) > 0 else 0.0
            })
        
        stats[team] = team_stats
    
    return stats

def calculate_poisson_probabilities(home_team, away_team, team_stats, league_avg_home, league_avg_away, max_goals=5):
    """
    计算泊松分布概率
    
    Args:
        home_team: 主队名称
        away_team: 客队名称
        team_stats: 球队统计数据
        league_avg_home: 联赛主场平均进球
        league_avg_away: 联赛客场平均进球
        max_goals: 最大进球数
        
    Returns:
        dict: 泊松分布结果
    """
    if home_team not in team_stats or away_team not in team_stats:
        return None
        
    home_stats = team_stats[home_team]
    away_stats = team_stats[away_team]
    
    # 计算预期进球
    home_exp_goals = round_to_2dp(home_stats['home_attack'] * away_stats['away_defense'] * league_avg_home)
    away_exp_goals = round_to_2dp(away_stats['away_attack'] * home_stats['home_defense'] * league_avg_away)
    
    # 计算概率矩阵
    prob_matrix = []
    
    for home_goals in range(max_goals + 1):
        row = []
        for away_goals in range(max_goals + 1):
            # 使用scipy.stats.poisson计算概率
            home_prob = poisson.pmf(home_goals, home_exp_goals)
            away_prob = poisson.pmf(away_goals, away_exp_goals)
            
            score_prob = home_prob * away_prob
            score_prob = round_to_2dp(score_prob)
            
            odds = round_to_2dp(1/score_prob) if score_prob > 0 else float('inf')
            
            row.append({
                'home_goals': home_goals,
                'away_goals': away_goals,
                'probability': score_prob,
                'percentage': round_to_2dp(score_prob * 100),
                'odds': odds,
                'score': f"{home_goals}-{away_goals}"
            })
        
        prob_matrix.append(row)
    
    # 扁平化并按概率排序
    flat_probs = []
    for row in prob_matrix:
        flat_probs.extend(row)
    
    flat_probs.sort(key=lambda x: x['probability'], reverse=True)
    
    # 计算比赛结果概率
    outcomes = calculate_match_outcomes(flat_probs)
    
    # 计算大小球概率
    over_under = calculate_over_under_probabilities(home_exp_goals, away_exp_goals)
    
    # 计算置信区间
    confidence_intervals = {
        'home_goals': calculate_confidence_intervals(home_exp_goals),
        'away_goals': calculate_confidence_intervals(away_exp_goals)
    }
    
    return {
        'home_team': home_team,
        'away_team': away_team,
        'expected_goals': {
            'home': home_exp_goals,
            'away': away_exp_goals,
            'total': round_to_2dp(home_exp_goals + away_exp_goals)
        },
        'probabilities': flat_probs,
        'outcomes': outcomes,
        'over_under': over_under,
        'confidence_intervals': confidence_intervals,
        'most_likely': flat_probs[0],
        'team_stats': {
            'home': home_stats,
            'away': away_stats
        },
        'league_averages': {
            'home': league_avg_home,
            'away': league_avg_away
        }
    }

def calculate_match_outcomes(probabilities):
    """
    计算比赛结果概率
    
    Args:
        probabilities: 概率列表
        
    Returns:
        dict: 主胜、平局、客胜概率
    """
    home_win = 0
    draw = 0
    away_win = 0
    
    for prob in probabilities:
        if prob['home_goals'] > prob['away_goals']:
            home_win += prob['probability']
        elif prob['home_goals'] == prob['away_goals']:
            draw += prob['probability']
        else:
            away_win += prob['probability']
    
    return {
        'home_win': round_to_2dp(home_win * 100),
        'draw': round_to_2dp(draw * 100),
        'away_win': round_to_2dp(away_win * 100),
        'home_win_odds': round_to_2dp(1/home_win) if home_win > 0 else float('inf'),
        'draw_odds': round_to_2dp(1/draw) if draw > 0 else float('inf'),
        'away_win_odds': round_to_2dp(1/away_win) if away_win > 0 else float('inf')
    }

def calculate_over_under_probabilities(home_lambda, away_lambda):
    """
    计算大小球概率
    
    Args:
        home_lambda: 主队期望进球
        away_lambda: 客队期望进球
        
    Returns:
        dict: 大小球概率
    """
    total_lambda = home_lambda + away_lambda
    
    # 常见大小球盘口
    ou_lines = [0.5, 1.5, 2.5, 3.5, 4.5, 5.5]
    ou_probs = {}
    
    for line in ou_lines:
        # 计算小于等于line-0.5的概率（小球）
        under_prob = 0.0
        for goals in range(int(line) + 1):
            under_prob += poisson.pmf(goals, total_lambda)
        
        over_prob = 1 - under_prob
        
        ou_probs[f"大{line}"] = round_to_2dp(over_prob * 100)
        ou_probs[f"小{line}"] = round_to_2dp(under_prob * 100)
        ou_probs[f"大{line}_odds"] = round_to_2dp(1/over_prob) if over_prob > 0 else float('inf')
        ou_probs[f"小{line}_odds"] = round_to_2dp(1/under_prob) if under_prob > 0 else float('inf')
    
    return ou_probs

def calculate_confidence_intervals(lambda_val, confidence=0.95):
    """
    计算泊松分布的置信区间
    
    Args:
        lambda_val: 期望值
        confidence: 置信度
        
    Returns:
        dict: 置信区间信息
    """
    if lambda_val >= 10:
        z_score = 1.96 if confidence == 0.95 else 2.58
        margin = z_score * np.sqrt(lambda_val)
        lower = max(0, lambda_val - margin)
        upper = lambda_val + margin
    else:
        std = np.sqrt(lambda_val)
        margin = 1.96 * std if confidence == 0.95 else 2.58 * std
        lower = max(0, lambda_val - margin)
        upper = lambda_val + margin
    
    return {
        'expected': round_to_2dp(lambda_val),
        'lower_bound': round_to_2dp(lower),
        'upper_bound': round_to_2dp(upper),
        'confidence_level': confidence
    }

def create_heatmap_data(probabilities, max_goals):
    """
    为热图创建数据
    
    Args:
        probabilities: 概率列表
        max_goals: 最大进球数
        
    Returns:
        numpy.ndarray: 热图数据矩阵
    """
    heatmap_data = np.zeros((max_goals + 1, max_goals + 1))
    
    for prob in probabilities:
        h = prob['home_goals']
        a = prob['away_goals']
        if h <= max_goals and a <= max_goals:
            heatmap_data[a, h] = prob['percentage']
    
    return heatmap_data

def create_total_goals_data(probabilities):
    """
    创建总进球分布数据
    
    Args:
        probabilities: 概率列表
        
    Returns:
        list: (进球数, 概率百分比) 元组列表
    """
    total_goals = {}
    for prob in probabilities:
        total = prob['home_goals'] + prob['away_goals']
        if total not in total_goals:
            total_goals[total] = 0
        total_goals[total] += prob['probability']
    
    # 按总进球数排序
    total_goals_data = sorted([(k, round_to_2dp(v * 100)) for k, v in total_goals.items()])
    return total_goals_data

def predict_match_by_names(home_team_name, away_team_name, league_id, recent_matches=8):
    """
    通过球队名称预测比赛
    
    Args:
        home_team_name: 主队名称
        away_team_name: 客队名称
        league_id: 联赛ID
        recent_matches: 最近比赛数量
        
    Returns:
        dict: 预测结果
    """
    # 加载比赛数据
    match_data = load_match_data(league_id)
    
    if match_data.empty:
        return {'error': '无法加载比赛数据'}
    
    # 获取联赛平均值
    league_avg_home, league_avg_away = calculate_league_averages(match_data)
    
    # 计算球队统计
    teams = [home_team_name, away_team_name]
    team_stats = calculate_team_stats(match_data, teams, recent_matches)
    
    # 计算预测
    result = calculate_poisson_probabilities(
        home_team_name, away_team_name, team_stats, 
        league_avg_home, league_avg_away
    )
    
    return result

# 快速接口函数
def quick_predict(home_team_name, away_team_name, league_id):
    """快速预测接口"""
    return predict_match_by_names(home_team_name, away_team_name, league_id)

if __name__ == "__main__":
    # 测试代码
    print("=== 泊松分布足球预测测试 ===")
    
    # 测试预测
    result = quick_predict("大阪钢巴", "大阪樱花", 25)
    
    if result and 'error' not in result:
        print(f"\n预测摘要:")
        print(f"主队: {result['home_team']}")
        print(f"客队: {result['away_team']}")
        print(f"主队期望进球: {result['expected_goals']['home']}")
        print(f"客队期望进球: {result['expected_goals']['away']}")
        print(f"总进球期望: {result['expected_goals']['total']}")
        print(f"最可能比分: {result['most_likely']['score']} (概率: {result['most_likely']['percentage']}%)")
        
        print(f"\n胜平负概率:")
        outcomes = result['outcomes']
        print(f"主胜: {outcomes['home_win']}% (赔率: {outcomes['home_win_odds']})")
        print(f"平局: {outcomes['draw']}% (赔率: {outcomes['draw_odds']})")
        print(f"客胜: {outcomes['away_win']}% (赔率: {outcomes['away_win_odds']})")
        
        print(f"\n置信区间 (95%):")
        print(f"主队进球: {result['confidence_intervals']['home_goals']['lower_bound']} - {result['confidence_intervals']['home_goals']['upper_bound']}")
        print(f"客队进球: {result['confidence_intervals']['away_goals']['lower_bound']} - {result['confidence_intervals']['away_goals']['upper_bound']}")
        
        print(f"\n主要比分概率:")
        for i, prob in enumerate(result['probabilities'][:10]):
            print(f"{prob['score']}: {prob['percentage']}% (赔率: {prob['odds']})")
        
        print(f"\n大小球概率:")
        ou = result['over_under']
        for line in [2.5, 3.5]:
            print(f"大{line}: {ou[f'大{line}']}% (赔率: {ou[f'大{line}_odds']}), 小{line}: {ou[f'小{line}']}% (赔率: {ou[f'小{line}_odds']})")
        
    else:
        print(f"预测失败: {result.get('error', '未知错误')}")
