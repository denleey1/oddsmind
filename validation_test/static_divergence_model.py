#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
静态博弈模型 —— 只用初终两点，挖掘机构"不同步"信号
Static Game Theory Model: Two-Point Divergence Analysis

核心三差值：
  Gap_Opening  = 机构初赔 - 全市场均值初赔  （初盘态度）
  Gap_Closing  = 机构终赔 - 全市场均值终赔  （终盘态度）
  Internal_Move= 机构终赔 - 机构初赔        （机构自身变动）
  External_Move= 市场均值终赔 - 市场均值初赔  （市场整体变动）
  Relative_Move= Internal_Move - External_Move （背离度）

五大分析维度：
  维度1：形态差 / 行为标签（纹丝不动 / 降幅不足 / 逆势而行）
  维度2：初终偏离度矩阵（A先知 / B引诱 / C后觉 / D孤傲）
  维度3：返还率收缩压（临场抽水变狠=巨大赔付压力）
  维度4：最敏锐机构识别（爆冷场次中谁升赔幅度最大）
  维度5：复合筛选器（下盘陷阱 + 稳胆防御）
"""

import sys, os, statistics, json
from pathlib import Path
from collections import defaultdict
from datetime import datetime

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymysql
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / "oddsmind.env")


def get_db():
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "oddsmind"),
        port=int(os.getenv("MYSQL_PORT", 3306)),
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )


def result_of(hs, as_):
    if hs is None or as_ is None: return None
    return 'home' if hs > as_ else ('draw' if hs == as_ else 'away')


# 全样本自然概率
NATURAL = {'home': 0.431, 'draw': 0.259, 'away': 0.307}
NATURAL_NOT = {'home': 0.569, 'draw': 0.741, 'away': 0.693}
NAT_FAV_FAIL = 0.485    # 热门翻车基础率
NAT_FAV_WIN  = 0.515    # 热门胜出基础率（但按实际计，约51.5%）


def print_rule(label, n, hit, base, mode='not_out'):
    if n < 10:
        return 0
    rate = hit / n
    lift = rate - base
    mk = " ✦✦" if lift > 0.10 else (" ✦" if lift > 0.05 else (" →" if lift > 0.02 else " ⚠️"))
    print(f"  {label:<52} n={n:>5}  命中={rate:.1%}  基础={base:.1%}  提升={lift:>+.1%}{mk}")
    return lift


# ══════════════════════════════════════════════════════════
# 数据加载：全市场 + 关注机构
# ══════════════════════════════════════════════════════════

def load_all_data(db):
    """
    加载两份数据：
    1. 全市场每场比赛的均值初赔/终赔（用于计算背离度）
    2. 关注机构的初赔/终赔（澳门80、皇冠545、HKJC432、SNAI110、Pinnacle177）
    """
    # ── 全市场均值（只取有效赔率的公司）──────────────────
    sql_market = """
        SELECT
            match_id,
            AVG(initial_home)        AS avg_init_home,
            AVG(initial_draw)        AS avg_init_draw,
            AVG(initial_away)        AS avg_init_away,
            AVG(current_home)        AS avg_curr_home,
            AVG(current_draw)        AS avg_curr_draw,
            AVG(current_away)        AS avg_curr_away,
            AVG(initial_return_rate) AS avg_init_rr,
            AVG(current_return_rate) AS avg_curr_rr,
            STDDEV(current_home)     AS std_home,
            COUNT(DISTINCT company_id) AS n_companies
        FROM european_odds
        WHERE odds_type = '1x2'
          AND initial_home > 1 AND current_home > 1
          AND initial_home IS NOT NULL AND current_home IS NOT NULL
        GROUP BY match_id
        HAVING n_companies >= 10
    """
    with db.cursor() as c:
        c.execute(sql_market)
        mkt_rows = c.fetchall()
    market = {r['match_id']: r for r in mkt_rows}

    # ── 关注机构 ──────────────────────────────────────────
    FOCUS_CIDS = [80, 545, 432, 110, 177]
    ph = ",".join(["%s"] * len(FOCUS_CIDS))
    sql_focus = f"""
        SELECT eo.match_id, eo.company_id,
               eo.initial_home, eo.initial_draw, eo.initial_away,
               eo.current_home, eo.current_draw, eo.current_away,
               eo.initial_return_rate, eo.current_return_rate,
               m.home_score, m.away_score, m.match_time, m.league_id
        FROM european_odds eo
        JOIN matches m ON m.match_id = eo.match_id
        WHERE eo.company_id IN ({ph})
          AND eo.odds_type = '1x2'
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND eo.initial_home > 1 AND eo.current_home > 1
          AND eo.initial_home IS NOT NULL AND eo.current_home IS NOT NULL
    """
    with db.cursor() as c:
        c.execute(sql_focus, FOCUS_CIDS)
        focus_rows = c.fetchall()

    focus = defaultdict(dict)
    match_meta = {}
    for r in focus_rows:
        mid = r['match_id']
        focus[mid][r['company_id']] = r
        match_meta[mid] = {'hs': r['home_score'], 'as': r['away_score'],
                           'time': r['match_time'], 'lid': r['league_id']}

    # 只保留同时有市场数据和关注机构数据的比赛
    valid_mids = set(market.keys()) & set(focus.keys())
    print(f"  全市场数据: {len(market)} 场  关注机构数据: {len(focus)} 场")
    print(f"  有效交集:   {len(valid_mids)} 场")

    return market, focus, match_meta, valid_mids


# ══════════════════════════════════════════════════════════
# 核心：计算三差值
# ══════════════════════════════════════════════════════════

def compute_gaps(mkt, company_row, side):
    """
    side: 'home' / 'draw' / 'away'
    返回:
      gap_open    = company_init - market_init  （负=机构初赔低于市场）
      gap_close   = company_curr - market_curr  （负=机构终赔低于市场）
      internal_mv = company_curr - company_init （负=机构自身降赔）
      external_mv = market_curr - market_init   （负=市场整体降赔）
      relative_mv = internal_mv - external_mv   （正=机构降幅小于市场 → 相对升赔）
    """
    fmap = {'home': ('initial_home', 'current_home', 'avg_init_home', 'avg_curr_home'),
            'draw': ('initial_draw', 'current_draw', 'avg_init_draw', 'avg_curr_draw'),
            'away': ('initial_away', 'current_away', 'avg_init_away', 'avg_curr_away')}
    ci, cc, mi, mc = fmap[side]
    try:
        c_i = float(company_row[ci])
        c_c = float(company_row[cc])
        m_i = float(mkt[mi])
        m_c = float(mkt[mc])
        return {
            'gap_open':    c_i - m_i,
            'gap_close':   c_c - m_c,
            'internal_mv': c_c - c_i,
            'external_mv': m_c - m_i,
            'relative_mv': (c_c - c_i) - (m_c - m_i),
            'c_i': c_i, 'c_c': c_c, 'm_i': m_i, 'm_c': m_c,
        }
    except:
        return None


# ══════════════════════════════════════════════════════════
# 维度1：行为标签分析
# ══════════════════════════════════════════════════════════

def analyze_behavior_labels(market, focus, match_meta, valid_mids):
    print("\n" + "═"*74)
    print("【维度1】行为标签分析")
    print("  纹丝不动: 机构终赔=初赔，但市场均值大幅变动(>0.10)")
    print("  降幅不足: 市场降赔0.10+，机构只降0.03以内(相对升赔)")
    print("  逆势而行: 市场降赔，机构不降反升")
    print("═"*74)

    FOCUS_INFO = {80: "澳门", 545: "皇冠", 432: "HKJC", 110: "SNAI", 177: "Pinnacle"}

    labels = {
        'static_anchor':   "纹丝不动(市场大动≥0.10，机构不动≤0.02)",
        'lag_behind':      "降幅不足(市场降≥0.08，机构降<0.03)",
        'counter_move':    "逆势而行(市场降≥0.05，机构不降反升≥0.02)",
        'follow_lead':     "同步跟随(方向一致，幅度相近)",
    }

    results = {}
    for cid, cname in FOCUS_INFO.items():
        stats = {lbl: {'n': 0, 'hit_not': defaultdict(int), 'total': defaultdict(int)}
                 for lbl in labels}

        for mid in valid_mids:
            mkt = market[mid]
            crow = focus[mid].get(cid)
            if not crow: continue
            res = result_of(match_meta[mid]['hs'], match_meta[mid]['as'])
            if res is None: continue

            for side in ['home', 'draw', 'away']:
                g = compute_gaps(mkt, crow, side)
                if g is None: continue

                ext = g['external_mv']
                rel = g['relative_mv']
                int_mv = g['internal_mv']

                if abs(ext) >= 0.10 and abs(int_mv) <= 0.02:
                    lbl = 'static_anchor'
                elif ext <= -0.08 and int_mv > -0.03:
                    lbl = 'lag_behind'
                elif ext <= -0.05 and int_mv >= 0.02:
                    lbl = 'counter_move'
                else:
                    lbl = 'follow_lead'

                stats[lbl]['n'] += 1
                stats[lbl]['total'][side] += 1
                if res != side:
                    stats[lbl]['hit_not'][side] += 1

        print(f"\n  ── {cname} ──")
        for lbl, desc in labels.items():
            st = stats[lbl]
            n = st['n']
            if n < 10: continue
            hit = sum(st['hit_not'].values())
            # 加权自然不出率
            total_sides = sum(st['total'].values())
            wbase = sum(st['total'][s] * NATURAL_NOT[s] for s in ['home','draw','away']) / total_sides if total_sides else 0
            print_rule(f"[{desc}]", n, hit, wbase)

        results[cid] = stats

    return results


# ══════════════════════════════════════════════════════════
# 维度2：初终偏离度矩阵（四象限）
# ══════════════════════════════════════════════════════════

def analyze_quadrant_matrix(market, focus, match_meta, valid_mids):
    print("\n" + "═"*74)
    print("【维度2】初终偏离度矩阵（四象限）——以赔率差值定性机构行为")
    print("  A象限「先知型」: 初赔<均值 且 终赔<均值(始终防守)→ 该向稳")
    print("  B象限「引诱型」: 初赔<均值 但 终赔>均值(开场防守,临场放弃)→ 下盘")
    print("  C象限「后觉型」: 初赔>均值 但 终赔≈均值(被市场打服)→ 参考有限")
    print("  D象限「孤傲型」: 初赔>均值 且 终赔>均值(始终高赔,不认可)→ 该向不出")
    print("═"*74)

    THRESHOLD = 0.05   # 偏离阈值（赔率）

    FOCUS_INFO = {80: "澳门", 545: "皇冠", 432: "HKJC", 110: "SNAI"}

    all_results = {}

    for cid, cname in FOCUS_INFO.items():
        quads = {q: {'n':0, 'hit':0, 'side_cnt': defaultdict(int)}
                 for q in ['A','B','C','D','neutral']}

        for mid in valid_mids:
            mkt = market[mid]
            crow = focus[mid].get(cid)
            if not crow: continue
            res = result_of(match_meta[mid]['hs'], match_meta[mid]['as'])
            if res is None: continue

            for side in ['home', 'draw', 'away']:
                g = compute_gaps(mkt, crow, side)
                if g is None: continue

                go = g['gap_open']    # 初盘态度（负=低于市场=防守）
                gc = g['gap_close']   # 终盘态度（负=低于市场=防守）

                if go < -THRESHOLD and gc < -THRESHOLD:
                    q = 'A'   # 先知：全程防守（低赔）→ 该向通常跑出
                elif go < -THRESHOLD and gc > THRESHOLD:
                    q = 'B'   # 引诱：从防守到放弃 → 该向下盘
                elif go > THRESHOLD and abs(gc) <= THRESHOLD:
                    q = 'C'   # 后觉：初赔高被打回来
                elif go > THRESHOLD and gc > THRESHOLD:
                    q = 'D'   # 孤傲：全程不认可 → 该向不出
                else:
                    q = 'neutral'

                quads[q]['n'] += 1
                quads[q]['side_cnt'][side] += 1
                if res != side:
                    quads[q]['hit'] += 1

        print(f"\n  ── {cname} (阈值±{THRESHOLD}) ──")
        q_labels = {
            'A': ('先知型：全程低赔(初终<均值)    → 该向跑出率', 'hit'),
            'B': ('引诱型：初低终高              → 该向不出率', 'not'),
            'C': ('后觉型：初高终平              → 该向不出率', 'not'),
            'D': ('孤傲型：全程高赔(初终>均值)    → 该向不出率', 'not'),
        }
        for q, (desc, mode) in q_labels.items():
            st = quads[q]
            n  = st['n']
            if n < 10: continue
            total_sides = sum(st['side_cnt'].values())
            if total_sides == 0: continue
            wbase_not = sum(st['side_cnt'][s]*NATURAL_NOT[s] for s in ['home','draw','away']) / total_sides
            wbase_win = 1 - wbase_not
            if mode == 'hit':   # 先知：统计该向跑出率
                hit = n - st['hit']   # hit=不出，n-hit=出
                base = wbase_win
            else:               # 其他：统计该向不出率
                hit = st['hit']
                base = wbase_not
            print_rule(f"[{q}] {desc}", n, hit, base)

        all_results[cid] = quads

    return all_results


# ══════════════════════════════════════════════════════════
# 维度3：返还率收缩压
# ══════════════════════════════════════════════════════════

def analyze_margin_compression(market, focus, match_meta, valid_mids):
    print("\n" + "═"*74)
    print("【维度3】返还率收缩压——临场抽水变化揭示赔付压力")
    print("  收缩：机构终盘返还率 < 初盘返还率（整体压价止损）")
    print("  膨胀：机构终盘返还率 > 初盘返还率（引流，赔付增加）")
    print("═"*74)

    FOCUS_INFO = {80: "澳门", 545: "皇冠", 432: "HKJC", 110: "SNAI"}

    for cid, cname in FOCUS_INFO.items():
        # 收缩场次：终返还率 < 初返还率 - 0.5%
        shrink = {'n':0, 'results': []}
        # 膨胀场次：终返还率 > 初返还率 + 0.5%
        expand = {'n':0, 'results': []}
        # 稳定场次：返还率不变
        stable = {'n':0, 'results': []}

        for mid in valid_mids:
            crow = focus[mid].get(cid)
            if not crow: continue
            res = result_of(match_meta[mid]['hs'], match_meta[mid]['as'])
            if res is None: continue

            try:
                init_rr = float(crow['initial_return_rate'])
                curr_rr = float(crow['current_return_rate'])
                if init_rr <= 0 or curr_rr <= 0: continue
                delta_rr = curr_rr - init_rr
            except:
                continue

            if delta_rr < -0.5:
                shrink['n'] += 1
                shrink['results'].append(res)
            elif delta_rr > 0.5:
                expand['n'] += 1
                expand['results'].append(res)
            else:
                stable['n'] += 1
                stable['results'].append(res)

        print(f"\n  ── {cname} ──")
        for bucket, label in [
            (shrink, "收缩(终返还率<初-0.5%，止损压价)"),
            (expand, "膨胀(终返还率>初+0.5%，引流)"),
            (stable, "稳定(返还率不变)"),
        ]:
            n = bucket['n']
            rs = bucket['results']
            if n < 10: continue
            h_rate = sum(1 for r in rs if r=='home') / n
            d_rate = sum(1 for r in rs if r=='draw') / n
            a_rate = sum(1 for r in rs if r=='away') / n
            print(f"  [{label}] n={n}")
            print(f"    主赢={h_rate:.1%}(基础{NATURAL['home']:.1%},提升{h_rate-NATURAL['home']:+.1%})  "
                  f"平={d_rate:.1%}(基础{NATURAL['draw']:.1%},提升{d_rate-NATURAL['draw']:+.1%})  "
                  f"客赢={a_rate:.1%}(基础{NATURAL['away']:.1%},提升{a_rate-NATURAL['away']:+.1%})")


# ══════════════════════════════════════════════════════════
# 维度4：最敏锐机构识别
# ══════════════════════════════════════════════════════════

def analyze_upset_sensitivity(market, focus, match_meta, valid_mids):
    print("\n" + "═"*74)
    print("【维度4】最敏锐机构识别——爆冷场次中，谁的终赔相对初赔升幅最大？")
    print("  爆冷定义：市场热门(市场均值最低赔率方向)最终未出")
    print("  指标：爆冷场次中，机构终赔/初赔的平均升幅排名")
    print("═"*74)

    FOCUS_INFO = {80: "澳门", 545: "皇冠", 432: "HKJC", 110: "SNAI", 177: "Pinnacle"}

    upset_data = {cid: {'upset_rel_moves': [], 'normal_rel_moves': []}
                  for cid in FOCUS_INFO}

    for mid in valid_mids:
        mkt = market[mid]
        res = result_of(match_meta[mid]['hs'], match_meta[mid]['as'])
        if res is None: continue

        # 市场热门方向（均值赔率最低）
        fav_side = min(['home','draw','away'],
                       key=lambda s: float(mkt.get(f'avg_curr_{s}', 999) or 999))
        is_upset = (res != fav_side)

        for cid in FOCUS_INFO:
            crow = focus[mid].get(cid)
            if not crow: continue
            g = compute_gaps(mkt, crow, fav_side)
            if g is None: continue
            # 相对变动：机构在热门方向的Internal_Move - External_Move
            rel = g['relative_mv']
            if is_upset:
                upset_data[cid]['upset_rel_moves'].append(rel)
            else:
                upset_data[cid]['normal_rel_moves'].append(rel)

    print(f"\n  {'机构':<12} {'爆冷场次':>8} {'爆冷相对升赔均值':>16} {'正常场次':>8} {'正常相对升赔均值':>16} {'区分度':>8}")
    print("─"*74)

    sensitivity_scores = []
    for cid, name in FOCUS_INFO.items():
        ud = upset_data[cid]
        upsets = ud['upset_rel_moves']
        normals = ud['normal_rel_moves']
        if len(upsets) < 20 or len(normals) < 20: continue
        avg_up = sum(upsets) / len(upsets)
        avg_no = sum(normals) / len(normals)
        # 区分度：爆冷时相对升赔比正常时多多少
        diff = avg_up - avg_no
        sensitivity_scores.append((diff, cid, name, len(upsets), avg_up, len(normals), avg_no))

    sensitivity_scores.sort(key=lambda x: -x[0])
    for diff, cid, name, n_up, avg_up, n_no, avg_no in sensitivity_scores:
        marker = " ← 最敏锐" if diff == sensitivity_scores[0][0] else ""
        print(f"  {name:<12} {n_up:>8}  {avg_up:>+15.4f}  {n_no:>8}  {avg_no:>+15.4f}  {diff:>+7.4f}{marker}")


# ══════════════════════════════════════════════════════════
# 维度5：复合筛选器
# ══════════════════════════════════════════════════════════

def analyze_composite_filters(market, focus, match_meta, valid_mids):
    print("\n" + "═"*74)
    print("【维度5】复合筛选器")
    print("  [下盘陷阱] 强队赔率1.5-1.9 + 市场降赔 + 澳门Gap_Close>0.03 + 澳门从低转高")
    print("  [稳胆防御] Gap_Close<-0.05 + 澳门纹丝不动 + 即使市场逆风也不动")
    print("  [背离捕捉] Gap_Closing>0.03 且 External_Move<-0.05（市场降，澳门不跟）")
    print("═"*74)

    trap_records = []      # 下盘陷阱
    defense_records = []   # 稳胆防御
    diverge_records = []   # 背离捕捉

    for mid in valid_mids:
        mkt = market[mid]
        macao = focus[mid].get(80)
        if not macao: continue
        res = result_of(match_meta[mid]['hs'], match_meta[mid]['as'])
        if res is None: continue

        for side in ['home', 'draw', 'away']:
            g = compute_gaps(mkt, macao, side)
            if g is None: continue

            go  = g['gap_open']
            gc  = g['gap_close']
            im  = g['internal_mv']
            em  = g['external_mv']
            rm  = g['relative_mv']
            avg_curr = g['m_c']

            # ── 下盘陷阱 ──────────────────────────────────
            # 条件1：该方向是强队赔率区（1.5-1.9）
            # 条件2：市场在降赔（em < -0.05，市场热捧）
            # 条件3：澳门终赔高于市场（gc > 0.03，澳门不认可）
            # 条件4：澳门从看好变为不看好（go < 0 但 gc > 0，引诱型B象限变体）
            if (1.50 <= avg_curr <= 1.90 and
                em < -0.05 and
                gc > 0.03 and
                go < 0.02 and gc > go + 0.04):
                trap_records.append({'side': side, 'result': res})

            # ── 稳胆防御 ──────────────────────────────────
            # 条件1：澳门终赔低于市场（gc < -0.05，澳门看好该方向）
            # 条件2：澳门纹丝不动（|im| <= 0.02）
            # 条件3：市场在上升（em > 0.03，市场遇冷，但澳门无视）
            if (gc < -0.05 and
                abs(im) <= 0.02 and
                em > 0.03):
                defense_records.append({'side': side, 'result': res})

            # ── 背离捕捉 ──────────────────────────────────
            # 市场大幅降赔（热捧某方向）但澳门不跟（相对升赔）
            # 最强形式：em < -0.08 且 rm > 0.05（背离度大）
            if em < -0.08 and rm > 0.05:
                diverge_records.append({'side': side, 'result': res, 'rm': rm})

    print(f"\n  [下盘陷阱] 条件：强队1.5-1.9 + 市场热捧 + 澳门反向高赔 + 从看好到不看好")
    n = len(trap_records)
    if n >= 10:
        # 陷阱侧不出（被引诱方向不出）
        hit = sum(1 for r in trap_records if r['result'] != r['side'])
        side_cnt = defaultdict(int)
        for r in trap_records: side_cnt[r['side']] += 1
        wbase = sum(side_cnt[s]*NATURAL_NOT[s] for s in ['home','draw','away']) / n
        print_rule("  强队陷阱→该向不出率", n, hit, wbase)
    else:
        print(f"  样本不足 (n={n})")

    print(f"\n  [稳胆防御] 条件：澳门终赔<市场-5% + 澳门不动 + 市场遇冷无视")
    n = len(defense_records)
    if n >= 10:
        hit = sum(1 for r in defense_records if r['result'] == r['side'])
        side_cnt = defaultdict(int)
        for r in defense_records: side_cnt[r['side']] += 1
        wbase = sum(side_cnt[s]*NATURAL[s] for s in ['home','draw','away']) / n
        print_rule("  稳胆防御→该向跑出率", n, hit, wbase, 'win')
    else:
        print(f"  样本不足 (n={n})")

    print(f"\n  [背离捕捉] 条件：市场降赔≥0.08 + 澳门相对升赔≥0.05")
    n = len(diverge_records)
    if n >= 10:
        hit = sum(1 for r in diverge_records if r['result'] != r['side'])
        side_cnt = defaultdict(int)
        for r in diverge_records: side_cnt[r['side']] += 1
        wbase = sum(side_cnt[s]*NATURAL_NOT[s] for s in ['home','draw','away']) / n
        print_rule("  背离→被市场热捧方向不出率", n, hit, wbase)

        # 按背离幅度细分
        print(f"\n  背离幅度细分（Relative_Move区间）：")
        for lo, hi, label in [(0.05, 0.10, "0.05-0.10"), (0.10, 0.15, "0.10-0.15"), (0.15, 99, "0.15+")]:
            sub = [r for r in diverge_records if lo <= r['rm'] < hi]
            ns = len(sub)
            if ns < 5: continue
            hs = sum(1 for r in sub if r['result'] != r['side'])
            rs = hs/ns
            sc = defaultdict(int)
            for r in sub: sc[r['side']] += 1
            wb = sum(sc[s]*NATURAL_NOT[s] for s in ['home','draw','away']) / ns if ns else 0
            print_rule(f"    背离幅度{label}", ns, hs, wb)
    else:
        print(f"  样本不足 (n={n})")


# ══════════════════════════════════════════════════════════
# 补充：Gap_Close > 0.03 的全量统计（按机构+Side）
# ══════════════════════════════════════════════════════════

def analyze_gap_close_ranking(market, focus, match_meta, valid_mids):
    print("\n" + "═"*74)
    print("【补充】Gap_Close > 0.03 的不出率排行（哪家机构+方向组合最准？）")
    print("  Gap_Close = 机构终赔 - 全市场均值终赔 > 0.03")
    print("  = 机构终赔比市场高0.03 = 机构不认可该方向 → 该向不出率")
    print("═"*74)

    FOCUS_INFO = {80: "澳门", 545: "皇冠", 432: "HKJC", 110: "SNAI", 177: "Pinnacle"}

    rows = []
    for cid, cname in FOCUS_INFO.items():
        for threshold in [0.03, 0.05, 0.08]:
            n_tot, n_hit = 0, 0
            side_cnt = defaultdict(int)
            for mid in valid_mids:
                mkt = market[mid]
                crow = focus[mid].get(cid)
                if not crow: continue
                res = result_of(match_meta[mid]['hs'], match_meta[mid]['as'])
                if res is None: continue
                for side in ['home', 'draw', 'away']:
                    g = compute_gaps(mkt, crow, side)
                    if g is None: continue
                    if g['gap_close'] > threshold:
                        n_tot += 1
                        side_cnt[side] += 1
                        if res != side: n_hit += 1

            if n_tot < 15: continue
            wbase = sum(side_cnt[s]*NATURAL_NOT[s] for s in ['home','draw','away']) / n_tot
            rate = n_hit / n_tot
            lift = rate - wbase
            rows.append((lift, cname, threshold, n_tot, rate, wbase))

    rows.sort(key=lambda x: -x[0])
    print(f"\n  {'机构':<12} {'阈值':>6} {'n':>6}  {'不出率':>8}  {'基础':>8}  {'提升':>8}")
    print("─"*60)
    for lift, cname, thr, n, rate, base in rows:
        marker = " ✦✦" if lift > 0.10 else (" ✦" if lift > 0.05 else "")
        print(f"  {cname:<12} >{thr:.2f}   {n:>5}  {rate:>7.1%}  {base:>7.1%}  {lift:>+7.1%}{marker}")


# ══════════════════════════════════════════════════════════
# 主程序
# ══════════════════════════════════════════════════════════

def main():
    print("=" * 74)
    print("  静态博弈模型 —— 初终两点背离分析")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 74)

    db = get_db()
    print("\n加载数据...")
    market, focus, match_meta, valid_mids = load_all_data(db)
    db.close()

    analyze_behavior_labels(market, focus, match_meta, valid_mids)
    analyze_quadrant_matrix(market, focus, match_meta, valid_mids)
    analyze_margin_compression(market, focus, match_meta, valid_mids)
    analyze_upset_sensitivity(market, focus, match_meta, valid_mids)
    analyze_composite_filters(market, focus, match_meta, valid_mids)
    analyze_gap_close_ranking(market, focus, match_meta, valid_mids)

    print("\n" + "="*74)
    print("分析完成。")


if __name__ == '__main__':
    main()
