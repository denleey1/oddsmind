#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
全维度挖掘（重点补充平局维度组合）
让方即时赔率 >= 1.40，排除大热门
"""
import os
import sys
from typing import Dict, List, Optional
from collections import defaultdict
from itertools import combinations
import pymysql
import pymysql.cursors

sys.stdout.reconfigure(encoding='utf-8')

RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']
COMPANY_ID = '115'
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
MIN_SAMPLE = 10
MIN_ODDS = 1.40


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

        # 过滤大热门
        if curr_h_odds < MIN_ODDS:
            continue

        matches.append({
            'match_id': row['match_id'],
            'league_id': row['league_id'],
            'is_big5': row['league_id'] in BIG5_LEAGUE_IDS,
            'result': result,
            'curr_h_odds': curr_h_odds,
            # 所有维度
            'curr_h': get_range_type(curr_h_range),
            'curr_r': get_range_type(curr_r_range),
            'curr_draw': row['current_draw_range'],
            'init_h': get_range_type(init_h_range),
            'init_r': get_range_type(init_r_range),
            'init_draw': row['initial_draw_range'],
            'h_change': classify_odds_change(init_h_odds, curr_h_odds),
            'r_change': classify_odds_change(init_r_odds, curr_r_odds),
            'd_change': classify_odds_change(row['initial_draw'], row['current_draw']),
            'power': classify_power_diff(row['power_diff']),
        })
    return matches


def mine_all(matches):
    """用全排列方式系统挖掘所有2D和3D组合"""

    # 所有维度定义
    all_dims = {
        '即时让方': lambda m: m['curr_h'],
        '即时受让方': lambda m: m['curr_r'],
        '即时平局': lambda m: m['curr_draw'],
        '初盘让方': lambda m: m['init_h'],
        '初盘受让方': lambda m: m['init_r'],
        '初盘平局': lambda m: m['init_draw'],
        '让方变化': lambda m: m['h_change'],
        '受让方变化': lambda m: m['r_change'],
        '平赔变化': lambda m: m['d_change'],
        '力量差': lambda m: m['power'],
    }

    targets = {
        '让方必赢': lambda m: m['result'] == 'handicap_win',
        '让方不输': lambda m: m['result'] in ('handicap_win', 'draw'),
        '受让方不输': lambda m: m['result'] in ('receiver_win', 'draw'),
    }

    results = []
    dim_names = list(all_dims.keys())
    dim_fns = list(all_dims.values())

    # 1D
    for i, (name, fn) in enumerate(all_dims.items()):
        groups = defaultdict(list)
        for m in matches:
            v = fn(m)
            if v:
                groups[v].append(m)
        for val, group in groups.items():
            if len(group) < MIN_SAMPLE:
                continue
            for tname, tfn in targets.items():
                hits = sum(1 for m in group if tfn(m))
                acc = hits / len(group) * 100
                if acc >= 75:
                    avg_h = sum(m['curr_h_odds'] for m in group) / len(group)
                    results.append({
                        'dims': 1, 'condition': f'{name}={val}',
                        'target': tname, 'sample': len(group),
                        'hits': hits, 'accuracy': acc, 'avg_h_odds': avg_h,
                    })

    # 2D: 所有C(10,2)=45种组合
    for i, j in combinations(range(len(dim_names)), 2):
        n1, f1 = dim_names[i], dim_fns[i]
        n2, f2 = dim_names[j], dim_fns[j]
        groups = defaultdict(list)
        for m in matches:
            v1, v2 = f1(m), f2(m)
            if v1 and v2:
                groups[(v1, v2)].append(m)
        for (v1, v2), group in groups.items():
            if len(group) < MIN_SAMPLE:
                continue
            for tname, tfn in targets.items():
                hits = sum(1 for m in group if tfn(m))
                acc = hits / len(group) * 100
                if acc >= 75:
                    avg_h = sum(m['curr_h_odds'] for m in group) / len(group)
                    results.append({
                        'dims': 2, 'condition': f'{n1}={v1} + {n2}={v2}',
                        'target': tname, 'sample': len(group),
                        'hits': hits, 'accuracy': acc, 'avg_h_odds': avg_h,
                    })

    # 3D: 所有C(10,3)=120种组合
    for i, j, k in combinations(range(len(dim_names)), 3):
        n1, f1 = dim_names[i], dim_fns[i]
        n2, f2 = dim_names[j], dim_fns[j]
        n3, f3 = dim_names[k], dim_fns[k]
        groups = defaultdict(list)
        for m in matches:
            v1, v2, v3 = f1(m), f2(m), f3(m)
            if v1 and v2 and v3:
                groups[(v1, v2, v3)].append(m)
        for (v1, v2, v3), group in groups.items():
            if len(group) < MIN_SAMPLE:
                continue
            for tname, tfn in targets.items():
                hits = sum(1 for m in group if tfn(m))
                acc = hits / len(group) * 100
                if acc >= 75:
                    avg_h = sum(m['curr_h_odds'] for m in group) / len(group)
                    results.append({
                        'dims': 3, 'condition': f'{n1}={v1} + {n2}={v2} + {n3}={v3}',
                        'target': tname, 'sample': len(group),
                        'hits': hits, 'accuracy': acc, 'avg_h_odds': avg_h,
                    })

    return results


def main():
    print("=" * 100)
    print(f"全维度盘型挖掘（含平局维度全组合）")
    print(f"过滤: 让方即时赔率>={MIN_ODDS}  |  样本>={MIN_SAMPLE}  |  准确率>=75%")
    print(f"维度: 10个（即时让方/受让方/平局盘型 + 初盘让方/受让方/平局盘型 + 3个赔率变化 + 力量差）")
    print(f"组合: 1D=10, 2D=C(10,2)=45, 3D=C(10,3)=120 种排列")
    print("=" * 100)

    rows = load_data()
    matches = process(rows)
    print(f"有效比赛: {len(matches)} 场（已排除让方赔率<{MIN_ODDS}的大热门）")

    hw = sum(1 for m in matches if m['result'] == 'handicap_win')
    dr = sum(1 for m in matches if m['result'] == 'draw')
    rw = sum(1 for m in matches if m['result'] == 'receiver_win')
    print(f"基准: 让方赢{hw}({hw/len(matches)*100:.1f}%) 平{dr}({dr/len(matches)*100:.1f}%) 受让方赢{rw}({rw/len(matches)*100:.1f}%)")
    print(f"基准: 让方不输={((hw+dr)/len(matches)*100):.1f}% | 受让方不输={((rw+dr)/len(matches)*100):.1f}%")

    print("\n正在挖掘所有组合...")
    results = mine_all(matches)
    print(f"共找到 {len(results)} 条>=75%的规则")

    # 分离含平局维度和不含平局维度的规则
    draw_rules = [r for r in results if '平局' in r['condition'] or '平赔' in r['condition']]
    no_draw_rules = [r for r in results if '平局' not in r['condition'] and '平赔' not in r['condition']]

    print(f"  含平局/平赔维度: {len(draw_rules)} 条")
    print(f"  不含平局维度: {len(no_draw_rules)} 条")

    # ============ 重点输出: 含平局维度的高准确率规则 ============
    draw_ge80 = [r for r in draw_rules if r['accuracy'] >= 80 and r['sample'] >= 12]
    draw_ge80.sort(key=lambda r: (-r['accuracy'], -r['sample']))

    for target in ['让方必赢', '让方不输', '受让方不输']:
        subset = [r for r in draw_ge80 if r['target'] == target]
        if not subset:
            continue
        print(f"\n{'=' * 100}")
        print(f"【含平局维度】目标: {target}  准确率>=80%, 样本>=12")
        print(f"{'=' * 100}")
        print(f"{'维':>2} | {'准确率':>7} | {'命中/样本':>10} | {'均赔':>5} | 条件")
        print("-" * 100)
        for r in subset[:60]:
            print(f" {r['dims']}D | {r['accuracy']:6.1f}% | {r['hits']:>4}/{r['sample']:<5} | {r['avg_h_odds']:5.2f} | {r['condition']}")

    # ============ 汇总统计 ============
    print(f"\n{'=' * 100}")
    print("汇总统计")
    print(f"{'=' * 100}")

    for label, subset in [("所有规则", results), ("含平局维度", draw_rules)]:
        ge80_s15 = [r for r in subset if r['accuracy'] >= 80 and r['sample'] >= 15]
        ge85_s15 = [r for r in subset if r['accuracy'] >= 85 and r['sample'] >= 15]
        ge90_s10 = [r for r in subset if r['accuracy'] >= 90 and r['sample'] >= 10]
        print(f"\n  {label}:")
        print(f"    >=75% 总数: {len(subset)}")
        print(f"    >=80% 且样本>=15: {len(ge80_s15)}")
        print(f"    >=85% 且样本>=15: {len(ge85_s15)}")
        print(f"    >=90% 且样本>=10: {len(ge90_s10)}")

    # ============ 最终精选: 所有>=85%且样本>=15 ============
    top_rules = [r for r in results if r['accuracy'] >= 85 and r['sample'] >= 15]
    top_rules.sort(key=lambda r: (-r['accuracy'], -r['sample']))

    print(f"\n{'=' * 100}")
    print(f"精选规则: 准确率>=85% 且 样本>=15（排除大热门后）")
    print(f"{'=' * 100}")
    print(f"{'维':>2} | {'准确率':>7} | {'命中/样本':>10} | {'均赔':>5} | {'目标':<10} | {'含平':>3} | 条件")
    print("-" * 110)
    for r in top_rules:
        has_draw = '✓' if ('平局' in r['condition'] or '平赔' in r['condition']) else ' '
        print(f" {r['dims']}D | {r['accuracy']:6.1f}% | {r['hits']:>4}/{r['sample']:<5} | {r['avg_h_odds']:5.2f} | {r['target']:<10} | {has_draw:>3} | {r['condition']}")


if __name__ == '__main__':
    main()
