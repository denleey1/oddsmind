#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
精准规则挖掘器 v1.0
=====================
专注挖掘高命中率（≥90%）的精准规则

目标：
1. 让方必赢 - 预测正确率高
2. 受让方不输 - 预测正确率高  
3. 必出平局 - 预测正确率高

特点：
- 只使用威廉公司数据
- 五大联赛和其他联赛分开
- 样本可以少，但命中率要高（≥90%或100%）
- 挖掘有意义的规则组合
"""
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional
import json

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

# ==================== 配置 ====================
MIN_SAMPLE_SIZE = 3  # 最小样本数（可以很少）
HIGH_ACCURACY = 0.90  # 高准确率阈值
PERFECT_ACCURACY = 1.0  # 100%命中
COMPANY_ID = '115'   # 威廉公司

# 五大联赛
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
BIG5_NAMES = {36: '英超', 31: '西甲', 34: '意甲', 8: '德甲', 11: '法甲'}

# 盘型前缀
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


# ==================== 工具函数 ====================

def get_range_type(range_str: str) -> Optional[str]:
    """提取盘面类型前缀"""
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def classify_odds_change(init: float, curr: float) -> str:
    """分类赔率变化"""
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
            oar.power_diff,
            m.home_team_name, m.away_team_name, 
            m.home_score, m.away_score, m.match_time,
            l.league_id, l.name_cn as league_name,
            eo.initial_home, eo.initial_draw, eo.initial_away,
            eo.current_home, eo.current_draw, eo.current_away,
            eo.kelly_home, eo.kelly_draw, eo.kelly_away
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
    init_away = float(row['initial_away'])
    curr_home = float(row['current_home'])
    curr_away = float(row['current_away'])
    init_draw = float(row['initial_draw'])
    curr_draw = float(row['current_draw'])
    
    # 判断让球方（初赔小者为让球方）
    if init_home <= init_away:
        handicap_side = 'home'
        h_score, r_score = row['home_score'], row['away_score']
        init_h_range = row['initial_home_range']
        init_r_range = row['initial_away_range']
        curr_h_range = row['current_home_range']
        curr_r_range = row['current_away_range']
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
        init_h_odds, init_r_odds = init_away, init_home
        curr_h_odds, curr_r_odds = curr_away, curr_home
        kelly_h, kelly_r = row['kelly_away'], row['kelly_home']
    
    # 赛果判断
    if h_score > r_score:
        result = 'handicap_win'
    elif h_score == r_score:
        result = 'draw'
    else:
        result = 'receiver_win'
    
    return {
        'match_id': row['match_id'],
        'league_id': row['league_id'],
        'league_name': row['league_name'],
        'home_team': row['home_team_name'],
        'away_team': row['away_team_name'],
        'handicap_side': handicap_side,
        'match_time': row['match_time'],
        'home_score': row['home_score'],
        'away_score': row['away_score'],
        'h_score': h_score,
        'r_score': r_score,
        'result': result,
        
        # 联赛分类
        'is_big5': row['league_id'] in BIG5_LEAGUE_IDS,
        
        # 盘型特征
        'init_h': get_range_type(init_h_range),
        'init_r': get_range_type(init_r_range),
        'curr_h': get_range_type(curr_h_range),
        'curr_r': get_range_type(curr_r_range),
        
        # 平局盘型
        'init_draw': row['initial_draw_range'],
        'curr_draw': row['current_draw_range'],
        
        # 赔率变化
        'h_change': classify_odds_change(init_h_odds, curr_h_odds),
        'r_change': classify_odds_change(init_r_odds, curr_r_odds),
        'd_change': classify_odds_change(init_draw, curr_draw),
        
        # Kelly
        'kelly_h': classify_kelly(float(kelly_h) if kelly_h else None),
        'kelly_r': classify_kelly(float(kelly_r) if kelly_r else None),
        
        # 力量差
        'power': classify_power_diff(float(row['power_diff']) if row['power_diff'] else None),
    }


class PrecisionRuleMiner:
    """精准规则挖掘器"""
    
    def __init__(self, min_sample: int = MIN_SAMPLE_SIZE):
        self.min_sample = min_sample
        self.matches = []
        self.big5_matches = []
        self.other_matches = []
        self.perfect_rules = []  # 100%命中规则
        self.high_acc_rules = []  # ≥90%命中规则
        
    def load_data(self):
        """加载数据"""
        print("=" * 100)
        print("🎯 精准规则挖掘器 v1.0 - 只挖掘高命中率规则")
        print("=" * 100)
        print()
        
        raw_data = load_match_data()
        print(f"✅ 加载原始数据: {len(raw_data)} 场比赛")
        
        self.matches = [process_match(row) for row in raw_data]
        self.big5_matches = [m for m in self.matches if m['is_big5']]
        self.other_matches = [m for m in self.matches if not m['is_big5']]
        
        print(f"   - 五大联赛: {len(self.big5_matches)} 场")
        print(f"   - 其他联赛: {len(self.other_matches)} 场")
        print()
        
    def _check_rule(self, matches: List[Dict], condition, predict_fn) -> Dict:
        """检查规则准确率"""
        total = 0
        correct = 0
        sample_matches = []
        
        for m in matches:
            try:
                if condition(m):
                    total += 1
                    sample_matches.append(m)
                    if predict_fn(m):
                        correct += 1
            except Exception:
                continue
        
        return {
            'total': total,
            'correct': correct,
            'accuracy': correct / total if total > 0 else 0,
            'samples': sample_matches[:5]  # 只保留前5个样本
        }
    
    def mine_single_feature_rules(self, matches: List[Dict], league_type: str):
        """单特征规则挖掘"""
        print(f"\n{'='*80}")
        print(f"【{league_type}】单特征精准规则")
        print(f"{'='*80}")
        
        # 定义单特征规则
        rules = [
            # 即时让方盘型规则
            ('即时让方韬光', lambda m: m['curr_h'] == '韬光', 
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            ('即时让方超韬', lambda m: m['curr_h'] == '超韬',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            ('即时让方超实', lambda m: m['curr_h'] == '超实',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('即时让方超深', lambda m: m['curr_h'] == '超深',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('即时让方超散', lambda m: m['curr_h'] == '超散',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('即时让方低开', lambda m: m['curr_h'] == '低开',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            
            # 即时受让方盘型规则
            ('即时受让方韬光', lambda m: m['curr_r'] == '韬光',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('即时受让方超韬', lambda m: m['curr_r'] == '超韬',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('即时受让方超实', lambda m: m['curr_r'] == '超实',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            
            # Kelly规则
            ('让方低Kelly', lambda m: m['kelly_h'] == '低Kelly',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('让方高Kelly', lambda m: m['kelly_h'] == '高Kelly',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            ('受让方低Kelly', lambda m: m['kelly_r'] == '低Kelly',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            
            # 赔率变化规则
            ('让方赔率降', lambda m: m['h_change'] == '降',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('让方赔率升', lambda m: m['h_change'] == '升',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            ('受让方赔率降', lambda m: m['r_change'] == '降',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            
            # 力量差规则
            ('强让', lambda m: m['power'] == '强让',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强受', lambda m: m['power'] == '强受',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
        ]
        
        perfect = []
        high_acc = []
        
        print(f"\n{'规则名称':<25} {'预测':<12} {'样本':>6} {'命中':>6} {'准确率':>8}")
        print('-' * 65)
        
        for name, condition, predict_fn, predict in rules:
            result = self._check_rule(matches, condition, predict_fn)
            if result['total'] >= self.min_sample:
                acc = result['accuracy']
                status = '🏆' if acc == 1.0 else ('⭐' if acc >= 0.90 else ('✓' if acc >= 0.80 else ''))
                print(f"{status} {name:<23} {predict:<12} {result['total']:>6} {result['correct']:>6} {acc*100:>7.1f}%")
                
                if acc == 1.0:
                    perfect.append({
                        'name': name, 'predict': predict, 
                        'accuracy': acc, 'total': result['total'],
                        'league_type': league_type
                    })
                elif acc >= 0.90:
                    high_acc.append({
                        'name': name, 'predict': predict,
                        'accuracy': acc, 'total': result['total'],
                        'league_type': league_type
                    })
        
        return perfect, high_acc
    
    def mine_double_feature_rules(self, matches: List[Dict], league_type: str):
        """双特征组合规则挖掘"""
        print(f"\n{'='*80}")
        print(f"【{league_type}】双特征精准规则组合")
        print(f"{'='*80}")
        
        # 力量差 + 盘型组合
        combos = [
            # 强让 + 盘型
            ('强让+即时让方韬光', lambda m: m['power']=='强让' and m['curr_h']=='韬光',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            ('强让+即时让方超实', lambda m: m['power']=='强让' and m['curr_h']=='超实',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强让+即时让方超散', lambda m: m['power']=='强让' and m['curr_h']=='超散',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强让+即时让方超深', lambda m: m['power']=='强让' and m['curr_h']=='超深',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强让+即时受让方韬光', lambda m: m['power']=='强让' and m['curr_r']=='韬光',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强让+即时受让方超韬', lambda m: m['power']=='强让' and m['curr_r']=='超韬',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            
            # 盘型 + 赔率变化
            ('即时让方韬光+让方赔率升', lambda m: m['curr_h']=='韬光' and m['h_change']=='升',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            ('即时让方超实+让方赔率降', lambda m: m['curr_h']=='超实' and m['h_change']=='降',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('即时受让方韬光+受让方赔率升', lambda m: m['curr_r']=='韬光' and m['r_change']=='升',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            
            # 双向赔率变化
            ('让方降+受让方升', lambda m: m['h_change']=='降' and m['r_change']=='升',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('让方升+受让方降', lambda m: m['h_change']=='升' and m['r_change']=='降',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            
            # 力量差 + 赔率变化
            ('强让+让方赔率稳', lambda m: m['power']=='强让' and m['h_change']=='稳',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强让+受让方赔率升', lambda m: m['power']=='强让' and m['r_change']=='升',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            
            # 力量差 + Kelly
            ('强让+让方低Kelly', lambda m: m['power']=='强让' and m['kelly_h']=='低Kelly',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('微让+让方低Kelly', lambda m: m['power']=='微让' and m['kelly_h']=='低Kelly',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            
            # 盘型变化组合（初盘→即时）
            ('初让方实开→即时韬光', lambda m: m['init_h']=='实开' and m['curr_h']=='韬光',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            ('初让方实开→即时超实', lambda m: m['init_h']=='实开' and m['curr_h']=='超实',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('初让方低开→即时超实', lambda m: m['init_h']=='低开' and m['curr_h']=='超实',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('初让方高开→即时韬光', lambda m: m['init_h']=='高开' and m['curr_h']=='韬光',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
        ]
        
        perfect = []
        high_acc = []
        
        print(f"\n{'规则名称':<35} {'预测':<12} {'样本':>6} {'命中':>6} {'准确率':>8}")
        print('-' * 75)
        
        for name, condition, predict_fn, predict in combos:
            result = self._check_rule(matches, condition, predict_fn)
            if result['total'] >= self.min_sample:
                acc = result['accuracy']
                status = '🏆' if acc == 1.0 else ('⭐' if acc >= 0.90 else ('✓' if acc >= 0.80 else ''))
                print(f"{status} {name:<33} {predict:<12} {result['total']:>6} {result['correct']:>6} {acc*100:>7.1f}%")
                
                if acc == 1.0:
                    perfect.append({
                        'name': name, 'predict': predict,
                        'accuracy': acc, 'total': result['total'],
                        'league_type': league_type
                    })
                elif acc >= 0.90:
                    high_acc.append({
                        'name': name, 'predict': predict,
                        'accuracy': acc, 'total': result['total'],
                        'league_type': league_type
                    })
        
        return perfect, high_acc
    
    def mine_triple_feature_rules(self, matches: List[Dict], league_type: str):
        """三特征组合规则挖掘"""
        print(f"\n{'='*80}")
        print(f"【{league_type}】三特征精准规则组合")
        print(f"{'='*80}")
        
        combos = [
            # 力量差 + 盘型 + 赔率变化
            ('强让+即时让方超实+让方赔率降', 
             lambda m: m['power']=='强让' and m['curr_h']=='超实' and m['h_change']=='降',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强让+即时让方超实+受让方赔率升',
             lambda m: m['power']=='强让' and m['curr_h']=='超实' and m['r_change']=='升',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强让+即时受让方韬光+受让方赔率升',
             lambda m: m['power']=='强让' and m['curr_r']=='韬光' and m['r_change']=='升',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('强让+即时让方韬光+让方赔率升',
             lambda m: m['power']=='强让' and m['curr_h']=='韬光' and m['h_change']=='升',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            
            # 盘型变化 + 赔率变化
            ('初让方实开→即时韬光+让方赔率升',
             lambda m: m['init_h']=='实开' and m['curr_h']=='韬光' and m['h_change']=='升',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
            ('初让方实开→即时超实+让方赔率降',
             lambda m: m['init_h']=='实开' and m['curr_h']=='超实' and m['h_change']=='降',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            
            # 双盘型 + 赔率变化
            ('即时让方超实+即时受让方韬光+让方降',
             lambda m: m['curr_h']=='超实' and m['curr_r']=='韬光' and m['h_change']=='降',
             lambda m: m['h_score'] >= m['r_score'], '让方不输'),
            ('即时让方韬光+即时受让方超实+让方升',
             lambda m: m['curr_h']=='韬光' and m['curr_r']=='超实' and m['h_change']=='升',
             lambda m: m['h_score'] <= m['r_score'], '受让方不输'),
        ]
        
        perfect = []
        high_acc = []
        
        print(f"\n{'规则名称':<45} {'预测':<12} {'样本':>6} {'命中':>6} {'准确率':>8}")
        print('-' * 85)
        
        for name, condition, predict_fn, predict in combos:
            result = self._check_rule(matches, condition, predict_fn)
            if result['total'] >= self.min_sample:
                acc = result['accuracy']
                status = '🏆' if acc == 1.0 else ('⭐' if acc >= 0.90 else ('✓' if acc >= 0.80 else ''))
                print(f"{status} {name:<43} {predict:<12} {result['total']:>6} {result['correct']:>6} {acc*100:>7.1f}%")
                
                if acc == 1.0:
                    perfect.append({
                        'name': name, 'predict': predict,
                        'accuracy': acc, 'total': result['total'],
                        'league_type': league_type
                    })
                elif acc >= 0.90:
                    high_acc.append({
                        'name': name, 'predict': predict,
                        'accuracy': acc, 'total': result['total'],
                        'league_type': league_type
                    })
        
        return perfect, high_acc
    
    def mine_must_win_rules(self, matches: List[Dict], league_type: str):
        """挖掘"必赢"规则（让方必赢 / 受让方必赢）"""
        print(f"\n{'='*80}")
        print(f"【{league_type}】必赢规则挖掘")
        print(f"{'='*80}")
        
        combos = [
            # 让方必赢规则
            ('强让+即时让方超深', lambda m: m['power']=='强让' and m['curr_h']=='超深',
             lambda m: m['h_score'] > m['r_score'], '让方必赢'),
            ('强让+即时让方超散', lambda m: m['power']=='强让' and m['curr_h']=='超散',
             lambda m: m['h_score'] > m['r_score'], '让方必赢'),
            ('强让+即时让方超实+让方降', lambda m: m['power']=='强让' and m['curr_h']=='超实' and m['h_change']=='降',
             lambda m: m['h_score'] > m['r_score'], '让方必赢'),
            ('强让+即时受让方超韬', lambda m: m['power']=='强让' and m['curr_r']=='超韬',
             lambda m: m['h_score'] > m['r_score'], '让方必赢'),
            ('强让+即时受让方韬光+受让方升', lambda m: m['power']=='强让' and m['curr_r']=='韬光' and m['r_change']=='升',
             lambda m: m['h_score'] > m['r_score'], '让方必赢'),
            
            # 受让方必赢规则
            ('强受+即时受让方超实', lambda m: m['power']=='强受' and m['curr_r']=='超实',
             lambda m: m['h_score'] < m['r_score'], '受让方必赢'),
            ('即时让方超韬+让方赔率升', lambda m: m['curr_h']=='超韬' and m['h_change']=='升',
             lambda m: m['h_score'] < m['r_score'], '受让方必赢'),
            ('强让+即时让方韬光+让方升', lambda m: m['power']=='强让' and m['curr_h']=='韬光' and m['h_change']=='升',
             lambda m: m['h_score'] < m['r_score'], '受让方必赢'),
        ]
        
        perfect = []
        high_acc = []
        
        print(f"\n{'规则名称':<45} {'预测':<12} {'样本':>6} {'命中':>6} {'准确率':>8}")
        print('-' * 85)
        
        for name, condition, predict_fn, predict in combos:
            result = self._check_rule(matches, condition, predict_fn)
            if result['total'] >= self.min_sample:
                acc = result['accuracy']
                # 必赢规则阈值更高
                status = '🏆' if acc >= 0.85 else ('⭐' if acc >= 0.75 else ('✓' if acc >= 0.65 else ''))
                print(f"{status} {name:<43} {predict:<12} {result['total']:>6} {result['correct']:>6} {acc*100:>7.1f}%")
                
                if acc >= 0.85:
                    perfect.append({
                        'name': name, 'predict': predict,
                        'accuracy': acc, 'total': result['total'],
                        'league_type': league_type
                    })
                elif acc >= 0.75:
                    high_acc.append({
                        'name': name, 'predict': predict,
                        'accuracy': acc, 'total': result['total'],
                        'league_type': league_type
                    })
        
        return perfect, high_acc
    
    def mine_draw_rules(self, matches: List[Dict], league_type: str):
        """挖掘平局规则"""
        print(f"\n{'='*80}")
        print(f"【{league_type}】平局规则挖掘")
        print(f"{'='*80}")
        
        combos = [
            ('平手+平局赔率降', lambda m: m['power']=='平手' and m['d_change']=='降',
             lambda m: m['h_score'] == m['r_score'], '必出平局'),
            ('平手+让方赔率升+受让方赔率升', lambda m: m['power']=='平手' and m['h_change']=='升' and m['r_change']=='升',
             lambda m: m['h_score'] == m['r_score'], '必出平局'),
            ('即时让方实开+即时受让方实开', lambda m: m['curr_h']=='实开' and m['curr_r']=='实开',
             lambda m: m['h_score'] == m['r_score'], '可能平局'),
            ('平手+即时让方低开+即时受让方高开', lambda m: m['power']=='平手' and m['curr_h']=='低开' and m['curr_r']=='高开',
             lambda m: m['h_score'] == m['r_score'], '可能平局'),
        ]
        
        print(f"\n{'规则名称':<45} {'预测':<12} {'样本':>6} {'命中':>6} {'准确率':>8}")
        print('-' * 85)
        
        for name, condition, predict_fn, predict in combos:
            result = self._check_rule(matches, condition, predict_fn)
            if result['total'] >= self.min_sample:
                acc = result['accuracy']
                # 平局规则准确率难以很高
                status = '🏆' if acc >= 0.50 else ('⭐' if acc >= 0.40 else ('✓' if acc >= 0.30 else ''))
                print(f"{status} {name:<43} {predict:<12} {result['total']:>6} {result['correct']:>6} {acc*100:>7.1f}%")
    
    def generate_summary(self):
        """生成规则汇总"""
        print()
        print("=" * 100)
        print("🏆 精准规则汇总")
        print("=" * 100)
        
        print(f"\n📊 100%命中规则（{len(self.perfect_rules)}个）:")
        print("-" * 80)
        for r in sorted(self.perfect_rules, key=lambda x: -x['total']):
            print(f"  [{r['league_type']}] {r['name']} → {r['predict']} ({r['total']}场)")
        
        print(f"\n⭐ 90%+命中规则（{len(self.high_acc_rules)}个）:")
        print("-" * 80)
        for r in sorted(self.high_acc_rules, key=lambda x: (-x['accuracy'], -x['total']))[:20]:
            print(f"  [{r['league_type']}] {r['name']} → {r['predict']} ({r['accuracy']*100:.1f}%, {r['total']}场)")
        
        # 保存到JSON
        output = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'total_matches': len(self.matches),
            'big5_matches': len(self.big5_matches),
            'other_matches': len(self.other_matches),
            'perfect_rules': self.perfect_rules,
            'high_accuracy_rules': self.high_acc_rules,
        }
        
        output_path = Path(__file__).parent / 'precision_rules.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 规则已保存到: {output_path}")
    
    def run(self):
        """运行挖掘"""
        self.load_data()
        
        # 五大联赛挖掘
        p1, h1 = self.mine_single_feature_rules(self.big5_matches, '五大联赛')
        p2, h2 = self.mine_double_feature_rules(self.big5_matches, '五大联赛')
        p3, h3 = self.mine_triple_feature_rules(self.big5_matches, '五大联赛')
        p4, h4 = self.mine_must_win_rules(self.big5_matches, '五大联赛')
        self.mine_draw_rules(self.big5_matches, '五大联赛')
        
        self.perfect_rules.extend(p1 + p2 + p3 + p4)
        self.high_acc_rules.extend(h1 + h2 + h3 + h4)
        
        # 其他联赛挖掘
        p1, h1 = self.mine_single_feature_rules(self.other_matches, '其他联赛')
        p2, h2 = self.mine_double_feature_rules(self.other_matches, '其他联赛')
        p3, h3 = self.mine_triple_feature_rules(self.other_matches, '其他联赛')
        p4, h4 = self.mine_must_win_rules(self.other_matches, '其他联赛')
        self.mine_draw_rules(self.other_matches, '其他联赛')
        
        self.perfect_rules.extend(p1 + p2 + p3 + p4)
        self.high_acc_rules.extend(h1 + h2 + h3 + h4)
        
        # 全部联赛（可能发现更大样本的规则）
        p1, h1 = self.mine_single_feature_rules(self.matches, '全部联赛')
        p2, h2 = self.mine_double_feature_rules(self.matches, '全部联赛')
        p3, h3 = self.mine_triple_feature_rules(self.matches, '全部联赛')
        p4, h4 = self.mine_must_win_rules(self.matches, '全部联赛')
        
        self.perfect_rules.extend(p1 + p2 + p3 + p4)
        self.high_acc_rules.extend(h1 + h2 + h3 + h4)
        
        self.generate_summary()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='精准规则挖掘器')
    parser.add_argument('--min-sample', type=int, default=3, help='最小样本数（默认3）')
    args = parser.parse_args()
    
    miner = PrecisionRuleMiner(min_sample=args.min_sample)
    miner.run()


if __name__ == '__main__':
    main()
