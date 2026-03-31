#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
回测日志：读取监控日志中的预测记录，查询实际比分，统计命中率
用法:
    python3 backtest_log.py                  # 回测昨天的日志
    python3 backtest_log.py 2026-02-08       # 回测指定日期
    python3 backtest_log.py all              # 回测所有日志
"""
import sys
import os
import json
import glob
from collections import defaultdict
from datetime import datetime, timedelta
import pymysql
import pymysql.cursors

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, 'logs', 'monitor')


def get_db():
    return pymysql.connect(
        host='localhost', port=3306,
        user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def load_log(date_str):
    """加载指定日期的JSON日志"""
    log_file = os.path.join(LOG_DIR, f'{date_str}.json')
    if not os.path.exists(log_file):
        return []
    with open(log_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_all_logs():
    """加载所有日志"""
    records = []
    for f in sorted(glob.glob(os.path.join(LOG_DIR, '*.json'))):
        with open(f, 'r', encoding='utf-8') as fh:
            records.extend(json.load(fh))
    return records


def fetch_results(match_ids):
    """从数据库查询比赛结果"""
    if not match_ids:
        return {}
    conn = get_db()
    try:
        with conn.cursor() as cur:
            placeholders = ','.join(['%s'] * len(match_ids))
            cur.execute(f'''
                SELECT match_id, home_score, away_score, match_status,
                       home_team_name, away_team_name
                FROM matches
                WHERE match_id IN ({placeholders})
            ''', list(match_ids))
            return {r['match_id']: r for r in cur.fetchall()}
    finally:
        conn.close()


def determine_result(rec, match_info):
    """判断预测是否命中"""
    if match_info['match_status'] != 'finished':
        return None, None

    hs = match_info['home_score']
    as_ = match_info['away_score']
    if hs is None or as_ is None:
        return None, None

    score_str = f"{hs}-{as_}"

    # 判断让方是主队还是客队
    if rec['h_team'] == match_info['home_team_name']:
        h_score, r_score = hs, as_
    else:
        h_score, r_score = as_, hs

    target = rec['target']
    if target == '让方必赢':
        hit = h_score > r_score
    elif target == '让方不输':
        hit = h_score >= r_score
    elif target == '受让方不输':
        hit = r_score >= h_score
    else:
        hit = None

    return hit, score_str


def main():
    if len(sys.argv) > 1:
        arg = sys.argv[1]
    else:
        arg = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

    if arg == 'all':
        records = load_all_logs()
        title = "所有日志"
    else:
        records = load_log(arg)
        title = arg

    if not records:
        print(f"没有找到 {title} 的日志记录")
        print(f"日志目录: {LOG_DIR}")
        return

    # 去重（同一场比赛同一规则只算一次）
    seen = set()
    unique_records = []
    for rec in records:
        key = (rec['match_id'], rec['rule'])
        if key not in seen:
            seen.add(key)
            unique_records.append(rec)
    records = unique_records

    # 查询比赛结果
    match_ids = set(r['match_id'] for r in records)
    results = fetch_results(match_ids)

    # 统计
    print(f"\n{'=' * 90}")
    print(f"  回测报告: {title}")
    print(f"  预测记录: {len(records)} 条 | 涉及比赛: {len(match_ids)} 场")
    print(f"{'=' * 90}")

    # 按目标分组统计
    by_target = defaultdict(lambda: {'total': 0, 'hit': 0, 'miss': 0, 'pending': 0, 'details': []})

    for rec in records:
        mi = results.get(rec['match_id'])
        if not mi:
            hit, score = None, '未知'
        else:
            hit, score = determine_result(rec, mi)

        target = rec['target']
        stats = by_target[target]
        stats['total'] += 1

        detail = {
            'match_time': rec['match_time'],
            'league': rec.get('league', ''),
            'home': rec.get('home_team', ''),
            'away': rec.get('away_team', ''),
            'h_team': rec.get('h_team', ''),
            'h_odds': rec.get('curr_h_odds') or 0,
            'rule': rec.get('rule', ''),
            'accuracy': rec.get('accuracy') or 0,
            'score': score or '待赛',
            'hit': hit,
        }

        if hit is None:
            stats['pending'] += 1
            detail['mark'] = '?'
        elif hit:
            stats['hit'] += 1
            detail['mark'] = 'O'
        else:
            stats['miss'] += 1
            detail['mark'] = 'X'

        stats['details'].append(detail)

    for target in ['让方必赢', '让方不输', '受让方不输']:
        stats = by_target.get(target)
        if not stats:
            continue

        decided = stats['hit'] + stats['miss']
        acc = (stats['hit'] / decided * 100) if decided > 0 else 0

        print(f"\n  --- {target} ---")
        print(f"  命中: {stats['hit']}  未中: {stats['miss']}  待定: {stats['pending']}  "
              f"准确率: {acc:.1f}% ({stats['hit']}/{decided})")
        print()
        print(f"  {'结果':>4} | {'比分':>6} | {'赔率':>5} | {'规则准确率':>8} | {'联赛':<12} | 比赛 | 规则")
        print(f"  {'-' * 85}")

        for d in sorted(stats['details'], key=lambda x: x['match_time']):
            print(f"   {d['mark']:>3} | {d['score']:>6} | {d['h_odds']:>5.2f} | "
                  f"{d['accuracy']:>7.1f}% | {d['league']:<12} | "
                  f"{d['home']} vs {d['away']} | {d['rule']}")

    # 总汇
    total_hit = sum(s['hit'] for s in by_target.values())
    total_miss = sum(s['miss'] for s in by_target.values())
    total_pending = sum(s['pending'] for s in by_target.values())
    total_decided = total_hit + total_miss
    total_acc = (total_hit / total_decided * 100) if total_decided > 0 else 0

    print(f"\n{'=' * 90}")
    print(f"  总计: 命中 {total_hit} / 已决 {total_decided} = {total_acc:.1f}%  |  待定 {total_pending}")
    print(f"{'=' * 90}\n")


if __name__ == '__main__':
    main()
