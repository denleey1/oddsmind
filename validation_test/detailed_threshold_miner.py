#!/usr/bin/env python3
"""
细化阈值规则挖掘器
==================
把赔率变化分成多个级别，找出高命中率的精细规则
"""

import sys
from pathlib import Path
from collections import defaultdict
import json

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

# 威廉公司ID
WILLIAM_ID = 115

# 五大联赛
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
BIG5_NAMES = {36: '英超', 31: '西甲', 34: '意甲', 8: '德甲', 11: '法甲'}

# 盘型
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


def get_range_type(range_str):
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def classify_odds_change_detailed(init: float, curr: float) -> str:
    """
    细化赔率变化分类
    """
    if init <= 0:
        return '未知'
    
    change_pct = (curr - init) / init
    
    if change_pct > 0.15:
        return '暴升(>15%)'
    elif change_pct > 0.10:
        return '大升(10-15%)'
    elif change_pct > 0.05:
        return '小升(5-10%)'
    elif change_pct > 0.02:
        return '微升(2-5%)'
    elif change_pct >= -0.02:
        return '稳定(±2%)'
    elif change_pct >= -0.05:
        return '微降(2-5%)'
    elif change_pct >= -0.10:
        return '小降(5-10%)'
    elif change_pct >= -0.15:
        return '大降(10-15%)'
    else:
        return '暴降(>15%)'


def classify_power_diff(power_diff):
    if power_diff is None:
        return '未知'
    if power_diff > 2:
        return '强让'
    elif power_diff > 0.5:
        return '微让'
    elif power_diff > -0.5:
        return '平手'
    elif power_diff > -2:
        return '微受'
    return '强受'


def load_match_data():
    """加载比赛数据"""
    db = get_connection()
    query = '''
        SELECT 
            oar.match_id,
            oar.initial_home_range, oar.initial_away_range,
            oar.current_home_range, oar.current_away_range,
            oar.power_diff,
            m.home_team_name, m.away_team_name, 
            m.home_score, m.away_score,
            l.league_id, l.name_cn as league_name,
            eo.initial_home, eo.initial_draw, eo.initial_away,
            eo.current_home, eo.current_draw, eo.current_away
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        JOIN european_odds eo ON oar.match_id = eo.match_id AND oar.company_id = eo.company_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = %s
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
    '''
    return db.execute_query(query, (WILLIAM_ID,), fetch='all')


def process_match(row):
    """处理单场比赛数据"""
    init_home = float(row['initial_home'])
    init_away = float(row['initial_away'])
    curr_home = float(row['current_home'])
    curr_away = float(row['current_away'])
    
    # 让球方判断
    if init_home <= init_away:
        handicap_side = 'home'
        h_score, r_score = row['home_score'], row['away_score']
        init_h_range, init_r_range = row['initial_home_range'], row['initial_away_range']
        curr_h_range, curr_r_range = row['current_home_range'], row['current_away_range']
        init_h_odds, init_r_odds = init_home, init_away
        curr_h_odds, curr_r_odds = curr_home, curr_away
    else:
        handicap_side = 'away'
        h_score, r_score = row['away_score'], row['home_score']
        init_h_range, init_r_range = row['initial_away_range'], row['initial_home_range']
        curr_h_range, curr_r_range = row['current_away_range'], row['current_home_range']
        init_h_odds, init_r_odds = init_away, init_home
        curr_h_odds, curr_r_odds = curr_away, curr_home
    
    return {
        'league_id': row['league_id'],
        'is_big5': row['league_id'] in BIG5_LEAGUE_IDS,
        'h_score': h_score,
        'r_score': r_score,
        'power': classify_power_diff(float(row['power_diff']) if row['power_diff'] else None),
        'init_h': get_range_type(init_h_range),
        'init_r': get_range_type(init_r_range),
        'curr_h': get_range_type(curr_h_range),
        'curr_r': get_range_type(curr_r_range),
        'h_change': classify_odds_change_detailed(init_h_odds, curr_h_odds),
        'r_change': classify_odds_change_detailed(init_r_odds, curr_r_odds),
    }


