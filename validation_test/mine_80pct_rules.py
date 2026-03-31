#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
挖掘准确率~80%的盘型规则（单维度+组合）
目标：让方必赢 / 让方不输 / 受让方不输
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

# 最小样本量（太少无意义）
MIN_SAMPLE = 15


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

        matches.append({
            'match_id': row['match_id'],
            'league_id': row['league_id'],
            'league_name': row['league_name'],
            'is_big5': row['league_id'] in BIG5_LEAGUE_IDS,
            'h_score': h_score,
            'r_score': r_score,
            'result': result,
            'handicap_side': handicap_side,
            # 盘型
            'init_h': get_range_type(init_h_range),
            'init_r': get_range_type(init_r_range),
            'curr_h': get_range_type(curr_h_range),
            'curr_r': get_range_type(curr_r_range),
            'init_draw': row['initial_draw_range'],
            'curr_draw': row['current_draw_range'],
            # 赔率变化
            'h_change': classify_odds_change(init_h_odds, curr_h_odds),
            'r_change': classify_odds_change(init_r_odds, curr_r_odds),
            'd_change': classify_odds_change(row['initial_draw'], row['current_draw']),
            # 力量差
            'power': classify_power_diff(row['power_diff']),
        })
    return matches


def mine_rules(matches):
    """挖掘所有维度和组合"""
    results = []

    # ============== 三种目标 ==============
    targets = {
        '让方必赢': lambda m: m['result'] == 'handicap_win',
        '让方不输': lambda m: m['result'] in ('handicap_win', 'draw'),
        '受让方不输': lambda m: m['result'] in ('receiver_win', 'draw'),
    }

    # ============== 单维度条件 ==============
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

    # ============== 双维度组合条件 ==============
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
    ]

    # ============== 三维度组合 ==============
    triple_dims = [
        ('即时让方盘型', lambda m: m['curr_h'], '即时受让方盘型', lambda m: m['curr_r'], '力量差', lambda m: m['power']),
        ('即时让方盘型', lambda m: m['curr_h'], '让方赔率变化', lambda m: m['h_change'], '力量差', lambda m: m['power']),
        ('即时受让方盘型', lambda m: m['curr_r'], '受让方赔率变化', lambda m: m['r_change'], '力量差', lambda m: m['power']),
        ('即时让方盘型', lambda m: m['curr_h'], '即时受让方盘型', lambda m: m['curr_r'], '让方赔率变化', lambda m: m['h_change']),
        ('即时让方盘型', lambda m: m['curr_h'], '即时平局盘型', lambda m: m['curr_draw'], '力量差', lambda m: m['power']),
    ]

    print(f"总比赛数: {len(matches)}")
    print(f"五大联赛: {sum(1 for m in matches if m['is_big5'])}")
    print(f"其他联赛: {sum(1 for m in matches if not m['is_big5'])}")

    # ------------ 1. 单维度挖掘 ------------
    print("\n" + "=" * 90)
    print("【单维度挖掘】")
    print("=" * 90)

    for dim_name, dim_fn in single_dims.items():
        groups = defaultdict(list)
        for m in matches:
            val = dim_fn(m)
            if val:
                groups[val].append(m)

        for val, group in sorted(groups.items(), key=lambda x: -len(x[1])):
            if len(group) < MIN_SAMPLE:
                continue
            for target_name, target_fn in targets.items():
                hits = sum(1 for m in group if target_fn(m))
                acc = hits / len(group) * 100
                if acc >= 75:
                    results.append({
                        'dims': 1,
                        'condition': f'{dim_name}={val}',
                        'target': target_name,
                        'sample': len(group),
                        'hits': hits,
                        'accuracy': acc,
                    })

    # ------------ 2. 双维度挖掘 ------------
    print("\n" + "=" * 90)
    print("【双维度挖掘】")
    print("=" * 90)

    for d1_name, d1_fn, d2_name, d2_fn in combo_dims:
        groups = defaultdict(list)
        for m in matches:
            v1 = d1_fn(m)
            v2 = d2_fn(m)
            if v1 and v2:
                groups[(v1, v2)].append(m)

        for (v1, v2), group in sorted(groups.items(), key=lambda x: -len(x[1])):
            if len(group) < MIN_SAMPLE:
                continue
            for target_name, target_fn in targets.items():
                hits = sum(1 for m in group if target_fn(m))
                acc = hits / len(group) * 100
                if acc >= 75:
                    results.append({
                        'dims': 2,
                        'condition': f'{d1_name}={v1} + {d2_name}={v2}',
                        'target': target_name,
                        'sample': len(group),
                        'hits': hits,
                        'accuracy': acc,
                    })

    # ------------ 3. 三维度挖掘 ------------
    print("\n" + "=" * 90)
    print("【三维度挖掘】")
    print("=" * 90)

    for d1_name, d1_fn, d2_name, d2_fn, d3_name, d3_fn in triple_dims:
        groups = defaultdict(list)
        for m in matches:
            v1 = d1_fn(m)
            v2 = d2_fn(m)
            v3 = d3_fn(m)
            if v1 and v2 and v3:
                groups[(v1, v2, v3)].append(m)

        for (v1, v2, v3), group in sorted(groups.items(), key=lambda x: -len(x[1])):
            if len(group) < MIN_SAMPLE:
                continue
            for target_name, target_fn in targets.items():
                hits = sum(1 for m in group if target_fn(m))
                acc = hits / len(group) * 100
                if acc >= 75:
                    results.append({
                        'dims': 3,
                        'condition': f'{d1_name}={v1} + {d2_name}={v2} + {d3_name}={v3}',
                        'target': target_name,
                        'sample': len(group),
                        'hits': hits,
                        'accuracy': acc,
                    })

    return results


