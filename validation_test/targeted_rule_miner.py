#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
定向规则挖掘器
==================
专门挖掘：
1. 让方必赢（让球方赢球）
2. 受让方不输（让方打不赢 = 平或受让方赢）

只要五大联赛100%命中 或 全部联赛90%+命中的规则
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
MIN_SAMPLE_SIZE = 3
COMPANY_ID = '115'  # 威廉公司

# 五大联赛
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
BIG5_NAMES = {36: '英超', 31: '西甲', 34: '意甲', 8: '德甲', 11: '法甲'}

# 盘型
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


def get_range_type(range_str: str) -> Optional[str]:
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def classify_odds_change(init: float, curr: float) -> str:
    if curr > init * 1.05:
        return '升'
    elif curr < init * 0.95:
        return '降'
    return '稳'


def classify_kelly(kelly: float) -> str:
    if kelly is None:
        return '未知'
    if kelly < 0.85:
        return '低Kelly'
    elif kelly < 0.95:
        return '中Kelly'
    elif kelly < 1.05:
        return '正常Kelly'
    return '高Kelly'


def classify_power_diff(diff: float) -> str:
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
    return '强受'


def load_match_data() -> List[Dict]:
    db = get_connection()
    query = '''
        SELECT 
            oar.match_id,
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
    init_home = float(row['initial_home'])
    init_away = float(row['initial_away'])
    curr_home = float(row['current_home'])
    curr_away = float(row['current_away'])
    init_draw = float(row['initial_draw'])
    curr_draw = float(row['current_draw'])
    
    # 让球方判断
    if init_home <= init_away:
        handicap_side = 'home'
        h_score, r_score = row['home_score'], row['away_score']
        init_h_range, init_r_range = row['initial_home_range'], row['initial_away_range']
        curr_h_range, curr_r_range = row['current_home_range'], row['current_away_range']
        init_h_odds, init_r_odds = init_home, init_away
        curr_h_odds, curr_r_odds = curr_home, curr_away
        kelly_h, kelly_r = row['kelly_home'], row['kelly_away']
    else:
        handicap_side = 'away'
        h_score, r_score = row['away_score'], row['home_score']
        init_h_range, init_r_range = row['initial_away_range'], row['initial_home_range']
        curr_h_range, curr_r_range = row['current_away_range'], row['current_home_range']
        init_h_odds, init_r_odds = init_away, init_home
        curr_h_odds, curr_r_odds = curr_away, curr_home
        kelly_h, kelly_r = row['kelly_away'], row['kelly_home']
    
    return {
        'match_id': row['match_id'],
        'league_id': row['league_id'],
        'league_name': row['league_name'],
        'home_team': row['home_team_name'],
        'away_team': row['away_team_name'],
        'match_time': row['match_time'],
        'h_score': h_score,
        'r_score': r_score,
        'is_big5': row['league_id'] in BIG5_LEAGUE_IDS,
        'init_h': get_range_type(init_h_range),
        'init_r': get_range_type(init_r_range),
        'curr_h': get_range_type(curr_h_range),
        'curr_r': get_range_type(curr_r_range),
        'init_draw': row['initial_draw_range'],
        'curr_draw': row['current_draw_range'],
        'h_change': classify_odds_change(init_h_odds, curr_h_odds),
        'r_change': classify_odds_change(init_r_odds, curr_r_odds),
        'd_change': classify_odds_change(init_draw, curr_draw),
        'kelly_h': classify_kelly(float(kelly_h) if kelly_h else None),
        'kelly_r': classify_kelly(float(kelly_r) if kelly_r else None),
        'power': classify_power_diff(float(row['power_diff']) if row['power_diff'] else None),
    }


class TargetedRuleMiner:
    """定向规则挖掘器"""
    
    def __init__(self):
        self.matches = []
        self.big5_matches = []
        self.all_matches = []
        self.valuable_rules = []
        
    def load_data(self):
        print("=" * 100)
        print("🎯 定向规则挖掘器 - 只找【让方必赢】和【受让方不输】")
        print("=" * 100)
        print()
        
        raw_data = load_match_data()
        print(f"✅ 加载数据: {len(raw_data)} 场比赛")
        
        self.matches = [process_match(row) for row in raw_data]
        self.big5_matches = [m for m in self.matches if m['is_big5']]
        self.all_matches = self.matches
        
        print(f"   - 五大联赛: {len(self.big5_matches)} 场")
        print(f"   - 其他联赛: {len(self.matches) - len(self.big5_matches)} 场")
        print()
    
    def _check_handicap_win(self, m: Dict) -> bool:
        """让方必赢"""
        return m['h_score'] > m['r_score']
    
    def _check_receiver_not_lose(self, m: Dict) -> bool:
        """受让方不输 = 让方打不赢"""
        return m['h_score'] <= m['r_score']
    
    def _eval_rule(self, matches: List[Dict], condition, check_fn) -> Dict:
        total = 0
        correct = 0
        samples = []
        
        for m in matches:
            try:
                if condition(m):
                    total += 1
                    samples.append({
                        'match': f"{m['home_team']} vs {m['away_team']}",
                        'score': f"{m['h_score']}-{m['r_score']}",
                        'result': '命中' if check_fn(m) else '未命中'
                    })
                    if check_fn(m):
                        correct += 1
            except:
                continue
        
        return {
            'total': total,
            'correct': correct,
            'accuracy': correct / total if total > 0 else 0,
            'samples': samples[:5]
        }
    
    def mine_rules(self):
        """挖掘规则"""
        
        # 定义所有可能的规则组合
        rules_to_check = []
        
        # === 让方必赢规则 ===
        handicap_win_rules = [
            # 单特征
            ('强让', lambda m: m['power']=='强让'),
            ('即时让方超实', lambda m: m['curr_h']=='超实'),
            ('即时让方超散', lambda m: m['curr_h']=='超散'),
            ('即时让方超深', lambda m: m['curr_h']=='超深'),
            ('即时让方低开', lambda m: m['curr_h']=='低开'),
            ('即时受让方韬光', lambda m: m['curr_r']=='韬光'),
            ('即时受让方超韬', lambda m: m['curr_r']=='超韬'),
            ('让方赔率降', lambda m: m['h_change']=='降'),
            ('受让方赔率升', lambda m: m['r_change']=='升'),
            ('让方低Kelly', lambda m: m['kelly_h']=='低Kelly'),
            
            # 双特征
            ('强让+即时让方超实', lambda m: m['power']=='强让' and m['curr_h']=='超实'),
            ('强让+即时让方超散', lambda m: m['power']=='强让' and m['curr_h']=='超散'),
            ('强让+即时让方超深', lambda m: m['power']=='强让' and m['curr_h']=='超深'),
            ('强让+即时受让方韬光', lambda m: m['power']=='强让' and m['curr_r']=='韬光'),
            ('强让+即时受让方超韬', lambda m: m['power']=='强让' and m['curr_r']=='超韬'),
            ('强让+让方赔率降', lambda m: m['power']=='强让' and m['h_change']=='降'),
            ('强让+受让方赔率升', lambda m: m['power']=='强让' and m['r_change']=='升'),
            ('强让+让方赔率稳', lambda m: m['power']=='强让' and m['h_change']=='稳'),
            ('即时让方超实+让方赔率降', lambda m: m['curr_h']=='超实' and m['h_change']=='降'),
            ('即时让方超实+受让方赔率升', lambda m: m['curr_h']=='超实' and m['r_change']=='升'),
            ('即时受让方韬光+受让方赔率升', lambda m: m['curr_r']=='韬光' and m['r_change']=='升'),
            ('即时受让方超韬+受让方赔率升', lambda m: m['curr_r']=='超韬' and m['r_change']=='升'),
            ('让方赔率降+受让方赔率升', lambda m: m['h_change']=='降' and m['r_change']=='升'),
            ('初让方实开→即时超实', lambda m: m['init_h']=='实开' and m['curr_h']=='超实'),
            ('初让方低开→即时超实', lambda m: m['init_h']=='低开' and m['curr_h']=='超实'),
            ('初让方实开→即时超散', lambda m: m['init_h']=='实开' and m['curr_h']=='超散'),
            
            # 三特征
            ('强让+即时让方超实+让方赔率降', lambda m: m['power']=='强让' and m['curr_h']=='超实' and m['h_change']=='降'),
            ('强让+即时让方超实+受让方赔率升', lambda m: m['power']=='强让' and m['curr_h']=='超实' and m['r_change']=='升'),
            ('强让+即时受让方韬光+受让方赔率升', lambda m: m['power']=='强让' and m['curr_r']=='韬光' and m['r_change']=='升'),
            ('强让+即时受让方超韬+受让方赔率升', lambda m: m['power']=='强让' and m['curr_r']=='超韬' and m['r_change']=='升'),
            ('强让+让方赔率降+受让方赔率升', lambda m: m['power']=='强让' and m['h_change']=='降' and m['r_change']=='升'),
            ('即时让方超实+即时受让方韬光+让方赔率降', lambda m: m['curr_h']=='超实' and m['curr_r']=='韬光' and m['h_change']=='降'),
        ]
        
        for name, cond in handicap_win_rules:
            rules_to_check.append((name, cond, self._check_handicap_win, '让方必赢'))
        
        # === 受让方不输规则 ===
        receiver_not_lose_rules = [
            # 单特征
            ('即时让方韬光', lambda m: m['curr_h']=='韬光'),
            ('即时让方超韬', lambda m: m['curr_h']=='超韬'),
            ('即时让方高开', lambda m: m['curr_h']=='高开'),
            ('即时受让方超实', lambda m: m['curr_r']=='超实'),
            ('即时受让方低开', lambda m: m['curr_r']=='低开'),
            ('让方赔率升', lambda m: m['h_change']=='升'),
            ('受让方赔率降', lambda m: m['r_change']=='降'),
            ('让方高Kelly', lambda m: m['kelly_h']=='高Kelly'),
            ('受让方低Kelly', lambda m: m['kelly_r']=='低Kelly'),
            
            # 双特征
            ('即时让方韬光+让方赔率升', lambda m: m['curr_h']=='韬光' and m['h_change']=='升'),
            ('即时让方韬光+受让方赔率降', lambda m: m['curr_h']=='韬光' and m['r_change']=='降'),
            ('即时让方超韬+让方赔率升', lambda m: m['curr_h']=='超韬' and m['h_change']=='升'),
            ('让方赔率升+受让方赔率降', lambda m: m['h_change']=='升' and m['r_change']=='降'),
            ('强让+即时让方韬光', lambda m: m['power']=='强让' and m['curr_h']=='韬光'),
            ('强让+即时让方超韬', lambda m: m['power']=='强让' and m['curr_h']=='超韬'),
            ('强让+让方赔率升', lambda m: m['power']=='强让' and m['h_change']=='升'),
            ('微让+即时让方韬光', lambda m: m['power']=='微让' and m['curr_h']=='韬光'),
            ('平手+即时让方韬光', lambda m: m['power']=='平手' and m['curr_h']=='韬光'),
            ('初让方实开→即时韬光', lambda m: m['init_h']=='实开' and m['curr_h']=='韬光'),
            ('初让方高开→即时韬光', lambda m: m['init_h']=='高开' and m['curr_h']=='韬光'),
            ('初让方超实→即时韬光', lambda m: m['init_h']=='超实' and m['curr_h']=='韬光'),
            ('初让方低开→即时韬光', lambda m: m['init_h']=='低开' and m['curr_h']=='韬光'),
            
            # 三特征
            ('即时让方韬光+让方赔率升+受让方赔率降', lambda m: m['curr_h']=='韬光' and m['h_change']=='升' and m['r_change']=='降'),
            ('强让+即时让方韬光+让方赔率升', lambda m: m['power']=='强让' and m['curr_h']=='韬光' and m['h_change']=='升'),
            ('初让方实开→即时韬光+让方赔率升', lambda m: m['init_h']=='实开' and m['curr_h']=='韬光' and m['h_change']=='升'),
        ]
        
        for name, cond in receiver_not_lose_rules:
            rules_to_check.append((name, cond, self._check_receiver_not_lose, '受让方不输'))
        
        # 分别检查五大联赛和全部联赛
        print("=" * 120)
        print("【五大联赛】精准规则（100%命中优先）")
        print("=" * 120)
        print(f"\n{'规则名称':<45} {'预测':<12} {'样本':>6} {'命中':>6} {'准确率':>8}")
        print("-" * 85)
        
        big5_perfect = []
        for name, cond, check_fn, predict in rules_to_check:
            result = self._eval_rule(self.big5_matches, cond, check_fn)
            if result['total'] >= MIN_SAMPLE_SIZE:
                acc = result['accuracy']
                if acc == 1.0:
                    print(f"🏆 {name:<43} {predict:<12} {result['total']:>6} {result['correct']:>6} {acc*100:>7.1f}%")
                    big5_perfect.append({
                        'name': f"【五大】{name}",
                        'condition': name,
                        'predict': predict,
                        'accuracy': acc,
                        'total': result['total'],
                        'league_type': '五大联赛'
                    })
        
        print(f"\n找到 {len(big5_perfect)} 条五大联赛100%命中规则")
        
        # 全部联赛90%+
        print("\n" + "=" * 120)
        print("【全部联赛】高准确率规则（≥90%命中）")
        print("=" * 120)
        print(f"\n{'规则名称':<45} {'预测':<12} {'样本':>6} {'命中':>6} {'准确率':>8}")
        print("-" * 85)
        
        all_high = []
        for name, cond, check_fn, predict in rules_to_check:
            result = self._eval_rule(self.all_matches, cond, check_fn)
            if result['total'] >= MIN_SAMPLE_SIZE:
                acc = result['accuracy']
                if acc >= 0.90:
                    status = '🏆' if acc == 1.0 else '⭐'
                    print(f"{status} {name:<43} {predict:<12} {result['total']:>6} {result['correct']:>6} {acc*100:>7.1f}%")
                    all_high.append({
                        'name': name,
                        'condition': name,
                        'predict': predict,
                        'accuracy': acc,
                        'total': result['total'],
                        'league_type': '全部联赛'
                    })
        
        print(f"\n找到 {len(all_high)} 条全部联赛90%+命中规则")
        
        self.valuable_rules = big5_perfect + all_high
        
        # 汇总输出
        print("\n" + "=" * 120)
        print("🏆🏆🏆 最终精选规则汇总 🏆🏆🏆")
        print("=" * 120)
        
        print("\n📌 【让方必赢】规则:")
        print("-" * 80)
        win_rules = [r for r in self.valuable_rules if r['predict'] == '让方必赢']
        for r in sorted(win_rules, key=lambda x: (-x['accuracy'], -x['total'])):
            print(f"  [{r['league_type']}] {r['condition']} → {r['predict']} ({r['accuracy']*100:.1f}%, {r['total']}场)")
        
        print("\n📌 【受让方不输】规则:")
        print("-" * 80)
        not_lose_rules = [r for r in self.valuable_rules if r['predict'] == '受让方不输']
        for r in sorted(not_lose_rules, key=lambda x: (-x['accuracy'], -x['total'])):
            print(f"  [{r['league_type']}] {r['condition']} → {r['predict']} ({r['accuracy']*100:.1f}%, {r['total']}场)")
        
        # 保存
        output = {
            'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'criteria': '让方必赢 或 受让方不输, 五大100%或全部90%+',
            'handicap_win_rules': win_rules,
            'receiver_not_lose_rules': not_lose_rules,
        }
        
        output_path = Path(__file__).parent / 'targeted_rules.json'
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 已保存到: {output_path}")
    
    def run(self):
        self.load_data()
        self.mine_rules()


def main():
    miner = TargetedRuleMiner()
    miner.run()


if __name__ == '__main__':
    main()
