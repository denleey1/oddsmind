#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
信号扫描器 — 竞争区间规则引擎 v3.1
====================================
按小时窗口扫描比赛，汇总重仓/强烈/参考信号。

用法:
  python scan_signals.py              # 默认扫未来24小时
  python scan_signals.py -H 3         # 未来3小时
  python scan_signals.py -H 72        # 未来72小时
  python scan_signals.py -H 24 -v     # 详细模式(显示规则明细)
  python scan_signals.py -H 24 --save # 同时保存结果到数据库
"""

import sys
import os
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)



def get_matches_in_window(hours: int):
    """获取指定小时窗口内的所有比赛"""
    from database.connection import get_connection
    db = get_connection()

    now = datetime.now()
    future = now + timedelta(hours=hours)

    query = '''
        SELECT m.match_id, m.match_time,
               m.home_team_name, m.away_team_name,
               m.match_status,
               l.league_id, l.name_cn as league_name
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_time BETWEEN %s AND %s
          AND m.match_status IN ('scheduled', 'live')
        ORDER BY m.match_time
    '''
    return db.execute_query(query, (now, future), fetch='all') or []


def scan(hours: int, verbose: bool = False, save_db: bool = False):
    """执行扫描并输出结果"""
    import logging
    logging.basicConfig(level=logging.WARNING)
    log = logging.getLogger('scan')

    from database.connection import get_connection
    from services.auto_rule_matcher_logic_ops import evaluate_match, RULES
    from services.auto_rule_matcher_db_ops import save_signal_summary, _cleanup_stale_rules

    db = get_connection()
    matches = get_matches_in_window(hours)

    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"\n{'=' * 80}")
    print(f"  🎯 v3.1 信号扫描 | {now_str} | 窗口: 未来 {hours} 小时")
    print(f"  规则: {len(RULES)} 条 | 比赛: {len(matches)} 场")
    print(f"{'=' * 80}")

    if not matches:
        print(f"\n  未来 {hours} 小时内没有比赛。")
        print(f"{'=' * 80}\n")
        return

    # 按日期分组统计
    heavy, strong, refer = [], [], []
    no_signal = 0
    no_data = 0
    saved_total = 0

    for match in matches:
        match_id = match['match_id']
        result = evaluate_match(match_id, db)

        signal = result.get('signal', '无信号')
        if signal == '无数据':
            no_data += 1
            continue
        if signal == '无信号':
            no_signal += 1
            if save_db:
                _cleanup_stale_rules(match_id, [], log)
            continue

        feat = result.get('features', {})
        side_cn = result.get('side_cn', '')
        mode = result.get('mode', '')
        mode_cn = {'wml': '三公司', 'wm': '威廉+澳门', 'wl': '威廉+立博'}.get(mode, '')
        triggered = result.get('triggered', [])

        home_is_h = feat.get('home_is_h', True)
        home = match.get('home_team_name', '')
        away = match.get('away_team_name', '')

        info = {
            'match_id': match_id,
            'match_time': str(match['match_time']),
            'date': str(match['match_time'])[:10],
            'league': match.get('league_name', '') or '',
            'home': home,
            'away': away,
            'handicap': home if home_is_h else away,
            'receiver': away if home_is_h else home,
            'signal': signal,
            'side': side_cn,
            'mode': mode_cn,
            'rules': len(triggered),
            'n_s': sum(1 for r in triggered if r['grade'] == 'S'),
            'n_a': sum(1 for r in triggered if r['grade'] == 'A'),
            'cross': result.get('cross_confirm', False),
            'conflict': result.get('conflict', False),
            'score': result.get('score', 0),
            'rule_list': triggered,
            'w_h': feat.get('w_h', 0),
            'w_r': feat.get('w_r', 0),
            'w_d': feat.get('w_d', 0),
        }

        if signal == '重仓':
            heavy.append(info)
        elif signal == '强烈':
            strong.append(info)
        else:
            refer.append(info)

        # 保存到数据库
        if save_db:
            match_info = {'home_name': home, 'away_name': away,
                          'league_name': match.get('league_name', '')}
            saved = save_signal_summary(match_id, result, match_info, log)
            saved_total += saved

    # ==================== 汇总 ====================
    total_signal = len(heavy) + len(strong) + len(refer)
    total_all = total_signal + no_signal + no_data

    print(f"\n  📊 扫描结果汇总")
    print(f"  {'─' * 40}")
    print(f"  🔴 重仓:  {len(heavy):>3} 场")
    print(f"  🟠 强烈:  {len(strong):>3} 场")
    print(f"  🟡 参考:  {len(refer):>3} 场")
    print(f"  {'─' * 40}")
    print(f"  ✅ 有信号: {total_signal:>3} 场 ({total_signal/total_all*100:.1f}%)" if total_all else "")
    print(f"  ⚪ 无信号: {no_signal:>3} 场")
    print(f"  ⬛ 无数据: {no_data:>3} 场")
    if save_db:
        print(f"  📝 已保存: {saved_total} 条规则记录到数据库")

    # ==================== 按日期分组汇总 ====================
    all_signals = heavy + strong + refer
    if all_signals:
        dates = sorted(set(m['date'] for m in all_signals))
        if len(dates) > 1:
            print(f"\n  📅 按日期分布")
            print(f"  {'─' * 40}")
            for d in dates:
                dh = sum(1 for m in heavy if m['date'] == d)
                ds = sum(1 for m in strong if m['date'] == d)
                dr = sum(1 for m in refer if m['date'] == d)
                print(f"  {d}: 🔴{dh} 🟠{ds} 🟡{dr} (共{dh+ds+dr}场)")

    # ==================== 详细列表 ====================
    def print_group(label, icon, items):
        if not items:
            return
        print(f"\n{'=' * 80}")
        print(f"  {icon} {label} ({len(items)}场)")
        print(f"{'=' * 80}")
        for m in sorted(items, key=lambda x: x['match_time']):
            cross_tag = ' ★共振' if m['cross'] else ''
            conflict_tag = ' ⚡冲突' if m['conflict'] else ''
            print(f"\n  {m['match_time']} [{m['league']}]")
            print(f"    {m['home']} vs {m['away']}")
            odds_str = f"{m['w_h']:.2f} / {m['w_d']:.2f} / {m['w_r']:.2f}" if m['w_h'] else ''
            print(f"    → {m['side']} | {m['mode']} | "
                  f"{m['rules']}条规则({m['n_s']}S+{m['n_a']}A) "
                  f"分数={m['score']}{cross_tag}{conflict_tag}")
            if odds_str:
                print(f"    赔率: {odds_str}  让方={m['handicap']}  受让方={m['receiver']}")
            if verbose:
                for r in m['rule_list']:
                    g = {'S': '★★★', 'A': '★★', 'B': '★'}.get(r['grade'], '')
                    print(f"    {g} [{r['id']}] {r['desc']}")

    print_group('重仓信号', '🔴', heavy)
    print_group('强烈信号', '🟠', strong)
    print_group('参考信号', '🟡', refer)

    print(f"\n{'=' * 80}\n")


def main():
    parser = argparse.ArgumentParser(
        description='v3.1 信号扫描器 — 按小时窗口扫描比赛信号')
    parser.add_argument('-H', '--hours', type=int, default=24,
                        help='扫描未来多少小时的比赛 (默认24)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='详细模式: 显示每条触发规则的明细')
    parser.add_argument('--save', action='store_true',
                        help='将匹配结果保存到数据库 (供小程序API读取)')
    args = parser.parse_args()

    scan(hours=args.hours, verbose=args.verbose, save_db=args.save)


if __name__ == '__main__':
    main()
