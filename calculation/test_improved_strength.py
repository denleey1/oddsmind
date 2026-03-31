#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
改进版广义实力计算测试脚本
对比现有算法与改进算法的差异

改进措施：
1. 近况轮次改为 min(8, team_count // 3)，更符合"近况"的语义
2. 主客场数量不平衡问题：使用加权平均
3. 档距划分：使用分位数分档而非线性等距分档
4. 保持8轮后才开始使用
"""

import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
from typing import Dict, Optional, List, Tuple
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.logger import get_logger
import pymysql
from pymysql.cursors import DictCursor

logger = get_logger(__name__)

# 直接使用数据库连接
def get_db_connection():
    return pymysql.connect(
        host='localhost',
        user='root',
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind',
        charset='utf8mb4',
        cursorclass=DictCursor
    )

class SimpleDB:
    """简单数据库包装器"""
    def execute_query(self, query, params=None, fetch='all'):
        conn = get_db_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(query, params)
                if fetch == 'all':
                    return cursor.fetchall()
                elif fetch == 'one':
                    return cursor.fetchone()
                else:
                    return None
        finally:
            conn.close()

DB = SimpleDB()


class ImprovedStrengthCalculator:
    """改进版广义实力计算器"""
    
    def __init__(self, league_id: int, company_id: int = 115):
        """
        初始化计算器
        
        Args:
            league_id: 联赛ID
            company_id: 博彩公司ID (默认115=威廉希尔)
        """
        self.league_id = league_id
        self.company_id = company_id
        self.db = DB
        
    def load_data(self) -> pd.DataFrame:
        """加载比赛和赔率数据"""
        query = """
        SELECT 
            m.match_id,
            m.round_number,
            m.home_team_id,
            m.away_team_id,
            m.home_team_name as home_team,
            m.away_team_name as away_team,
            eo.initial_home_prob,
            eo.initial_draw_prob,
            eo.initial_away_prob,
            c.name_cn as company_name
        FROM matches m
        JOIN european_odds eo ON m.match_id = eo.match_id
        JOIN companies c ON eo.company_id = c.company_id
        WHERE m.league_id = %s
          AND eo.company_id = %s
          AND m.match_status = 'finished'
          AND eo.initial_home_prob IS NOT NULL
          AND m.round_number IS NOT NULL
          AND m.round_number > 0
        ORDER BY m.round_number
        """
        
        results = self.db.execute_query(query, (self.league_id, self.company_id), fetch='all')
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        
        # 转换数据类型
        df['initial_home_prob'] = pd.to_numeric(df['initial_home_prob'])
        df['initial_draw_prob'] = pd.to_numeric(df['initial_draw_prob'])
        df['initial_away_prob'] = pd.to_numeric(df['initial_away_prob'])
        
        # 计算不败率
        df['home_team_unbeaten_rate'] = df['initial_home_prob'] + df['initial_draw_prob']
        df['away_team_unbeaten_rate'] = df['initial_away_prob'] + df['initial_draw_prob']
        
        return df
    
    def calculate_original(self, matches_df: pd.DataFrame) -> Dict:
        """使用原始算法计算（用于对比）"""
        if matches_df.empty:
            return {}
        
        # 获取所有球队ID
        all_team_ids = list(set(matches_df['home_team_id'].tolist() + matches_df['away_team_id'].tolist()))
        team_count = len(all_team_ids)
        
        # 原始近况轮次 = 球队数 - 1
        recent_rounds_original = team_count - 1
        
        teams_data = {}
        
        for team_id in all_team_ids:
            home_matches = matches_df[matches_df['home_team_id'] == team_id]
            away_matches = matches_df[matches_df['away_team_id'] == team_id]
            
            # 获取球队名称
            if not home_matches.empty:
                team_name = home_matches['home_team'].iloc[0]
            elif not away_matches.empty:
                team_name = away_matches['away_team'].iloc[0]
            else:
                continue
            
            # 原始算法：直接取均值
            home_avg = home_matches['home_team_unbeaten_rate'].mean() if not home_matches.empty else 0
            away_avg = away_matches['away_team_unbeaten_rate'].mean() if not away_matches.empty else 0
            total_power = home_avg + away_avg
            
            # 近况计算（原始：team_count - 1 轮）
            all_rounds = list(home_matches['round_number']) + list(away_matches['round_number'])
            team_max_round = max(all_rounds) if all_rounds else 0
            recent_threshold = team_max_round - recent_rounds_original
            
            recent_home = home_matches[home_matches['round_number'] > recent_threshold]
            recent_away = away_matches[away_matches['round_number'] > recent_threshold]
            
            recent_home_avg = recent_home['home_team_unbeaten_rate'].mean() if not recent_home.empty else 0
            recent_away_avg = recent_away['away_team_unbeaten_rate'].mean() if not recent_away.empty else 0
            recent_power = recent_home_avg + recent_away_avg
            
            # 综合实力
            combined_power = total_power * 0.2 + recent_power * 0.8
            
            teams_data[team_id] = {
                'team_name': team_name,
                'total_power': total_power,
                'recent_power': recent_power,
                'combined_power': combined_power,
                'home_matches': len(home_matches),
                'away_matches': len(away_matches),
                'recent_home_matches': len(recent_home),
                'recent_away_matches': len(recent_away)
            }
        
        # 计算相对实力和档距（原始算法）
        teams_df = pd.DataFrame.from_dict(teams_data, orient='index')
        min_power = teams_df['combined_power'].min()
        
        for team_id in teams_data:
            relative_power = teams_data[team_id]['combined_power'] - min_power
            power_level = round(relative_power / 10.5, 1)
            teams_data[team_id]['relative_power'] = relative_power
            teams_data[team_id]['power_level'] = power_level
            teams_data[team_id]['tier_level'] = self._categorize_team_original(power_level)
        
        return teams_data
    
    def calculate_improved(self, matches_df: pd.DataFrame) -> Dict:
        """使用改进算法计算"""
        if matches_df.empty:
            return {}
        
        # 获取所有球队ID
        all_team_ids = list(set(matches_df['home_team_id'].tolist() + matches_df['away_team_id'].tolist()))
        team_count = len(all_team_ids)
        
        # 【改进1】近况轮次 = min(8, team_count // 3)
        recent_rounds_improved = min(8, max(team_count // 3, 5))  # 至少5轮，最多8轮
        
        teams_data = {}
        
        for team_id in all_team_ids:
            home_matches = matches_df[matches_df['home_team_id'] == team_id]
            away_matches = matches_df[matches_df['away_team_id'] == team_id]
            
            # 获取球队名称
            if not home_matches.empty:
                team_name = home_matches['home_team'].iloc[0]
            elif not away_matches.empty:
                team_name = away_matches['away_team'].iloc[0]
            else:
                continue
            
            home_count = len(home_matches)
            away_count = len(away_matches)
            total_count = home_count + away_count
            
            if total_count == 0:
                continue
            
            # 【改进2】加权平均，考虑样本量
            home_avg = home_matches['home_team_unbeaten_rate'].mean() if not home_matches.empty else 0
            away_avg = away_matches['away_team_unbeaten_rate'].mean() if not away_matches.empty else 0
            
            # 使用样本量加权
            if home_count > 0 and away_count > 0:
                # 分别计算主场和客场的加权贡献
                # 主场不败率权重 = 主场比赛数 / 总比赛数
                # 客场不败率权重 = 客场比赛数 / 总比赛数
                home_weight = home_count / total_count
                away_weight = away_count / total_count
                total_power = home_avg * home_weight * 2 + away_avg * away_weight * 2  # *2是为了保持量纲一致
            elif home_count > 0:
                total_power = home_avg * 2  # 只有主场数据
            else:
                total_power = away_avg * 2  # 只有客场数据
            
            # 近况计算（改进：min(8, team_count//3) 轮）
            all_rounds = list(home_matches['round_number']) + list(away_matches['round_number'])
            team_max_round = max(all_rounds) if all_rounds else 0
            recent_threshold = team_max_round - recent_rounds_improved
            
            recent_home = home_matches[home_matches['round_number'] > recent_threshold]
            recent_away = away_matches[away_matches['round_number'] > recent_threshold]
            
            recent_home_count = len(recent_home)
            recent_away_count = len(recent_away)
            recent_total_count = recent_home_count + recent_away_count
            
            if recent_total_count > 0:
                recent_home_avg = recent_home['home_team_unbeaten_rate'].mean() if not recent_home.empty else 0
                recent_away_avg = recent_away['away_team_unbeaten_rate'].mean() if not recent_away.empty else 0
                
                # 同样使用加权平均
                if recent_home_count > 0 and recent_away_count > 0:
                    recent_home_weight = recent_home_count / recent_total_count
                    recent_away_weight = recent_away_count / recent_total_count
                    recent_power = recent_home_avg * recent_home_weight * 2 + recent_away_avg * recent_away_weight * 2
                elif recent_home_count > 0:
                    recent_power = recent_home_avg * 2
                else:
                    recent_power = recent_away_avg * 2
            else:
                recent_power = total_power  # 如果没有近况数据，使用总体数据
            
            # 综合实力（权重保持不变）
            combined_power = total_power * 0.2 + recent_power * 0.8
            
            teams_data[team_id] = {
                'team_name': team_name,
                'total_power': total_power,
                'recent_power': recent_power,
                'combined_power': combined_power,
                'home_matches': home_count,
                'away_matches': away_count,
                'recent_home_matches': recent_home_count,
                'recent_away_matches': recent_away_count,
                'recent_rounds_used': recent_rounds_improved
            }
        
        # 【改进3】使用分位数分档
        teams_df = pd.DataFrame.from_dict(teams_data, orient='index')
        min_power = teams_df['combined_power'].min()
        
        # 先计算相对实力
        for team_id in teams_data:
            teams_data[team_id]['relative_power'] = teams_data[team_id]['combined_power'] - min_power
        
        # 使用分位数分档
        relative_powers = [teams_data[tid]['relative_power'] for tid in teams_data]
        
        # 定义分位数边界（18档，每档约5.5%）
        percentiles = np.linspace(0, 100, 19)  # 0, 5.56, 11.11, ..., 100
        boundaries = np.percentile(relative_powers, percentiles)
        
        for team_id in teams_data:
            rp = teams_data[team_id]['relative_power']
            
            # 找到该球队属于哪个分位数区间（从低到高）
            percentile_rank = 0
            for i in range(len(boundaries) - 1):
                if rp <= boundaries[i + 1]:
                    percentile_rank = i  # i=0对应最弱，i=17对应最强
                    break
            else:
                percentile_rank = 17  # 最强
            
            # 转换为档距（0-9的尺度）- 高分位数对应高档距
            power_level = round(percentile_rank / 2, 1)  # 0-8.5
            
            teams_data[team_id]['power_level'] = power_level
            teams_data[team_id]['percentile_rank'] = percentile_rank
            teams_data[team_id]['tier_level'] = self._categorize_team_improved(power_level)
        
        return teams_data
    
    def _categorize_team_original(self, power_level: float) -> str:
        """原始分档逻辑"""
        if power_level >= 8.5: return "超强1"
        elif power_level >= 8.0: return "超强2"
        elif power_level >= 7.5: return "人强1"
        elif power_level >= 7.0: return "人强2"
        elif power_level >= 6.5: return "普强1"
        elif power_level >= 6.0: return "普强2"
        elif power_level >= 5.5: return "准强1"
        elif power_level >= 5.0: return "准强2"
        elif power_level >= 4.5: return "中强1"
        elif power_level >= 4.0: return "中强2"
        elif power_level >= 3.5: return "中上1"
        elif power_level >= 3.0: return "中上2"
        elif power_level >= 2.5: return "中游1"
        elif power_level >= 2.0: return "中游2"
        elif power_level >= 1.5: return "中下1"
        elif power_level >= 1.0: return "中下2"
        elif power_level >= 0.5: return "下游1"
        else: return "下游2"
    
    def _categorize_team_improved(self, power_level: float) -> str:
        """改进版分档逻辑（基于分位数）"""
        # 由于使用分位数，power_level范围是0-9
        if power_level >= 8.0: return "超强1"
        elif power_level >= 7.0: return "超强2"
        elif power_level >= 6.5: return "人强1"
        elif power_level >= 6.0: return "人强2"
        elif power_level >= 5.5: return "普强1"
        elif power_level >= 5.0: return "普强2"
        elif power_level >= 4.5: return "准强1"
        elif power_level >= 4.0: return "准强2"
        elif power_level >= 3.5: return "中强1"
        elif power_level >= 3.0: return "中强2"
        elif power_level >= 2.5: return "中上1"
        elif power_level >= 2.0: return "中上2"
        elif power_level >= 1.5: return "中游1"
        elif power_level >= 1.0: return "中游2"
        elif power_level >= 0.5: return "中下1"
        else: return "中下2"
    
    def compare_results(self, original: Dict, improved: Dict) -> pd.DataFrame:
        """对比原始和改进算法的结果"""
        comparison = []
        
        for team_id in original:
            if team_id not in improved:
                continue
            
            orig = original[team_id]
            impr = improved[team_id]
            
            comparison.append({
                'team_name': orig['team_name'],
                'orig_combined': round(orig['combined_power'], 2),
                'impr_combined': round(impr['combined_power'], 2),
                'combined_diff': round(impr['combined_power'] - orig['combined_power'], 2),
                'orig_relative': round(orig['relative_power'], 2),
                'impr_relative': round(impr['relative_power'], 2),
                'relative_diff': round(impr['relative_power'] - orig['relative_power'], 2),
                'orig_level': orig['power_level'],
                'impr_level': impr['power_level'],
                'level_diff': round(impr['power_level'] - orig['power_level'], 1),
                'orig_tier': orig['tier_level'],
                'impr_tier': impr['tier_level'],
                'tier_changed': orig['tier_level'] != impr['tier_level'],
                'home_matches': orig['home_matches'],
                'away_matches': orig['away_matches'],
                'imbalance_ratio': round(max(orig['home_matches'], orig['away_matches']) / 
                                        max(min(orig['home_matches'], orig['away_matches']), 1), 2),
                'orig_recent_rounds': orig.get('recent_home_matches', 0) + orig.get('recent_away_matches', 0),
                'impr_recent_rounds': impr.get('recent_home_matches', 0) + impr.get('recent_away_matches', 0)
            })
        
        df = pd.DataFrame(comparison)
        df = df.sort_values('orig_relative', ascending=False)
        
        return df


def get_existing_strength_data(league_id: int, company_id: int = 115) -> pd.DataFrame:
    """获取数据库中现有的广义实力数据"""
    query = """
    SELECT 
        team_id,
        team_name,
        total_power,
        recent_power,
        (total_power * 0.2 + recent_power * 0.8) as combined_power,
        relative_power,
        power_level,
        tier_level
    FROM team_power_ratings
    WHERE league_id = %s AND company_id = %s
    ORDER BY relative_power DESC
    """
    
    results = DB.execute_query(query, (league_id, company_id), fetch='all')
    
    if results:
        return pd.DataFrame(results)
    return pd.DataFrame()


def run_comparison(league_id: int, company_id: int = 115):
    """运行对比测试"""
    print("=" * 100)
    print(f"广义实力算法对比测试 - 联赛ID: {league_id}, 公司ID: {company_id}")
    print("=" * 100)
    
    # 获取联赛名称
    league_info = DB.execute_query(
        "SELECT name_cn FROM leagues WHERE league_id = %s",
        (league_id,), fetch='one'
    )
    league_name = league_info['name_cn'] if league_info else f"联赛{league_id}"
    print(f"\n联赛: {league_name}")
    
    # 初始化计算器
    calculator = ImprovedStrengthCalculator(league_id, company_id)
    
    # 加载数据
    print("\n1. 加载比赛数据...")
    matches_df = calculator.load_data()
    
    if matches_df.empty:
        print("   ❌ 没有找到比赛数据")
        return
    
    print(f"   ✅ 加载了 {len(matches_df)} 条比赛记录")
    print(f"   轮次范围: {matches_df['round_number'].min()} - {matches_df['round_number'].max()}")
    
    # 计算原始算法结果
    print("\n2. 计算原始算法结果...")
    original_results = calculator.calculate_original(matches_df)
    print(f"   ✅ 计算了 {len(original_results)} 支球队")
    
    # 计算改进算法结果
    print("\n3. 计算改进算法结果...")
    improved_results = calculator.calculate_improved(matches_df)
    print(f"   ✅ 计算了 {len(improved_results)} 支球队")
    
    # 获取数据库中现有数据
    print("\n4. 获取数据库现有数据...")
    existing_data = get_existing_strength_data(league_id, company_id)
    if not existing_data.empty:
        print(f"   ✅ 数据库中有 {len(existing_data)} 支球队的数据")
    else:
        print("   ⚠️ 数据库中没有该联赛的数据")
    
    # 对比结果
    print("\n5. 算法对比结果:")
    print("-" * 100)
    
    comparison = calculator.compare_results(original_results, improved_results)
    
    # 显示球队数量
    team_count = len(comparison)
    print(f"\n球队总数: {team_count}")
    
    # 显示近况轮次差异
    if not comparison.empty:
        first_team = list(improved_results.values())[0]
        orig_recent = team_count - 1
        impr_recent = first_team.get('recent_rounds_used', 0)
        print(f"原始近况轮次: {orig_recent} (球队数-1)")
        print(f"改进近况轮次: {impr_recent} (min(8, 球队数//3))")
    
    # 分档变化统计
    tier_changed = comparison[comparison['tier_changed'] == True]
    print(f"\n分档发生变化的球队: {len(tier_changed)} / {len(comparison)} ({len(tier_changed)/len(comparison)*100:.1f}%)")
    
    # 显示完整对比表格
    print("\n" + "=" * 100)
    print("完整对比表格 (按原始相对实力降序排列):")
    print("=" * 100)
    
    # 格式化输出
    print(f"\n{'球队':<15} {'原综合':>8} {'改综合':>8} {'差值':>6} | {'原档距':>6} {'改档距':>6} {'差':>4} | {'原分档':<6} {'改分档':<6} | {'主':>3}{'客':>3} {'不平衡':>6}")
    print("-" * 100)
    
    for _, row in comparison.iterrows():
        tier_mark = "⚠️" if row['tier_changed'] else "  "
        print(f"{row['team_name']:<15} {row['orig_combined']:>8.2f} {row['impr_combined']:>8.2f} {row['combined_diff']:>+6.2f} | "
              f"{row['orig_level']:>6.1f} {row['impr_level']:>6.1f} {row['level_diff']:>+4.1f} | "
              f"{row['orig_tier']:<6} {row['impr_tier']:<6} {tier_mark} | "
              f"{row['home_matches']:>3}{row['away_matches']:>3} {row['imbalance_ratio']:>6.2f}")
    
    # 统计分析
    print("\n" + "=" * 100)
    print("统计分析:")
    print("=" * 100)
    
    # 综合实力差异分析
    print(f"\n综合实力差异 (改进 - 原始):")
    print(f"  平均差异: {comparison['combined_diff'].mean():+.2f}")
    print(f"  标准差:   {comparison['combined_diff'].std():.2f}")
    print(f"  最大增加: {comparison['combined_diff'].max():+.2f}")
    print(f"  最大减少: {comparison['combined_diff'].min():+.2f}")
    
    # 档距差异分析
    print(f"\n档距差异 (改进 - 原始):")
    print(f"  平均差异: {comparison['level_diff'].mean():+.2f}")
    print(f"  标准差:   {comparison['level_diff'].std():.2f}")
    print(f"  最大增加: {comparison['level_diff'].max():+.2f}")
    print(f"  最大减少: {comparison['level_diff'].min():+.2f}")
    
    # 主客场不平衡分析
    print(f"\n主客场不平衡分析:")
    high_imbalance = comparison[comparison['imbalance_ratio'] > 1.5]
    print(f"  不平衡比>1.5的球队: {len(high_imbalance)} / {len(comparison)}")
    if not high_imbalance.empty:
        print(f"  这些球队的平均档距差异: {high_imbalance['level_diff'].mean():+.2f}")
    
    # 分档变化详情
    if not tier_changed.empty:
        print(f"\n分档变化详情:")
        for _, row in tier_changed.iterrows():
            direction = "↑" if row['level_diff'] > 0 else "↓"
            print(f"  {row['team_name']}: {row['orig_tier']} → {row['impr_tier']} ({direction}{abs(row['level_diff']):.1f}档)")
    
    # 与数据库现有数据对比（如果有）
    if not existing_data.empty:
        print("\n" + "=" * 100)
        print("与数据库现有数据对比:")
        print("=" * 100)
        
        # 合并对比
        db_comparison = []
        for _, db_row in existing_data.iterrows():
            team_id = db_row['team_id']
            if team_id in original_results:
                orig = original_results[team_id]
                db_comparison.append({
                    'team_name': db_row['team_name'],
                    'db_combined': float(db_row['combined_power']),
                    'calc_combined': round(orig['combined_power'], 2),
                    'diff': round(orig['combined_power'] - float(db_row['combined_power']), 2),
                    'db_tier': db_row['tier_level'],
                    'calc_tier': orig['tier_level']
                })
        
        if db_comparison:
            db_df = pd.DataFrame(db_comparison)
            db_df['diff'] = db_df['diff'].astype(float)
            diff_count = len(db_df[db_df['diff'].abs() > 0.01])
            print(f"\n数据一致性: {len(db_df) - diff_count} / {len(db_df)} 球队完全一致")
            if diff_count > 0:
                print(f"存在差异的球队: {diff_count}")
    
    return comparison


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="广义实力算法对比测试")
    parser.add_argument('--league-id', type=int, default=36, help='联赛ID (默认36=英超)')
    parser.add_argument('--company-id', type=int, default=115, help='公司ID (默认115=威廉希尔)')
    parser.add_argument('--all-major', action='store_true', help='测试所有主要联赛')
    
    args = parser.parse_args()
    
    if args.all_major:
        # 测试主要联赛
        major_leagues = [
            (36, "英超"),
            (31, "西甲"),
            (34, "意甲"),
            (8, "德甲"),
            (11, "法甲"),
        ]
        
        all_comparisons = []
        for league_id, league_name in major_leagues:
            print(f"\n\n{'#' * 100}")
            print(f"# 测试联赛: {league_name}")
            print(f"{'#' * 100}")
            comparison = run_comparison(league_id, args.company_id)
            if comparison is not None and not comparison.empty:
                comparison['league'] = league_name
                all_comparisons.append(comparison)
        
        # 汇总统计
        if all_comparisons:
            print("\n\n" + "=" * 100)
            print("所有联赛汇总统计")
            print("=" * 100)
            
            all_df = pd.concat(all_comparisons)
            print(f"\n总球队数: {len(all_df)}")
            print(f"分档变化球队数: {all_df['tier_changed'].sum()} ({all_df['tier_changed'].mean()*100:.1f}%)")
            print(f"平均档距差异: {all_df['level_diff'].mean():+.2f}")
            print(f"档距差异标准差: {all_df['level_diff'].std():.2f}")
    else:
        run_comparison(args.league_id, args.company_id)


if __name__ == "__main__":
    main()
