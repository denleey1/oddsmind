"""
澳门分歧信号（Macau Divergence Signal）
======================================
版本: v1.0   状态: 观察验证中，未接入生产规则引擎

核心逻辑
--------
当市场（百家均值）大幅向某热门方向移动，而澳门在排除自身高抽水
差异后仍坚持更高赔率（不跟随市场），该热门的不赢概率显著提升。

信号随时间增强（数据验证）：
  最老批次准确率：~35%
  近期批次准确率：~83%
  信号趋势向 90% 持续增强

参数说明
--------
ADJ_DIFF_THRESHOLD = 0.15
    含义：澳门 RR 修正差值门槛
    计算：adj_diff = 澳门赔率(热门) - 百家均值赔率(热门) × (澳门RR / 百家RR)
    解读：澳门"应给"的赔率（基于概率相同的假设）= 百家均值 × (澳门RR/百家RR)
          如果实际赔率 > 应给赔率 + 0.15，说明澳门真实地不看好热门
    举例：百家热门均值 2.25，百家RR=93.9%，澳门RR=88.6%
          应给赔率 = 2.25 × (88.6/93.9) = 2.12
          澳门实给 2.28，adj_diff = 2.28 - 2.12 = 0.16 > 0.15 → 触发

AVG_MOVE_THRESHOLD = 0.05
    含义：市场向热门方向移动的最小幅度
    计算：avg_move = 百家开盘均值赔率(热门) - 百家即时均值赔率(热门)
    解读：正值 = 开盘后市场赔率下降 = 更多资金涌入支持热门
          > 0.05 表示市场已明显向热门倾斜，澳门的不跟随更有意义
    举例：开盘均值 2.47 → 即时均值 2.25，avg_move = 0.22 → 触发

FAV_ODDS_LO / FAV_ODDS_HI = 2.0 / 2.5
    含义：热门方百家即时均值赔率的区间限制
    解读：只关注"竞争性热门"
          < 2.0：强热门，另一套规律（大小球/让球更合适）
          > 2.5：实力接近，算不上热门
    举例：主场均值 2.24、客场均值 3.41 → 主场是热门，avg_fav=2.24 ∈ [2.0,2.5] → 参与判断

预测结果
--------
触发信号后预测：热门方"不赢"（平局或输）
  热门=主队 → 预测 "不是主胜"（平局或主负）
  热门=客队 → 预测 "不是客胜"（平局或客负）

用法
----
  python macau_divergence_signal.py                   # 显示帮助
  python macau_divergence_signal.py --check 2814925   # 分析单场
  python macau_divergence_signal.py --backtest        # 历史回测
  python macau_divergence_signal.py --scan            # 扫描近期未完成比赛
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_connection
from collections import defaultdict
from datetime import datetime, timedelta

# ===================== 信号参数 =====================
ADJ_DIFF_THRESHOLD  = 0.15   # 澳门RR修正差值门槛（核心条件）
AVG_MOVE_THRESHOLD  = 0.05   # 市场向热门移动门槛
FAV_ODDS_LO         = 2.00   # 热门赔率区间下限
FAV_ODDS_HI         = 2.50   # 热门赔率区间上限
MIN_MKT_COMPANIES   = 5      # 计算百家均值所需最少公司数
MACAU_ID            = 80
# ====================================================


def _compute_market_avg(cdata, exclude_ids):
    """计算排除参照公司后的百家即时均值和开盘均值"""
    cur = [(v['ch'], v['cd'], v['ca'])
           for cid, v in cdata.items()
           if cid not in exclude_ids and v['ch'] > 1.0]
    if len(cur) < MIN_MKT_COMPANIES:
        return None

    n = len(cur)
    ah = sum(x[0] for x in cur) / n
    ad = sum(x[1] for x in cur) / n
    aa = sum(x[2] for x in cur) / n
    avg_rr = 100 / (1/ah + 1/ad + 1/aa)

    ini = [(v['ih'], v['ia'])
           for cid, v in cdata.items()
           if cid not in exclude_ids and v['ih'] > 1.0]
    n_ini = len(ini)
    i_ah = sum(x[0] for x in ini) / n_ini if n_ini >= 5 else ah
    i_aa = sum(x[1] for x in ini) / n_ini if n_ini >= 5 else aa

    return {'ah': ah, 'ad': ad, 'aa': aa, 'rr': avg_rr,
            'i_ah': i_ah, 'i_aa': i_aa, 'n': n}


def analyze_match(match_id, db=None):
    """
    分析单场比赛是否触发澳门分歧信号。

    Returns
    -------
    dict or None
        包含以下字段：
          signal_triggered (bool)   是否触发信号
          fav_side         (str)    热门方 'home' 或 'away'
          avg_fav          (float)  热门方百家即时均值赔率
          avg_fav_open     (float)  热门方百家开盘均值赔率
          avg_move         (float)  市场移动量（正=市场更看好热门）
          mac_fav_odds     (float)  澳门即时赔率（热门方）
          expected_mac     (float)  澳门"应给"赔率（RR修正后）
          adj_diff         (float)  澳门RR修正差值（mac - expected）
          avg_rr           (float)  百家平均返还率 %
          mac_rr           (float)  澳门返还率 %
          n_companies      (int)    参与均值的公司数
        None if 数据不足
    """
    close_db = False
    if db is None:
        db = get_connection()
        close_db = True

    mac_row = db.execute_query(
        'SELECT current_home, current_draw, current_away, '
        'initial_home, initial_away, current_return_rate '
        'FROM european_odds WHERE match_id=%s AND company_id=%s',
        (match_id, MACAU_ID), fetch='one'
    )
    if not mac_row or not mac_row.get('current_home'):
        return None

    others = db.execute_query(
        'SELECT company_id, current_home, current_draw, current_away, '
        'initial_home, initial_away, current_return_rate '
        'FROM european_odds WHERE match_id=%s AND company_id NOT IN (0,%s) '
        'AND current_home>1.0 AND initial_home>1.0',
        (match_id, MACAU_ID), fetch='all'
    )

    cdata = {}
    for o in others:
        cdata[o['company_id']] = {
            'ch': float(o['current_home']), 'cd': float(o['current_draw']),
            'ca': float(o['current_away']),
            'ih': float(o['initial_home']), 'ia': float(o['initial_away']),
            'rr': float(o['current_return_rate']) if o['current_return_rate'] else 91.0
        }

    mkt = _compute_market_avg(cdata, {0, MACAU_ID})
    if mkt is None:
        return None

    ah = mkt['ah']; ad = mkt['ad']; aa = mkt['aa']; avg_rr = mkt['rr']

    # 平局是热门则跳过
    if ad <= ah and ad <= aa:
        return None

    mac_rr = float(mac_row['current_return_rate']) if mac_row['current_return_rate'] else 88.0
    rr_ratio = mac_rr / avg_rr

    if ah <= aa:
        fav_side     = 'home'
        avg_fav      = ah
        avg_fav_open = mkt['i_ah']
        avg_move     = mkt['i_ah'] - ah
        mac_fav_odds = float(mac_row['current_home'])
    else:
        fav_side     = 'away'
        avg_fav      = aa
        avg_fav_open = mkt['i_aa']
        avg_move     = mkt['i_aa'] - aa
        mac_fav_odds = float(mac_row['current_away'])

    expected_mac = avg_fav * rr_ratio
    adj_diff     = mac_fav_odds - expected_mac

    signal_triggered = (
        FAV_ODDS_LO <= avg_fav < FAV_ODDS_HI
        and avg_move    > AVG_MOVE_THRESHOLD
        and adj_diff    > ADJ_DIFF_THRESHOLD
    )

    return {
        'match_id':        match_id,
        'signal_triggered': signal_triggered,
        'fav_side':        fav_side,
        'avg_fav':         round(avg_fav, 3),
        'avg_fav_open':    round(avg_fav_open, 3),
        'avg_move':        round(avg_move, 3),
        'mac_fav_odds':    round(mac_fav_odds, 3),
        'expected_mac':    round(expected_mac, 3),
        'adj_diff':        round(adj_diff, 3),
        'avg_rr':          round(avg_rr, 2),
        'mac_rr':          round(mac_rr, 2),
        'n_companies':     mkt['n'],
    }


def check_single(match_id):
    """分析单场并打印详情"""
    db = get_connection()

    match = db.execute_query(
        'SELECT home_team_name, away_team_name, match_time, '
        'home_score, away_score, match_status, league_id '
        'FROM matches WHERE match_id=%s',
        (match_id,), fetch='one'
    )
    league = None
    if match:
        league = db.execute_query(
            'SELECT name_cn FROM leagues WHERE league_id=%s',
            (match['league_id'],), fetch='one'
        )

    print(f"\n{'='*60}")
    if match:
        lg = league['name_cn'] if league else f"lid={match['league_id']}"
        print(f"  [{lg}] {match['home_team_name']} vs {match['away_team_name']}")
        print(f"  时间: {match['match_time']}  状态: {match['match_status']}")
        if match['home_score'] is not None:
            print(f"  比分: {match['home_score']}-{match['away_score']}")
    print(f"{'='*60}")

    r = analyze_match(match_id, db)
    if r is None:
        print("  ⚠ 数据不足（缺少澳门赔率或百家公司数量不够）")
        return

    fav_name = "主队" if r['fav_side'] == 'home' else "客队"
    print(f"\n  热门方: {fav_name}")
    print(f"  ┌─ 百家开盘均值: {r['avg_fav_open']}")
    print(f"  │  百家即时均值: {r['avg_fav']}  (↓{r['avg_move']:.3f}, 市场{'更看好热门✓' if r['avg_move']>0 else '未向热门移动'})")
    print(f"  │  参与公司数:   {r['n_companies']} 家,  百家RR: {r['avg_rr']}%")
    print(f"  ├─ 澳门即时赔率: {r['mac_fav_odds']}  (澳门RR: {r['mac_rr']}%)")
    print(f"  │  澳门应给赔率: {r['expected_mac']}  [= {r['avg_fav']} × ({r['mac_rr']}/{r['avg_rr']})]")
    print(f"  └─ adj_diff:    {r['adj_diff']:+.3f}  ({'澳门不看好热门 ✓' if r['adj_diff']>0 else '澳门跟随市场'})")

    print()
    # 判断条件
    cond1 = f"{'✓' if FAV_ODDS_LO<=r['avg_fav']<FAV_ODDS_HI else '✗'} 赔率区间 [{FAV_ODDS_LO},{FAV_ODDS_HI}): avg_fav={r['avg_fav']}"
    cond2 = f"{'✓' if r['avg_move']>AVG_MOVE_THRESHOLD else '✗'} 市场移动 >{AVG_MOVE_THRESHOLD}: avg_move={r['avg_move']:+.3f}"
    cond3 = f"{'✓' if r['adj_diff']>ADJ_DIFF_THRESHOLD else '✗'} RR修正差 >{ADJ_DIFF_THRESHOLD}: adj_diff={r['adj_diff']:+.3f}"
    print(f"  条件检查:")
    print(f"    {cond1}")
    print(f"    {cond2}")
    print(f"    {cond3}")

    print()
    if r['signal_triggered']:
        print(f"  🔴 信号触发！预测: {fav_name}不赢（平局或输）")
        print(f"     历史近期准确率: ~83%（持续增强中）")
    else:
        print(f"  ⚪ 信号未触发")

    # 如果已有结果，显示是否命中
    if match and match['home_score'] is not None and r['signal_triggered']:
        if r['fav_side'] == 'home':
            actual_fail = match['home_score'] <= match['away_score']
        else:
            actual_fail = match['away_score'] <= match['home_score']
        print(f"     实际结果: {'✓ 命中（热门确实未赢）' if actual_fail else '✗ 未中（热门赢了）'}")

    print(f"{'='*60}\n")


def backtest(limit=30000, verbose=False):
    """历史回测，显示按时间分段的准确率"""
    db = get_connection()

    rows = db.execute_query('''
        SELECT m.match_id, m.home_score, m.away_score
        FROM matches m
        WHERE m.match_status='finished' AND m.home_score IS NOT NULL
        ORDER BY m.match_id ASC
        LIMIT %s
    ''', (limit,), fetch='all')

    match_ids = [r['match_id'] for r in rows]
    ph = ','.join(['%s'] * len(match_ids))

    all_o = db.execute_query(f'''
        SELECT match_id, company_id, current_home, current_draw, current_away,
               initial_home, initial_away, current_return_rate
        FROM european_odds WHERE match_id IN ({ph})
          AND company_id NOT IN (0) AND current_home>1.0 AND initial_home>1.0
    ''', match_ids, fetch='all')

    match_company = defaultdict(dict)
    for o in all_o:
        match_company[o['match_id']][o['company_id']] = {
            'ch': float(o['current_home']), 'cd': float(o['current_draw']),
            'ca': float(o['current_away']),
            'ih': float(o['initial_home']), 'ia': float(o['initial_away']),
            'rr': float(o['current_return_rate']) if o['current_return_rate'] else 91.0
        }

    result_map = {r['match_id']: r for r in rows}
    triggered_list = []

    for r in rows:
        mid = r['match_id']
        mac = match_company[mid].get(MACAU_ID)
        if not mac: continue

        cdata = {cid: v for cid, v in match_company[mid].items()}
        mkt = _compute_market_avg(cdata, {0, MACAU_ID})
        if mkt is None: continue

        ah = mkt['ah']; ad = mkt['ad']; aa = mkt['aa']; avg_rr = mkt['rr']
        if ad <= ah and ad <= aa: continue

        mac_rr = mac['rr']
        rr_ratio = mac_rr / avg_rr

        if ah <= aa:
            avg_fav = ah; avg_move = mkt['i_ah'] - ah
            adj_diff = mac['ch'] - ah * rr_ratio
            fav_failed = r['home_score'] <= r['away_score']
        else:
            avg_fav = aa; avg_move = mkt['i_aa'] - aa
            adj_diff = mac['ca'] - aa * rr_ratio
            fav_failed = r['away_score'] <= r['home_score']

        if (FAV_ODDS_LO <= avg_fav < FAV_ODDS_HI
                and avg_move > AVG_MOVE_THRESHOLD
                and adj_diff > ADJ_DIFF_THRESHOLD):
            triggered_list.append({
                'match_id': mid, 'fav_failed': fav_failed,
                'avg_fav': avg_fav, 'avg_move': avg_move, 'adj_diff': adj_diff,
            })

    total = len(triggered_list)
    hits  = sum(1 for x in triggered_list if x['fav_failed'])

    print(f"\n{'='*60}")
    print(f"  澳门分歧信号  历史回测")
    print(f"{'='*60}")
    print(f"  参数: adj_diff>{ADJ_DIFF_THRESHOLD}  avg_move>{AVG_MOVE_THRESHOLD}  赔率{FAV_ODDS_LO}-{FAV_ODDS_HI}")
    print(f"  总触发: {total} 场  命中: {hits} 场  总准确率: {hits/total*100:.1f}%\n" if total else "  无触发\n")

    # 时间四等分分析
    if total >= 20:
        print(f"  按时间分段（验证信号是否增强）：")
        q = total // 4
        segments = [
            (0, q,       "最老 25%"),
            (q, 2*q,     "25-50%"),
            (2*q, 3*q,   "50-75%"),
            (3*q, total, "最新 25%"),
        ]
        for s, e, label in segments:
            seg = triggered_list[s:e]
            if not seg: continue
            f = sum(1 for x in seg if x['fav_failed'])
            print(f"    {label}: {f}/{len(seg)} = {f/len(seg)*100:.1f}%")

    if verbose and triggered_list:
        print(f"\n  触发的比赛（最新30场）：")
        for x in triggered_list[-30:]:
            r = result_map[x['match_id']]
            status = "✓" if x['fav_failed'] else "✗"
            print(f"    {x['match_id']}  avg_fav={x['avg_fav']:.2f}  "
                  f"move={x['avg_move']:+.2f}  adj={x['adj_diff']:.2f}  "
                  f"比分:{r['home_score']}-{r['away_score']}  {status}")

    return triggered_list


def scan_upcoming(days_ahead=3):
    """扫描近期未完成比赛，找出触发信号的比赛"""
    db = get_connection()

    now = datetime.utcnow()
    upcoming = db.execute_query('''
        SELECT m.match_id, m.home_team_name, m.away_team_name,
               m.match_time, m.league_id, l.name_cn as league_name
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        WHERE m.match_status IN ('scheduled', 'pending')
          AND m.match_time BETWEEN %s AND %s
        ORDER BY m.match_time ASC
    ''', (now - timedelta(hours=2), now + timedelta(days=days_ahead)), fetch='all')

    if not upcoming:
        print("暂无近期比赛数据")
        return

    print(f"\n扫描 {len(upcoming)} 场近期比赛...")
    found = []
    for m in upcoming:
        r = analyze_match(m['match_id'], db)
        if r and r['signal_triggered']:
            found.append({**r, **m})

    print(f"\n{'='*60}")
    print(f"  澳门分歧信号  近期扫描结果")
    print(f"{'='*60}")
    if not found:
        print("  当前无触发信号的比赛")
    else:
        for x in found:
            fav_name = "主" if x['fav_side'] == 'home' else "客"
            print(f"\n  🔴 [{x['league_name']}]")
            print(f"     {x['home_team_name']} vs {x['away_team_name']}")
            print(f"     时间: {x['match_time']}")
            print(f"     {fav_name}热门赔率: 百家均值={x['avg_fav']}  澳门={x['mac_fav_odds']}")
            print(f"     市场移动: {x['avg_move']:+.3f}  RR修正差: {x['adj_diff']:+.3f}")
            print(f"     预测: {fav_name}队不赢（历史准确率近期约83%）")

    return found


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='澳门分歧信号分析工具')
    parser.add_argument('--check',   type=int, metavar='MATCH_ID', help='分析单场比赛')
    parser.add_argument('--backtest',action='store_true',          help='历史回测')
    parser.add_argument('--verbose', action='store_true',          help='回测时显示详细列表')
    parser.add_argument('--scan',    action='store_true',          help='扫描近期未完成比赛')
    parser.add_argument('--days',    type=int, default=3,          help='扫描未来N天（默认3）')
    args = parser.parse_args()

    if args.check:
        check_single(args.check)
    elif args.backtest:
        backtest(verbose=args.verbose)
    elif args.scan:
        scan_upcoming(days_ahead=args.days)
    else:
        print(__doc__)
        print("示例：")
        print("  python macau_divergence_signal.py --check 2814925")
        print("  python macau_divergence_signal.py --backtest")
        print("  python macau_divergence_signal.py --backtest --verbose")
        print("  python macau_divergence_signal.py --scan")
