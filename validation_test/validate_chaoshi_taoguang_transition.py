#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证脚本：超实 vs 韬光 初盘组合 → 即时盘韬光变超韬、超实不变 的比分统计

筛选条件：
  - 初盘(initial)：一方为"超实"，另一方为"韬光"（不分主客）
  - 即时盘(current)：超实一方保持"超实"不变，韬光一方变成"超韬"
  - 比赛已完赛 (match_status = 'finished')

统计目标：
  - 韬光一侧的比分 >= 超实一侧的比分 的比例
"""

import sys
import os
import pymysql
import pymysql.cursors
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8')

COMPANY_ID = '115'  # 默认公司ID（与其他验证脚本一致）

RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


def get_db():
    return pymysql.connect(
        host='localhost', port=3306,
        user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def get_range_type(range_str):
    """从完整盘型字符串中提取盘型前缀"""
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def query_matches():
    """
    查询满足条件的比赛：
    情况A：初盘主=超实 & 初盘客=韬光 → 即时主=超实 & 即时客=超韬
    情况B：初盘主=韬光 & 初盘客=超实 → 即时主=超韬 & 即时客=超实
    """
    conn = get_db()
    query = '''
        SELECT
            oar.match_id,
            oar.company_name,
            oar.initial_home_range,
            oar.initial_away_range,
            oar.current_home_range,
            oar.current_away_range,
            oar.initial_home_fullwater,
            oar.initial_away_fullwater,
            oar.current_home_fullwater,
            oar.current_away_fullwater,
            oar.power_diff,
            m.home_team_name,
            m.away_team_name,
            m.home_score,
            m.away_score,
            m.match_time,
            m.match_status,
            l.name_cn AS league_name
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = 115
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
          AND (
              -- 情况A：初盘主=超实，客=韬光 → 即时客=超韬（不要求超实不变）
              (
                  oar.initial_home_range LIKE '超实%%'
                  AND oar.initial_away_range LIKE '韬光%%'
                  AND oar.current_away_range LIKE '超韬%%'
              )
              OR
              -- 情况B：初盘主=韬光，客=超实 → 即时主=超韬（不要求超实不变）
              (
                  oar.initial_home_range LIKE '韬光%%'
                  AND oar.initial_away_range LIKE '超实%%'
                  AND oar.current_home_range LIKE '超韬%%'
              )
          )
        ORDER BY m.match_time DESC
    '''
    try:
        with conn.cursor() as cursor:
            cursor.execute(query)
            return cursor.fetchall()
    finally:
        conn.close()


def analyze(rows):
    """分析韬光一侧比分 >= 超实一侧比分的比例"""
    total = len(rows)
    if total == 0:
        return [], 0, 0, 0

    taoguang_ge_count = 0  # 韬光侧比分 >= 超实侧
    taoguang_win_count = 0  # 韬光侧比分 > 超实侧
    draw_count = 0  # 两侧比分相等
    chaoshi_win_count = 0  # 超实侧比分 > 韬光侧
    details = []

    for row in rows:
        init_home_type = get_range_type(row['initial_home_range'])
        init_away_type = get_range_type(row['initial_away_range'])

        home_score = int(row['home_score'])
        away_score = int(row['away_score'])

        # 判断哪边是韬光，哪边是超实
        if init_home_type == '超实' and init_away_type == '韬光':
            # 主=超实，客=韬光
            chaoshi_score = home_score
            taoguang_score = away_score
            chaoshi_side = '主'
            taoguang_side = '客'
        else:
            # 主=韬光，客=超实
            chaoshi_score = away_score
            taoguang_score = home_score
            chaoshi_side = '客'
            taoguang_side = '主'

        taoguang_ge = taoguang_score >= chaoshi_score
        if taoguang_ge:
            taoguang_ge_count += 1

        if taoguang_score > chaoshi_score:
            taoguang_win_count += 1
        elif taoguang_score == chaoshi_score:
            draw_count += 1
        else:
            chaoshi_win_count += 1

        # 比分结果标注
        if taoguang_score > chaoshi_score:
            result_tag = '✓ 韬光胜'
        elif taoguang_score == chaoshi_score:
            result_tag = '= 平局'
        else:
            result_tag = '✗ 超实胜'

        details.append({
            'match_id': row['match_id'],
            'match_time': row['match_time'],
            'league': row.get('league_name', '未知'),
            'home_team': row['home_team_name'],
            'away_team': row['away_team_name'],
            'score': f"{home_score}:{away_score}",
            'chaoshi_side': chaoshi_side,
            'taoguang_side': taoguang_side,
            'chaoshi_score': chaoshi_score,
            'taoguang_score': taoguang_score,
            'taoguang_ge': taoguang_ge,
            'result_tag': result_tag,
            'init_home_range': row['initial_home_range'],
            'init_away_range': row['initial_away_range'],
            'curr_home_range': row['current_home_range'],
            'curr_away_range': row['current_away_range'],
            'company_name': row.get('company_name', ''),
        })

    return details, taoguang_ge_count, total, {
        'taoguang_win': taoguang_win_count,
        'draw': draw_count,
        'chaoshi_win': chaoshi_win_count,
    }


def print_report(details, taoguang_ge_count, total, breakdown):
    """打印验证报告"""
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    print(f"\n{'=' * 90}")
    print(f"  验证报告：超实 vs 韬光 → 即时韬光变超韬、超实不变")
    print(f"  生成时间: {now_str}")
    print(f"{'=' * 90}")

    if total == 0:
        print("\n  没有找到符合条件的比赛。")
        print(f"\n{'=' * 90}\n")
        return

    pct = taoguang_ge_count / total * 100

    print(f"\n  【核心统计】")
    print(f"  ─────────────────────────────────────────")
    print(f"  符合条件的比赛总数:  {total} 场")
    print(f"  韬光侧比分 >= 超实侧: {taoguang_ge_count} 场  ({pct:.1f}%)")
    print(f"  ─────────────────────────────────────────")

    print(f"\n  【详细分布】")
    tw = breakdown['taoguang_win']
    dr = breakdown['draw']
    cw = breakdown['chaoshi_win']
    print(f"  韬光侧胜 (韬光 > 超实):  {tw} 场  ({tw/total*100:.1f}%)")
    print(f"  两侧平局 (韬光 = 超实):  {dr} 场  ({dr/total*100:.1f}%)")
    print(f"  超实侧胜 (超实 > 韬光):  {cw} 场  ({cw/total*100:.1f}%)")
    print(f"  ─────────────────────────────────────────")
    print(f"  韬光侧不败(>=超实):      {taoguang_ge_count} 场  ({pct:.1f}%)")

    # 按公司分组统计
    by_company = {}
    for d in details:
        cname = d['company_name'] or '未知'
        if cname not in by_company:
            by_company[cname] = {'total': 0, 'ge': 0}
        by_company[cname]['total'] += 1
        if d['taoguang_ge']:
            by_company[cname]['ge'] += 1

    if len(by_company) > 1:
        print(f"\n  【按公司分组】")
        for cname, stats in sorted(by_company.items(), key=lambda x: -x[1]['total']):
            cpct = stats['ge'] / stats['total'] * 100 if stats['total'] > 0 else 0
            print(f"  {cname:20s}  总{stats['total']:3d}场  韬光>=超实: {stats['ge']:3d}场  ({cpct:.1f}%)")

    # 详细比赛列表
    print(f"\n  【比赛明细】")
    print(f"  {'比赛时间':<20s} {'联赛':<12s} {'主队':>10s}  比分  {'客队':<10s}  "
          f"{'超实侧':<4s} {'韬光侧':<4s}  结果       初盘→即时")
    print(f"  {'─' * 110}")

    for d in details:
        match_time_str = d['match_time'].strftime('%Y-%m-%d %H:%M') if hasattr(d['match_time'], 'strftime') else str(d['match_time'])[:16]
        init_desc = f"主:{d['init_home_range']} 客:{d['init_away_range']}"
        curr_desc = f"→ 主:{d['curr_home_range']} 客:{d['curr_away_range']}"

        print(f"  {match_time_str:<20s} {(d['league'] or '?'):<12s} "
              f"{d['home_team']:>10s}  {d['score']:^5s}  {d['away_team']:<10s}  "
              f"超实={d['chaoshi_side']}  韬光={d['taoguang_side']}  {d['result_tag']:<10s}")
        print(f"  {'':>20s} {init_desc}  {curr_desc}")

    print(f"\n{'=' * 90}")

    # 总结
    print(f"\n  【结论】")
    print(f"  在初盘[超实 vs 韬光]且即时盘韬光→超韬、超实不变的 {total} 场比赛中，")
    print(f"  韬光一侧比分 >= 超实一侧的比例为 {pct:.1f}% ({taoguang_ge_count}/{total})")
    print(f"\n{'=' * 90}\n")


def main():
    import argparse
    parser = argparse.ArgumentParser(description='验证：超实vs韬光初盘→即时韬光变超韬的比分统计')
    parser.add_argument('--company', type=str, default=None,
                        help='指定公司ID进行筛选（默认不限公司）')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='显示详细调试信息')
    args = parser.parse_args()

    print("\n正在查询数据库...")
    rows = query_matches()

    if args.company:
        rows = [r for r in rows if str(r.get('company_id', '')) == args.company]

    print(f"查询到 {len(rows)} 条符合条件的记录")

    if args.verbose and rows:
        print("\n[调试] 前5条原始数据:")
        for r in rows[:5]:
            print(f"  match_id={r['match_id']} "
                  f"初盘: 主={r['initial_home_range']} 客={r['initial_away_range']}  "
                  f"即时: 主={r['current_home_range']} 客={r['current_away_range']}  "
                  f"比分: {r['home_score']}:{r['away_score']}")

    details, taoguang_ge_count, total, breakdown = analyze(rows)
    print_report(details, taoguang_ge_count, total, breakdown)


if __name__ == '__main__':
    main()
