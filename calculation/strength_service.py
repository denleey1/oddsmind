#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
广义实力计算服务
负责计算球队的广义实力指标
"""
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

logger = get_logger(__name__)

class StrengthCalculationService:
    """
    广义实力计算服务
    基于赔率数据计算球队的综合实力指标
    """
    
    def __init__(self):
        """初始化计算服务"""
        self.logger = get_logger(__name__)
    
    def calculate_all_teams_strength(self, matches_df: pd.DataFrame) -> Tuple[Dict, Optional[int]]:
        """
        计算所有球队的广义实力
        
        Args:
            matches_df: 包含比赛和赔率数据的DataFrame
            
        Returns:
            一个元组，包含:
            - 包含各队实力指标的字典
            - 当前计算所基于的最新轮次
        """
        if matches_df.empty:
            self.logger.warning("输入数据为空，无法计算实力")
            return {}, None
        
        # 获取当前数据集中的最大轮次
        current_round = None
        if 'round_number' in matches_df.columns and not matches_df.empty:
            max_round = matches_df['round_number'].max()
            if pd.notna(max_round):
                current_round = int(max_round)

        # 按照guangyishili算法计算不败率
        # 注意：数据库中存储的已经是百分数(如46.16代表46.16%)，直接使用即可
        matches_df = matches_df.copy()
        matches_df['home_team_unbeaten_rate'] = pd.to_numeric(matches_df['initial_home_prob']) + pd.to_numeric(matches_df['initial_draw_prob'])
        matches_df['away_team_unbeaten_rate'] = pd.to_numeric(matches_df['initial_away_prob']) + pd.to_numeric(matches_df['initial_draw_prob'])
        
        # 获取所有球队ID
        all_team_ids = list(set(matches_df['home_team_id'].tolist() + matches_df['away_team_id'].tolist()))
        self.logger.info(f"开始计算 {len(all_team_ids)} 支队伍的广义实力...")
        
        # 估算球队总数（用于计算近况轮次）
        team_count = len(all_team_ids)
        recent_rounds = team_count - 1  # 近况轮次数 = 球队总数 - 1
        
        teams_data = {}
        
        for team_id in all_team_ids:
            try:
                team_power = self._calculate_team_strength_guangyishili(matches_df, team_id, recent_rounds)
                if team_power:
                    teams_data[team_id] = team_power
            except Exception as e:
                self.logger.error(f"计算球队ID {team_id} 实力时出错: {e}")
                continue
        
        if teams_data:
            # 转换为DataFrame便于后续处理
            teams_df = pd.DataFrame.from_dict(teams_data, orient='index')
            
            # 按照guangyishili算法计算相对实力
            team_powers = self._calculate_guangyishili_relative_powers(teams_df)
            self.logger.info(f"成功计算了 {len(team_powers)} 支球队的广义实力")
        else:
            self.logger.warning("没有计算出任何球队的实力数据")
            team_powers = {}
        
        return team_powers, current_round
    
    def _get_all_teams(self, matches_df: pd.DataFrame) -> Dict[int, str]:
        """获取所有球队的ID和名称"""
        teams = {}
        
        # 从主队数据获取
        home_teams = matches_df[['home_team_id', 'home_team']].drop_duplicates()
        for _, row in home_teams.iterrows():
            teams[row['home_team_id']] = row['home_team']
        
        # 从客队数据获取
        away_teams = matches_df[['away_team_id', 'away_team']].drop_duplicates()
        for _, row in away_teams.iterrows():
            teams[row['away_team_id']] = row['away_team']
        
        return teams
    
    def _calculate_team_strength(self, matches_df: pd.DataFrame, team_id: int, team_name: str) -> Optional[Dict]:
        """计算单个球队的实力指标"""
        
        # 获取该球队的所有比赛
        team_matches = matches_df[
            (matches_df['home_team_id'] == team_id) | 
            (matches_df['away_team_id'] == team_id)
        ].copy()
        
        if team_matches.empty:
            self.logger.debug(f"球队 {team_name} 没有比赛数据")
            return None
        
        # 计算基础实力指标
        total_power = self._calculate_total_power(team_matches, team_id)
        recent_power = self._calculate_recent_power(team_matches, team_id)
        
        # 计算综合实力
        combined_power = self._calculate_combined_power(total_power, recent_power)
        
        return {
            'team_name': team_name,
            'total_power': total_power,
            'recent_power': recent_power,
            'combined_power': combined_power,
            'matches_count': len(team_matches),
            'calculation_date': datetime.now().date().isoformat()
        }
    
    def _calculate_total_power(self, team_matches: pd.DataFrame, team_id: int) -> float:
        """计算总实力（基于所有比赛）"""
        # 获取该球队的主场比赛
        home_matches = team_matches[team_matches['home_team_id'] == team_id]
        # 获取该球队的客场比赛
        away_matches = team_matches[team_matches['away_team_id'] == team_id]
        
        # 计算主场平均不败率 (使用已转换好的不败率字段)
        if not home_matches.empty:
            avg_home_unbeaten_rate = home_matches['home_team_unbeaten_rate'].mean()
        else:
            avg_home_unbeaten_rate = 0.0
        
        # 计算客场平均不败率 (使用已转换好的不败率字段)
        if not away_matches.empty:
            avg_away_unbeaten_rate = away_matches['away_team_unbeaten_rate'].mean()
        else:
            avg_away_unbeaten_rate = 0.0
        
        # 总实力 = 主场不败率 + 客场不败率
        total_power = avg_home_unbeaten_rate + avg_away_unbeaten_rate
        
        return total_power
    
    def _calculate_recent_power(self, team_matches: pd.DataFrame, team_id: int) -> float:
        """计算近期实力（基于最近N轮比赛）"""
        # 获取该球队的主场比赛
        home_matches = team_matches[team_matches['home_team_id'] == team_id]
        # 获取该球队的客场比赛
        away_matches = team_matches[team_matches['away_team_id'] == team_id]
        
        # 计算该队最大轮次
        all_rounds = []
        if not home_matches.empty:
            all_rounds.extend(home_matches['round_number'].tolist())
        if not away_matches.empty:
            all_rounds.extend(away_matches['round_number'].tolist())
        
        team_max_round = max(all_rounds) if all_rounds else 0
        
        # 计算近况轮次数 = 球队总数 - 1
        # 这里需要从外部传入球队总数，暂时使用固定值20
        team_count = 20  # 这个应该从外部传入
        recent_rounds = team_count - 1
        
        # 计算近况阈值
        recent_threshold = team_max_round - recent_rounds
        
        # 获取近况比赛
        recent_home = home_matches[home_matches['round_number'] > recent_threshold]
        recent_away = away_matches[away_matches['round_number'] > recent_threshold]
        
        # 计算近况主场平均不败率 (使用已转换好的不败率字段)
        if not recent_home.empty:
            recent_home_avg = recent_home['home_team_unbeaten_rate'].mean()
        else:
            recent_home_avg = 0.0
        
        # 计算近况客场平均不败率 (使用已转换好的不败率字段)
        if not recent_away.empty:
            recent_away_avg = recent_away['away_team_unbeaten_rate'].mean()
        else:
            recent_away_avg = 0.0
        
        # 近期实力 = 近况主场不败率 + 近况客场不败率
        recent_power = recent_home_avg + recent_away_avg
        
        return recent_power
    
    def _calculate_combined_power(self, total_power: float, recent_power: float) -> float:
        """计算综合实力（总实力和近期实力的加权平均）"""
        # 按照原始逻辑：近期实力权重更高
        recent_weight = 0.8
        total_weight = 0.2
        
        return total_power * total_weight + recent_power * recent_weight
    
    def _calculate_relative_powers(self, team_powers: Dict) -> Dict:
        """计算相对实力和等级分类"""
        if not team_powers:
            return team_powers
        
        # 获取所有综合实力值
        combined_powers = [data['combined_power'] for data in team_powers.values()]
        
        if not combined_powers:
            return team_powers
        
        # 计算统计指标
        mean_power = np.mean(combined_powers)
        std_power = np.std(combined_powers)
        
        # 为每个球队计算相对实力和等级
        for team_id, team_data in team_powers.items():
            combined_power = team_data['combined_power']
            
            # 计算相对实力（标准化）
            if std_power > 0:
                relative_power = (combined_power - mean_power) / std_power
            else:
                relative_power = 0.0
            
            # 计算档距（按照原始逻辑）
            power_level = (relative_power / 10.5).round(1)
            
            # 等级分类（按照原始逻辑的详细分类）
            def categorize_team(power_level):
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
            
            tier_level = categorize_team(power_level)
            
            # 更新数据，保持与原有表结构一致
            team_data.update({
                'relative_power': relative_power,
                'power_level': power_level,     # power_level 对应档距
                'tier_distance': relative_power, # tier_distance 对应相对实力
                'tier_level': tier_level,       # tier_level 对应等级分类
                'level_class': tier_level       # 保持兼容性
            })
        
        return team_powers
    
    def _calculate_combined_power(self, total_power: float, recent_power: float) -> float:
        """计算综合实力（总实力和近期实力的加权平均）- 保持原有接口兼容性"""
        # 按照guangyishili算法：近期实力权重0.8，总体权重0.2
        recent_weight = 0.8
        total_weight = 0.2
        
        return total_power * total_weight + recent_power * recent_weight
    
    def _calculate_team_strength_guangyishili(self, matches_df: pd.DataFrame, team_id: int, recent_rounds: int) -> Optional[Dict]:
        """
        按照guangyishili算法计算单个球队的实力指标
        """
        # 获取该球队的所有比赛
        team_matches = matches_df[
            (matches_df['home_team_id'] == team_id) | 
            (matches_df['away_team_id'] == team_id)
        ].copy()
        
        if team_matches.empty:
            return None
        
        # 获取球队名称
        team_name = None
        home_matches = team_matches[team_matches['home_team_id'] == team_id]
        away_matches = team_matches[team_matches['away_team_id'] == team_id]
        
        if not home_matches.empty:
            team_name = home_matches['home_team'].iloc[0]
        elif not away_matches.empty:
            team_name = away_matches['away_team'].iloc[0]
        else:
            team_name = f'Team_{team_id}'
        
        # 计算总体实力（基于所有比赛）
        total_power = self._calculate_total_power_guangyishili(home_matches, away_matches)
        
        # 计算近况实力（基于最近N轮）
        recent_power = self._calculate_recent_power_guangyishili(home_matches, away_matches, recent_rounds)
        
        # 计算综合实力：总体权重0.2，近况权重0.8
        combined_power = total_power * 0.2 + recent_power * 0.8
        
        return {
            'team_name': team_name,
            'total_power': total_power,
            'recent_power': recent_power,
            'combined_power': combined_power,
            'matches_count': len(team_matches)
        }
    
    def _calculate_total_power_guangyishili(self, home_matches: pd.DataFrame, away_matches: pd.DataFrame) -> float:
        """按照guangyishili算法计算总体实力"""
        # 计算主场平均不败率
        if not home_matches.empty:
            home_unbeaten_avg = home_matches['home_team_unbeaten_rate'].mean()
        else:
            home_unbeaten_avg = 0.0
        
        # 计算客场平均不败率
        if not away_matches.empty:
            away_unbeaten_avg = away_matches['away_team_unbeaten_rate'].mean()
        else:
            away_unbeaten_avg = 0.0
        
        # 总体实力 = 主场不败率 + 客场不败率
        return home_unbeaten_avg + away_unbeaten_avg
    
    def _calculate_recent_power_guangyishili(self, home_matches: pd.DataFrame, away_matches: pd.DataFrame, recent_rounds: int) -> float:
        """按照guangyishili算法计算近况实力"""
        # 计算该队最大轮次
        all_rounds = []
        if not home_matches.empty:
            all_rounds.extend(home_matches['round_number'].tolist())
        if not away_matches.empty:
            all_rounds.extend(away_matches['round_number'].tolist())
        
        if not all_rounds:
            return 0.0
            
        team_max_round = max(all_rounds)
        
        # 计算近况阈值轮次 = 最大轮次 - 近况轮数
        recent_threshold = team_max_round - recent_rounds
        
        # 获取近况比赛（轮次号大于阈值的比赛）
        recent_home = home_matches[home_matches['round_number'] > recent_threshold]
        recent_away = away_matches[away_matches['round_number'] > recent_threshold]
        
        # 计算近况主场平均不败率
        if not recent_home.empty:
            recent_home_avg = recent_home['home_team_unbeaten_rate'].mean()
        else:
            recent_home_avg = 0.0
        
        # 计算近况客场平均不败率
        if not recent_away.empty:
            recent_away_avg = recent_away['away_team_unbeaten_rate'].mean()
        else:
            recent_away_avg = 0.0
        
        # 近况实力 = 近况主场不败率 + 近况客场不败率
        return recent_home_avg + recent_away_avg
    
    def _calculate_guangyishili_relative_powers(self, teams_df: pd.DataFrame) -> Dict:
        """按照guangyishili算法计算相对实力和等级分类"""
        if teams_df.empty:
            return {}
        
        # 用第5百分位数作为参考基准，而非绝对最小值。
        # 这样能防止单支极端弱队（如仅有个位数不败率的队伍）把全联赛的
        # relative_power 拉大，导致其他所有队伍都虚高到"超强"档位。
        # 对于正常联赛（各队实力分布均匀），第5百分位接近绝对最小值，几乎不影响结果；
        # 仅当存在明显离群弱队时才会生效。
        min_power = float(teams_df['combined_power'].quantile(0.05))
        
        team_powers = {}
        
        # 为每个球队计算相对实力和等级
        for team_id, team_data in teams_df.iterrows():
            combined_power = team_data['combined_power']
            
            # 相对实力 = 综合实力 - 参考基准（低于基准的队伍相对实力为0）
            relative_power = max(0.0, combined_power - min_power)
            
            # 档距 = 相对实力 / 10.5 (保留1位小数)
            power_level = round(relative_power / 10.5, 1)
            
            # 等级分类
            def categorize_team(power_level):
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
            
            tier_level = categorize_team(power_level)

            # 场次可信度标记：赛季初场次不足时强度值仅供参考
            # < 6场: 赛季初，数据波动大
            # 6~11场: 约赛季前1/3，基本可参考
            # >= 12场: 数据稳定，可信
            mc = int(team_data['matches_count'])
            if mc < 6:
                data_confidence = 'low'      # 赛季初，参考
            elif mc < 12:
                data_confidence = 'medium'   # 赛季前段，可参考
            else:
                data_confidence = 'high'     # 数据稳定

            # 构建完整的团队数据，保持与数据库字段一致
            team_powers[team_id] = {
                'team_name': team_data['team_name'],
                'total_power': team_data['total_power'],
                'recent_power': team_data['recent_power'],
                'combined_power': combined_power,
                'relative_power': relative_power,
                'power_level': power_level,        # 档距
                'tier_distance': relative_power,   # 相对实力（兼容字段）
                'tier_level': tier_level,          # 等级分类
                'level_class': tier_level,         # 等级分类（兼容字段）
                'matches_count': mc,
                'data_confidence': data_confidence,  # low/medium/high
            }
        
        return team_powers
