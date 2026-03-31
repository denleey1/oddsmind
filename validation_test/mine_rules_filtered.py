#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
过滤低赔后的盘型规则挖掘
只看让方即时赔率 >= 1.40 的比赛（排除大热门）
"""
import os
import sys
from typing import Dict, List, Optional
from collections import defaultdict
import pymysql
import pymysql.cursors

sys.stdout.reconfigure(encoding='utf-8')

RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']
COMPANY_ID = '115'
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
MIN_SAMPLE = 10
MIN_ODDS = 1.40  # 让方最低赔率


def get_db():
    return pymysql.connect(
        host='localhost', port=3306,
        user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def get_range_type(range_str):
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def classify_odds_change(init, curr):
    if init is None or curr is None or float(init) == 0:
        return '未知'
    ratio = float(curr) / float(init)
    if ratio > 1.05:
        return '升'
    elif ratio < 0.95:
        return '降'
    return '稳'


def classify_power_diff(diff):
    if diff is None:
        return '未知'
    d = float(diff)
    if d > 2:
        return '强让'
    elif d > 0.5:
        return '微让'
    elif d > -0.5:
        return '平手'
    elif d > -2:
        return '微受'
    else:
        return '强受'


def load_data():
    conn = get_db()
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
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (COMPANY_ID,))
            return cursor.fetchall()
    finally:
        conn.close()


def process(rows):
    matches = []
    all_matches = []  # 用于统计赔率分布

    for row in rows:
        ih = float(row['initial_home'])
        ia = float(row['initial_away'])
        ch = float(row['current_home'])
        ca = float(row['current_away'])

        if ih <= ia:
            handicap_side = 'home'
            h_score, r_score = row['home_score'], row['away_score']
            init_h_range = row['initial_home_range']
            init_r_range = row['initial_away_range']
            curr_h_range = row['current_home_range']
            curr_r_range = row['current_away_range']
            init_h_odds, init_r_odds = ih, ia
            curr_h_odds, curr_r_odds = ch, ca
        else:
            handicap_side = 'away'
            h_score, r_score = row['away_score'], row['home_score']
            init_h_range = row['initial_away_range']
            init_r_range = row['initial_home_range']
            curr_h_range = row['current_away_range']
            curr_r_range = row['current_home_range']
            init_h_odds, init_r_odds = ia, ih
            curr_h_odds, curr_r_odds = ca, ch

        if h_score > r_score:
            result = 'handicap_win'
        elif h_score == r_score:
            result = 'draw'
        else:
            result = 'receiver_win'

        m = {
            'match_id': row['match_id'],
            'league_id': row['league_id'],
            'league_name': row['league_name'],
            'is_big5': row['league_id'] in BIG5_LEAGUE_IDS,
            'h_score': h_score,
            'r_score': r_score,
            'result': result,
            'handicap_side': handicap_side,
            'init_h': get_range_type(init_h_range),
            'init_r': get_range_type(init_r_range),
            'curr_h': get_range_type(curr_h_range),
            'curr_r': get_range_type(curr_r_range),
            'init_draw': row['initial_draw_range'],
            'curr_draw': row['current_draw_range'],
            'h_change': classify_odds_change(init_h_odds, curr_h_odds),
            'r_change': classify_odds_change(init_r_odds, curr_r_odds),
            'd_change': classify_odds_change(row['initial_draw'], row['current_draw']),
            'power': classify_power_diff(row['power_diff']),
            'curr_h_odds': curr_h_odds,
            'curr_r_odds': curr_r_odds,
            'init_h_odds': init_h_odds,
            'init_r_odds': init_r_odds,
        }
        all_matches.append(m)

    return all_matches


def show_odds_distribution(matches):
    """先展示上次高准确率规则的赔率分布"""
    print("\n" + "=" * 90)
    print("【验证】上次高准确率规则中，让方即时赔率分布")
    print("=" * 90)

    checks = [
        ('力量差=强让', lambda m: m['power'] == '强让'),
        ('即时让方=超实 + 力量差=强让', lambda m: m['curr_h'] == '超实' and m['power'] == '强让'),
        ('即时让方=超深', lambda m: m['curr_h'] == '超深'),
        ('让方赔率稳 + 平赔升', lambda m: m['h_change'] == '稳' and m['d_change'] == '升'),
        ('受让方赔率变化=升', lambda m: m['r_change'] == '升'),
    ]

    for name, cond in checks:
        group = [m for m in matches if cond(m)]
        if not group:
            continue
        odds_list = [m['curr_h_odds'] for m in group]
        below_14 = sum(1 for o in odds_list if o < 1.40)
        between_14_20 = sum(1 for o in odds_list if 1.40 <= o < 2.00)
        above_20 = sum(1 for o in odds_list if o >= 2.00)
        avg_odds = sum(odds_list) / len(odds_list)

        print(f"\n  {name} ({len(group)}场, 平均让方赔率={avg_odds:.2f})")
        print(f"    <1.40: {below_14}场 ({below_14/len(group)*100:.1f}%)")
        print(f"    1.40~2.00: {between_14_20}场 ({between_14_20/len(group)*100:.1f}%)")
        print(f"    >=2.00: {above_20}场 ({above_20/len(group)*100:.1f}%)")


def mine_rules(matches):
    """在过滤后的数据上挖掘"""
    results = []

    targets = {
        '让方必赢': lambda m: m['result'] == 'handicap_win',
        '让方不输': lambda m: m['result'] in ('handicap_win', 'draw'),
        '受让方不输': lambda m: m['result'] in ('receiver_win', 'draw'),
    }

    single_dims = {
        '即时让方盘型': lambda m: m['curr_h'],
        '即时受让方盘型': lambda m: m['curr_r'],
        '初盘让方盘型': lambda m: m['init_h'],
        '初盘受让方盘型': lambda m: m['init_r'],
        '即时平局盘型': lambda m: m['curr_draw'],
        '初盘平局盘型': lambda m: m['init_draw'],
        '让方赔率变化': lambda m: m['h_change'],
        '受让方赔率变化': lambda m: m['r_change'],
        '平赔变化': lambda m: m['d_change'],
        '力量差': lambda m: m['power'],
    }

    combo_dims = [
        ('即时让方盘型', lambda m: m['curr_h'], '即时受让方盘型', lambda m: m['curr_r']),
        ('即时让方盘型', lambda m: m['curr_h'], '让方赔率变化', lambda m: m['h_change']),
        ('即时受让方盘型', lambda m: m['curr_r'], '受让方赔率变化', lambda m: m['r_change']),
        ('即时让方盘型', lambda m: m['curr_h'], '力量差', lambda m: m['power']),
        ('即时受让方盘型', lambda m: m['curr_r'], '力量差', lambda m: m['power']),
        ('即时让方盘型', lambda m: m['curr_h'], '即时平局盘型', lambda m: m['curr_draw']),
        ('即时受让方盘型', lambda m: m['curr_r'], '即时平局盘型', lambda m: m['curr_draw']),
        ('力量差', lambda m: m['power'], '让方赔率变化', lambda m: m['h_change']),
        ('力量差', lambda m: m['power'], '受让方赔率变化', lambda m: m['r_change']),
        ('初盘让方盘型', lambda m: m['init_h'], '即时让方盘型', lambda m: m['curr_h']),
        ('初盘受让方盘型', lambda m: m['init_r'], '即时受让方盘型', lambda m: m['curr_r']),
        ('让方赔率变化', lambda m: m['h_change'], '受让方赔率变化', lambda m: m['r_change']),
        ('让方赔率变化', lambda m: m['h_change'], '平赔变化', lambda m: m['d_change']),
        ('受让方赔率变化', lambda m: m['r_change'], '平赔变化', lambda m: m['d_change']),
    ]

    triple_dims = [
        ('即时让方盘型', lambda m: m['curr_h'], '即时受让方盘型', lambda m: m['curr_r'], '力量差', lambda m: m['power']),
        ('即时让方盘型', lambda m: m['curr_h'], '让方赔率变化', lambda m: m['h_change'], '力量差', lambda m: m['power']),
        ('即时受让方盘型', lambda m: m['curr_r'], '受让方赔率变化', lambda m: m['r_change'], '力量差', lambda m: m['power']),
        ('即时让方盘型', lambda m: m['curr_h'], '即时受让方盘型', lambda m: m['curr_r'], '让方赔率变化', lambda m: m['h_change']),
        ('即时让方盘型', lambda m: m['curr_h'], '即时平局盘型', lambda m: m['curr_draw'], '力量差', lambda m: m['power']),
        ('即时让方盘型', lambda m: m['curr_h'], '受让方赔率变化', lambda m: m['r_change'], '力量差', lambda m: m['power']),
        ('即时受让方盘型', lambda m: m['curr_r'], '让方赔率变化', lambda m: m['h_change'], '力量差', lambda m: m['power']),
        ('让方赔率变化', lambda m: m['h_change'], '受让方赔率变化', lambda m: m['r_change'], '平赔变化', lambda m: m['d_change']),
        ('即时让方盘型', lambda m: m['curr_h'], '让方赔率变化', lambda m: m['h_change'], '受让方赔率变化', lambda m: m['r_change']),
        ('即时受让方盘型', lambda m: m['curr_r'], '让方赔率变化', lambda m: m['h_change'], '受让方赔率变化', lambda m: m['r_change']),
    ]

    # 单维度
    for dim_name, dim_fn in single_dims.items():
        groups = defaultdict(list)
        for m in matches:
            val = dim_fn(m)
            if val:
                groups[val].append(m)
        for val, group in groups.items():
            if len(group) < MIN_SAMPLE:
                continue
            for target_name, target_fn in targets.items():
                hits = sum(1 for m in group if target_fn(m))
                acc = hits / len(group) * 100
                if acc >= 70:
                    avg_h = sum(m['curr_h_odds'] for m in group) / len(group)
                    results.append({
                        'dims': 1, 'condition': f'{dim_name}={val}',
                        'target': target_name, 'sample': len(group),
                        'hits': hits, 'accuracy': acc, 'avg_h_odds': avg_h,
                    })

    # 双维度
    for d1_name, d1_fn, d2_name, d2_fn in combo_dims:
        groups = defaultdict(list)
        for m in matches:
            v1, v2 = d1_fn(m), d2_fn(m)
            if v1 and v2:
                groups[(v1, v2)].append(m)
        for (v1, v2), group in groups.items():
            if len(group) < MIN_SAMPLE:
                continue
            for target_name, target_fn in targets.items():
                hits = sum(1 for m in group if target_fn(m))
                acc = hits / len(group) * 100
                if acc >= 70:
                    avg_h = sum(m['curr_h_odds'] for m in group) / len(group)
                    results.append({
                        'dims': 2, 'condition': f'{d1_name}={v1} + {d2_name}={v2}',
                        'target': target_name, 'sample': len(group),
                        'hits': hits, 'accuracy': acc, 'avg_h_odds': avg_h,
                    })

    # 三维度
    for d1_name, d1_fn, d2_name, d2_fn, d3_name, d3_fn in triple_dims:
        groups = defaultdict(list)
        for m in matches:
            v1, v2, v3 = d1_fn(m), d2_fn(m), d3_fn(m)
            if v1 and v2 and v3:
                groups[(v1, v2, v3)].append(m)
        for (v1, v2, v3), group in groups.items():
            if len(group) < MIN_SAMPLE:
                continue
            for target_name, target_fn in targets.items():
                hits = sum(1 for m in group if target_fn(m))
                acc = hits / len(group) * 100
                if acc >= 70:
                    avg_h = sum(m['curr_h_odds'] for m in group) / len(group)
                    results.append({
                        'dims': 3, 'condition': f'{d1_name}={v1} + {d2_name}={v2} + {d3_name}={v3}',
                        'target': target_name, 'sample': len(group),
                        'hits': hits, 'accuracy': acc, 'avg_h_odds': avg_h,
                    })

    return results


def main():
    print("=" * 90)
    print(f"盘型规则挖掘（排除大热门: 让方即时赔率 >= {MIN_ODDS}）")
    print(f"数据源: 威廉公司(ID={COMPANY_ID}), 最小样本={MIN_SAMPLE}")
    print("=" * 90)

    rows = load_data()
    all_matches = process(rows)
    print(f"全部比赛: {len(all_matches)}")

    # 先展示上次规则的赔率分布
    show_odds_distribution(all_matches)

    # 过滤
    filtered = [m for m in all_matches if m['curr_h_odds'] >= MIN_ODDS]
    print(f"\n{'=' * 90}")
    print(f"过滤后（让方即时赔率>={MIN_ODDS}）: {len(filtered)} 场")
    print(f"被排除（大热门<{MIN_ODDS}）: {len(all_matches) - len(filtered)} 场")
    print(f"{'=' * 90}")

    # 过滤后赛果分布
    hw = sum(1 for m in filtered if m['result'] == 'handicap_win')
    dr = sum(1 for m in filtered if m['result'] == 'draw')
    rw = sum(1 for m in filtered if m['result'] == 'receiver_win')
    print(f"\n  过滤后赛果基准线:")
    print(f"    让方赢: {hw} ({hw/len(filtered)*100:.1f}%)")
    print(f"    平局:   {dr} ({dr/len(filtered)*100:.1f}%)")
    print(f"    受让方赢: {rw} ({rw/len(filtered)*100:.1f}%)")
    print(f"    让方不输基准: {(hw+dr)/len(filtered)*100:.1f}%")
    print(f"    受让方不输基准: {(rw+dr)/len(filtered)*100:.1f}%")

    results = mine_rules(filtered)
    results.sort(key=lambda r: (-r['accuracy'], -r['sample']))

    # 输出
    for target in ['让方必赢', '让方不输', '受让方不输']:
        subset = [r for r in results if r['target'] == target]
        if not subset:
            print(f"\n{'=' * 90}")
            print(f"目标: {target} — 无达标规则")
            continue

        print(f"\n{'=' * 90}")
        print(f"目标: {target}  (共 {len(subset)} 条, 样本>={MIN_SAMPLE}, 准确率>=70%)")
        print(f"{'=' * 90}")
        print(f"{'维':>2} | {'准确率':>7} | {'命中/样本':>10} | {'均赔':>5} | 条件")
        print("-" * 90)

        for r in subset[:50]:  # 只显示前50
            print(f" {r['dims']}D | {r['accuracy']:6.1f}% | {r['hits']:>4}/{r['sample']:<5} | {r['avg_h_odds']:5.2f} | {r['condition']}")

    # 重点汇总
    ge75 = [r for r in results if r['accuracy'] >= 75 and r['sample'] >= 15]
    ge80 = [r for r in results if r['accuracy'] >= 80 and r['sample'] >= 15]
    print(f"\n{'=' * 90}")
    print(f"重点汇总（过滤大热门后）")
    print(f"{'=' * 90}")
    print(f">=70% 且样本>=10: {len(results)}")
    print(f">=75% 且样本>=15: {len(ge75)}")
    print(f">=80% 且样本>=15: {len(ge80)}")

    if ge80:
        print(f"\n*** >=80% 且样本>=15（排除大热门后）***")
        print(f"{'维':>2} | {'准确率':>7} | {'命中/样本':>10} | {'均赔':>5} | {'目标':<10} | 条件")
        print("-" * 100)
        ge80.sort(key=lambda r: (-r['accuracy'], -r['sample']))
        for r in ge80:
            print(f" {r['dims']}D | {r['accuracy']:6.1f}% | {r['hits']:>4}/{r['sample']:<5} | {r['avg_h_odds']:5.2f} | {r['target']:<10} | {r['condition']}")
    elif ge75:
        print(f"\n*** 没有>=80%的，展示>=75% 且样本>=15 ***")
        print(f"{'维':>2} | {'准确率':>7} | {'命中/样本':>10} | {'均赔':>5} | {'目标':<10} | 条件")
        print("-" * 100)
        ge75.sort(key=lambda r: (-r['accuracy'], -r['sample']))
        for r in ge75[:30]:
            print(f" {r['dims']}D | {r['accuracy']:6.1f}% | {r['hits']:>4}/{r['sample']:<5} | {r['avg_h_odds']:5.2f} | {r['target']:<10} | {r['condition']}")


if __name__ == '__main__':
    main()