def mine_detailed_rules(matches):
    """挖掘细化规则"""
    
    # 定义规则模板
    rule_templates = []
    
    # 变化幅度
    changes = ['暴升(>15%)', '大升(10-15%)', '小升(5-10%)', '微升(2-5%)', 
               '稳定(±2%)', '微降(2-5%)', '小降(5-10%)', '大降(10-15%)', '暴降(>15%)']
    
    # 力量差
    powers = ['强让', '微让', '平手']
    
    # 盘型
    ranges = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']
    
    # ============= 让方必赢规则 =============
    
    # 1. 力量差 + 让方变化幅度
    for power in powers:
        for h_change in changes:
            if '降' in h_change or '稳' in h_change:  # 让方降或稳
                rule_templates.append({
                    'name': f'{power}+让方{h_change}',
                    'condition': lambda m, p=power, hc=h_change: m['power']==p and m['h_change']==hc,
                    'check': lambda m: m['h_score'] > m['r_score'],
                    'predict': '让方必赢'
                })
    
    # 2. 力量差 + 让方变化 + 受让方变化
    for power in powers:
        for h_change in changes:
            for r_change in changes:
                if '降' in h_change and '升' in r_change:  # 让方降+受让方升
                    rule_templates.append({
                        'name': f'{power}+让方{h_change}+受让方{r_change}',
                        'condition': lambda m, p=power, hc=h_change, rc=r_change: 
                            m['power']==p and m['h_change']==hc and m['r_change']==rc,
                        'check': lambda m: m['h_score'] > m['r_score'],
                        'predict': '让方必赢'
                    })
    
    # 3. 力量差 + 即时盘型 + 变化
    for power in ['强让', '微让']:
        for curr_r in ['韬光', '超韬', '高开']:  # 受让方不被看好的盘型
            for r_change in changes:
                if '升' in r_change:  # 受让方赔率升
                    rule_templates.append({
                        'name': f'{power}+即时受让方{curr_r}+受让方{r_change}',
                        'condition': lambda m, p=power, cr=curr_r, rc=r_change: 
                            m['power']==p and m['curr_r']==cr and m['r_change']==rc,
                        'check': lambda m: m['h_score'] > m['r_score'],
                        'predict': '让方必赢'
                    })
    
    # ============= 受让方不输规则 =============
    
    # 4. 即时让方盘型 + 让方变化
    for curr_h in ['韬光', '超韬', '高开']:  # 让方不被看好
        for h_change in changes:
            if '升' in h_change:  # 让方赔率升
                rule_templates.append({
                    'name': f'即时让方{curr_h}+让方{h_change}',
                    'condition': lambda m, ch=curr_h, hc=h_change: m['curr_h']==ch and m['h_change']==hc,
                    'check': lambda m: m['h_score'] <= m['r_score'],
                    'predict': '受让方不输'
                })
    
    # 5. 即时让方盘型 + 受让方变化
    for curr_h in ['韬光', '超韬', '高开']:
        for r_change in changes:
            if '降' in r_change:  # 受让方赔率降
                rule_templates.append({
                    'name': f'即时让方{curr_h}+受让方{r_change}',
                    'condition': lambda m, ch=curr_h, rc=r_change: m['curr_h']==ch and m['r_change']==rc,
                    'check': lambda m: m['h_score'] <= m['r_score'],
                    'predict': '受让方不输'
                })
    
    # 6. 让方变化 + 受让方变化（双向）
    for h_change in changes:
        for r_change in changes:
            if '升' in h_change and '降' in r_change:  # 让方升+受让方降
                rule_templates.append({
                    'name': f'让方{h_change}+受让方{r_change}',
                    'condition': lambda m, hc=h_change, rc=r_change: m['h_change']==hc and m['r_change']==rc,
                    'check': lambda m: m['h_score'] <= m['r_score'],
                    'predict': '受让方不输'
                })
    
    # 7. 盘型变化 + 赔率变化
    for init_h in ['实开', '低开']:
        for curr_h in ['韬光', '超韬', '高开']:
            for h_change in changes:
                if '升' in h_change:
                    rule_templates.append({
                        'name': f'初让方{init_h}→即时{curr_h}+让方{h_change}',
                        'condition': lambda m, ih=init_h, ch=curr_h, hc=h_change: 
                            m['init_h']==ih and m['curr_h']==ch and m['h_change']==hc,
                        'check': lambda m: m['h_score'] <= m['r_score'],
                        'predict': '受让方不输'
                    })
    
    # 8. 力量差 + 盘型 + 变化
    for power in ['强让', '微让']:
        for curr_h in ['韬光', '超韬']:
            for h_change in changes:
                if '升' in h_change:
                    rule_templates.append({
                        'name': f'{power}+即时让方{curr_h}+让方{h_change}',
                        'condition': lambda m, p=power, ch=curr_h, hc=h_change: 
                            m['power']==p and m['curr_h']==ch and m['h_change']==hc,
                        'check': lambda m: m['h_score'] <= m['r_score'],
                        'predict': '受让方不输'
                    })
    
    # 统计每个规则的命中情况
    results = []
    
    for rule in rule_templates:
        big5_total = 0
        big5_correct = 0
        other_total = 0
        other_correct = 0
        
        for m in matches:
            try:
                if rule['condition'](m):
                    if m['is_big5']:
                        big5_total += 1
                        if rule['check'](m):
                            big5_correct += 1
                    else:
                        other_total += 1
                        if rule['check'](m):
                            other_correct += 1
            except:
                continue
        
        big5_acc = big5_correct / big5_total if big5_total > 0 else 0
        other_acc = other_correct / other_total if other_total > 0 else 0
        all_total = big5_total + other_total
        all_correct = big5_correct + other_correct
        all_acc = all_correct / all_total if all_total > 0 else 0
        
        # 只保留有意义的规则
        if all_total >= 3:
            results.append({
                'name': rule['name'],
                'predict': rule['predict'],
                'big5_total': big5_total,
                'big5_correct': big5_correct,
                'big5_acc': big5_acc,
                'other_total': other_total,
                'other_correct': other_correct,
                'other_acc': other_acc,
                'all_total': all_total,
                'all_acc': all_acc,
                # 评分：五大100%加分，普通90%+加分
                'score': (10 if big5_acc == 1.0 and big5_total >= 3 else 0) + 
                         (5 if other_acc >= 0.9 and other_total >= 5 else 0) +
                         (big5_acc * 2 if big5_total >= 3 else 0) +
                         (other_acc if other_total >= 3 else 0)
            })
    
    return results


