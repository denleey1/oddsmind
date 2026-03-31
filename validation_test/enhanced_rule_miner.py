#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
增强版规则挖掘器 v3.0
=======================
基于3000+场已完成比赛数据，深度挖掘赔率组合规律

特征维度：
1. 盘型特征: 初盘/即时 主胜、平局、客胜 的区间类型
2. 赔率变化: 初赔→终赔 的变化方向和幅度
3. Kelly系数: 三项Kelly值的分布
4. 返还率变化: 返还率升降
5. 让球方视角: 统一转换为让方/受让方分析
6. 联赛分层: 五大联赛 vs 其他联赛
7. 赔率差值: 初盘rule_diff的分布
8. 力量差异: power_diff的分布

输出：
- 高准确率规则列表 (≥80%)
- 各维度特征分布统计
- 具体规则及样本数据
"""
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
import json

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

# ==================== 配置 ====================
MIN_SAMPLE_SIZE = 3  # 最小样本数
MIN_ACCURACY = 0.75   # 最小准确率
COMPANY_ID = '115'   # 威廉公司

# 五大联赛
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
BIG5_NAMES = {36: '英超', 31: '西甲', 34: '意甲', 8: '德甲', 11: '法甲'}

# 盘型前缀映射
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


# ==================== 工具函数 ====================

def get_range_type(range_str: str) -> Optional[str]:
    """提取盘面类型前缀（如 韬光、实开等）"""
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def get_water_level(range_str: str) -> Optional[str]:
    """提取水位（如 低水、中水、高水等）"""
    if not range_str:
        return None
    waters = ['超低水', '低水', '中低水', '中水', '中高水', '高水', '超高水', '中下水', '中上水']
    for w in waters:
        if w in range_str:
            return w
    return '中水'


def get_draw_range_type(range_str: str) -> Optional[str]:
    """提取平局盘型（如 低开平、超实平等）"""
    if not range_str:
        return None
    return range_str


def classify_odds_change(init: float, curr: float) -> str:
    """分类赔率变化: 升、降、稳"""
    if curr > init * 1.05:
        return '升'
    elif curr < init * 0.95:
        return '降'
    return '稳'


def classify_kelly(kelly: float) -> str:
    """分类Kelly系数"""
    if kelly is None:
        return '未知'
    if kelly < 0.85:
        return '低Kelly'
    elif kelly < 0.95:
        return '中Kelly'
    elif kelly < 1.05:
        return '正常Kelly'
    else:
        return '高Kelly'


def classify_power_diff(diff: float) -> str:
    """分类力量差"""
    if diff is None:
        return '未知'
    if diff > 2:
        return '强让'
    elif diff > 0.5:
        return '微让'
    elif diff > -0.5:
        return '平手'
    elif diff > -2:
        return '微受'
    else:
        return '强受'


def classify_rule_diff(diff: float) -> str:
    """分类规则差"""
    if diff is None:
        return '未知'
    if diff < -2:
        return '大负'
    elif diff < -0.5:
        return '小负'
    elif diff < 0.5:
        return '平衡'
    elif diff < 2:
        return '小正'
    else:
        return '大正'


# ==================== 数据加载 ====================

def load_match_data() -> List[Dict]:
    """加载已完成比赛的详细数据"""
    db = get_connection()
    
    query = '''
        SELECT 
            oar.match_id,
            oar.company_id,
            oar.initial_home_range, oar.initial_away_range, oar.initial_draw_range,
            oar.current_home_range, oar.current_away_range, oar.current_draw_range,
            oar.initial_home_rule_value, oar.initial_away_rule_value, oar.initial_rule_diff,
            oar.current_home_rule_value, oar.current_away_rule_value, oar.current_rule_diff,
            oar.power_diff, oar.home_power_level, oar.away_power_level,
            m.home_team_name, m.away_team_name, 
            m.home_score, m.away_score, m.match_time,
            l.league_id, l.name_cn as league_name,
            eo.initial_home, eo.initial_draw, eo.initial_away,
            eo.current_home, eo.current_draw, eo.current_away,
            eo.kelly_home, eo.kelly_draw, eo.kelly_away,
            eo.initial_return_rate, eo.current_return_rate
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        JOIN european_odds eo ON oar.match_id = eo.match_id AND oar.company_id = eo.company_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = %s
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
    '''
    
    return db.execute_query(query, (COMPANY_ID,), fetch='all')


def process_match(row: Dict) -> Dict:
    """处理单场比赛，提取所有特征"""
    init_home = float(row['initial_home'])
    init_draw = float(row['initial_draw'])
    init_away = float(row['initial_away'])
    curr_home = float(row['current_home'])
    curr_draw = float(row['current_draw'])
    curr_away = float(row['current_away'])
    
    # 判断让球方（初赔小者为让球方）
    if init_home <= init_away:
        handicap_side = 'home'
        h_score, r_score = row['home_score'], row['away_score']
        init_h_range = row['initial_home_range']
        init_r_range = row['initial_away_range']
        curr_h_range = row['current_home_range']
        curr_r_range = row['current_away_range']
        handicap_team = row['home_team_name']
        receiver_team = row['away_team_name']
        init_h_odds, init_r_odds = init_home, init_away
        curr_h_odds, curr_r_odds = curr_home, curr_away
        kelly_h, kelly_r = row['kelly_home'], row['kelly_away']
    else:
        handicap_side = 'away'
        h_score, r_score = row['away_score'], row['home_score']
        init_h_range = row['initial_away_range']
        init_r_range = row['initial_home_range']
        curr_h_range = row['current_away_range']
        curr_r_range = row['current_home_range']
        handicap_team = row['away_team_name']
        receiver_team = row['home_team_name']
        init_h_odds, init_r_odds = init_away, init_home
        curr_h_odds, curr_r_odds = curr_away, curr_home
        kelly_h, kelly_r = row['kelly_away'], row['kelly_home']
    
    # 赛果判断（让球方视角）
    if h_score > r_score:
        result = 'handicap_win'
        result_cn = '让方胜'
    elif h_score == r_score:
        result = 'draw'
        result_cn = '平'
    else:
        result = 'receiver_win'
        result_cn = '受让胜'
    
    # 提取所有特征
    features = {
        # 基础信息
        'match_id': row['match_id'],
        'league_id': row['league_id'],
        'league_name': row['league_name'],
        'home_team': row['home_team_name'],
        'away_team': row['away_team_name'],
        'handicap_team': handicap_team,
        'receiver_team': receiver_team,
        'handicap_side': handicap_side,
        'match_time': row['match_time'],
        
        # 比分
        'home_score': row['home_score'],
        'away_score': row['away_score'],
        'h_score': h_score,  # 让球方得分
        'r_score': r_score,  # 受让方得分
        'result': result,
        'result_cn': result_cn,
        
        # 联赛分类
        'is_big5': row['league_id'] in BIG5_LEAGUE_IDS,
        
        # 盘型特征 - 让球方视角
        'init_h_type': get_range_type(init_h_range),
        'init_r_type': get_range_type(init_r_range),
        'curr_h_type': get_range_type(curr_h_range),
        'curr_r_type': get_range_type(curr_r_range),
        
        # 原始盘型（不转换）
        'init_home_type': get_range_type(row['initial_home_range']),
        'init_away_type': get_range_type(row['initial_away_range']),
        'curr_home_type': get_range_type(row['current_home_range']),
        'curr_away_type': get_range_type(row['current_away_range']),
        
        # 平局盘型
        'init_draw_range': row['initial_draw_range'],
        'curr_draw_range': row['current_draw_range'],
        
        # 水位
        'init_h_water': get_water_level(init_h_range),
        'init_r_water': get_water_level(init_r_range),
        'curr_h_water': get_water_level(curr_h_range),
        'curr_r_water': get_water_level(curr_r_range),
        
        # 赔率变化
        'h_odds_change': classify_odds_change(init_h_odds, curr_h_odds),
        'r_odds_change': classify_odds_change(init_r_odds, curr_r_odds),
        'draw_odds_change': classify_odds_change(init_draw, curr_draw),
        
        # Kelly系数
        'kelly_h': classify_kelly(float(kelly_h) if kelly_h else None),
        'kelly_r': classify_kelly(float(kelly_r) if kelly_r else None),
        'kelly_draw': classify_kelly(float(row['kelly_draw']) if row['kelly_draw'] else None),
        
        # 力量差 & 规则差
        'power_diff': float(row['power_diff']) if row['power_diff'] else None,
        'power_class': classify_power_diff(float(row['power_diff']) if row['power_diff'] else None),
        'init_rule_diff': float(row['initial_rule_diff']) if row['initial_rule_diff'] else None,
        'curr_rule_diff': float(row['current_rule_diff']) if row['current_rule_diff'] else None,
        'init_rule_class': classify_rule_diff(float(row['initial_rule_diff']) if row['initial_rule_diff'] else None),
        'curr_rule_class': classify_rule_diff(float(row['current_rule_diff']) if row['current_rule_diff'] else None),
        
        # 返还率变化
        'return_rate_change': '升' if row['current_return_rate'] and row['initial_return_rate'] 
                              and float(row['current_return_rate']) > float(row['initial_return_rate']) + 0.5 
                              else ('降' if row['current_return_rate'] and row['initial_return_rate']
                                    and float(row['current_return_rate']) < float(row['initial_return_rate']) - 0.5 
                                    else '稳'),
    }
    
    return features


# ==================== 规则检查函数 ====================

def check_handicap_win(m: Dict) -> bool:
    """让方胜"""
    return m['h_score'] > m['r_score']


def check_handicap_not_lose(m: Dict) -> bool:
    """让方不输（胜或平）"""
    return m['h_score'] >= m['r_score']


def check_receiver_win(m: Dict) -> bool:
    """受让方胜"""
    return m['h_score'] < m['r_score']


def check_receiver_not_lose(m: Dict) -> bool:
    """受让方不输（胜或平）"""
    return m['h_score'] <= m['r_score']


def check_draw(m: Dict) -> bool:
    """平局"""
    return m['h_score'] == m['r_score']


# ==================== 规则挖掘 ====================

class RuleMiner:
    """规则挖掘器"""
    
    def __init__(self, min_sample: int = MIN_SAMPLE_SIZE, min_accuracy: float = MIN_ACCURACY):
        self.min_sample = min_sample
        self.min_accuracy = min_accuracy
        self.matches = []
        self.rules_found = []
        
    def load_data(self):
        """加载数据"""
        print("=" * 100)
        print("📊 增强版规则挖掘器 v3.0")
        print("=" * 100)
        print()
        
        raw_data = load_match_data()
        print(f"✅ 加载原始数据: {len(raw_data)} 场比赛")
        
        self.matches = [process_match(row) for row in raw_data]
        
        # 统计分布
        big5_count = sum(1 for m in self.matches if m['is_big5'])
        print(f"   - 五大联赛: {big5_count} 场")
        print(f"   - 其他联赛: {len(self.matches) - big5_count} 场")
        print()
        
    def mine_partial_rules(self):
        """挖掘部分特征规则"""
        print("=" * 100)
        print("【1. 部分特征规则挖掘】")
        print("=" * 100)
        
        # 定义要检查的规则
        partial_rules = [
            # === 让球方视角规则 ===
            {
                'name': '即时让方韬光盘',
                'condition': lambda m: m['curr_h_type'] == '韬光',
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            {
                'name': '即时让方超韬盘',
                'condition': lambda m: m['curr_h_type'] == '超韬',
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            {
                'name': '初双实开→即时让方低开+受让方高开',
                'condition': lambda m: (m['init_h_type'] == '实开' and m['init_r_type'] == '实开' and
                                        m['curr_h_type'] == '低开' and m['curr_r_type'] == '高开'),
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            {
                'name': '初让方低开+受让方高开→即时双实开',
                'condition': lambda m: (m['init_h_type'] == '低开' and m['init_r_type'] == '高开' and
                                        m['curr_h_type'] == '实开' and m['curr_r_type'] == '实开'),
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            {
                'name': '初双实开→即时让方高开+受让方低开',
                'condition': lambda m: (m['init_h_type'] == '实开' and m['init_r_type'] == '实开' and
                                        m['curr_h_type'] == '高开' and m['curr_r_type'] == '低开'),
                'predict_fn': check_handicap_not_lose,
                'predict_name': '让方不输',
            },
            {
                'name': '初让方超实+受让方韬光→即时让方低开+受让方韬光',
                'condition': lambda m: (m['init_h_type'] == '超实' and m['init_r_type'] == '韬光' and
                                        m['curr_h_type'] == '低开' and m['curr_r_type'] == '韬光'),
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            # === 平局相关规则 ===
            {
                'name': '初双实开+低开平',
                'condition': lambda m: (m['init_home_type'] == '实开' and m['init_away_type'] == '实开' and
                                        m['init_draw_range'] and m['init_draw_range'].startswith('低开平')),
                'predict_fn': check_handicap_not_lose,
                'predict_name': '让方不输',
            },
            {
                'name': '初双实开+超实平',
                'condition': lambda m: (m['init_home_type'] == '实开' and m['init_away_type'] == '实开' and
                                        m['init_draw_range'] and m['init_draw_range'].startswith('超实平')),
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            # === 赔率变化规则 ===
            {
                'name': '让方赔率升+受让方赔率降',
                'condition': lambda m: m['h_odds_change'] == '升' and m['r_odds_change'] == '降',
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            {
                'name': '让方赔率降+受让方赔率升',
                'condition': lambda m: m['h_odds_change'] == '降' and m['r_odds_change'] == '升',
                'predict_fn': check_handicap_not_lose,
                'predict_name': '让方不输',
            },
            {
                'name': '让方低Kelly',
                'condition': lambda m: m['kelly_h'] == '低Kelly',
                'predict_fn': check_handicap_not_lose,
                'predict_name': '让方不输',
            },
            {
                'name': '受让方低Kelly',
                'condition': lambda m: m['kelly_r'] == '低Kelly',
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            # === 力量差规则 ===
            {
                'name': '强让+即时让方韬光',
                'condition': lambda m: m['power_class'] == '强让' and m['curr_h_type'] == '韬光',
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
            {
                'name': '平手盘+让方赔率升',
                'condition': lambda m: m['power_class'] == '平手' and m['h_odds_change'] == '升',
                'predict_fn': check_receiver_not_lose,
                'predict_name': '受让方不输',
            },
        ]
        
        print(f"\n{'规则名称':<50} {'预测':<15} {'样本':>6} {'命中':>6} {'准确率':>8} {'五大联赛':>15}")
        print('-' * 110)
        
        high_acc_rules = []
        
        for rule in partial_rules:
            stats = {'total': 0, 'correct': 0, 'big5': 0, 'big5_c': 0, 'matches': []}
            
            for m in self.matches:
                try:
                    if rule['condition'](m):
                        stats['total'] += 1
                        stats['matches'].append(m)
                        if m['is_big5']:
                            stats['big5'] += 1
                        if rule['predict_fn'](m):
                            stats['correct'] += 1
                            if m['is_big5']:
                                stats['big5_c'] += 1
                except Exception:
                    continue
            
            if stats['total'] >= self.min_sample:
                acc = stats['correct'] / stats['total']
                big5_str = f"{stats['big5_c']}/{stats['big5']}={stats['big5_c']/stats['big5']*100:.1f}%" if stats['big5'] > 0 else '-'
                
                status = '✅' if acc >= self.min_accuracy else ('⚠️' if acc >= 0.65 else '❌')
                print(f"{status} {rule['name']:<48} {rule['predict_name']:<15} {stats['total']:>6} {stats['correct']:>6} {acc*100:>7.1f}% {big5_str:>15}")
                
                if acc >= self.min_accuracy:
                    high_acc_rules.append({
                        'name': rule['name'],
                        'predict': rule['predict_name'],
                        'accuracy': acc,
                        'total': stats['total'],
                        'correct': stats['correct'],
                        'big5_acc': stats['big5_c']/stats['big5'] if stats['big5'] > 0 else None,
                    })
        
        self.rules_found.extend(high_acc_rules)
        return high_acc_rules
    
    def mine_combo_rules(self):
        """挖掘组合特征规则 (5特征精确匹配)"""
        print()
        print("=" * 100)
        print("【2. 5特征组合规则挖掘】初让方+初受让+初平+即让方+即受让")
        print("=" * 100)
        
        # 统计组合
        combo_stats = defaultdict(lambda: {'win': 0, 'draw': 0, 'lose': 0, 
                                            'big5_win': 0, 'big5_draw': 0, 'big5_lose': 0,
                                            'matches': []})
        
        for m in self.matches:
            combo = (m['init_h_type'], m['init_r_type'], m['init_draw_range'], 
                     m['curr_h_type'], m['curr_r_type'])
            
            if m['h_score'] > m['r_score']:
                combo_stats[combo]['win'] += 1
                if m['is_big5']:
                    combo_stats[combo]['big5_win'] += 1
            elif m['h_score'] == m['r_score']:
                combo_stats[combo]['draw'] += 1
                if m['is_big5']:
                    combo_stats[combo]['big5_draw'] += 1
            else:
                combo_stats[combo]['lose'] += 1
                if m['is_big5']:
                    combo_stats[combo]['big5_lose'] += 1
            combo_stats[combo]['matches'].append(m)
        
        # 挖掘让方必赢规则
        print(f"\n【让方必赢】≥{self.min_accuracy*100:.0f}% (样本≥{self.min_sample})")
        print(f"{'初让方':<8} {'初受让':<8} {'初平':<12} {'即让方':<8} {'即受让':<8} | {'样本':>6} {'胜':>4} {'平':>4} {'负':>4} {'准确率':>8}")
        print('-' * 95)
        
        win_rules = []
        for combo, stats in sorted(combo_stats.items(), 
                                    key=lambda x: x[1]['win']/(x[1]['win']+x[1]['draw']+x[1]['lose']) if (x[1]['win']+x[1]['draw']+x[1]['lose']) >= self.min_sample else 0,
                                    reverse=True):
            total = stats['win'] + stats['draw'] + stats['lose']
            if total >= self.min_sample:
                win_rate = stats['win'] / total
                if win_rate >= self.min_accuracy:
                    print(f"{combo[0] or '-':<8} {combo[1] or '-':<8} {(combo[2] or '-'):<12} {combo[3] or '-':<8} {combo[4] or '-':<8} | {total:>6} {stats['win']:>4} {stats['draw']:>4} {stats['lose']:>4} {win_rate*100:>7.1f}%")
                    win_rules.append({
                        'combo': combo,
                        'predict': '让方必赢',
                        'accuracy': win_rate,
                        'total': total,
                        'correct': stats['win'],
                    })
        
        if not win_rules:
            print("（无符合条件的组合）")
        
        # 挖掘受让方不输规则
        print(f"\n【受让方不输】≥{self.min_accuracy*100:.0f}% (样本≥{self.min_sample})")
        print(f"{'初让方':<8} {'初受让':<8} {'初平':<12} {'即让方':<8} {'即受让':<8} | {'样本':>6} {'胜':>4} {'平':>4} {'负':>4} {'准确率':>8}")
        print('-' * 95)
        
        down_rules = []
        for combo, stats in sorted(combo_stats.items(),
                                    key=lambda x: (x[1]['draw']+x[1]['lose'])/(x[1]['win']+x[1]['draw']+x[1]['lose']) if (x[1]['win']+x[1]['draw']+x[1]['lose']) >= self.min_sample else 0,
                                    reverse=True):
            total = stats['win'] + stats['draw'] + stats['lose']
            if total >= self.min_sample:
                not_win_rate = (stats['draw'] + stats['lose']) / total
                if not_win_rate >= self.min_accuracy:
                    print(f"{combo[0] or '-':<8} {combo[1] or '-':<8} {(combo[2] or '-'):<12} {combo[3] or '-':<8} {combo[4] or '-':<8} | {total:>6} {stats['win']:>4} {stats['draw']:>4} {stats['lose']:>4} {not_win_rate*100:>7.1f}%")
                    down_rules.append({
                        'combo': combo,
                        'predict': '受让方不输',
                        'accuracy': not_win_rate,
                        'total': total,
                        'correct': stats['draw'] + stats['lose'],
                    })
        
        if not down_rules:
            print("（无符合条件的组合）")
        
        # 挖掘让方不输规则
        print(f"\n【让方不输】≥{self.min_accuracy*100:.0f}% (样本≥{self.min_sample})")
        print(f"{'初让方':<8} {'初受让':<8} {'初平':<12} {'即让方':<8} {'即受让':<8} | {'样本':>6} {'胜':>4} {'平':>4} {'负':>4} {'准确率':>8}")
        print('-' * 95)
        
        up_rules = []
        for combo, stats in sorted(combo_stats.items(),
                                    key=lambda x: (x[1]['win']+x[1]['draw'])/(x[1]['win']+x[1]['draw']+x[1]['lose']) if (x[1]['win']+x[1]['draw']+x[1]['lose']) >= self.min_sample else 0,
                                    reverse=True):
            total = stats['win'] + stats['draw'] + stats['lose']
            if total >= self.min_sample:
                not_lose_rate = (stats['win'] + stats['draw']) / total
                if not_lose_rate >= self.min_accuracy:
                    print(f"{combo[0] or '-':<8} {combo[1] or '-':<8} {(combo[2] or '-'):<12} {combo[3] or '-':<8} {combo[4] or '-':<8} | {total:>6} {stats['win']:>4} {stats['draw']:>4} {stats['lose']:>4} {not_lose_rate*100:>7.1f}%")
                    up_rules.append({
                        'combo': combo,
                        'predict': '让方不输',
                        'accuracy': not_lose_rate,
                        'total': total,
                        'correct': stats['win'] + stats['draw'],
                    })
        
        if not up_rules:
            print("（无符合条件的组合）")
        
        print()
        print(f"统计: 让方必赢组合 {len(win_rules)} 个, 受让方不输组合 {len(down_rules)} 个, 让方不输组合 {len(up_rules)} 个")
        
        return win_rules, down_rules, up_rules
    
    def mine_multi_dimension_rules(self):
        """多维度交叉规则挖掘"""
        print()
        print("=" * 100)
        print("【3. 多维度交叉规则挖掘】")
        print("=" * 100)
        
        # 定义维度组合
        dimensions = [
            ('curr_h_type', '即时让方盘型'),
            ('curr_r_type', '即时受让方盘型'),
            ('h_odds_change', '让方赔率变化'),
            ('r_odds_change', '受让方赔率变化'),
            ('kelly_h', '让方Kelly'),
            ('power_class', '力量差'),
            ('init_rule_class', '初盘规则差'),
            ('is_big5', '五大联赛'),
        ]
        
        high_acc_combos = []
        
        # 两两组合分析
        for i, (dim1, name1) in enumerate(dimensions):
            for dim2, name2 in dimensions[i+1:]:
                combo_stats = defaultdict(lambda: {'h_win': 0, 'draw': 0, 'r_win': 0, 'total': 0})
                
                for m in self.matches:
                    val1 = m.get(dim1)
                    val2 = m.get(dim2)
                    if val1 is None or val2 is None:
                        continue
                    
                    key = (val1, val2)
                    combo_stats[key]['total'] += 1
                    if m['h_score'] > m['r_score']:
                        combo_stats[key]['h_win'] += 1
                    elif m['h_score'] == m['r_score']:
                        combo_stats[key]['draw'] += 1
                    else:
                        combo_stats[key]['r_win'] += 1
                
                # 检查高准确率组合
                for key, stats in combo_stats.items():
                    if stats['total'] >= self.min_sample:
                        # 让方不输
                        h_not_lose = (stats['h_win'] + stats['draw']) / stats['total']
                        if h_not_lose >= self.min_accuracy:
                            high_acc_combos.append({
                                'dims': f"{name1}={key[0]} + {name2}={key[1]}",
                                'predict': '让方不输',
                                'accuracy': h_not_lose,
                                'total': stats['total'],
                            })
                        
                        # 受让方不输
                        r_not_lose = (stats['r_win'] + stats['draw']) / stats['total']
                        if r_not_lose >= self.min_accuracy:
                            high_acc_combos.append({
                                'dims': f"{name1}={key[0]} + {name2}={key[1]}",
                                'predict': '受让方不输',
                                'accuracy': r_not_lose,
                                'total': stats['total'],
                            })
        
        # 按准确率排序输出
        high_acc_combos.sort(key=lambda x: (-x['accuracy'], -x['total']))
        
        print(f"\n发现 {len(high_acc_combos)} 个高准确率二维组合 (≥{self.min_accuracy*100:.0f}%, 样本≥{self.min_sample})")
        print()
        print(f"{'维度组合':<60} {'预测':<15} {'样本':>6} {'准确率':>8}")
        print('-' * 95)
        
        shown = set()
        count = 0
        for combo in high_acc_combos:
            key = (combo['dims'], combo['predict'])
            if key not in shown and count < 50:
                shown.add(key)
                print(f"{combo['dims']:<60} {combo['predict']:<15} {combo['total']:>6} {combo['accuracy']*100:>7.1f}%")
                count += 1
        
        return high_acc_combos
    
    def mine_extended_combo_rules(self):
        """挖掘扩展组合规则（加入更多维度）"""
        print()
        print("=" * 100)
        print("【4. 扩展组合规则挖掘】盘型+赔率变化+Kelly")
        print("=" * 100)
        
        # 7维组合: 初让方+初受让+即让方+即受让+让方赔率变化+受让方赔率变化+让方Kelly
        combo_stats = defaultdict(lambda: {'win': 0, 'draw': 0, 'lose': 0, 'matches': []})
        
        for m in self.matches:
            combo = (
                m['init_h_type'], m['init_r_type'],
                m['curr_h_type'], m['curr_r_type'],
                m['h_odds_change'], m['r_odds_change'],
                m['kelly_h']
            )
            
            if m['h_score'] > m['r_score']:
                combo_stats[combo]['win'] += 1
            elif m['h_score'] == m['r_score']:
                combo_stats[combo]['draw'] += 1
            else:
                combo_stats[combo]['lose'] += 1
            combo_stats[combo]['matches'].append(m)
        
        print(f"\n【超高准确率组合】≥85% (样本≥{self.min_sample})")
        print(f"{'初让':>6} {'初受':>6} {'即让':>6} {'即受':>6} {'让变':>4} {'受变':>4} {'Kelly':>8} | {'样本':>4} {'胜':>3} {'平':>3} {'负':>3} {'预测':<15} {'准确率':>7}")
        print('-' * 110)
        
        super_rules = []
        for combo, stats in combo_stats.items():
            total = stats['win'] + stats['draw'] + stats['lose']
            if total >= self.min_sample:
                win_rate = stats['win'] / total
                not_win_rate = (stats['draw'] + stats['lose']) / total
                not_lose_rate = (stats['win'] + stats['draw']) / total
                
                best_predict = None
                best_rate = 0
                
                if win_rate >= 0.85:
                    best_predict = '让方必赢'
                    best_rate = win_rate
                elif not_win_rate >= 0.85:
                    best_predict = '受让方不输'
                    best_rate = not_win_rate
                elif not_lose_rate >= 0.85:
                    best_predict = '让方不输'
                    best_rate = not_lose_rate
                
                if best_predict:
                    print(f"{combo[0] or '-':>6} {combo[1] or '-':>6} {combo[2] or '-':>6} {combo[3] or '-':>6} {combo[4]:>4} {combo[5]:>4} {combo[6]:>8} | {total:>4} {stats['win']:>3} {stats['draw']:>3} {stats['lose']:>3} {best_predict:<15} {best_rate*100:>6.1f}%")
                    super_rules.append({
                        'combo': combo,
                        'predict': best_predict,
                        'accuracy': best_rate,
                        'total': total,
                    })
        
        if not super_rules:
            print("（无符合条件的组合）")
        
        print(f"\n发现 {len(super_rules)} 个超高准确率扩展组合")
        return super_rules
    
    def mine_league_specific_rules(self):
        """联赛特定规则挖掘"""
        print()
        print("=" * 100)
        print("【5. 联赛特定规则】")
        print("=" * 100)
        
        # 按联赛分组统计
        league_stats = defaultdict(lambda: {'h_win': 0, 'draw': 0, 'r_win': 0, 'total': 0})
        
        for m in self.matches:
            league_stats[m['league_name']]['total'] += 1
            if m['h_score'] > m['r_score']:
                league_stats[m['league_name']]['h_win'] += 1
            elif m['h_score'] == m['r_score']:
                league_stats[m['league_name']]['draw'] += 1
            else:
                league_stats[m['league_name']]['r_win'] += 1
        
        print(f"\n{'联赛':<20} {'样本':>6} {'让方胜':>6} {'平局':>6} {'受让胜':>6} {'让方胜率':>8} {'让方不输':>8}")
        print('-' * 85)
        
        for league, stats in sorted(league_stats.items(), key=lambda x: -x[1]['total'])[:20]:
            h_win_rate = stats['h_win'] / stats['total'] * 100
            h_not_lose = (stats['h_win'] + stats['draw']) / stats['total'] * 100
            print(f"{league:<20} {stats['total']:>6} {stats['h_win']:>6} {stats['draw']:>6} {stats['r_win']:>6} {h_win_rate:>7.1f}% {h_not_lose:>7.1f}%")
        
        # 五大联赛特定规则
        print()
        print("【五大联赛特定盘型规则】")
        
        big5_matches = [m for m in self.matches if m['is_big5']]
        
        # 即时让方盘型分析
        h_type_stats = defaultdict(lambda: {'h_win': 0, 'draw': 0, 'r_win': 0, 'total': 0})
        for m in big5_matches:
            h_type_stats[m['curr_h_type']]['total'] += 1
            if m['h_score'] > m['r_score']:
                h_type_stats[m['curr_h_type']]['h_win'] += 1
            elif m['h_score'] == m['r_score']:
                h_type_stats[m['curr_h_type']]['draw'] += 1
            else:
                h_type_stats[m['curr_h_type']]['r_win'] += 1
        
        print(f"\n{'即时让方盘型':<15} {'样本':>6} {'让方胜':>6} {'平局':>6} {'受让胜':>6} {'让方胜率':>8} {'受让不输':>8}")
        print('-' * 75)
        
        for h_type, stats in sorted(h_type_stats.items(), key=lambda x: -x[1]['total']):
            if stats['total'] >= 10:
                h_win_rate = stats['h_win'] / stats['total'] * 100
                r_not_lose = (stats['r_win'] + stats['draw']) / stats['total'] * 100
                marker = '⭐' if r_not_lose >= 75 or h_win_rate >= 60 else ''
                print(f"{marker} {h_type or '-':<13} {stats['total']:>6} {stats['h_win']:>6} {stats['draw']:>6} {stats['r_win']:>6} {h_win_rate:>7.1f}% {r_not_lose:>7.1f}%")
    
    def generate_report(self):
        """生成挖掘报告"""
        print()
        print("=" * 100)
        print("【📋 规则挖掘总结报告】")
        print("=" * 100)
        
        print(f"""
