#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
非重叠规则挖掘：降赔幅度 × 支持数降幅

目标：找出互不重叠的区间组合，分为两类：
  1. 让方必胜区间 —— 让方胜率最高
  2. 受让方不败区间 —— 受让方不败率(平+受让方胜)最高，即让方胜率最低
"""

import os
import sys
import pymysql
import pymysql.cursors
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

WILLIAM_COMPANY_ID = 115
MIN_SAMPLE = 8

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


def map_rec(rec, hrv=None, arv=None):
    if not rec: return []
    if rec == '双平偏让平':
        if hrv is not None and arv is not None:
            if hrv < arv: return ['home_win']
            elif arv < hrv: return ['away_win']
        return ['draw']
    return RECOMMENDATION_MAPPING.get(rec, [])


def calc_support(companies, target):
    ic = cc = 0.0
    for c in companies:
        im = map_rec(c['initial_recommended_outcome'],
                     c.get('initial_home_rule_value'), c.get('initial_away_rule_value'))
        if im and target in im: ic += 1.0 / len(im)
        cm = map_rec(c['current_recommended_outcome'],
                     c.get('current_home_rule_value'), c.get('current_away_rule_value'))
        if cm and target in cm: cc += 1.0 / len(cm)
    return round(ic), round(cc)


def ranges_overlap(r1, r2):
    """判断两个二维区间是否重叠。r = (od_lo, od_hi, sd_lo, sd_hi)"""
    od_overlap = r1[0] < r2[1] and r2[0] < r1[1]
    sd_overlap = r1[2] < r2[3] and r2[2] < r1[3]
    return od_overlap and sd_overlap


def greedy_select(candidates, max_rules=10):
    """贪心选择不重叠的规则，按主指标从高到低"""
    selected = []
    for cand in candidates:
        rect = (cand['od_lo'], cand['od_hi'], cand['sd_lo'], cand['sd_hi'])
        conflict = False
        for sel in selected:
            sel_rect = (sel['od_lo'], sel['od_hi'], sel['sd_lo'], sel['sd_hi'])
            if ranges_overlap(rect, sel_rect):
                conflict = True
                break
        if not conflict:
            selected.append(cand)
            if len(selected) >= max_rules:
                break
    return selected


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--min-sample', type=int, default=MIN_SAMPLE)
    parser.add_argument('--max-rules', type=int, default=8, help='每类最多选几条规则')
    parser.add_argument('--verbose', '-v', action='store_true')
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

    mids = [r['match_id'] for r in wm_list]
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

    # 构建数据点: (odds_drop, support_drop, fav_won, is_draw, fav_lost, match_info)
    data = []
    for wm in wm_list:
        mid = wm['match_id']
        ih, ia = float(wm['initial_home_fullwater']), float(wm['initial_away_fullwater'])
        ch, ca = float(wm['current_home_fullwater']), float(wm['current_away_fullwater'])
        hs, aws = int(wm['home_score']), int(wm['away_score'])
        if ih < ia:
            fi, fc, fo = ih, ch, 'home_win'
            fw, fl = hs > aws, hs < aws
        elif ia < ih:
            fi, fc, fo = ia, ca, 'away_win'
            fw, fl = aws > hs, aws < hs
        else:
            continue
        od = fi - fc
        if od <= 0: continue
        companies = all_cd.get(mid, [])
        isup, csup = calc_support(companies, fo)
        sd = isup - csup
        if sd <= 0: continue
        data.append({
            'od': od, 'sd': sd,
            'fav_won': fw, 'is_draw': hs == aws, 'fav_lost': fl,
            'info': wm,
        })

    print(f"威廉已完赛: {len(wm_list)} 场 → 满足条件: {len(data)} 场\n")

    # ========== 网格搜索 ==========
    od_cuts = [0.01, 0.03, 0.05, 0.08, 0.10, 0.13, 0.16, 0.20, 0.25, 0.30, 0.40, 0.50, 999]
    sd_cuts = [1, 3, 5, 8, 10, 15, 20, 25, 30, 40, 50, 9999]

    all_zones = []
    for i in range(len(od_cuts)):
        for j in range(i + 1, len(od_cuts)):
            for k in range(len(sd_cuts)):
                for l in range(k + 1, len(sd_cuts)):
                    od_lo, od_hi = od_cuts[i], od_cuts[j]
                    sd_lo, sd_hi = sd_cuts[k], sd_cuts[l]
                    sub = [d for d in data if od_lo <= d['od'] < od_hi and sd_lo <= d['sd'] < sd_hi]
                    n = len(sub)
                    if n < args.min_sample: continue
                    w = sum(1 for d in sub if d['fav_won'])
                    dr = sum(1 for d in sub if d['is_draw'])
                    lo = n - w - dr
                    all_zones.append({
                        'od_lo': od_lo, 'od_hi': od_hi,
                        'sd_lo': sd_lo, 'sd_hi': sd_hi,
                        'n': n, 'win': w, 'draw': dr, 'lose': lo,
                        'win_pct': w / n * 100,
                        'nb_pct': (w + dr) / n * 100,  # 让方不败
                        'dog_nb_pct': (dr + lo) / n * 100,  # 受让方不败 = 平+让方负
                    })

    print(f"搜索完成: {len(all_zones)} 个有效区间组合")

    # ========== 让方必胜规则 ==========
    fav_cands = sorted(all_zones, key=lambda z: (-z['win_pct'], -z['n']))
    fav_rules = greedy_select(fav_cands, max_rules=args.max_rules)

    # ========== 受让方不败规则 ==========
    # 受让方不败 = 平 + 让方负，即让方胜率越低越好
    dog_cands = sorted(all_zones, key=lambda z: (-z['dog_nb_pct'], -z['n']))
    # 排除与让方必胜规则重叠的
    dog_rules = []
    for cand in dog_cands:
        if len(dog_rules) >= args.max_rules: break
        rect = (cand['od_lo'], cand['od_hi'], cand['sd_lo'], cand['sd_hi'])
        conflict = False
        # 不与自己组内重叠
        for sel in dog_rules:
            if ranges_overlap(rect, (sel['od_lo'], sel['od_hi'], sel['sd_lo'], sel['sd_hi'])):
                conflict = True; break
        # 不与让方必胜组重叠
        if not conflict:
            for sel in fav_rules:
                if ranges_overlap(rect, (sel['od_lo'], sel['od_hi'], sel['sd_lo'], sel['sd_hi'])):
                    conflict = True; break
        if not conflict:
            dog_rules.append(cand)

    # ========== 输出 ==========
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'=' * 100}")
    print(f"  非重叠规则挖掘：让方降赔 + 公司支持数减少")
    print(f"  基准: 威廉 | 时间: {now_str} | 总样本: {len(data)} 场 | 最小样本: {args.min_sample}")
    print(f"{'=' * 100}")

    def print_rules(rules, title, main_metric, highlight_field):
        print(f"\n  ◆ {title}")
        print(f"  {'─' * 92}")
        print(f"  {'#':>3s}  {'降赔区间':<16s}  {'支持数降幅':<14s}  {'场次':>4s}  {'胜':>3s}  {'平':>3s}  {'负':>3s}  "
              f"{'让方胜率':>8s}  {'受让方不败率':>10s}")
        print(f"  {'─' * 92}")
        if not rules:
            print(f"  没有找到满足条件的规则")
            return
        total_n = total_w = total_d = total_l = 0
        for idx, r in enumerate(rules, 1):
            od_hi_s = f"{r['od_hi']:.2f}" if r['od_hi'] < 100 else "∞"
            sd_hi_s = f"{int(r['sd_hi'])}" if r['sd_hi'] < 9000 else "∞"
            mark = ' ★★' if r[highlight_field] >= 85 else (' ★' if r[highlight_field] >= 75 else '')
            print(f"  {idx:>3d}  [{r['od_lo']:.2f}, {od_hi_s}){'':<4s}  "
                  f"[{int(r['sd_lo'])}, {sd_hi_s}){'':<4s}  "
                  f"{r['n']:>4d}  {r['win']:>3d}  {r['draw']:>3d}  {r['lose']:>3d}  "
                  f"{r['win_pct']:>7.1f}%  {r['dog_nb_pct']:>9.1f}%{mark}")
            total_n += r['n']; total_w += r['win']; total_d += r['draw']; total_l += r['lose']
        print(f"  {'─' * 92}")
        if total_n > 0:
            print(f"  {'合计':>3s}  {'':16s}  {'':14s}  {total_n:>4d}  {total_w:>3d}  {total_d:>3d}  {total_l:>3d}  "
                  f"{total_w/total_n*100:>7.1f}%  {(total_d+total_l)/total_n*100:>9.1f}%")

    print_rules(fav_rules, "让方必胜规则（让方胜率最高，互不重叠）", 'win_pct', 'win_pct')
    print_rules(dog_rules, "受让方不败规则（受让方不败率最高，与上组也不重叠）", 'dog_nb_pct', 'dog_nb_pct')

    # ========== 覆盖统计 ==========
    fav_covered = set()
    dog_covered = set()
    uncovered = []

    for idx, d in enumerate(data):
        in_fav = False
        in_dog = False
        for r in fav_rules:
            if r['od_lo'] <= d['od'] < r['od_hi'] and r['sd_lo'] <= d['sd'] < r['sd_hi']:
                in_fav = True; break
        for r in dog_rules:
            if r['od_lo'] <= d['od'] < r['od_hi'] and r['sd_lo'] <= d['sd'] < r['sd_hi']:
                in_dog = True; break
        if in_fav:
            fav_covered.add(idx)
        elif in_dog:
            dog_covered.add(idx)
        else:
            uncovered.append(d)

    print(f"\n  ◆ 覆盖情况")
    print(f"  {'─' * 60}")
    print(f"  总样本:        {len(data)} 场")
    print(f"  让方必胜覆盖:  {len(fav_covered)} 场")
    print(f"  受让方不败覆盖: {len(dog_covered)} 场")
    print(f"  未覆盖:        {len(uncovered)} 场")
    if uncovered:
        uw = sum(1 for d in uncovered if d['fav_won'])
        ud = sum(1 for d in uncovered if d['is_draw'])
        ul = len(uncovered) - uw - ud
        print(f"  未覆盖区域:    胜{uw} 平{ud} 负{ul} → 让方胜率{uw/len(uncovered)*100:.1f}%")

    # ========== 验证：回测两组规则命中的比赛 ==========
    print(f"\n  ◆ 回测验证")
    print(f"  {'─' * 60}")
    fav_data = [data[i] for i in fav_covered]
    dog_data = [data[i] for i in dog_covered]
    if fav_data:
        fw = sum(1 for d in fav_data if d['fav_won'])
        fd = sum(1 for d in fav_data if d['is_draw'])
        fl = len(fav_data) - fw - fd
        print(f"  让方必胜命中:  {len(fav_data)}场 → 胜{fw} 平{fd} 负{fl} → 让方胜率 {fw/len(fav_data)*100:.1f}%")
    if dog_data:
        dw = sum(1 for d in dog_data if d['fav_won'])
        dd = sum(1 for d in dog_data if d['is_draw'])
        dl = len(dog_data) - dw - dd
        print(f"  受让方不败命中: {len(dog_data)}场 → 胜{dw} 平{dd} 负{dl} → 受让方不败率 {(dd+dl)/len(dog_data)*100:.1f}%")

    # ========== 详细比赛列表 ==========
    if args.verbose:
        for rule_set, rule_list, label in [
            (fav_covered, fav_rules, '让方必胜'),
            (dog_covered, dog_rules, '受让方不败')]:
            matched = [data[i] for i in rule_set]
            if not matched: continue
            matched.sort(key=lambda d: d['info']['match_time'], reverse=True)
            print(f"\n  【{label} 命中比赛】")
            print(f"  {'时间':<17s} {'联赛':<10s} {'主队':>8s}  比分  {'客队':<8s}  "
                  f"{'降赔':>6s}  {'支持↓':>5s}  结果  命中区间")
            print(f"  {'─' * 100}")
            for d in matched:
                wm = d['info']
                mt = wm['match_time'].strftime('%m-%d %H:%M') if hasattr(wm['match_time'], 'strftime') else str(wm['match_time'])[:11]
                tag = '✓胜' if d['fav_won'] else ('=平' if d['is_draw'] else '✗负')
                # 找命中的规则
                hit_rule = ''
                for r in rule_list:
                    if r['od_lo'] <= d['od'] < r['od_hi'] and r['sd_lo'] <= d['sd'] < r['sd_hi']:
                        od_hi_s = f"{r['od_hi']:.2f}" if r['od_hi'] < 100 else "∞"
                        sd_hi_s = f"{int(r['sd_hi'])}" if r['sd_hi'] < 9000 else "∞"
                        hit_rule = f"赔[{r['od_lo']:.2f},{od_hi_s})支持[{int(r['sd_lo'])},{sd_hi_s})"
                        break
                print(f"  {mt:<17s} {(wm.get('league_name') or '?'):<10s} "
                      f"{wm['home_team_name'][:8]:>8s}  {int(wm['home_score'])}:{int(wm['away_score'])}  "
                      f"{wm['away_team_name'][:8]:<8s}  "
                      f"↓{d['od']:.3f}  ↓{d['sd']:>3d}  {tag}  {hit_rule}")

    print(f"\n{'=' * 100}\n")


if __name__ == '__main__':
    main()
