#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自动监控：检查未来30分钟内开赛的比赛，匹配高准确率规则
支持 --log 模式，将命中记录追加到日志文件供回测
"""
import sys
import os
import json
import argparse
from collections import defaultdict
from datetime import datetime
import pymysql
import pymysql.cursors

sys.stdout.reconfigure(encoding='utf-8')

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, 'logs', 'monitor')

RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']
COMPANY_ID = '115'
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


def load_upcoming(minutes=30):
    conn = get_db()
    query = '''
        SELECT
            oar.match_id,
            oar.initial_home_range, oar.initial_away_range, oar.initial_draw_range,
            oar.current_home_range, oar.current_away_range, oar.current_draw_range,
            oar.power_diff,
            m.home_team_name, m.away_team_name,
            m.match_time,
            l.league_id, l.name_cn as league_name,
            oc.initial_home, oc.initial_draw, oc.initial_away,
            oc.current_home, oc.current_draw, oc.current_away
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        JOIN odds_changes oc ON oar.match_id = oc.match_id AND oar.company_id = oc.company_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = %s
          AND m.match_status = 'scheduled'
          AND m.match_time >= NOW()
          AND m.match_time <= NOW() + INTERVAL %s MINUTE
        ORDER BY m.match_time
    '''
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (COMPANY_ID, minutes))
            return cursor.fetchall()
    finally:
        conn.close()


def process_match(row):
    ih = float(row['initial_home'])
    ia = float(row['initial_away'])
    ch = float(row['current_home'])
    ca = float(row['current_away'])

    if ih <= ia:
        h_team = row['home_team_name']
        r_team = row['away_team_name']
        init_h_range = row['initial_home_range']
        init_r_range = row['initial_away_range']
        curr_h_range = row['current_home_range']
        curr_r_range = row['current_away_range']
        init_h_odds, init_r_odds = ih, ia
        curr_h_odds, curr_r_odds = ch, ca
    else:
        h_team = row['away_team_name']
        r_team = row['home_team_name']
        init_h_range = row['initial_away_range']
        init_r_range = row['initial_home_range']
        curr_h_range = row['current_away_range']
        curr_r_range = row['current_home_range']
        init_h_odds, init_r_odds = ia, ih
        curr_h_odds, curr_r_odds = ca, ch

    return {
        'match_id': row['match_id'],
        'home_team': row['home_team_name'],
        'away_team': row['away_team_name'],
        'h_team': h_team,
        'r_team': r_team,
        'match_time': row['match_time'],
        'league': row['league_name'],
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
        'curr_h_odds': curr_h_odds,
        'curr_r_odds': curr_r_odds,
        'curr_h_range_full': curr_h_range,
        'curr_r_range_full': curr_r_range,
        'curr_draw_full': row['current_draw_range'],
        'init_h_range_full': init_h_range,
        'init_r_range_full': init_r_range,
        'init_draw_full': row['initial_draw_range'],
        'odds_str': f"{ch:.2f} / {float(row['current_draw']):.2f} / {ca:.2f}",
    }


# ====== 规则定义 ======
RULES = [
    # ---- 让方不输 ----
    ("即时平局=平实低 + 初盘让方=实开 + 力量差=强让",
     "让方不输", 100.0, 22, 1.63,
     lambda m: m['curr_draw'] == '平实低' and m['init_h'] == '实开' and m['power'] == '强让'),

    ("即时让方=实开 + 受让方变化=升 + 力量差=微让",
     "让方不输", 100.0, 21, 1.86,
     lambda m: m['curr_h'] == '实开' and m['r_change'] == '升' and m['power'] == '微让'),

    ("即时平局=平实低 + 初盘受让方=实开 + 力量差=强让",
     "让方不输", 100.0, 21, 1.65,
     lambda m: m['curr_draw'] == '平实低' and m['init_r'] == '实开' and m['power'] == '强让'),

    ("即时让方=实开 + 即时平局=平实低 + 力量差=强让",
     "让方不输", 100.0, 17, 1.60,
     lambda m: m['curr_h'] == '实开' and m['curr_draw'] == '平实低' and m['power'] == '强让'),

    ("即时受让方=高开 + 初盘受让方=实开 + 初盘平局=平实低",
     "让方不输", 94.7, 19, 1.90,
     lambda m: m['curr_r'] == '高开' and m['init_r'] == '实开' and m['init_draw'] == '平实低'),

    ("即时让方=实开 + 初盘平局=平实低 + 受让方变化=升",
     "让方不输", 94.1, 17, 2.07,
     lambda m: m['curr_h'] == '实开' and m['init_draw'] == '平实低' and m['r_change'] == '升'),

    ("即时受让方=高开 + 受让方变化=升 + 平赔变化=稳",
     "让方不输", 93.5, 31, 2.01,
     lambda m: m['curr_r'] == '高开' and m['r_change'] == '升' and m['d_change'] == '稳'),

    ("初盘受让方=实开 + 初盘平局=低开平 + 受让方变化=升",
     "让方不输", 93.5, 31, 1.96,
     lambda m: m['init_r'] == '实开' and m['init_draw'] == '低开平' and m['r_change'] == '升'),

    ("即时受让方=实开 + 让方变化=稳 + 力量差=微受",
     "让方不输", 94.1, 17, 2.46,
     lambda m: m['curr_r'] == '实开' and m['h_change'] == '稳' and m['power'] == '微受'),

    ("即时平局=平实低 + 让方变化=稳 + 受让方变化=降",
     "让方不输", 94.1, 19, 1.80,
     lambda m: m['curr_draw'] == '平实低' and m['h_change'] == '稳' and m['r_change'] == '降'),

    ("即时让方=实开 + 让方变化=降 + 受让方变化=升",
     "让方不输", 91.5, 47, 1.98,
     lambda m: m['curr_h'] == '实开' and m['h_change'] == '降' and m['r_change'] == '升'),

    ("即时平局=平实低 + 力量差=强让",
     "让方不输", 91.7, 36, 1.64,
     lambda m: m['curr_draw'] == '平实低' and m['power'] == '强让'),

    ("即时受让方=高开 + 让方变化=降 + 受让方变化=升",
     "让方不输", 88.6, 44, 1.89,
     lambda m: m['curr_r'] == '高开' and m['h_change'] == '降' and m['r_change'] == '升'),

    ("即时受让方=高开 + 受让方变化=升",
     "让方不输", 87.1, 62, 1.87,
     lambda m: m['curr_r'] == '高开' and m['r_change'] == '升'),

    ("即时让方=实开 + 让方变化=降",
     "让方不输", 86.5, 52, 1.97,
     lambda m: m['curr_h'] == '实开' and m['h_change'] == '降'),

    ("平赔变化=升 + 力量差=强让",
     "让方不输", 90.3, 31, 1.50,
     lambda m: m['d_change'] == '升' and m['power'] == '强让'),

    ("初盘平局=低开平 + 让方变化=降 + 力量差=平手",
     "让方不输", 94.1, 17, 1.98,
     lambda m: m['init_draw'] == '低开平' and m['h_change'] == '降' and m['power'] == '平手'),

    ("初盘受让方=实开 + 初盘平局=平实低 + 受让方变化=升",
     "让方不输", 93.5, 31, 1.84,
     lambda m: m['init_r'] == '实开' and m['init_draw'] == '平实低' and m['r_change'] == '升'),

    # ---- 让方必赢 ----
    ("即时让方=韬光 + 初盘受让方=实开 + 平赔变化=降",
     "让方必赢", 91.7, 12, 2.18,
     lambda m: m['curr_h'] == '韬光' and m['init_r'] == '实开' and m['d_change'] == '降'),

    ("即时让方=实开 + 即时平局=平实低 + 力量差=强让",
     "让方必赢", 88.2, 17, 1.60,
     lambda m: m['curr_h'] == '实开' and m['curr_draw'] == '平实低' and m['power'] == '强让'),

    ("即时受让方=韬光 + 初盘平局=低开平 + 力量差=平手",
     "让方必赢", 86.7, 15, 2.03,
     lambda m: m['curr_r'] == '韬光' and m['init_draw'] == '低开平' and m['power'] == '平手'),

    ("即时平局=平实低 + 让方变化=降 + 平赔变化=升",
     "让方必赢", 80.8, 26, 1.67,
     lambda m: m['curr_draw'] == '平实低' and m['h_change'] == '降' and m['d_change'] == '升'),

    ("即时平局=平实低 + 受让方变化=升 + 平赔变化=升",
     "让方必赢", 80.0, 25, 1.67,
     lambda m: m['curr_draw'] == '平实低' and m['r_change'] == '升' and m['d_change'] == '升'),

    # ---- 受让方不输 ----
    ("初盘让方=高开 + 受让方变化=降 + 平赔变化=稳",
     "受让方不输", 93.8, 16, 2.36,
     lambda m: m['init_h'] == '高开' and m['r_change'] == '降' and m['d_change'] == '稳'),

    ("即时让方=韬光 + 平赔变化=稳",
     "受让方不输", 84.6, 39, 2.54,
     lambda m: m['curr_h'] == '韬光' and m['d_change'] == '稳'),

    ("即时让方=韬光 + 让方变化=升 + 平赔变化=稳",
     "受让方不输", 83.9, 31, 2.64,
     lambda m: m['curr_h'] == '韬光' and m['h_change'] == '升' and m['d_change'] == '稳'),

    ("即时受让方=低开 + 即时平局=平实低 + 平赔变化=稳",
     "受让方不输", 86.7, 15, 2.42,
     lambda m: m['curr_r'] == '低开' and m['curr_draw'] == '平实低' and m['d_change'] == '稳'),

    ("即时让方=韬光 + 即时受让方=超实 + 平赔变化=稳",
     "受让方不输", 85.7, 14, 2.43,
     lambda m: m['curr_h'] == '韬光' and m['curr_r'] == '超实' and m['d_change'] == '稳'),
]


def save_log(all_hits, check_time, minutes):
    """将命中记录追加写入日志文件"""
    os.makedirs(LOG_DIR, exist_ok=True)

    today = check_time.strftime('%Y-%m-%d')
    log_txt = os.path.join(LOG_DIR, f'{today}.log')
    log_json = os.path.join(LOG_DIR, f'{today}.json')

    # 读取已有JSON记录
    existing = []
    if os.path.exists(log_json):
        try:
            with open(log_json, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    # 已记录的match_id+rule组合（去重）
    seen = set()
    for rec in existing:
        seen.add((rec['match_id'], rec['rule']))

    new_records = []
    for hit in all_hits:
        m = hit['match']
        key = (m['match_id'], hit['rule'])
        if key in seen:
            continue
        seen.add(key)
        rec = {
            'check_time': check_time.strftime('%Y-%m-%d %H:%M:%S'),
            'match_id': m['match_id'],
            'match_time': str(m['match_time']),
            'league': m['league'],
            'home_team': m['home_team'],
            'away_team': m['away_team'],
            'h_team': m['h_team'],
            'r_team': m['r_team'],
            'curr_h_odds': m['curr_h_odds'],
            'curr_r_odds': m['curr_r_odds'],
            'odds_str': m['odds_str'],
            'rule': hit['rule'],
            'target': hit['target'],
            'accuracy': hit['accuracy'],
            'sample': hit['sample'],
            'result': None,  # 待回测填入
        }
        new_records.append(rec)
        existing.append(rec)

    # 写入JSON
    with open(log_json, 'w', encoding='utf-8') as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    # 追加写入文本日志
    if new_records:
        with open(log_txt, 'a', encoding='utf-8') as f:
            for rec in new_records:
                f.write(f"[{rec['check_time']}] {rec['match_time']} "
                        f"[{rec['league']}] {rec['home_team']} vs {rec['away_team']} | "
                        f"赔率: {rec['odds_str']} | "
                        f"让方: {rec['h_team']}({rec['curr_h_odds']:.2f}) | "
                        f">>> {rec['target']} [{rec['accuracy']:.1f}%|{rec['sample']}场] {rec['rule']}\n")

    return len(new_records)


def main():
    parser = argparse.ArgumentParser(description='监控即将开赛的比赛')
    parser.add_argument('-m', '--minutes', type=int, default=30,
                        help='查看未来多少分钟内的比赛 (默认30)')
    parser.add_argument('--log', action='store_true',
                        help='将结果记录到日志文件供回测')
    args = parser.parse_args()

    now = datetime.now()
    now_str = now.strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'=' * 80}")
    print(f"  赛前监控 | 当前时间: {now_str} | 窗口: 未来{args.minutes}分钟")
    print(f"{'=' * 80}")

    rows = load_upcoming(args.minutes)
    if not rows:
        print(f"\n  未来{args.minutes}分钟内没有比赛。")
        print(f"{'=' * 80}\n")
        return

    matches = []
    for row in rows:
        m = process_match(row)
        if m['curr_h_odds'] >= MIN_ODDS:
            matches.append(m)

    print(f"  未来{args.minutes}分钟内共 {len(rows)} 场比赛，排除大热门后 {len(matches)} 场")

    # 匹配规则
    all_hits = []
    for rule_name, target, acc, sample, avg_odds, cond_fn in RULES:
        for m in matches:
            if cond_fn(m):
                all_hits.append({
                    'match': m,
                    'rule': rule_name,
                    'target': target,
                    'accuracy': acc,
                    'sample': sample,
                    'avg_odds': avg_odds,
                })

    if not all_hits:
        print(f"\n  这些比赛中没有命中任何规则。")
        print(f"{'=' * 80}\n")
        return

    # 按比赛分组
    by_match = defaultdict(list)
    for hit in all_hits:
        by_match[hit['match']['match_id']].append(hit)

    sorted_matches = sorted(by_match.values(), key=lambda hits: hits[0]['match']['match_time'])

    print(f"  命中: {len(sorted_matches)} 场比赛，共 {len(all_hits)} 条规则")
    print(f"{'=' * 80}")

    for hits in sorted_matches:
        m = hits[0]['match']
        print(f"\n  [{m['league']}] {m['home_team']} vs {m['away_team']}")
        print(f"  开赛: {m['match_time']}  |  赔率: {m['odds_str']}")
        print(f"  让球方: {m['h_team']}({m['curr_h_odds']:.2f})  |  受让方: {m['r_team']}({m['curr_r_odds']:.2f})")
        print(f"  盘型: 让方={m['curr_h_range_full']}  受让方={m['curr_r_range_full']}  平局={m['curr_draw_full']}")
        print(f"  变化: 让方={m['h_change']}  受让方={m['r_change']}  平赔={m['d_change']}  |  力量差={m['power']}")

        by_target = defaultdict(list)
        for h in hits:
            by_target[h['target']].append(h)

        for target in ['让方必赢', '让方不输', '受让方不输']:
            if target not in by_target:
                continue
            rules = sorted(by_target[target], key=lambda x: -x['accuracy'])
            for h in rules:
                print(f"  >>> {target} [{h['accuracy']:.1f}% | 样本{h['sample']}] {h['rule']}")

    print(f"\n{'=' * 80}")

    # 写日志
    if args.log:
        new_count = save_log(all_hits, now, args.minutes)
        log_file = os.path.join(LOG_DIR, now.strftime('%Y-%m-%d') + '.json')
        print(f"  日志: 新增 {new_count} 条记录 → {log_file}")
        print(f"{'=' * 80}")

    print()


if __name__ == '__main__':
    main()
