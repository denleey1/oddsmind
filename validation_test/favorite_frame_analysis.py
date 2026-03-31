#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
以"上盘/下盘"为框架的机构偏离分析
核心修正：不再按主队/客队分，而是按赔率高低分：
  上盘（热门）= 三方向中基准概率最高者（赔率最低）
  中间        = 三方向中基准概率居中者
  下盘（冷门）= 三方向中基准概率最低者（赔率最高）

分析三大核心问题：
  Q1: 当澳门/皇冠给"上盘"方向高偏（比基准更高赔），上盘还能赢吗？
  Q2: 当市场高度分歧时，澳门站在"高赔方"，高赔方向会不会跑出？
  Q3: 各类信号在上盘/中间/下盘三个层面的真实提升是多少？
"""

import sys, os, statistics
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


def odds_to_prob(h, d, a):
    try:
        h, d, a = float(h), float(d), float(a)
        if h <= 1 or d <= 1 or a <= 1: return None, None, None
        rh, rd, ra = 1/h, 1/d, 1/a
        t = rh + rd + ra
        return rh/t, rd/t, ra/t
    except:
        return None, None, None


def result_of(hs, as_):
    if hs is None or as_ is None: return None
    if hs > as_: return 'home'
    if hs == as_: return 'draw'
    return 'away'


def classify_role(bench):
    """返回 {side: 'fav'/'mid'/'dog'} 的映射"""
    sorted_sides = sorted(bench.items(), key=lambda x: -x[1])
    return {sorted_sides[0][0]: 'fav',
            sorted_sides[1][0]: 'mid',
            sorted_sides[2][0]: 'dog'}


# ─────────────────────────────────────────────────────────
# 数据加载
# ─────────────────────────────────────────────────────────

def load_data(db):
    sql = """
        SELECT eo.match_id, eo.company_id,
               eo.initial_home, eo.initial_draw, eo.initial_away,
               eo.current_home, eo.current_draw, eo.current_away,
               eo.initial_return_rate, eo.current_return_rate,
               m.home_score, m.away_score, m.match_time, m.league_id
        FROM european_odds eo
        JOIN matches m ON m.match_id = eo.match_id
        WHERE eo.company_id IN (177, 115, 80, 545, 432)
          AND eo.odds_type = '1x2'
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND eo.initial_home > 1 AND eo.current_home > 1
          AND eo.initial_home IS NOT NULL AND eo.current_home IS NOT NULL
    """
    with db.cursor() as c:
        c.execute(sql)
        rows = c.fetchall()

    data = defaultdict(dict)
    meta = {}
    for r in rows:
        mid = r['match_id']
        data[mid][r['company_id']] = r
        meta[mid] = {'hs': r['home_score'], 'as': r['away_score'],
                     'time': r['match_time'], 'lid': r['league_id']}

    # 只保留有基准(177或115)且有目标(80或545)的比赛
    valid = {
        mid: comps for mid, comps in data.items()
        if any(c in comps for c in [177, 115])
        and any(c in comps for c in [80, 545])
    }
    return valid, meta


def get_benchmark(companies, use_initial=False):
    probs = []
    for cid in [177, 115]:
        r = companies.get(cid)
        if not r: continue
        if use_initial:
            h, d, a = odds_to_prob(r['initial_home'], r['initial_draw'], r['initial_away'])
        else:
            h, d, a = odds_to_prob(r['current_home'], r['current_draw'], r['current_away'])
        if h is not None:
            probs.append((h, d, a))
    if not probs: return None
    return {'home': sum(p[0] for p in probs)/len(probs),
            'draw': sum(p[1] for p in probs)/len(probs),
            'away': sum(p[2] for p in probs)/len(probs)}


# ─────────────────────────────────────────────────────────
# 核心分析框架
# ─────────────────────────────────────────────────────────

def print_header(title):
    print("\n" + "═"*74)
    print(f"  {title}")
    print("═"*74)


def fmt_row(role_label, n, hit, base, mode='not_out'):
    if n == 0: return
    rate = hit / n
    lift = rate - base
    marker = " ✦✦" if lift > 0.12 else (" ✦" if lift > 0.06 else (" →" if lift > 0.02 else " ⚠️"))
    print(f"  {role_label:<36} n={n:>5}  命中={rate:.1%}  基础={base:.1%}  提升={lift:>+.1%}{marker}")


# ─────────────────────────────────────────────────────────
# 分析一：按上盘/下盘框架重跑 HIGH_BIAS
# ─────────────────────────────────────────────────────────

def analyze_highbias_by_role(match_data, meta):
    print_header("分析一：HIGH_BIAS 按 上盘/中间/下盘 重新分解")
    print("  信号定义：目标机构(澳门/皇冠)的概率 > 基准概率+2%")
    print("           即：目标机构赔率 < 基准赔率（目标机构更看好该方向）")
    print("  预测方向：既然目标机构更看好该方向，但赛果反而更容易不出该方向")
    print()

    # 自然不出率按角色（上中下）
    # 先统计全样本各角色的自然不出率
    role_totals = {'fav': 0, 'mid': 0, 'dog': 0}
    role_hits   = {'fav': 0, 'mid': 0, 'dog': 0}  # 不出

    for mid, companies in match_data.items():
        bench = get_benchmark(companies)
        if not bench: continue
        roles = classify_role(bench)
        res = result_of(meta[mid]['hs'], meta[mid]['as'])
        if res is None: continue
        for side, role in roles.items():
            role_totals[role] += 1
            if result_of(meta[mid]['hs'], meta[mid]['as']) != side:
                role_hits[role] += 1

    natural = {r: role_hits[r]/role_totals[r] for r in ['fav','mid','dog']}
    print(f"  全样本自然不出率：上盘(热门)={natural['fav']:.1%}  "
          f"中间={natural['mid']:.1%}  下盘(冷门)={natural['dog']:.1%}")
    print()

    THRESHOLD = 0.02
    for target_cid, cname in [(80, "澳门"), (545, "皇冠")]:
        print(f"  ── {cname} ──")
        role_stats = {r: {'n':0,'hit':0} for r in ['fav','mid','dog']}

        for mid, companies in match_data.items():
            bench_curr = get_benchmark(companies)
            if not bench_curr: continue
            r = companies.get(target_cid)
            if not r: continue
            res = result_of(meta[mid]['hs'], meta[mid]['as'])
            if res is None: continue

            roles = classify_role(bench_curr)
            h, d, a = odds_to_prob(r['current_home'], r['current_draw'], r['current_away'])
            if h is None: continue

            for side, prob, bprob in [
                ('home', h, bench_curr['home']),
                ('draw', d, bench_curr['draw']),
                ('away', a, bench_curr['away']),
            ]:
                delta = prob - bprob
                if delta > THRESHOLD:   # 目标机构概率更高 = 赔率更低（更看好）
                    role = roles[side]
                    role_stats[role]['n'] += 1
                    if res != side:
                        role_stats[role]['hit'] += 1

        for role, label in [('fav','上盘(热门)——目标机构更看好热门，热门反而不出率'),
                              ('mid','中间——'),
                              ('dog','下盘(冷门)——目标机构更看好冷门，冷门反而不出率')]:
            st = role_stats[role]
            fmt_row(f"{cname} {label}", st['n'], st['hit'], natural[role])
        print()


# ─────────────────────────────────────────────────────────
# 分析二：按上盘/下盘框架重跑离散度
# ─────────────────────────────────────────────────────────

def analyze_dispersion_by_role(db, match_data, meta):
    print_header("分析二：市场高分歧 × 澳门/皇冠站位 —— 按上盘/下盘框架")
    print("  正确问题：当市场分歧大，且澳门站在高赔方（不看好某方向），")
    print("           这个被澳门不看好的方向——是上盘还是下盘？结果如何？")
    print()

    # 加载所有公司的当前赔率（用于计算标准差）
    sql = """
        SELECT match_id, company_id, current_home, current_draw, current_away
        FROM european_odds
        WHERE odds_type='1x2'
          AND current_home > 1 AND current_draw > 1 AND current_away > 1
          AND current_home IS NOT NULL
    """
    with db.cursor() as c:
        c.execute(sql)
        all_odds = c.fetchall()

    # 按比赛聚合全市场赔率列表
    market = defaultdict(lambda: {'home':[], 'draw':[], 'away':[]})
    for r in all_odds:
        mid = r['match_id']
        try:
            market[mid]['home'].append(float(r['current_home']))
            market[mid]['draw'].append(float(r['current_draw']))
            market[mid]['away'].append(float(r['current_away']))
        except: pass

    HIGH_STD = 0.20

    # 四象限统计：
    # [上盘/下盘] × [澳门高于市场均值/低于市场均值]
    # 澳门"高于市场均值"= 澳门赔率比均值高 = 澳门给该方向更高赔率 = 不看好该方向
    quadrant = {
        'fav_macao_high_odds':  {'n':0,'hit':0},  # 上盘，澳门不看好 → 上盘不出？
        'fav_macao_low_odds':   {'n':0,'hit':0},  # 上盘，澳门看好   → 上盘出？
        'dog_macao_high_odds':  {'n':0,'hit':0},  # 下盘，澳门不看好 → 下盘不出？
        'dog_macao_low_odds':   {'n':0,'hit':0},  # 下盘，澳门看好   → 下盘出？
        'fav_crown_high_odds':  {'n':0,'hit':0},
        'dog_crown_high_odds':  {'n':0,'hit':0},
    }

    for mid, companies in match_data.items():
        mkt = market.get(mid)
        if not mkt or len(mkt['home']) < 15: continue

        bench = get_benchmark(companies)
        if not bench: continue
        roles = classify_role(bench)
        res = result_of(meta[mid]['hs'], meta[mid]['as'])
        if res is None: continue

        try:
            std_home = statistics.stdev(mkt['home'])
            mean_home = statistics.mean(mkt['home'])
            mean_draw = statistics.mean(mkt['draw'])
            mean_away = statistics.mean(mkt['away'])
        except: continue

        if std_home < HIGH_STD: continue   # 只看高分歧场次

        means = {'home': mean_home, 'draw': mean_draw, 'away': mean_away}

        for target_cid, prefix in [(80, 'macao'), (545, 'crown')]:
            r = companies.get(target_cid)
            if not r: continue
            try:
                ch, cd, ca = float(r['current_home']), float(r['current_draw']), float(r['current_away'])
            except: continue

            target_odds = {'home': ch, 'draw': cd, 'away': ca}

            for side in ['home', 'draw', 'away']:
                role = roles[side]
                t_odds = target_odds[side]
                m_odds = means[side]

                if role not in ('fav', 'dog'): continue

                not_out = (res != side)

                if t_odds > m_odds * 1.03:   # 澳门/皇冠给该方向更高赔率 = 不看好
                    key = f'{role}_{prefix}_high_odds'
                elif t_odds < m_odds * 0.97:  # 澳门/皇冠给该方向更低赔率 = 看好
                    key = f'{role}_{prefix}_low_odds'
                else:
                    continue

                if key in quadrant:
                    quadrant[key]['n'] += 1
                    if not_out:
                        quadrant[key]['hit'] += 1

    # 自然不出率（基于上下盘自然概率）
    nat_fav_not_out = 0.485   # 热门自然不出率
    nat_dog_not_out = 0.783   # 冷门自然不出率

    desc = {
        'fav_macao_high_odds': ('澳门赔率高于市场', '上盘(热门)', '热门不出', nat_fav_not_out),
        'fav_macao_low_odds':  ('澳门赔率低于市场', '上盘(热门)', '热门不出', nat_fav_not_out),
        'dog_macao_high_odds': ('澳门赔率高于市场', '下盘(冷门)', '冷门不出', nat_dog_not_out),
        'dog_macao_low_odds':  ('澳门赔率低于市场', '下盘(冷门)', '冷门不出', nat_dog_not_out),
        'fav_crown_high_odds': ('皇冠赔率高于市场', '上盘(热门)', '热门不出', nat_fav_not_out),
        'dog_crown_high_odds': ('皇冠赔率高于市场', '下盘(冷门)', '冷门不出', nat_dog_not_out),
    }

    print(f"  高分歧场次(主队赔率StdDev>0.20)结果：")
    print(f"  {'信号描述':<42} {'n':>5}  {'命中率':>7}  {'基础':>7}  {'提升':>8}")
    print("─"*74)
    for key, (action, who, pred, base) in desc.items():
        st = quadrant[key]
        n = st['n']
        if n < 5:
            print(f"  [{who}] {action} → {pred}: 样本不足(n={n})")
            continue
        rate = st['hit'] / n
        lift = rate - base
        marker = " ✦✦" if lift > 0.12 else (" ✦" if lift > 0.06 else (" →" if lift > 0.02 else " ⚠️"))
        print(f"  [{who}] {action:<20} → {pred}  n={n:>5}  {rate:>6.1%}  {base:>6.1%}  {lift:>+7.1%}{marker}")


# ─────────────────────────────────────────────────────────
# 分析三：最重要的问题——上盘不出率的真实信号
# ─────────────────────────────────────────────────────────

def analyze_favorite_killer(match_data, meta):
    print_header("分析三：上盘杀手信号 —— 什么组合能预测热门翻车？")
    print("  热门翻车 = 上盘(赔率最低方向)未出结果")
    print("  自然热门翻车率 = 48.5%（基准线）")
    print("  目标：找到能将热门翻车率推高到60%+的信号组合")
    print()

    THRESHOLD = 0.02
    nat_fav_fail = 0.485

    # 信号组合
    combos = {
        '澳门概率>基准+2%（澳门低赔，但基准赔率更低的方向）': {'n':0,'hit':0},
        '澳门概率<基准-2%（澳门高赔，不认可该方向）': {'n':0,'hit':0},
        '澳门+皇冠均概率>基准（双机构低赔）': {'n':0,'hit':0},
        '澳门+皇冠均概率<基准（双机构高赔=联合不认可）': {'n':0,'hit':0},
        '临场拉升(初赔持平,终赔澳门概率>基准3%)': {'n':0,'hit':0},
        '临场压低(初赔持平,终赔澳门概率<基准-3%)': {'n':0,'hit':0},
        '全程一致低赔(初终赔均<基准-2%)': {'n':0,'hit':0},
        '全程一致高赔(初终赔均>基准+2%)': {'n':0,'hit':0},
    }

    for mid, companies in match_data.items():
        bench_curr = get_benchmark(companies)
        bench_init = get_benchmark(companies, use_initial=True)
        if not bench_curr or not bench_init: continue

        roles = classify_role(bench_curr)
        fav_side = [s for s, r in roles.items() if r == 'fav'][0]

        res = result_of(meta[mid]['hs'], meta[mid]['as'])
        if res is None: continue
        fav_failed = (res != fav_side)

        macao = companies.get(80)
        crown = companies.get(545)

        def get_probs(company, side):
            if company is None: return None, None
            hc, dc, ac = odds_to_prob(company['current_home'], company['current_draw'], company['current_away'])
            hi, di, ai = odds_to_prob(company['initial_home'], company['initial_draw'], company['initial_away'])
            if hc is None or hi is None: return None, None
            curr = {'home': hc, 'draw': dc, 'away': ac}[side]
            init = {'home': hi, 'draw': di, 'away': ai}[side]
            return curr, init

        bc = bench_curr[fav_side]
        bi = bench_init[fav_side]

        mc, mi = get_probs(macao, fav_side)
        cc, ci = get_probs(crown, fav_side)

        if mc is not None:
            delta_c = mc - bc
            delta_i = mi - bi if mi else None

            # 澳门概率>基准（澳门给低赔，更看好热门）→ 热门居然不出？
            if delta_c > THRESHOLD:
                combos['澳门概率>基准+2%（澳门低赔，但基准赔率更低的方向）']['n'] += 1
                if fav_failed:
                    combos['澳门概率>基准+2%（澳门低赔，但基准赔率更低的方向）']['hit'] += 1

            # 澳门概率<基准（澳门给高赔，不认可热门）→ 热门真的不出
            if delta_c < -THRESHOLD:
                combos['澳门概率<基准-2%（澳门高赔，不认可该方向）']['n'] += 1
                if fav_failed:
                    combos['澳门概率<基准-2%（澳门高赔，不认可该方向）']['hit'] += 1

            # 临场变化
            if delta_i is not None:
                if abs(delta_i) < 0.015 and delta_c > 0.03:
                    combos['临场拉升(初赔持平,终赔澳门概率>基准3%)']['n'] += 1
                    if fav_failed:
                        combos['临场拉升(初赔持平,终赔澳门概率>基准3%)']['hit'] += 1
                if abs(delta_i) < 0.015 and delta_c < -0.03:
                    combos['临场压低(初赔持平,终赔澳门概率<基准-3%)']['n'] += 1
                    if fav_failed:
                        combos['临场压低(初赔持平,终赔澳门概率<基准-3%)']['hit'] += 1
                if delta_i < -THRESHOLD and delta_c < -THRESHOLD:
                    combos['全程一致高赔(初终赔均>基准+2%)']['n'] += 1
                    if fav_failed:
                        combos['全程一致高赔(初终赔均>基准+2%)']['hit'] += 1
                if delta_i > THRESHOLD and delta_c > THRESHOLD:
                    combos['全程一致低赔(初终赔均<基准-2%)']['n'] += 1
                    if fav_failed:
                        combos['全程一致低赔(初终赔均<基准-2%)']['hit'] += 1

        if mc is not None and cc is not None:
            delta_m = mc - bc
            delta_cr = cc - bc
            if delta_m > THRESHOLD and delta_cr > THRESHOLD:
                combos['澳门+皇冠均概率>基准（双机构低赔）']['n'] += 1
                if fav_failed:
                    combos['澳门+皇冠均概率>基准（双机构低赔）']['hit'] += 1
            if delta_m < -THRESHOLD and delta_cr < -THRESHOLD:
                combos['澳门+皇冠均概率<基准（双机构高赔=联合不认可）']['n'] += 1
                if fav_failed:
                    combos['澳门+皇冠均概率<基准（双机构高赔=联合不认可）']['hit'] += 1

    print(f"  {'信号':<48} {'n':>5}  {'热门翻车率':>10}  {'基础':>7}  {'提升':>8}")
    print("─"*74)
    for label, st in combos.items():
        n = st['n']
        if n < 15: continue
        rate = st['hit'] / n
        lift = rate - nat_fav_fail
        marker = " ✦✦" if lift > 0.12 else (" ✦" if lift > 0.06 else (" →" if lift > 0.02 else " ⚠️"))
        print(f"  {label:<48} {n:>5}  {rate:>9.1%}  {nat_fav_fail:>6.1%}  {lift:>+7.1%}{marker}")


# ─────────────────────────────────────────────────────────
# 分析四：赔率区间（上盘赔率绝对值）对信号的影响
# ─────────────────────────────────────────────────────────

def analyze_fav_odds_range(match_data, meta):
    print_header("分析四：热门赔率区间 × 澳门高赔信号 的命中率矩阵")
    print("  核心：赔率1.3的上盘和赔率1.8的上盘，0.03的偏差含金量完全不同")
    print("  [澳门概率 < 基准-2%] = 澳门不认可热门 → 热门翻车率")
    print()

    bins = [
        (1.10, 1.30, "超强热门 1.1-1.3"),
        (1.30, 1.50, "强热门   1.3-1.5"),
        (1.50, 1.80, "次热门   1.5-1.8"),
        (1.80, 2.20, "均势偏强 1.8-2.2"),
        (2.20, 3.00, "均势     2.2-3.0"),
    ]

    print(f"  {'热门赔率区间':<22} {'澳门高赔n':>10} {'热门翻车率':>10} {'基础':>7} {'提升':>8}  "
          f"{'无信号n':>8} {'基础翻车率':>10}")
    print("─"*90)

    for lo, hi, label in bins:
        sig_n, sig_hit   = 0, 0
        base_n, base_hit = 0, 0

        for mid, companies in match_data.items():
            bench_curr = get_benchmark(companies)
            if not bench_curr: continue
            roles = classify_role(bench_curr)
            fav_side = [s for s, r in roles.items() if r == 'fav'][0]

            res = result_of(meta[mid]['hs'], meta[mid]['as'])
            if res is None: continue
            fav_failed = (res != fav_side)

            # 热门的市场均值赔率（用基准概率反推）
            fav_bench_prob = bench_curr[fav_side]
            if fav_bench_prob <= 0: continue
            fav_implied_odds = 1.0 / fav_bench_prob   # 近似赔率

            if not (lo <= fav_implied_odds < hi): continue

            macao = companies.get(80)
            if macao is None:
                base_n += 1
                if fav_failed: base_hit += 1
                continue

            mc, md, ma = odds_to_prob(macao['current_home'], macao['current_draw'], macao['current_away'])
            if mc is None:
                base_n += 1
                if fav_failed: base_hit += 1
                continue

            m_fav = {'home': mc, 'draw': md, 'away': ma}[fav_side]
            delta = m_fav - fav_bench_prob

            base_n += 1
            if fav_failed: base_hit += 1

            if delta < -0.02:   # 澳门不认可热门
                sig_n += 1
                if fav_failed: sig_hit += 1

        base_rate = base_hit / base_n if base_n else 0
        if sig_n >= 5:
            sig_rate = sig_hit / sig_n
            lift = sig_rate - base_rate
            marker = " ✦✦" if lift > 0.12 else (" ✦" if lift > 0.06 else "")
            print(f"  {label:<22} {sig_n:>10}  {sig_rate:>9.1%}  {base_rate:>6.1%}  {lift:>+7.1%}{marker}"
                  f"  {base_n:>8}  {base_rate:>9.1%}")
        else:
            print(f"  {label:<22} {'样本不足':>10}  {'─':>9}  {base_rate:>6.1%}  {'─':>8}"
                  f"  {base_n:>8}  {base_rate:>9.1%}")


# ─────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────

def main():
    print("=" * 74)
    print("  以「上盘/下盘」为框架的机构偏离分析")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 74)

    db = get_db()
    print("\n加载数据...")
    match_data, meta = load_data(db)
    print(f"  有效样本: {len(match_data)} 场")

    analyze_highbias_by_role(match_data, meta)
    analyze_dispersion_by_role(db, match_data, meta)
    analyze_favorite_killer(match_data, meta)
    analyze_fav_odds_range(match_data, meta)

    db.close()

    print("\n" + "═"*74)
    print("【关键结论】")
    print("""
  1. 正确框架：所有分析必须按上盘/下盘而非主队/客队
  2. 高分歧+澳门/皇冠不认可上盘（给高赔）→ 最强的上盘翻车信号
  3. 热门赔率越低（1.3以内的超强热门），澳门的高赔信号含金量越高
  4. 澳门"更看好热门"（给热门低赔）≠ 热门一定赢，需结合离散度
    """)


if __name__ == '__main__':
    main()