def print_results(results):
    # 按准确率降序，样本量降序排列
    results.sort(key=lambda r: (-r['accuracy'], -r['sample']))

    # 分类输出
    for target in ['让方必赢', '让方不输', '受让方不输']:
        subset = [r for r in results if r['target'] == target]
        if not subset:
            continue

        print(f"\n{'=' * 90}")
        print(f"目标: {target}  (共 {len(subset)} 条规则, 样本>={MIN_SAMPLE}, 准确率>=75%)")
        print(f"{'=' * 90}")
        print(f"{'维度':>4} | {'准确率':>7} | {'命中/样本':>10} | 条件")
        print("-" * 90)

        for r in subset:
            print(f"  {r['dims']}D  | {r['accuracy']:6.1f}% | {r['hits']:>4}/{r['sample']:<5} | {r['condition']}")


def main():
    print("=" * 90)
    print("盘型规则挖掘 - 目标: ~80%准确率")
    print(f"数据源: 威廉公司(ID={COMPANY_ID}), 最小样本={MIN_SAMPLE}")
    print("=" * 90)

    print("\n正在加载数据...")
    rows = load_data()
    print(f"原始记录: {len(rows)}")

    matches = process(rows)
    results = mine_rules(matches)
    print_results(results)

    # 总结
    print(f"\n{'=' * 90}")
    print("总结")
    print(f"{'=' * 90}")
    total = len(results)
    ge80 = [r for r in results if r['accuracy'] >= 80]
    ge85 = [r for r in results if r['accuracy'] >= 85]
    ge90 = [r for r in results if r['accuracy'] >= 90]
    big_sample = [r for r in results if r['accuracy'] >= 80 and r['sample'] >= 30]
    print(f">=75%: {total} 条")
    print(f">=80%: {len(ge80)} 条")
    print(f">=85%: {len(ge85)} 条")
    print(f">=90%: {len(ge90)} 条")
    print(f">=80% 且样本>=30: {len(big_sample)} 条")

    if big_sample:
        print(f"\n*** 重点关注: >=80%准确率 且 样本>=30 ***")
        big_sample.sort(key=lambda r: (-r['accuracy'], -r['sample']))
        print(f"{'维度':>4} | {'准确率':>7} | {'命中/样本':>10} | {'目标':<10} | 条件")
        print("-" * 90)
        for r in big_sample:
            print(f"  {r['dims']}D  | {r['accuracy']:6.1f}% | {r['hits']:>4}/{r['sample']:<5} | {r['target']:<10} | {r['condition']}")


if __name__ == '__main__':
    main()
