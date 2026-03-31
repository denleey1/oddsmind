#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证脚本：让方降赔 + 公司支持数减少 → 让方胜率

条件：
  1. 以威廉(company_id=115)初盘赔率确定让方（赔率低的一方）
  2. 威廉让方赔率从初盘到即时盘下降（降赔）
  3. 所有公司的推荐映射成胜平负后，支持让方胜的公司数从初盘到即时减少

统计：满足以上条件时，让方实际获胜的比例
"""

import sys
import os
import json
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
    '双平偏让平': ['draw'],  # 简化处理，特殊逻辑见下方
}


def get_db():
    return pymysql.connect(
        host='localhost', port=3306,
        user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def map_recommendation(rec, home_rule_value=None, away_rule_value=None):
    """将推荐结果映射为 home_win / draw / away_win 列表"""
    if not rec:
        return []

    # 双平偏让平 特殊处理
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

    # fallback
    if '主胜' in rec:
        return ['home_win']
    elif '客胜' in rec:
        return ['away_win']
    elif '平' in rec:
        return ['draw']
    return []


def calc_support_count(companies, target_outcome):
    """
    计算支持某个结果(home_win/away_win)的公司加权数
    返回 (initial_count, current_count)
    """
    init_count = 0.0
    curr_count = 0.0

    for c in companies:
        # 初盘
        init_mapped = map_recommendation(
            c['initial_recommended_outcome'],
            c.get('initial_home_rule_value'),
            c.get('initial_away_rule_value')
        )
        if init_mapped and target_outcome in init_mapped:
            weight = 1.0 / len(init_mapped)
            init_count += weight

        # 即时盘
        curr_mapped = map_recommendation(
            c['current_recommended_outcome'],
            c.get('current_home_rule_value'),
            c.get('current_away_rule_value')
        )
        if curr_mapped and target_outcome in curr_mapped:
            weight = 1.0 / len(curr_mapped)
            curr_count += weight

    return round(init_count), round(curr_count)


def main():
    import argparse
    parser = argparse.ArgumentParser(description='验证：让方降赔+公司支持数减少→让方胜率')
    parser.add_argument('--verbose', '-v', action='store_true', help='显示详细比赛列表')
    args = parser.parse_args()

    conn = get_db()
    cursor = conn.cursor()

    print("\n正在查询威廉数据...")

    # 第1步：获取威廉的所有已完赛比赛
    cursor.execute('''
        SELECT
            oar.match_id,
            oar.initial_home_fullwater,
            oar.initial_away_fullwater,
            oar.current_home_fullwater,
            oar.current_away_fullwater,
            m.home_team_name,
            m.away_team_name,
            m.home_score,
            m.away_score,
            m.match_time,
            l.name_cn AS league_name
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = %s
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
          AND oar.initial_home_fullwater IS NOT NULL
          AND oar.initial_away_fullwater IS NOT NULL
          AND oar.current_home_fullwater IS NOT NULL
          AND oar.current_away_fullwater IS NOT NULL
        ORDER BY m.match_time DESC
    ''', (WILLIAM_COMPANY_ID,))
    william_matches = cursor.fetchall()
    print(f"威廉已完赛比赛: {len(william_matches)} 场")

    # 第2步：获取所有这些比赛的全部公司推荐数据
    match_ids = [r['match_id'] for r in william_matches]
    if not match_ids:
        print("没有数据")
        conn.close()
        return

    # 分批查询，避免 SQL IN 太长
    all_company_data = {}
    batch_size = 500
    for i in range(0, len(match_ids), batch_size):
        batch = match_ids[i:i + batch_size]
        placeholders = ','.join(['%s'] * len(batch))
        cursor.execute(f'''
            SELECT
                match_id, company_id,
                initial_recommended_outcome,
                current_recommended_outcome,
                initial_home_rule_value,
                initial_away_rule_value,
                current_home_rule_value,
                current_away_rule_value
            FROM odds_analysis_results
            WHERE match_id IN ({placeholders})
        ''', batch)
        for row in cursor.fetchall():
            mid = row['match_id']
            if mid not in all_company_data:
                all_company_data[mid] = []
            all_company_data[mid].append(row)

    conn.close()
    print(f"获取到 {len(all_company_data)} 场比赛的公司数据")

    # 第3步：逐场分析
    results = []
    total_finished = 0
    fav_odds_drop = 0
    fav_support_drop = 0
    both_conditions = 0

    for wm in william_matches:
        mid = wm['match_id']
        ih = float(wm['initial_home_fullwater'])
        ia = float(wm['initial_away_fullwater'])
        ch = float(wm['current_home_fullwater'])
        ca = float(wm['current_away_fullwater'])
        home_score = int(wm['home_score'])
        away_score = int(wm['away_score'])

        total_finished += 1

        # 确定让方: 赔率低的一方
        if ih < ia:
            fav_side = 'home'
            fav_init_odds = ih
            fav_curr_odds = ch
            fav_team = wm['home_team_name']
            dog_team = wm['away_team_name']
            fav_outcome = 'home_win'
        elif ia < ih:
            fav_side = 'away'
            fav_init_odds = ia
            fav_curr_odds = ca
            fav_team = wm['away_team_name']
            dog_team = wm['home_team_name']
            fav_outcome = 'away_win'
        else:
            continue  # 赔率相等，跳过

        # 条件1：让方降赔
        odds_dropped = fav_curr_odds < fav_init_odds
        if odds_dropped:
            fav_odds_drop += 1

        # 条件2：支持让方胜的公司数减少
        companies = all_company_data.get(mid, [])
        init_support, curr_support = calc_support_count(companies, fav_outcome)
        support_dropped = curr_support < init_support

        if support_dropped:
            fav_support_drop += 1

        # 同时满足两个条件
        if odds_dropped and support_dropped:
            both_conditions += 1

            # 让方实际是否获胜
            if fav_side == 'home':
                fav_won = home_score > away_score
                fav_not_lose = home_score >= away_score
            else:
                fav_won = away_score > home_score
                fav_not_lose = away_score >= home_score

            results.append({
                'match_id': mid,
                'match_time': wm['match_time'],
                'league': wm.get('league_name', '?'),
                'home_team': wm['home_team_name'],
                'away_team': wm['away_team_name'],
                'score': f"{home_score}:{away_score}",
                'fav_side': '主' if fav_side == 'home' else '客',
                'fav_team': fav_team,
                'fav_init_odds': fav_init_odds,
                'fav_curr_odds': fav_curr_odds,
                'init_support': init_support,
                'curr_support': curr_support,
                'fav_won': fav_won,
                'fav_not_lose': fav_not_lose,
                'total_companies': len(companies),
            })

    # ========== 输出报告 ==========
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'=' * 90}")
    print(f"  验证报告：让方降赔 + 公司支持数减少 → 让方胜率")
    print(f"  基准公司: 威廉 (company_id={WILLIAM_COMPANY_ID})")
    print(f"  生成时间: {now_str}")
    print(f"{'=' * 90}")

    print(f"\n  【数据漏斗】")
    print(f"  ─────────────────────────────────────────")
    print(f"  威廉已完赛比赛:              {total_finished} 场")
    print(f"  让方降赔:                    {fav_odds_drop} 场")
    print(f"  公司支持让方数减少:           {fav_support_drop} 场")
    print(f"  同时满足(降赔+支持数减少):    {both_conditions} 场")
    print(f"  ─────────────────────────────────────────")

    if not results:
        print("\n  没有找到同时满足条件的比赛。")
        print(f"\n{'=' * 90}\n")
        return

    total = len(results)
    fav_win_count = sum(1 for r in results if r['fav_won'])
    fav_not_lose_count = sum(1 for r in results if r['fav_not_lose'])
    draw_count = sum(1 for r in results if not r['fav_won'] and r['fav_not_lose'])
    fav_lose_count = total - fav_not_lose_count

    print(f"\n  【核心统计】")
    print(f"  ─────────────────────────────────────────")
    print(f"  符合条件的比赛:    {total} 场")
    print(f"  让方胜:            {fav_win_count} 场  ({fav_win_count/total*100:.1f}%)")
    print(f"  平局:              {draw_count} 场  ({draw_count/total*100:.1f}%)")
    print(f"  让方负:            {fav_lose_count} 场  ({fav_lose_count/total*100:.1f}%)")
    print(f"  ─────────────────────────────────────────")
    print(f"  让方不败:          {fav_not_lose_count} 场  ({fav_not_lose_count/total*100:.1f}%)")

    # 按支持数下降幅度分组
    drop_ranges = [
        ('下降1-5家', lambda r: 1 <= r['init_support'] - r['curr_support'] <= 5),
        ('下降6-15家', lambda r: 6 <= r['init_support'] - r['curr_support'] <= 15),
        ('下降16-30家', lambda r: 16 <= r['init_support'] - r['curr_support'] <= 30),
        ('下降>30家', lambda r: r['init_support'] - r['curr_support'] > 30),
    ]
    print(f"\n  【按支持数下降幅度分组】")
    print(f"  {'下降幅度':<12s}  {'场次':>4s}  {'让方胜':>6s}  {'胜率':>6s}  {'不败率':>6s}")
    print(f"  {'─' * 50}")
    for label, cond_fn in drop_ranges:
        subset = [r for r in results if cond_fn(r)]
        if subset:
            wins = sum(1 for r in subset if r['fav_won'])
            not_lose = sum(1 for r in subset if r['fav_not_lose'])
            n = len(subset)
            print(f"  {label:<12s}  {n:>4d}  {wins:>6d}  {wins/n*100:>5.1f}%  {not_lose/n*100:>5.1f}%")

    # 比赛详细列表
    if args.verbose:
        print(f"\n  【比赛明细】")
        print(f"  {'时间':<18s} {'联赛':<12s} {'主队':>10s}  比分  {'客队':<10s}  "
              f"让方  {'初赔':>5s}→{'即赔':>5s}  支持:初→即  结果")
        print(f"  {'─' * 105}")

        for r in results:
            mt = r['match_time'].strftime('%Y-%m-%d %H:%M') if hasattr(r['match_time'], 'strftime') else str(r['match_time'])[:16]
            tag = '✓胜' if r['fav_won'] else ('=平' if r['fav_not_lose'] else '✗负')
            print(f"  {mt:<18s} {(r['league'] or '?'):<12s} "
                  f"{r['home_team']:>10s}  {r['score']:^5s}  {r['away_team']:<10s}  "
                  f"{r['fav_side']}({r['fav_team'][:6]})  "
                  f"{r['fav_init_odds']:>5.2f}→{r['fav_curr_odds']:>5.2f}  "
                  f"{r['init_support']:>3d}→{r['curr_support']:>3d}(↓{r['init_support']-r['curr_support']})  "
                  f"{tag}")
    else:
        print(f"\n  提示: 使用 -v 参数查看完整比赛明细")

    print(f"\n{'=' * 90}")

    # 结论
    print(f"\n  【结论】")
    print(f"  在威廉让方降赔、且支持让方胜的公司数减少的 {total} 场比赛中，")
    print(f"  让方胜率为 {fav_win_count/total*100:.1f}% ({fav_win_count}/{total})")
    print(f"  让方不败率为 {fav_not_lose_count/total*100:.1f}% ({fav_not_lose_count}/{total})")
    print(f"\n{'=' * 90}\n")


if __name__ == '__main__':
    main()