数据概览:
  - 总比赛数: {len(self.matches)}
  - 五大联赛: {sum(1 for m in self.matches if m['is_big5'])}
  - 筛选条件: 样本≥{self.min_sample}, 准确率≥{self.min_accuracy*100:.0f}%

发现的高准确率规则:
  - 部分特征规则: {len([r for r in self.rules_found if 'combo' not in r])} 个
        """)
        
        # 输出推荐规则
        print("\n【💡 推荐使用的核心规则】")
        print("-" * 80)
        
        recommended = [
            ('即时让方韬光盘 → 受让方不输', '当让球方即时盘为韬光盘时，受让方大概率不输'),
            ('初双实开→即时让低受高 → 受让方不输', '初盘双实开，变化后让方低开受让方高开'),
            ('让方赔率升+受让方赔率降 → 受让方不输', '赔率变化方向明确指向受让方'),
            ('让方低Kelly → 让方不输', '低Kelly表示有信心'),
        ]
        
        for rule, desc in recommended:
            print(f"  ✅ {rule}")
            print(f"     {desc}")
            print()
    
    def run(self):
        """运行完整挖掘流程"""
        self.load_data()
        self.mine_partial_rules()
        self.mine_combo_rules()
        self.mine_multi_dimension_rules()
        self.mine_extended_combo_rules()
        self.mine_league_specific_rules()
        self.generate_report()


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='增强版规则挖掘器 v3.0')
    parser.add_argument('--min-sample', type=int, default=3, help='最小样本数（默认3）')
    parser.add_argument('--min-accuracy', type=float, default=0.75, help='最小准确率（默认0.75）')
    args = parser.parse_args()
    
    miner = RuleMiner(min_sample=args.min_sample, min_accuracy=args.min_accuracy)
    miner.run()


if __name__ == '__main__':
    main()
