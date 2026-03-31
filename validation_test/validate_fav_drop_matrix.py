#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证脚本：让方降赔幅度 × 公司支持数下降幅度 交叉分析矩阵

按降水区间和公司支持数下降区间分组，找出让方胜率/不败率的规律
"""

import sys
import os
import pymysql
import pymysql.cursors
from datetime import datetime
from collections import defaultdict

sys.stdout.reconfigure(encoding='utf-8')

WILLIAM_COMPANY_ID = 115

# ========== 推荐映射规则 ==========
RECOMMENDATION_MAPPING = {
    '主让1胜': ['home_win'],
    '主让1平': ['home_win'],
    '主让1负': ['draw', 'away_win'],
    '主让2胜': ['home_win'],
    '主让2平': ['home_win'],
    '客让1胜': ['away_win'],
    '客让1平': ['away_win'],
    '客让2胜': ['away_win'],
    '客让2平': ['away_win'],
    '主受1胜': ['home_win', 'draw'],
    '客受1胜': ['away_win', 'draw'],
    '平': ['draw'],
    '双平': ['home_win', 'draw', 'away_win'],
    '双平偏平': ['draw'],
    '双平偏让平': ['draw'],
}

# 降水区间定义
ODDS_DROP_BINS = [
    ('0.01-0.05', 0.01, 0.05),
    ('0.05-0.10', 0.05, 0.10),
    ('0.10-0.16', 0.10, 0.16),
    ('0.16-0.25', 0.16, 0.25),
    ('0.25-0.40', 0.25, 0.40),
    ('0.40+',     0.40, 999),
]

# 公司支持数下降区间
SUPPORT_DROP_BINS = [
    ('↓1-3',   1, 3),
    ('↓4-8',   4, 8),
    ('↓9-15',  9, 15),
    ('↓16-25', 16, 25),
    ('↓26-40', 26, 40),
    ('↓40+',   40, 9999),
]


def get_db():
    return pymysql.connect(
        host='localhost', port=3306,
        user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def map_recommendation(rec, home_rule_value=None, away_rule_value=None):
    if not rec:
        return []
    if rec == '双平偏让平':
        if home_rule_value is not None and away_rule_value is not None:
            if home_rule_value < away_rule_value:
                return ['home_win']
            elif away_rule_value < home_rule_value:
                return ['away_win']
            else:
                return ['draw']
        return ['draw']
    if rec in RECOMMENDATION_MAPPING:
        return RECOMMENDATION_MAPPING[rec]
    if '主胜' in rec:
        return ['home_win']
    elif '客胜' in rec:
        return ['away_win']
    elif '平' in rec:
        return ['draw']
    return []


def calc_support_count(companies, target_outcome):
    init_count = 0.0
    curr_count = 0.0
    for c in companies:
        init_mapped = map_recommendation(
            c['initial_recommended_outcome'],
            c.get('initial_home_rule_value'),
            c.get('initial_away_rule_value'))
        if init_mapped and target_outcome in init_mapped:
            init_count += 1.0 / len(init_mapped)
        curr_mapped = map_recommendation(
            c['current_recommended_outcome'],
            c.get('current_home_rule_value'),
            c.get('current_away_rule_value'))
        if curr_mapped and target_outcome in curr_mapped:
            curr_count += 1.0 / len(curr_mapped)
    return round(init_count), round(curr_count)


def find_bin(value, bins):
    for label, lo, hi in bins:
        if lo <= value < hi or (hi == 999 and value >= lo) or (hi == 9999 and value >= lo):
            return label
    return None


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--verbose', '-v', action='store_true')
    parser.add_argument('--min-sample', type=int, default=5, help='矩阵单元格最小样本数(默认5)')
    args = parser.parse_args()

    conn = get_db()
    cursor = conn.cursor()
    print("\n正在查询数据...")

    cursor.execute('''
        SELECT oar.match_id,
               oar.initial_home_fullwater, oar.initial_away_fullwater,
               oar.current_home_fullwater, oar.current_away_fullwater,
               m.home_team_name, m.away_team_name,
               m.home_score, m.away_score, m.match_time,
               l.name_cn AS league_name
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = %s
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
          AND oar.initial_home_fullwater IS NOT NULL
          AND oar.current_home_fullwater IS NOT NULL
        ORDER BY m.match_time DESC
    ''', (WILLIAM_COMPANY_ID,))
    william_matches = cursor.fetchall()
    print(f"威廉已完赛: {len(william_matches)} 场")

    match_ids = [r['match_id'] for r in william_matches]
    if not match_ids:
        print("无数据"); conn.close(); return

    all_company_data = {}
    batch_size = 500
    for i in range(0, len(match_ids), batch_size):
        batch = match_ids[i:i + batch_size]
        ph = ','.join(['%s'] * len(batch))
        cursor.execute(f'''
            SELECT match_id, company_id,
                   initial_recommended_outcome, current_recommended_outcome,
                   initial_home_rule_value, initial_away_rule_value,
                   current_home_rule_value, current_away_rule_value
            FROM odds_analysis_results WHERE match_id IN ({ph})
        ''', batch)
        for row in cursor.fetchall():
            all_company_data.setdefault(row['match_id'], []).append(row)
    conn.close()

    # ========== 逐场分析 ==========
    records = []  # 所有满足降赔+支持数减少的记录

    for wm in william_matches:
        mid = wm['match_id']
        ih = float(wm['initial_home_fullwater'])
        ia = float(wm['initial_away_fullwater'])
        ch = float(wm['current_home_fullwater'])
        ca = float(wm['current_away_fullwater'])
        hs = int(wm['home_score'])
        aws = int(wm['away_score'])

        if ih < ia:
            fav_side = 'home'
            fav_init, fav_curr = ih, ch
            fav_outcome = 'home_win'
            fav_team = wm['home_team_name']
        elif ia < ih:
            fav_side = 'away'
            fav_init, fav_curr = ia, ca
            fav_outcome = 'away_win'
            fav_team = wm['away_team_name']
        else:
            continue

        odds_drop = fav_init - fav_curr
        if odds_drop <= 0:
            continue  # 没降赔

        companies = all_company_data.get(mid, [])
        init_sup, curr_sup = calc_support_count(companies, fav_outcome)
        support_drop = init_sup - curr_sup
        if support_drop <= 0:
            continue  # 支持数没减少

        if fav_side == 'home':
            fav_won = hs > aws
            fav_not_lose = hs >= aws
        else:
            fav_won = aws > hs
            fav_not_lose = aws >= hs

        is_draw = hs == aws

        records.append({
            'match_id': mid,
            'match_time': wm['match_time'],
            'league': wm.get('league_name', '?'),
            'home_team': wm['home_team_name'],
            'away_team': wm['away_team_name'],
            'score': f"{hs}:{aws}",
            'fav_side': '主' if fav_side == 'home' else '客',
            'fav_team': fav_team,
            'fav_init': fav_init,
            'fav_curr': fav_curr,
            'odds_drop': odds_drop,
            'init_sup': init_sup,
            'curr_sup': curr_sup,
            'support_drop': support_drop,
            'fav_won': fav_won,
            'fav_not_lose': fav_not_lose,
            'is_draw': is_draw,
        })

    total = len(records)
    print(f"满足条件(降赔+支持数减少): {total} 场\n")

    # ========== 交叉矩阵 ==========
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{'=' * 100}")
    print(f"  降赔幅度 × 公司支持数下降幅度 → 让方胜率/不败率 交叉矩阵")
    print(f"  基准: 威廉 | 时间: {now_str} | 总样本: {total} 场")
    print(f"{'=' * 100}")

    # 构建矩阵数据
    matrix = {}
    for od_label, _, _ in ODDS_DROP_BINS:
        matrix[od_label] = {}
        for sd_label, _, _ in SUPPORT_DROP_BINS:
            matrix[od_label][sd_label] = {'total': 0, 'win': 0, 'draw': 0, 'lose': 0}

    for r in records:
        od_bin = find_bin(r['odds_drop'], ODDS_DROP_BINS)
        sd_bin = find_bin(r['support_drop'], SUPPORT_DROP_BINS)
        if od_bin and sd_bin:
            cell = matrix[od_bin][sd_bin]
            cell['total'] += 1
            if r['fav_won']:
                cell['win'] += 1
            elif r['is_draw']:
                cell['draw'] += 1
            else:
                cell['lose'] += 1

    # 打印矩阵 - 让方胜率
    sd_labels = [l for l, _, _ in SUPPORT_DROP_BINS]
    col_w = 14

    print(f"\n  ◆ 让方胜率矩阵 (样本数 >= {args.min_sample} 才显示)")
    header = f"  {'降赔＼支持↓':<12s}"
    for sl in sd_labels:
        header += f"  {sl:^{col_w}s}"
    header += f"  {'行合计':^{col_w}s}"
    print(header)
    print(f"  {'─' * (14 + (col_w + 2) * (len(sd_labels) + 1))}")

    for od_label, _, _ in ODDS_DROP_BINS:
        row_str = f"  {od_label:<12s}"
        row_total = row_win = row_draw = row_lose = 0
        for sl in sd_labels:
            cell = matrix[od_label][sl]
            n = cell['total']
            row_total += n
            row_win += cell['win']
            row_draw += cell['draw']
            row_lose += cell['lose']
            if n >= args.min_sample:
                pct = cell['win'] / n * 100
                row_str += f"  {pct:5.1f}%({n:3d}场)"
            elif n > 0:
                row_str += f"  {'---':>5s}({n:3d}场)"
            else:
                row_str += f"  {'':^{col_w}s}"
        # 行合计
        if row_total >= args.min_sample:
            rpct = row_win / row_total * 100
            row_str += f"  {rpct:5.1f}%({row_total:3d}场)"
        elif row_total > 0:
            row_str += f"  {'---':>5s}({row_total:3d}场)"
        print(row_str)

    # 列合计
    footer = f"  {'列合计':<12s}"
    for sl in sd_labels:
        col_t = sum(matrix[od][sl]['total'] for od, _, _ in ODDS_DROP_BINS)
        col_w_v = sum(matrix[od][sl]['win'] for od, _, _ in ODDS_DROP_BINS)
        if col_t >= args.min_sample:
            cpct = col_w_v / col_t * 100
            footer += f"  {cpct:5.1f}%({col_t:3d}场)"
        elif col_t > 0:
            footer += f"  {'---':>5s}({col_t:3d}场)"
        else:
            footer += f"  {'':^{col_w}s}"
    fw = sum(r['fav_won'] for r in records)
    footer += f"  {fw/total*100:5.1f}%({total:3d}场)"
    print(f"  {'─' * (14 + (col_w + 2) * (len(sd_labels) + 1))}")
    print(footer)

    # 打印矩阵 - 让方不败率
    print(f"\n  ◆ 让方不败率矩阵 (样本数 >= {args.min_sample} 才显示)")
    header = f"  {'降赔＼支持↓':<12s}"
    for sl in sd_labels:
        header += f"  {sl:^{col_w}s}"
    header += f"  {'行合计':^{col_w}s}"
    print(header)
    print(f"  {'─' * (14 + (col_w + 2) * (len(sd_labels) + 1))}")

    for od_label, _, _ in ODDS_DROP_BINS:
        row_str = f"  {od_label:<12s}"
        row_total = row_nb = 0
        for sl in sd_labels:
            cell = matrix[od_label][sl]
            n = cell['total']
            nb = cell['win'] + cell['draw']
            row_total += n
            row_nb += nb
            if n >= args.min_sample:
                pct = nb / n * 100
                marker = ' ★' if pct >= 80 else ''
                row_str += f"  {pct:5.1f}%({n:3d}场){marker}"
            elif n > 0:
                row_str += f"  {'---':>5s}({n:3d}场)  "
            else:
                row_str += f"  {'':^{col_w + 2}s}"
        if row_total >= args.min_sample:
            rpct = row_nb / row_total * 100
            marker = ' ★' if rpct >= 80 else ''
            row_str += f"  {rpct:5.1f}%({row_total:3d}场){marker}"
        elif row_total > 0:
            row_str += f"  {'---':>5s}({row_total:3d}场)"
        print(row_str)

    footer = f"  {'列合计':<12s}"
    for sl in sd_labels:
        col_t = sum(matrix[od][sl]['total'] for od, _, _ in ODDS_DROP_BINS)
        col_nb = sum(matrix[od][sl]['win'] + matrix[od][sl]['draw'] for od, _, _ in ODDS_DROP_BINS)
        if col_t >= args.min_sample:
            cpct = col_nb / col_t * 100
            marker = ' ★' if cpct >= 80 else ''
            footer += f"  {cpct:5.1f}%({col_t:3d}场){marker}"
        elif col_t > 0:
            footer += f"  {'---':>5s}({col_t:3d}场)  "
        else:
            footer += f"  {'':^{col_w + 2}s}"
    fnb = sum(r['fav_not_lose'] for r in records)
    footer += f"  {fnb/total*100:5.1f}%({total:3d}场)"
    print(f"  {'─' * (14 + (col_w + 2) * (len(sd_labels) + 1))}")
    print(footer)

    # ========== 找出★亮点区间 ==========
    print(f"\n  ◆ 高胜率亮点区间 (不败率 >= 80% 且样本 >= {args.min_sample})")
    print(f"  {'─' * 80}")
    highlights = []
    for od_label, _, _ in ODDS_DROP_BINS:
        for sl in sd_labels:
            cell = matrix[od_label][sl]
            n = cell['total']
            if n >= args.min_sample:
                nb = cell['win'] + cell['draw']
                nb_pct = nb / n * 100
                win_pct = cell['win'] / n * 100
                if nb_pct >= 80:
                    highlights.append((od_label, sl, n, cell['win'], cell['draw'], cell['lose'], win_pct, nb_pct))

    if highlights:
        print(f"  {'降赔区间':<12s} {'支持↓区间':<10s} {'场次':>4s}  {'胜':>3s}  {'平':>3s}  {'负':>3s}  {'胜率':>6s}  {'不败率':>6s}")
        print(f"  {'─' * 70}")
        for h in sorted(highlights, key=lambda x: -x[7]):
            print(f"  {h[0]:<12s} {h[1]:<10s} {h[2]:>4d}  {h[3]:>3d}  {h[4]:>3d}  {h[5]:>3d}  {h[6]:>5.1f}%  {h[7]:>5.1f}% ★")
    else:
        print(f"  没有找到不败率>=80%且样本>={args.min_sample}的区间组合")

    # ========== 低胜率区间 ==========
    print(f"\n  ◆ 低胜率区间 (让方胜率 < 50% 且样本 >= {args.min_sample})")
    print(f"  {'─' * 80}")
    lowlights = []
    for od_label, _, _ in ODDS_DROP_BINS:
        for sl in sd_labels:
            cell = matrix[od_label][sl]
            n = cell['total']
            if n >= args.min_sample:
                win_pct = cell['win'] / n * 100
                nb_pct = (cell['win'] + cell['draw']) / n * 100
                if win_pct < 50:
                    lowlights.append((od_label, sl, n, cell['win'], cell['draw'], cell['lose'], win_pct, nb_pct))

    if lowlights:
        print(f"  {'降赔区间':<12s} {'支持↓区间':<10s} {'场次':>4s}  {'胜':>3s}  {'平':>3s}  {'负':>3s}  {'胜率':>6s}  {'不败率':>6s}")
        print(f"  {'─' * 70}")
        for h in sorted(lowlights, key=lambda x: x[6]):
            print(f"  {h[0]:<12s} {h[1]:<10s} {h[2]:>4d}  {h[3]:>3d}  {h[4]:>3d}  {h[5]:>3d}  {h[6]:>5.1f}%  {h[7]:>5.1f}%")
    else:
        print(f"  所有区间胜率均>=50%")

    # ========== 单维度汇总 ==========
    print(f"\n  ◆ 单维度汇总：按降赔幅度")
    print(f"  {'区间':<12s} {'场次':>4s}  {'让方胜':>6s}  {'平局':>6s}  {'让方负':>6s}  {'胜率':>6s}  {'不败率':>6s}")
    print(f"  {'─' * 60}")
    for od_label, lo, hi in ODDS_DROP_BINS:
        subset = [r for r in records if lo <= r['odds_drop'] < hi or (hi >= 999 and r['odds_drop'] >= lo)]
        if subset:
            n = len(subset)
            w = sum(1 for r in subset if r['fav_won'])
            d = sum(1 for r in subset if r['is_draw'])
            l = n - w - d
            print(f"  {od_label:<12s} {n:>4d}  {w:>6d}  {d:>6d}  {l:>6d}  {w/n*100:>5.1f}%  {(w+d)/n*100:>5.1f}%")

    print(f"\n  ◆ 单维度汇总：按支持数下降幅度")
    print(f"  {'区间':<12s} {'场次':>4s}  {'让方胜':>6s}  {'平局':>6s}  {'让方负':>6s}  {'胜率':>6s}  {'不败率':>6s}")
    print(f"  {'─' * 60}")
    for sd_label, lo, hi in SUPPORT_DROP_BINS:
        subset = [r for r in records if lo <= r['support_drop'] < hi or (hi >= 9999 and r['support_drop'] >= lo)]
        if subset:
            n = len(subset)
            w = sum(1 for r in subset if r['fav_won'])
            d = sum(1 for r in subset if r['is_draw'])
            l = n - w - d
            print(f"  {sd_label:<12s} {n:>4d}  {w:>6d}  {d:>6d}  {l:>6d}  {w/n*100:>5.1f}%  {(w+d)/n*100:>5.1f}%")

    print(f"\n{'=' * 100}")

    # 详细列表（可选）
    if args.verbose:
        print(f"\n  【完整比赛列表】")
        print(f"  {'时间':<17s} {'联赛':<10s} {'主队':>8s}  比分  {'客队':<8s}  "
              f"让方  降赔     支持↓   结果")
        print(f"  {'─' * 95}")
        for r in records:
            mt = r['match_time'].strftime('%m-%d %H:%M') if hasattr(r['match_time'], 'strftime') else str(r['match_time'])[:16]
            tag = '✓胜' if r['fav_won'] else ('=平' if r['is_draw'] else '✗负')
            print(f"  {mt:<17s} {(r['league'] or '?'):<10s} "
                  f"{r['home_team'][:8]:>8s}  {r['score']:^5s}  {r['away_team'][:8]:<8s}  "
                  f"{r['fav_side']}  "
                  f"↓{r['odds_drop']:.3f}  "
                  f"{r['init_sup']:>3d}→{r['curr_sup']:>3d}(↓{r['support_drop']})  "
                  f"{tag}")

    print(f"\n{'=' * 100}\n")


if __name__ == '__main__':
    main()
