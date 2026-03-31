"""
澳门+马会双向信号验证器
======================
核心假设：
  当市场（百家均值）大幅向某热门方向移动，
  但澳门（80）和马会（432）在RR修正后仍不看好该热门，
  该热门不赢（draw or lose）的概率高达 ~90%。

关键指标定义：
  adj_diff = 澳门实际赔率 - 百家均值赔率 × (澳门RR / 百家RR)
           > 0 表示澳门扣除自身更高的抽水后，仍比百家更不看好热门
  hkjc_adj = 马会实际赔率 - 百家均值赔率 × (马会RR / 百家RR)
           > 0 表示马会也不看好热门（与澳门同向）
  avg_move = 百家开盘赔率 - 百家即时赔率
           > 0 表示市场在向热门方向移动（赔率降低=更看好）

触发条件（Black Signal）：
  1. 热门方赔率在 2.1-2.5 区间
  2. avg_move > 0.10（市场大幅移向热门）
  3. adj_diff > 0.10（澳门RR修正后仍不看好）
  4. hkjc_adj > 0.05（马会同向，也不看好热门）
  结论：热门不赢率约 91.7%

用法：
  python macau_hkjc_signal_validator.py [match_id]
  python macau_hkjc_signal_validator.py --backtest
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_connection
from collections import defaultdict

# ==================== 参数 ====================
ADJ_DIFF_THRESHOLD    = 0.10   # 澳门RR修正差值门槛
HKJC_ADJ_THRESHOLD   = 0.05   # 马会RR修正差值门槛
AVG_MOVE_THRESHOLD    = 0.10   # 市场向热门移动门槛
FAV_ODDS_LO          = 2.10   # 热门赔率区间下限
FAV_ODDS_HI          = 2.50   # 热门赔率区间上限
MIN_COMPANIES        = 5      # 参与均值计算的最少公司数

MACAU_ID = 80
HKJC_ID  = 432
# ==============================================


def _compute_avg(odds_list):
    """从list of (h,d,a)计算均值及返还率"""
    n = len(odds_list)
    if n == 0:
        return None
    ah = sum(x[0] for x in odds_list) / n
    ad = sum(x[1] for x in odds_list) / n
    aa = sum(x[2] for x in odds_list) / n
    rr = 100 / (1/ah + 1/ad + 1/aa)
    return ah, ad, aa, rr


def analyze_match(match_id, db=None):
    """
    对单场比赛计算信号强度。
    返回 dict，含 signal_hit(bool), adj_diff, hkjc_adj, avg_move, avg_fav, fav_side 等。
    """
    close_db = False
    if db is None:
        db = get_connection()
        close_db = True

    # 拉澳门
    mac_row = db.execute_query(
        'SELECT current_home, current_draw, current_away, initial_home, initial_away, current_return_rate '
        'FROM european_odds WHERE match_id=%s AND company_id=%s',
        (match_id, MACAU_ID), fetch='one'
    )
    if not mac_row or not mac_row.get('current_home'):
        return None

    # 拉马会
    hkjc_row = db.execute_query(
        'SELECT current_home, current_draw, current_away, current_return_rate '
        'FROM european_odds WHERE match_id=%s AND company_id=%s',
        (match_id, HKJC_ID), fetch='one'
    )

    # 拉其他公司即时和开盘
    others = db.execute_query(
        'SELECT current_home, current_draw, current_away, initial_home, initial_away '
        'FROM european_odds WHERE match_id=%s AND company_id NOT IN (0,%s,%s) '
        'AND current_home>1.0 AND initial_home>1.0',
        (match_id, MACAU_ID, HKJC_ID), fetch='all'
    )
    if len(others) < MIN_COMPANIES:
        return None

    cur_list = [(float(o['current_home']), float(o['current_draw']), float(o['current_away'])) for o in others]
    ini_list = [(float(o['initial_home']), float(o['initial_away'])) for o in others]

    ref_cur = _compute_avg(cur_list)
    if ref_cur is None:
        return None
    c_ah, c_ad, c_aa, avg_rr = ref_cur

    ni = len(ini_list)
    i_ah = sum(x[0] for x in ini_list) / ni
    i_aa = sum(x[1] for x in ini_list) / ni

    if c_ad <= c_ah and c_ad <= c_aa:  # 平局是热门，跳过
        return None

    mch = float(mac_row['current_home'])
    mca = float(mac_row['current_away'])
    mih = float(mac_row['initial_home'])
    mia = float(mac_row['initial_away'])
    mac_rr = float(mac_row['current_return_rate']) if mac_row['current_return_rate'] else 88.0
    rr_ratio = mac_rr / avg_rr

    if c_ah <= c_aa:
        fav_side = 'home'
        avg_fav = c_ah
        avg_move = i_ah - c_ah
        adj_diff = mch - c_ah * rr_ratio
        mac_fav_odds = mch
        hkjc_fav_odds = float(hkjc_row['current_home']) if hkjc_row else None
    else:
        fav_side = 'away'
        avg_fav = c_aa
        avg_move = i_aa - c_aa
        adj_diff = mca - c_aa * rr_ratio
        mac_fav_odds = mca
        hkjc_fav_odds = float(hkjc_row['current_away']) if hkjc_row else None

    hkjc_adj = None
    if hkjc_row and hkjc_fav_odds:
        hkjc_rr = float(hkjc_row['current_return_rate']) if hkjc_row['current_return_rate'] else 88.0
        hkjc_adj = hkjc_fav_odds - avg_fav * (hkjc_rr / avg_rr)

    # 信号触发检查
    signal_triggered = (
        FAV_ODDS_LO <= avg_fav < FAV_ODDS_HI
        and avg_move > AVG_MOVE_THRESHOLD
        and adj_diff > ADJ_DIFF_THRESHOLD
        and hkjc_adj is not None
        and hkjc_adj > HKJC_ADJ_THRESHOLD
    )

    result = {
        'match_id':         match_id,
        'fav_side':         fav_side,
        'avg_fav':          round(avg_fav, 3),
        'avg_move':         round(avg_move, 3),
        'mac_fav_odds':     round(mac_fav_odds, 3),
        'hkjc_fav_odds':    round(hkjc_fav_odds, 3) if hkjc_fav_odds else None,
        'adj_diff':         round(adj_diff, 3),
        'hkjc_adj':         round(hkjc_adj, 3) if hkjc_adj is not None else None,
        'avg_rr':           round(avg_rr, 2),
        'mac_rr':           round(mac_rr, 2),
        'signal_triggered': signal_triggered,
        'n_companies':      len(others),
    }

    if close_db:
        pass  # pool自动回收
    return result


def backtest(limit=12000):
    """对所有已完成比赛做回测"""
    db = get_connection()

    rows = db.execute_query('''
        SELECT m.match_id, m.home_score, m.away_score, m.league_id,
               mo.current_home, mo.current_draw, mo.current_away,
               mo.initial_home, mo.initial_away, mo.current_return_rate
        FROM matches m
        JOIN european_odds mo ON m.match_id = mo.match_id AND mo.company_id = %s
        WHERE m.match_status = 'finished' AND m.home_score IS NOT NULL
          AND mo.current_home > 1.0 AND mo.initial_home > 1.0
        LIMIT %s
    ''', (MACAU_ID, limit), fetch='all')

    match_ids = [r['match_id'] for r in rows]
    ph = ','.join(['%s'] * len(match_ids))

    all_o = db.execute_query(f'''
        SELECT match_id, company_id, current_home, current_draw, current_away,
               initial_home, initial_away, current_return_rate
        FROM european_odds WHERE match_id IN ({ph})
          AND company_id NOT IN (0) AND current_home > 1.0 AND initial_home > 1.0
    ''', match_ids, fetch='all')

    cur_map = defaultdict(list); ini_map = defaultdict(list); hkjc_map = {}
    for o in all_o:
        mid = o['match_id']; cid = o['company_id']
        ch = float(o['current_home']); cd = float(o['current_draw']); ca = float(o['current_away'])
        ih = float(o['initial_home']); ia = float(o['initial_away'])
        rr = float(o['current_return_rate']) if o['current_return_rate'] else 88.0
        if cid == HKJC_ID:
            hkjc_map[mid] = {'h': ch, 'd': cd, 'a': ca, 'rr': rr}
        if cid != MACAU_ID:
            cur_map[mid].append((ch, cd, ca))
            ini_map[mid].append((ih, ia))

    triggered = []
    for r in rows:
        mid = r['match_id']
        cl = cur_map.get(mid, []); il = ini_map.get(mid, [])
        if len(cl) < MIN_COMPANIES or len(il) < MIN_COMPANIES:
            continue

        ref = _compute_avg(cl)
        if ref is None:
            continue
        c_ah, c_ad, c_aa, avg_rr = ref

        ni = len(il)
        i_ah = sum(x[0] for x in il) / ni
        i_aa = sum(x[1] for x in il) / ni

        mch = float(r['current_home']); mca = float(r['current_away'])
        mih = float(r['initial_home']); mia = float(r['initial_away'])
        mac_rr = float(r['current_return_rate']) if r['current_return_rate'] else 88.0

        if c_ad <= c_ah and c_ad <= c_aa:
            continue
        rr_ratio = mac_rr / avg_rr

        if c_ah <= c_aa:
            fav_side = 'home'; avg_fav = c_ah; avg_move = i_ah - c_ah
            adj_diff = mch - c_ah * rr_ratio
            hkjc = hkjc_map.get(mid); hkjc_fav = hkjc['h'] if hkjc else None
            hkjc_rr = hkjc['rr'] if hkjc else None
            fav_failed = r['home_score'] <= r['away_score']
        else:
            fav_side = 'away'; avg_fav = c_aa; avg_move = i_aa - c_aa
            adj_diff = mca - c_aa * rr_ratio
            hkjc = hkjc_map.get(mid); hkjc_fav = hkjc['a'] if hkjc else None
            hkjc_rr = hkjc['rr'] if hkjc else None
            fav_failed = r['away_score'] <= r['home_score']

        if hkjc_fav and hkjc_rr:
            hkjc_adj = hkjc_fav - avg_fav * (hkjc_rr / avg_rr)
        else:
            continue  # 无马会数据，跳过

        if not (FAV_ODDS_LO <= avg_fav < FAV_ODDS_HI):
            continue
        if not (avg_move > AVG_MOVE_THRESHOLD and adj_diff > ADJ_DIFF_THRESHOLD and hkjc_adj > HKJC_ADJ_THRESHOLD):
            continue

        triggered.append({
            'match_id': mid, 'fav_side': fav_side, 'avg_fav': avg_fav,
            'avg_move': avg_move, 'adj_diff': adj_diff, 'hkjc_adj': hkjc_adj,
            'fav_failed': fav_failed, 'league_id': r['league_id'],
            'score': f"{r['home_score']}-{r['away_score']}"
        })

    print(f"\n{'='*60}")
    print(f"  澳门+马会双向信号 回测结果")
    print(f"{'='*60}")
    print(f"  条件: adj_diff>{ADJ_DIFF_THRESHOLD}  hkjc_adj>{HKJC_ADJ_THRESHOLD}  avg_move>{AVG_MOVE_THRESHOLD}")
    print(f"  赔率范围: {FAV_ODDS_LO}-{FAV_ODDS_HI}")
    print(f"  总触发场次: {len(triggered)}")
    if triggered:
        hits = sum(1 for x in triggered if x['fav_failed'])
        print(f"  热门不赢次数: {hits}")
        print(f"  准确率: {hits/len(triggered)*100:.1f}%")
        print()
        print("  触发的比赛详情：")
        for x in triggered:
            status = "✓命中" if x['fav_failed'] else "✗未中"
            print(f"    {x['match_id']}  {x['fav_side']}热门{x['avg_fav']:.2f}"
                  f"  移{x['avg_move']:+.2f}  adj={x['adj_diff']:.2f}  hk={x['hkjc_adj']:.2f}"
                  f"  比分:{x['score']}  {status}")

    return triggered


def check_single(match_id):
    db = get_connection()
    match = db.execute_query(
        'SELECT home_team_name, away_team_name, match_time, home_score, away_score, match_status '
        'FROM matches WHERE match_id=%s', (match_id,), fetch='one'
    )
    if match:
        print(f"\n比赛: {match['home_team_name']} vs {match['away_team_name']}")
        print(f"时间: {match['match_time']}  状态: {match['match_status']}  "
              f"比分: {match['home_score']}-{match['away_score']}")

    result = analyze_match(match_id, db)
    if result is None:
        print("无法分析（缺少澳门或公司数据）")
        return

    print(f"\n--- 信号分析 ---")
    print(f"热门方: {'主队' if result['fav_side']=='home' else '客队'}  均值赔率: {result['avg_fav']}")
    print(f"百家平均RR: {result['avg_rr']}%  澳门RR: {result['mac_rr']}%")
    print(f"市场移动(avg_move): {result['avg_move']:+.3f}  {'↑市场更看好热门' if result['avg_move']>0 else '↓市场更不看好热门'}")
    print(f"澳门RR修正差(adj_diff): {result['adj_diff']:+.3f}  {'→澳门不看好热门' if result['adj_diff']>0 else '→澳门看好热门'}")
    hkjc_str = f"{result['hkjc_adj']:+.3f}" if result['hkjc_adj'] is not None else 'N/A'
    hkjc_dir = '→马会不看好热门' if result['hkjc_adj'] and result['hkjc_adj'] > 0 else '→马会看好热门/无数据'
    print(f"马会RR修正差(hkjc_adj): {hkjc_str}  {hkjc_dir}")
    print(f"\n{'🔴 信号触发！热门不赢率 ~91.7%' if result['signal_triggered'] else '⚪ 未触发信号'}")


if __name__ == '__main__':
    if len(sys.argv) > 1:
        if sys.argv[1] == '--backtest':
            backtest()
        else:
            check_single(int(sys.argv[1]))
    else:
        print(__doc__)
        print("\n运行回测: python macau_hkjc_signal_validator.py --backtest")
        print("单场分析: python macau_hkjc_signal_validator.py <match_id>")
        print("\n示例: python macau_hkjc_signal_validator.py 2814925")
