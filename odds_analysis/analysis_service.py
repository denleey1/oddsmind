#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
赔率分析核心服务
封装所有赔率分析的算法和业务逻辑
"""
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import bisect
from decimal import Decimal, InvalidOperation

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.logger import get_logger

class AnalysisService:
    """
    提供赔率分析的核心算法和业务逻辑。
    这是一个无状态的服务，不直接与数据库交互。
    """
    def __init__(self, standard_odds_win: List[Dict], standard_odds_loss: List[Dict],
                 rule_conditions_home: List[Dict], rule_conditions_away: List[Dict],
                 rule_outcomes: List[Dict]):
        self.logger = get_logger(self.__class__.__name__)
        
        # 将参照表和规则缓存在实例中
        self.standard_odds_by_win = standard_odds_win
        self.standard_odds_by_loss = standard_odds_loss
        self.rule_conditions_home = rule_conditions_home
        self.rule_conditions_away = rule_conditions_away
        self.rule_outcomes = rule_outcomes

    def analyze_company_odds(self, odds_data: Dict, power_diff: float) -> Optional[Dict]:
        """
        对单个公司的赔率数据进行完整分析
        """
        try:
            company_name = odds_data.get('company_name', 'Unknown')
            self.logger.debug(f"[{company_name}] 开始分析。赔率: {odds_data}, 实力差: {power_diff}")

            # 检查关键赔率数据是否存在
            if odds_data.get('initial_home') is None or odds_data.get('initial_away') is None:
                self.logger.debug(f"[{company_name}] 缺少初始赔率，跳过分析。")
                return None

            # 计算满水赔率
            fullwater = self._calculate_fullwater(odds_data)
            self.logger.debug(f"[{company_name}] 满水赔率: {fullwater}")

            # 使用原有的分析逻辑
            initial_analysis = self._perform_single_analysis(
                float(fullwater['initial_home']), 
                float(fullwater['initial_away']), 
                power_diff
            )
            
            current_analysis = self._perform_single_analysis(
                float(fullwater['current_home']), 
                float(fullwater['current_away']), 
                power_diff
            )

            self.logger.debug(f"[{company_name}] 初始分析: RuleDiff={initial_analysis['rule_diff']}, Outcome={initial_analysis['recommendation']['outcome']}, Confidence={initial_analysis['recommendation']['confidence']}")
            self.logger.debug(f"[{company_name}] 即时分析: RuleDiff={current_analysis['rule_diff']}, Outcome={current_analysis['recommendation']['outcome']}, Confidence={current_analysis['recommendation']['confidence']}")

            # 只有在有推荐结果时才返回分析数据
            if initial_analysis['recommendation']['outcome'] != 'uncertain' or current_analysis['recommendation']['outcome'] != 'uncertain':
                self.logger.info(f"[{company_name}] 生成有效分析结果！")
                return {
                    'company_id': odds_data['company_id'],
                    'company_name': odds_data['company_name'],
                    'home_power': odds_data.get('home_power'),
                    'away_power': odds_data.get('away_power'),
                    'power_diff': power_diff,
                    **fullwater,
                    'initial_analysis': initial_analysis,
                    'current_analysis': current_analysis,
                    'draw_analysis': {
                        'initial_standard_draw': self._find_standard_draw_odds(fullwater['initial_home'], fullwater['initial_away']),
                        'initial_draw_range': self._get_draw_range(fullwater['initial_draw'], self._find_standard_draw_odds(fullwater['initial_home'], fullwater['initial_away'])),
                        'current_standard_draw': self._find_standard_draw_odds(fullwater['current_home'], fullwater['current_away']),
                        'current_draw_range': self._get_draw_range(fullwater['current_draw'], self._find_standard_draw_odds(fullwater['current_home'], fullwater['current_away']))
                    }
                }

            return None
        except Exception as e:
            self.logger.error(f"分析公司 {odds_data.get('company_name')} 赔率时出错: {e}", exc_info=True)
            return None

    def _perform_single_analysis(self, home_odds: float, away_odds: float, power_diff: float) -> Dict:
        """执行单次（初盘或即时）的胜平负分析"""
        home_theory = self._find_theory_distance(home_odds, 'home')
        away_theory = self._find_theory_distance(away_odds, 'away')
        
        home_offset = home_theory - power_diff
        away_offset = away_theory - power_diff
        
        home_rule = self._match_rule(home_offset, 'home')
        away_rule = self._match_rule(away_offset, 'away')
        
        rule_diff = home_rule['rule_value'] - away_rule['rule_value']
        recommendation = self._get_recommendation(rule_diff, power_diff)
        
        return {
            'home_theory_distance': home_theory,
            'away_theory_distance': away_theory,
            'home_offset': home_offset,
            'away_offset': away_offset,
            'home_rule': home_rule,
            'away_rule': away_rule,
            'rule_diff': rule_diff,
            'recommendation': recommendation
        }

    def _perform_draw_analysis(self, fullwater: Dict) -> Dict:
        """执行平赔分析"""
        initial_std_draw = self._find_standard_draw_odds(fullwater['initial_home'], fullwater['initial_away'])
        current_std_draw = self._find_standard_draw_odds(fullwater['current_home'], fullwater['current_away'])
        
        return {
            'initial_standard_draw': initial_std_draw,
            'initial_draw_range': self._get_draw_range(fullwater['initial_draw'], initial_std_draw),
            'current_standard_draw': current_std_draw,
            'current_draw_range': self._get_draw_range(fullwater['current_draw'], current_std_draw)
        }

    def _calculate_fullwater(self, odds_data: Dict) -> Optional[Dict]:
        """计算满水赔率"""
        try:
            # 确保所有参与计算的都是Decimal类型
            initial_home = Decimal(odds_data.get('initial_home', 0))
            initial_draw = Decimal(odds_data.get('initial_draw', 0))
            initial_away = Decimal(odds_data.get('initial_away', 0))
            initial_return_rate = odds_data.get('initial_return_rate')

            current_home = Decimal(odds_data.get('current_home', 0))
            current_draw = Decimal(odds_data.get('current_draw', 0))
            current_away = Decimal(odds_data.get('current_away', 0))
            current_return_rate = odds_data.get('current_return_rate')

            if not all([initial_home, initial_draw, initial_away, current_home, current_draw, current_away]):
                return None

            # 如果初始返还率为None，则根据赔率计算
            if initial_return_rate is None:
                if initial_home > 0 and initial_draw > 0 and initial_away > 0:
                    initial_return = Decimal(1) / (Decimal(1)/initial_home + Decimal(1)/initial_draw + Decimal(1)/initial_away)
                else:
                    initial_return = Decimal(0)
            else:
                initial_return = Decimal(initial_return_rate) / Decimal(100)

            # 如果即时返还率为None，则根据赔率计算
            if current_return_rate is None:
                if current_home > 0 and current_draw > 0 and current_away > 0:
                    current_return = Decimal(1) / (Decimal(1)/current_home + Decimal(1)/current_draw + Decimal(1)/current_away)
                else:
                    current_return = Decimal(0)
            else:
                current_return = Decimal(current_return_rate) / Decimal(100)
            
            if initial_return == 0 or current_return == 0:
                return None

            return {
                'initial_home': initial_home / initial_return,
                'initial_draw': initial_draw / initial_return,
                'initial_away': initial_away / initial_return,
                'current_home': current_home / current_return,
                'current_draw': current_draw / current_return,
                'current_away': current_away / current_return
            }
        except (InvalidOperation, TypeError) as e:
            self.logger.error(f"计算满水赔率时发生类型转换错误: {e}")
            return None

    def _find_theory_distance(self, target_odds: float, odds_type: str) -> float:
        """使用二分查找找到最接近的理论distance值"""
        odds_list, key_field = (self.standard_odds_by_win, 'win_odds') if odds_type == 'home' else (self.standard_odds_by_loss, 'odds')
        if not odds_list: return 0.0
        
        # bisect_left找到插入点
        keys = [item[key_field] for item in odds_list]
        idx = bisect.bisect_left(keys, float(target_odds))
        
        # 确定最近的项
        if idx == 0:
            return odds_list[0]['distance']
        if idx == len(odds_list):
            return odds_list[-1]['distance']
        
        before = odds_list[idx - 1]
        after = odds_list[idx]
        if abs(before[key_field] - float(target_odds)) < abs(after[key_field] - float(target_odds)):
            return before['distance']
        else:
            return after['distance']

    def _match_rule(self, offset: float, team_type: str) -> Dict:
        """根据偏移值匹配规则"""
        conditions = self.rule_conditions_home if team_type == 'home' else self.rule_conditions_away
        for condition in conditions:
            if condition['range_low'] <= offset <= condition['range_high']:
                return {'description': condition['description'], 'rule_value': condition['rule_value']}
        return {'description': 'unknown', 'rule_value': 0}

    def _get_recommendation(self, rule_diff: float, power_diff: float) -> Dict:
        """根据规则差值和广义实力差获取推荐结果"""
        use_ge_minus_1_5 = (power_diff >= -1.5)
        
        if not self.rule_outcomes:
            return {'outcome': 'uncertain', 'confidence': 'low'}

        # 找到最接近的规则
        closest = min(self.rule_outcomes, key=lambda x: abs(float(x['rule_value_diff']) - rule_diff))
        
        outcome_key = 'outcome_if_ge_minus_1_5' if use_ge_minus_1_5 else 'outcome_if_lt_minus_1_5'
        
        # 判断置信度
        is_exact_match = abs(float(closest['rule_value_diff']) - rule_diff) < 1e-9
        confidence = 'high' if is_exact_match else 'medium'

        return {'outcome': closest[outcome_key], 'confidence': confidence}

    def _find_standard_draw_odds(self, home_odds: float, away_odds: float) -> float:
        """根据主客满水赔率找到标准平赔"""
        min_odds = min(float(home_odds), float(away_odds))
        odds_list, key_field = (self.standard_odds_by_win, 'win_odds') if min_odds == float(home_odds) else (self.standard_odds_by_loss, 'odds')
        
        if not odds_list: return 3.325

        keys = [item[key_field] for item in odds_list]
        idx = bisect.bisect_left(keys, min_odds)
        
        if idx == 0: return odds_list[0]['draw_odds']
        if idx == len(odds_list): return odds_list[-1]['draw_odds']
        
        before, after = odds_list[idx - 1], odds_list[idx]
        if abs(before[key_field] - min_odds) < abs(after[key_field] - min_odds):
            return before['draw_odds']
        else:
            return after['draw_odds']

    def _get_draw_range(self, draw_odds: float, standard_draw: float) -> str:
        """根据平局满水赔率和标准平赔确定区间"""
        coefficients = [
            (0.77, "超深平"), (0.84, "超散平"), (0.90, "超实平"), (0.95, "低开平"),
            (0.99, "平实低"), (1.00, "平中庸下"), (1.01, "平中庸上"), (1.05, "平实高"),
            (1.10, "高开平"), (1.16, "韬光平")
        ]
        for coeff, name in coefficients:
            if draw_odds < standard_draw * coeff:
                return name
        return "超韬平"

    def _get_rule_details(self, rule: Optional[Dict], value_key: str) -> Tuple[Optional[str], Optional[float]]:
        """从规则中提取规则值和范围"""
        if rule is None:
            return None, None
        
        # 适配我们的规则结构，直接使用rule_value字段
        rule_value = rule.get('rule_value')
        if rule_value is not None:
            if value_key in ['initial_home_value', 'current_home_value']:
                return 'home', float(rule_value)
            elif value_key in ['initial_away_value', 'current_away_value']:
                return 'away', float(rule_value)
        
        return None, None

    def _calculate_rule_diff(self, home_rule_value: float, away_rule_value: float) -> Optional[float]:
        """计算规则差值"""
        if home_rule_value is None or away_rule_value is None:
            return None
        return home_rule_value - away_rule_value

    def _determine_recommendation(self, rule_diff: Optional[float], home_rule: Optional[Dict], away_rule: Optional[Dict], outcome_rule: Optional[Dict]) -> Tuple[Optional[str], Optional[str], Optional[Dict]]:
        if rule_diff is None or home_rule is None or away_rule is None:
            return None, None, None

        # 赛果规则从外部传入
        if not outcome_rule:
            return None, None, None

        # 使用历史文件的逻辑：根据规则差值获取推荐结果
        # 假设power_diff为0（简化处理）
        power_diff = 0.0
        use_ge_minus_1_5 = (power_diff >= -1.5)
        
        if use_ge_minus_1_5:
            outcome = outcome_rule.get('outcome_if_ge_minus_1_5', 'uncertain')
        else:
            outcome = outcome_rule.get('outcome_if_lt_minus_1_5', 'uncertain')
        
        # 简化的置信度判断
        if abs(rule_diff) >= 2.0:
            confidence = 'high'
        elif abs(rule_diff) >= 1.0:
            confidence = 'medium'
        else:
            confidence = 'low'
            
        return outcome, confidence, outcome_rule

    def _assign_confidence(self, diff: float, threshold: float) -> str:
        """根据差异和阈值的比率分配置信水平"""
        if threshold == 0:
            return 'high' # 防止除以零
        ratio = diff / threshold
        if ratio < 0.5:
            return 'high'
        elif ratio < 1.0:
            return 'medium'
        else:
            return 'low'
 