def main():
    print("=" * 90)
    print("细化阈值规则挖掘")
    print("=" * 90)
    print()
    
    # 加载数据
    print("加载数据...")
    raw_data = load_match_data()
    matches = [process_match(row) for row in raw_data]
    print(f"共 {len(matches)} 场已完成比赛")
    print()
    
    # 挖掘规则
    print("挖掘细化规则...")
    results = mine_detailed_rules(matches)
    print(f"共发现 {len(results)} 条有效规则")
    print()
    
    # 按预测类型分类，按得分排序
    handicap_win = [r for r in results if r['predict'] == '让方必赢']
    receiver_not_lose = [r for r in results if r['predict'] == '受让方不输']
    
    handicap_win.sort(key=lambda x: (-x['score'], -x['big5_acc'], -x['all_acc']))
    receiver_not_lose.sort(key=lambda x: (-x['score'], -x['big5_acc'], -x['all_acc']))
    
    # 输出让方必赢规则
    print("\n" + "=" * 90)
    print("🔴 让方必赢 - 高命中率规则 TOP 20")
    print("=" * 90)
    print()
    print(f"{'规则名称':<45} | {'五大':<12} | {'普通':<12} | {'总计':<12} | {'评分':<6}")
    print("-" * 95)
    
    for r in handicap_win[:20]:
        big5_str = f"{r['big5_correct']}/{r['big5_total']}={r['big5_acc']*100:.0f}%"
        other_str = f"{r['other_correct']}/{r['other_total']}={r['other_acc']*100:.0f}%"
        all_str = f"{r['big5_correct']+r['other_correct']}/{r['all_total']}={r['all_acc']*100:.0f}%"
        
        mark = ""
        if r['big5_acc'] == 1.0 and r['big5_total'] >= 3:
            mark = "★五大100%"
        elif r['other_acc'] >= 0.9 and r['other_total'] >= 5:
            mark = "★普通90%+"
        
        print(f"{r['name']:<45} | {big5_str:<12} | {other_str:<12} | {all_str:<12} | {r['score']:.1f} {mark}")
    
    # 输出受让方不输规则
    print("\n" + "=" * 90)
    print("🟢 受让方不输 - 高命中率规则 TOP 20")
    print("=" * 90)
    print()
    print(f"{'规则名称':<45} | {'五大':<12} | {'普通':<12} | {'总计':<12} | {'评分':<6}")
    print("-" * 95)
    
    for r in receiver_not_lose[:20]:
        big5_str = f"{r['big5_correct']}/{r['big5_total']}={r['big5_acc']*100:.0f}%"
        other_str = f"{r['other_correct']}/{r['other_total']}={r['other_acc']*100:.0f}%"
        all_str = f"{r['big5_correct']+r['other_correct']}/{r['all_total']}={r['all_acc']*100:.0f}%"
        
        mark = ""
        if r['big5_acc'] == 1.0 and r['big5_total'] >= 3:
            mark = "★五大100%"
        elif r['other_acc'] >= 0.9 and r['other_total'] >= 5:
            mark = "★普通90%+"
        
        print(f"{r['name']:<45} | {big5_str:<12} | {other_str:<12} | {all_str:<12} | {r['score']:.1f} {mark}")
    
    # 汇总最佳规则
    print("\n" + "=" * 90)
    print("📌 推荐添加的精细规则")
    print("=" * 90)
    
    best_rules = []
    
    # 五大100%的规则
    for r in results:
        if r['big5_acc'] == 1.0 and r['big5_total'] >= 3:
            best_rules.append({
                **r,
                'apply_to': 'big5_only',
                'reason': f"五大联赛100%命中（{r['big5_correct']}/{r['big5_total']}场）"
            })
    
    # 普通90%+的规则
    for r in results:
        if r['other_acc'] >= 0.9 and r['other_total'] >= 5:
            # 检查是否已经在五大规则里
            exists = any(br['name'] == r['name'] for br in best_rules)
            if not exists:
                best_rules.append({
                    **r,
                    'apply_to': 'other_only',
                    'reason': f"普通联赛90%+命中（{r['other_correct']}/{r['other_total']}场）"
                })
            else:
                # 更新为全部适用
                for br in best_rules:
                    if br['name'] == r['name']:
                        br['apply_to'] = 'all'
                        br['reason'] += f" + 普通联赛{r['other_acc']*100:.0f}%（{r['other_correct']}/{r['other_total']}场）"
    
    # 按预测分类输出
    hw_best = [r for r in best_rules if r['predict'] == '让方必赢']
    rn_best = [r for r in best_rules if r['predict'] == '受让方不输']
    
    print(f"\n🔴 让方必赢（{len(hw_best)}条）")
    print("-" * 90)
    for i, r in enumerate(hw_best, 1):
        print(f"{i}. {r['name']}")
        print(f"   适用: {r['apply_to']} | {r['reason']}")
    
    print(f"\n🟢 受让方不输（{len(rn_best)}条）")
    print("-" * 90)
    for i, r in enumerate(rn_best, 1):
        print(f"{i}. {r['name']}")
        print(f"   适用: {r['apply_to']} | {r['reason']}")
    
    # 保存到JSON
    output = {
        'generated_at': str(__import__('datetime').datetime.now()),
        'total_matches': len(matches),
        'handicap_win_rules': hw_best,
        'receiver_not_lose_rules': rn_best
    }
    
    output_path = PROJECT_ROOT / 'validation_test' / 'detailed_rules.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2, default=str)
    
    print(f"\n✅ 规则已保存到: {output_path}")


if __name__ == '__main__':
    main()
