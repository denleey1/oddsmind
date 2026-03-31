#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
网格搜索：降赔幅度 × 公司支持数降幅 → 让方胜率最优组合

自动遍历所有 [降赔下限, 降赔上限] × [支持数降幅下限, 支持数降幅上限] 组合
找出让方胜率和不败率最高的区间组合
"""

import sys
import os
import pymysql
import pymysql.cursors
from datetime import datetime
from itertools import combinations

sys.stdout.reconfigure(encoding='utf-8')

WILLIAM_COMPANY_ID = 115
MIN_SAMPLE = 8  # 最小样本数

RECOMMENDATION_MAPPING = {
    '主让1胜': ['home_win'], '主让1平': ['home_win'], '主让1负': ['draw', 'away_win'],
    '主让2胜': ['home_win'], '主让2平': ['home_win'],
    '客让1胜': ['away_win'], '客让1平': ['away_win'],
    '客让2胜': ['away_win'], '客让2平': ['away_win'],
    '主受1胜': ['home_win', 'draw'], '客受1胜': ['away_win', 'draw'],
    '平': ['draw'], '双平': ['home_win', 'draw', 'away_win'],
    '双平偏平': ['draw'], '双平偏让平': ['draw'],
}


def get_db():
    return pymysql.connect(
        host='localhost', port=3306, user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind', charset='utf8mb4', cursorclass=pymysql.cursors.DictCursor)


def map_recommendation(rec, hrv=None, arv=None):
    if not rec: return []
    if rec == '双平偏让平':
        if hrv is not None and arv is not None:
            if hrv < arv: return ['home_win']
            elif arv < hrv: return ['away_win']
        return ['draw']
    return RECOMMENDATION_MAPPING.get(rec, [])


def calc_support(companies, target):
    init_c = curr_c = 0.0
    for c in companies:
        im = map_recommendation(c['initial_recommended_outcome'],
                                c.get('initial_home_rule_value'), c.get('initial_away_rule_value'))
        if im and target in im: init_c += 1.0 / len(im)
        cm = map_recommendation(c['current_recommended_outcome'],
                                c.get('current_home_rule_value'), c.get('current_away_rule_value'))
        if cm and target in cm: curr_c += 1.0 / len(cm)
    return round(init_c), round(curr_c)


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--min-sample', type=int, default=MIN_SAMPLE)
    parser.add_argument('--top', type=int, default=30, help='显示前N个最优组合')
    args = parser.parse_args()

    conn = get_db()
    cur = conn.cursor()
    print("\n正在查询数据...")

    cur.execute('''
        SELECT oar.match_id, oar.initial_home_fullwater, oar.initial_away_fullwater,
               oar.current_home_fullwater, oar.current_away_fullwater,
               m.home_team_name, m.away_team_name, m.home_score, m.away_score, m.match_time,
               l.name_cn AS league_name
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = %s AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
          AND oar.initial_home_fullwater IS NOT NULL AND oar.current_home_fullwater IS NOT NULL
        ORDER BY m.match_time DESC
    ''', (WILLIAM_COMPANY_ID,))
    wm_list = cur.fetchall()
    print(f"威廉已完赛: {len(wm_list)} 场")

    mids = [r['match_id'] for r in wm_list]
    if not mids: print("无数据"); conn.close(); return

    all_cd = {}
    for i in range(0, len(mids), 500):
        batch = mids[i:i+500]
        ph = ','.join(['%s'] * len(batch))
        cur.execute(f'''SELECT match_id, company_id, initial_recommended_outcome, current_recommended_outcome,
                        initial_home_rule_value, initial_away_rule_value,
                        current_home_rule_value, current_away_rule_value
                    FROM odds_analysis_results WHERE match_id IN ({ph})''', batch)
        for r in cur.fetchall():
            all_cd.setdefault(r['match_id'], []).append(r)
    conn.close()

    # 构建每场比赛的两个维度值
    data_points = []  # (odds_drop, support_drop, fav_won, fav_not_lose, is_draw, match_info)

    for wm in wm_list:
        mid = wm['match_id']
        ih, ia = float(wm['initial_home_fullwater']), float(wm['initial_away_fullwater'])
        ch, ca = float(wm['current_home_fullwater']), float(wm['current_away_fullwater'])
        hs, aws = int(wm['home_score']), int(wm['away_score'])

        if ih < ia:
            fav_init, fav_curr, fav_out = ih, ch, 'home_win'
            fav_won, fav_nl = hs > aws, hs >= aws
        elif ia < ih:
            fav_init, fav_curr, fav_out = ia, ca, 'away_win'
            fav_won, fav_nl = aws > hs, aws >= hs
        else:
            continue

        od = fav_init - fav_curr
        if od <= 0: continue

        companies = all_cd.get(mid, [])
        isup, csup = calc_support(companies, fav_out)
        sd = isup - csup
        if sd <= 0: continue

        data_points.append((od, sd, fav_won, fav_nl, hs == aws))

    print(f"满足条件(降赔+支持数降): {len(data_points)} 场\n")

    # ========== 网格搜索 ==========
    # 降赔切分点
    od_cuts = [0.01, 0.03, 0.05, 0.08, 0.10, 0.13, 0.16, 0.20, 0.25, 0.30, 0.40, 0.50, 999]
    # 支持数降幅切分点
    sd_cuts = [1, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50, 9999]

    # 生成所有区间组合
    od_ranges = []
    for i in range(len(od_cuts)):
        for j in range(i + 1, len(od_cuts)):
            od_ranges.append((od_cuts[i], od_cuts[j]))

    sd_ranges = []
    for i in range(len(sd_cuts)):
        for j in range(i + 1, len(sd_cuts)):
            sd_ranges.append((sd_cuts[i], sd_cuts[j]))

    # 搜索最优组合
    results_win = []   # (胜率, 不败率, 场次, 胜, 平, 负, od_lo, od_hi, sd_lo, sd_hi)
    results_nb = []    # 同上，按不败率排

    for od_lo, od_hi in od_ranges:
        for sd_lo, sd_hi in sd_ranges:
            subset = [d for d in data_points
                      if od_lo <= d[0] < od_hi and sd_lo <= d[1] < sd_hi]
            n = len(subset)
            if n < args.min_sample:
                continue
            w = sum(1 for d in subset if d[2])
            dr = sum(1 for d in subset if d[4])
            l = n - w - dr
            win_pct = w / n * 100
            nb_pct = (w + dr) / n * 100
            row = (win_pct, nb_pct, n, w, dr, l, od_lo, od_hi, sd_lo, sd_hi)
            results_win.append(row)
            results_nb.append(row)

    results_win.sort(key=lambda x: (-x[0], -x[2]))  # 胜率优先，样本量次之
    results_nb.sort(key=lambda x: (-x[1], -x[2]))    # 不败率优先

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{'=' * 110}")
    print(f"  网格搜索结果：降赔幅度 × 支持数降幅 → 让方胜率/不败率")
    print(f"  基准: 威廉 | 时间: {now_str} | 总样本: {len(data_points)} 场 | 最小样本: {args.min_sample}")
    print(f"  搜索空间: {len(od_ranges)} 个降赔区间 × {len(sd_ranges)} 个支持降幅区间 = {len(od_ranges)*len(sd_ranges)} 种组合")
    print(f"{'=' * 110}")

    # TOP N 让方胜率
    print(f"\n  ◆ TOP {args.top} 让方胜率最高组合")
    print(f"  {'#':>3s}  {'降赔区间':<16s}  {'支持数降幅':<14s}  {'场次':>4s}  {'胜':>3s}  {'平':>3s}  {'负':>3s}  {'胜率':>7s}  {'不败率':>7s}")
    print(f"  {'─' * 85}")
    seen = set()
    rank = 0
    for r in results_win:
        if rank >= args.top: break
        key = (r[6], r[7], r[8], r[9])
        if key in seen: continue
        seen.add(key)
        rank += 1
        od_hi_str = f"{r[7]:.2f}" if r[7] < 100 else "∞"
        sd_hi_str = f"{int(r[9])}" if r[9] < 9000 else "∞"
        print(f"  {rank:>3d}  [{r[6]:.2f}, {od_hi_str}){'':<4s}  "
              f"[{int(r[8])}, {sd_hi_str}){'':<4s}  "
              f"{r[2]:>4d}  {r[3]:>3d}  {r[4]:>3d}  {r[5]:>3d}  {r[0]:>6.1f}%  {r[1]:>6.1f}%")

    # TOP N 让方不败率
    print(f"\n  ◆ TOP {args.top} 让方不败率最高组合")
    print(f"  {'#':>3s}  {'降赔区间':<16s}  {'支持数降幅':<14s}  {'场次':>4s}  {'胜':>3s}  {'平':>3s}  {'负':>3s}  {'胜率':>7s}  {'不败率':>7s}")
    print(f"  {'─' * 85}")
    seen = set()
    rank = 0
    for r in results_nb:
        if rank >= args.top: break
        key = (r[6], r[7], r[8], r[9])
        if key in seen: continue
        seen.add(key)
        rank += 1
        od_hi_str = f"{r[7]:.2f}" if r[7] < 100 else "∞"
        sd_hi_str = f"{int(r[9])}" if r[9] < 9000 else "∞"
        print(f"  {rank:>3d}  [{r[6]:.2f}, {od_hi_str}){'':<4s}  "
              f"[{int(r[8])}, {sd_hi_str}){'':<4s}  "
              f"{r[2]:>4d}  {r[3]:>3d}  {r[4]:>3d}  {r[5]:>3d}  {r[0]:>6.1f}%  {r[1]:>6.1f}%")

    # ========== 实用推荐区间 ==========
    # 从不败率排序中，找样本>=15 且不败率>=80% 的
    print(f"\n  ◆ 实用推荐（不败率>=80% 且 样本>=15）")
    print(f"  {'#':>3s}  {'降赔区间':<16s}  {'支持数降幅':<14s}  {'场次':>4s}  {'胜':>3s}  {'平':>3s}  {'负':>3s}  {'胜率':>7s}  {'不败率':>7s}")
    print(f"  {'─' * 85}")
    practical = [r for r in results_nb if r[1] >= 80 and r[2] >= 15]
    # 去掉互相嵌套的大区间，优先保留小区间
    practical.sort(key=lambda x: (-x[1], -x[0], x[2]))
    rank = 0
    for r in practical[:30]:
        rank += 1
        od_hi_str = f"{r[7]:.2f}" if r[7] < 100 else "∞"
        sd_hi_str = f"{int(r[9])}" if r[9] < 9000 else "∞"
        star = ' ★★' if r[0] >= 70 else (' ★' if r[0] >= 60 else '')
        print(f"  {rank:>3d}  [{r[6]:.2f}, {od_hi_str}){'':<4s}  "
              f"[{int(r[8])}, {sd_hi_str}){'':<4s}  "
              f"{r[2]:>4d}  {r[3]:>3d}  {r[4]:>3d}  {r[5]:>3d}  {r[0]:>6.1f}%  {r[1]:>6.1f}%{star}")

    if not practical:
        print("  未找到满足条件的组合，请降低 --min-sample")

    # ========== 最差区间（让方负率最高） ==========
    worst = sorted(results_win, key=lambda x: (x[0], -x[2]))
    print(f"\n  ◆ 让方最差区间（胜率最低，样本>=10）")
    print(f"  {'#':>3s}  {'降赔区间':<16s}  {'支持数降幅':<14s}  {'场次':>4s}  {'胜':>3s}  {'平':>3s}  {'负':>3s}  {'胜率':>7s}  {'不败率':>7s}")
    print(f"  {'─' * 85}")
    seen = set()
    rank = 0
    for r in worst:
        if rank >= 15: break
        if r[2] < 10: continue
        key = (r[6], r[7], r[8], r[9])
        if key in seen: continue
        seen.add(key)
        rank += 1
        od_hi_str = f"{r[7]:.2f}" if r[7] < 100 else "∞"
        sd_hi_str = f"{int(r[9])}" if r[9] < 9000 else "∞"
        print(f"  {rank:>3d}  [{r[6]:.2f}, {od_hi_str}){'':<4s}  "
              f"[{int(r[8])}, {sd_hi_str}){'':<4s}  "
              f"{r[2]:>4d}  {r[3]:>3d}  {r[4]:>3d}  {r[5]:>3d}  {r[0]:>6.1f}%  {r[1]:>6.1f}%")

    # ========== 散点分布 ==========
    print(f"\n  ◆ 数据散点分布（降赔 vs 支持降幅 频次）")
    # 用固定区间做一个简洁的热力图
    od_fixed = [(0.01, 0.05), (0.05, 0.10), (0.10, 0.16), (0.16, 0.25), (0.25, 0.40), (0.40, 999)]
    sd_fixed = [(1, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 9999)]

    od_labels = ['0.01-0.05', '0.05-0.10', '0.10-0.16', '0.16-0.25', '0.25-0.40', '0.40+']
    sd_labels = ['↓1-4', '↓5-9', '↓10-19', '↓20-29', '↓30-49', '↓50+']

    print(f"\n  {'降赔＼支持↓':>12s}", end='')
    for sl in sd_labels:
        print(f"  {sl:>12s}", end='')
    print()
    print(f"  {'─' * (14 + 14 * len(sd_labels))}")

    for oi, (od_lo, od_hi) in enumerate(od_fixed):
        print(f"  {od_labels[oi]:>12s}", end='')
        for si, (sd_lo, sd_hi) in enumerate(sd_fixed):
            sub = [d for d in data_points if od_lo <= d[0] < od_hi and sd_lo <= d[1] < sd_hi]
            n = len(sub)
            if n == 0:
                print(f"  {'·':>12s}", end='')
            else:
                w = sum(1 for d in sub if d[2])
                pct = w / n * 100 if n > 0 else 0
                if n >= args.min_sample:
                    marker = '★' if (w + sum(1 for d in sub if d[4])) / n >= 0.8 else ' '
                    print(f"  {pct:4.0f}%/{n:2d}场{marker}", end='')
                else:
                    print(f"  ({pct:3.0f}%/{n:1d}场) ", end='')
        print()

    print(f"\n{'=' * 110}\n")


if __name__ == '__main__':
    main()
