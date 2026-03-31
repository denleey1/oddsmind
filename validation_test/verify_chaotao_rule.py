#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
验证规则：即时盘超韬利盘的一方，得分+1 >= 另一方得分
即：超韬一方最多只输1球
"""
import os
import sys
from typing import Dict, List, Optional
from collections import defaultdict
import pymysql
import pymysql.cursors

sys.stdout.reconfigure(encoding='utf-8')


def get_db():
    return pymysql.connect(
        host='localhost', port=3306,
        user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )

# 盘型前缀
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']
COMPANY_ID = '115'  # 威廉公司

# 五大联赛
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
BIG5_NAMES = {36: '英超', 31: '西甲', 34: '意甲', 8: '德甲', 11: '法甲'}


def get_range_type(range_str: str) -> Optional[str]:
    """提取盘面类型前缀"""
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def load_match_data() -> List[Dict]:
    """加载已完成比赛的详细数据"""
    conn = get_db()

    query = '''
        SELECT
            oar.match_id,
            oar.company_id,
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

    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (COMPANY_ID,))
            return cursor.fetchall()
    finally:
        conn.close()


def verify_rule():
    """
    验证规则：即时盘是超韬的一方，其得分+1 >= 另一方得分

    超韬 = 赔率远高于理论标准 = 利盘（对投注者有利）
    规则含义：超韬一方最多只输1球
    """
    print("=" * 80)
    print("规则验证：即时盘超韬利盘一方，得分+1 >= 另一方得分")
    print("=" * 80)

    print("\n正在加载数据...")
    rows = load_match_data()
    print(f"共加载 {len(rows)} 条比赛记录")

    # ====== 分析主队即时盘=超韬 ======
    home_chaotao = []  # 主队即时盘=超韬
    away_chaotao = []  # 客队即时盘=超韬

    # 按让球方/受让方分析
    handicap_chaotao = []   # 让球方即时盘=超韬
    receiver_chaotao = []   # 受让方即时盘=超韬

    for row in rows:
        curr_home_type = get_range_type(row['current_home_range'])
        curr_away_type = get_range_type(row['current_away_range'])

        init_home = float(row['initial_home'])
        init_away = float(row['initial_away'])

        # 判断让球方（初赔较小者为让球方）
        if init_home <= init_away:
            handicap_side = 'home'
        else:
            handicap_side = 'away'

        match_info = {
            'match_id': row['match_id'],
            'home_team': row['home_team_name'],
            'away_team': row['away_team_name'],
            'home_score': row['home_score'],
            'away_score': row['away_score'],
            'match_time': row['match_time'],
            'league': row['league_name'],
            'league_id': row['league_id'],
            'curr_home_range': row['current_home_range'],
            'curr_away_range': row['current_away_range'],
            'init_home_odds': init_home,
            'init_away_odds': init_away,
            'handicap_side': handicap_side,
        }

        # 主队即时盘=超韬
        if curr_home_type == '超韬':
            home_chaotao.append(match_info)
            if handicap_side == 'home':
                handicap_chaotao.append(match_info)
            else:
                receiver_chaotao.append(match_info)

        # 客队即时盘=超韬
        if curr_away_type == '超韬':
            away_chaotao.append(match_info)
            if handicap_side == 'away':
                handicap_chaotao.append(match_info)
            else:
                receiver_chaotao.append(match_info)

    # ==============================
    # 验证1：主队超韬 → 主队得分+1 >= 客队得分
    # ==============================
    print("\n" + "=" * 80)
    print("【验证1】主队即时盘=超韬 → 主队得分+1 >= 客队得分（主队最多输1球）")
    print("=" * 80)
    verify_group(home_chaotao, 'home')

    # ==============================
    # 验证2：客队超韬 → 客队得分+1 >= 主队得分
    # ==============================
    print("\n" + "=" * 80)
    print("【验证2】客队即时盘=超韬 → 客队得分+1 >= 主队得分（客队最多输1球）")
    print("=" * 80)
    verify_group(away_chaotao, 'away')

    # ==============================
    # 验证3：让球方超韬 → 让球方得分+1 >= 受让方得分
    # ==============================
    print("\n" + "=" * 80)
    print("【验证3】让球方即时盘=超韬 → 让球方得分+1 >= 受让方得分")
    print("=" * 80)
    verify_group_by_handicap(handicap_chaotao, 'handicap')

    # ==============================
    # 验证4：受让方超韬 → 受让方得分+1 >= 让球方得分
    # ==============================
    print("\n" + "=" * 80)
    print("【验证4】受让方即时盘=超韬 → 受让方得分+1 >= 让球方得分")
    print("=" * 80)
    verify_group_by_handicap(receiver_chaotao, 'receiver')

    # ==============================
    # 汇总
    # ==============================
    print("\n" + "=" * 80)
    print("汇总统计")
    print("=" * 80)
    print(f"主队即时超韬: {len(home_chaotao)} 场")
    print(f"客队即时超韬: {len(away_chaotao)} 场")
    print(f"让球方即时超韬: {len(handicap_chaotao)} 场")
    print(f"受让方即时超韬: {len(receiver_chaotao)} 场")


def verify_group(matches: List[Dict], chaotao_side: str):
    """验证超韬一方得分+1 >= 另一方得分"""
    if not matches:
        print("  无符合条件的比赛")
        return

    total = len(matches)
    passed = 0
    failed = 0
    failed_matches = []

    # 按联赛统计
    league_stats = defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0})
    # 按赛果统计
    result_counts = defaultdict(int)

    for m in matches:
        hs = m['home_score']
        aws = m['away_score']

        if chaotao_side == 'home':
            chaotao_score = hs
            other_score = aws
        else:
            chaotao_score = aws
            other_score = hs

        # 规则：超韬一方得分+1 >= 另一方得分
        rule_ok = (chaotao_score + 1) >= other_score

        # 赛果
        if chaotao_score > other_score:
            result = '超韬方赢'
        elif chaotao_score == other_score:
            result = '平局'
        else:
            diff = other_score - chaotao_score
            result = f'超韬方输{diff}球'

        result_counts[result] += 1
        lid = m['league']
        league_stats[lid]['total'] += 1

        if rule_ok:
            passed += 1
            league_stats[lid]['passed'] += 1
        else:
            failed += 1
            league_stats[lid]['failed'] += 1
            failed_matches.append({
                **m,
                'chaotao_score': chaotao_score,
                'other_score': other_score,
                'goal_diff': other_score - chaotao_score,
            })

    pct = passed / total * 100 if total > 0 else 0
    print(f"\n  总计: {total} 场")
    print(f"  符合规则: {passed} 场 ({pct:.1f}%)")
    print(f"  违反规则: {failed} 场 ({100 - pct:.1f}%)")

    print(f"\n  赛果分布:")
    for result, cnt in sorted(result_counts.items(), key=lambda x: -x[1]):
        print(f"    {result}: {cnt} 场 ({cnt/total*100:.1f}%)")

    print(f"\n  按联赛分布:")
    for league, stats in sorted(league_stats.items(), key=lambda x: -x[1]['total']):
        lpct = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"    {league}: {stats['total']}场, 符合{stats['passed']}场({lpct:.1f}%), 违反{stats['failed']}场")

    if failed_matches:
        print(f"\n  *** 违反规则的比赛（超韬方输2球及以上）***")
        for fm in sorted(failed_matches, key=lambda x: -x['goal_diff']):
            print(f"    [{fm['league']}] {fm['match_time']} "
                  f"{fm['home_team']} {fm['home_score']}:{fm['away_score']} {fm['away_team']} "
                  f"| 超韬方输{fm['goal_diff']}球 "
                  f"| 主区间={fm['curr_home_range']} 客区间={fm['curr_away_range']}")


def verify_group_by_handicap(matches: List[Dict], role: str):
    """验证让球方/受让方为超韬时的规则"""
    if not matches:
        print("  无符合条件的比赛")
        return

    total = len(matches)
    passed = 0
    failed = 0
    failed_matches = []

    league_stats = defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0})
    result_counts = defaultdict(int)

    for m in matches:
        hs = m['home_score']
        aws = m['away_score']

        if role == 'handicap':
            # 让球方是超韬方
            if m['handicap_side'] == 'home':
                chaotao_score = hs
                other_score = aws
            else:
                chaotao_score = aws
                other_score = hs
        else:
            # 受让方是超韬方
            if m['handicap_side'] == 'home':
                chaotao_score = aws  # 受让方=客队
                other_score = hs
            else:
                chaotao_score = hs  # 受让方=主队
                other_score = aws

        rule_ok = (chaotao_score + 1) >= other_score

        if chaotao_score > other_score:
            result = '超韬方赢'
        elif chaotao_score == other_score:
            result = '平局'
        else:
            diff = other_score - chaotao_score
            result = f'超韬方输{diff}球'

        result_counts[result] += 1
        lid = m['league']
        league_stats[lid]['total'] += 1

        if rule_ok:
            passed += 1
            league_stats[lid]['passed'] += 1
        else:
            failed += 1
            league_stats[lid]['failed'] += 1
            failed_matches.append({
                **m,
                'chaotao_score': chaotao_score,
                'other_score': other_score,
                'goal_diff': other_score - chaotao_score,
                'role': role,
            })

    pct = passed / total * 100 if total > 0 else 0
    print(f"\n  总计: {total} 场")
    print(f"  符合规则: {passed} 场 ({pct:.1f}%)")
    print(f"  违反规则: {failed} 场 ({100 - pct:.1f}%)")

    print(f"\n  赛果分布:")
    for result, cnt in sorted(result_counts.items(), key=lambda x: -x[1]):
        print(f"    {result}: {cnt} 场 ({cnt/total*100:.1f}%)")

    print(f"\n  按联赛分布:")
    for league, stats in sorted(league_stats.items(), key=lambda x: -x[1]['total']):
        lpct = stats['passed'] / stats['total'] * 100 if stats['total'] > 0 else 0
        print(f"    {league}: {stats['total']}场, 符合{stats['passed']}场({lpct:.1f}%), 违反{stats['failed']}场")

    if failed_matches:
        print(f"\n  *** 违反规则的比赛（超韬方输2球及以上）***")
        for fm in sorted(failed_matches, key=lambda x: -x['goal_diff']):
            role_str = "让球方" if fm['role'] == 'handicap' else "受让方"
            print(f"    [{fm['league']}] {fm['match_time']} "
                  f"{fm['home_team']} {fm['home_score']}:{fm['away_score']} {fm['away_team']} "
                  f"| {role_str}超韬,输{fm['goal_diff']}球 "
                  f"| 主区间={fm['curr_home_range']} 客区间={fm['curr_away_range']}")


if __name__ == '__main__':
    verify_rule()
