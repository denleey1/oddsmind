#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基础概率审计 —— 彻底排查规则是否只是在复现自然基础概率

关键问题：
1. 规则触发的是哪个方向（主/平/客）？对应的自然"不出率"是多少？
2. 规则真正的【提升值 = 实际准确率 - 自然基础概率】是多少？
3. 我的 HIGH_BIAS 到底是"高赔方不出"还是"低赔方不出"？
4. 澳门的赔率相对基准的方向到底是什么含义？
"""

import sys
import os
from pathlib import Path
from collections import defaultdict

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
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def odds_to_prob(h, d, a):
    if not (h and d and a and float(h) > 1 and float(d) > 1 and float(a) > 1):
        return None, None, None
    rh, rd, ra = 1/float(h), 1/float(d), 1/float(a)
    t = rh + rd + ra
    return rh/t, rd/t, ra/t


def golden_prob(companies, use_initial=False):
    probs = []
    for cid in [177, 115]:
        row = companies.get(cid)
        if not row:
            continue
        if use_initial:
            h, d, a = odds_to_prob(row['initial_home'], row['initial_draw'], row['initial_away'])
        else:
            h, d, a = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
        if h is not None:
            probs.append((h, d, a))
    if not probs:
        return None
    return {k: sum(p[i] for p in probs)/len(probs)
            for i, k in enumerate(['home', 'draw', 'away'])}


def result_of(companies):
    row = next(iter(companies.values()))
    h, a = row.get('home_score'), row.get('away_score')
    if h is None or a is None:
        return None
    return 'home' if h > a else ('draw' if h == a else 'away')


def load_data(db):
    company_ids = [177, 115, 80, 545]
    placeholders = ",".join(["%s"] * len(company_ids))
    sql = f"""
        SELECT eo.match_id, eo.company_id,
               eo.initial_home, eo.initial_draw, eo.initial_away,
               eo.current_home, eo.current_draw, eo.current_away,
               m.home_score, m.away_score
        FROM european_odds eo
        JOIN matches m ON m.match_id = eo.match_id
        WHERE eo.company_id IN ({placeholders})
          AND eo.odds_type = '1x2'
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND eo.initial_home > 1 AND eo.current_home > 1
          AND eo.initial_home IS NOT NULL AND eo.current_home IS NOT NULL
    """
    with db.cursor() as cur:
        cur.execute(sql, company_ids)
        rows = cur.fetchall()
    data = defaultdict(dict)
    for row in rows:
        data[row['match_id']][row['company_id']] = row
    return {
        mid: comps for mid, comps in data.items()
        if any(c in comps for c in [177, 115])
        and any(c in comps for c in [80, 545])
    }


# ─────────────────────────────────────────────────────────
# 第一步：完全搞清楚 delta 的方向含义
# ─────────────────────────────────────────────────────────

def audit_delta_direction(match_data):
    """
    抽样100场比赛，逐场展示：
    - 澳门实际赔率 vs 基准赔率
    - 对应的 delta_prob 方向
    - 赔率高低 vs 概率高低 的关系
    """
    print("═"*80)
    print("【第一步】delta方向澄清：澳门赔率 vs 基准赔率 vs delta_prob")
    print("═"*80)
    print(f"\n{'澳门主赔':>8} {'基准主赔':>8} {'澳赔高低':>8} {'澳概率':>8} {'基准概率':>8} {'delta':>8} 含义")
    print("─"*80)

    count = 0
    for mid, companies in match_data.items():
        if count >= 20:
            break
        bench = golden_prob(companies)
        macao = companies.get(80)
        if not bench or not macao:
            continue
        mh, md, ma = odds_to_prob(macao['current_home'], macao['current_draw'], macao['current_away'])
        if mh is None:
            continue

        m_home_odds = float(macao['current_home'])
        # 基准主队赔率（反推）
        b_home_prob = bench['home']
        # 注意：基准概率是Pinnacle+WH平均归一化概率，不是直接赔率的倒数
        # 用概率反推基准"隐含赔率"
        b_implied_odds = 1.0 / b_home_prob if b_home_prob > 0 else 0

        delta = mh - b_home_prob
        direction = "澳门赔率更高(低赔方)" if m_home_odds < b_implied_odds else "澳门赔率更低(高赔方)"
        delta_meaning = "澳门概率>基准" if delta > 0 else "澳门概率<基准"

        print(f"{m_home_odds:>8.3f} {b_implied_odds:>8.3f} {direction:>10} {mh:>8.3f} {b_home_prob:>8.3f} {delta:>+8.4f} {delta_meaning}")
        count += 1


# ─────────────────────────────────────────────────────────
# 第二步：按方向(home/draw/away)分解命中率，对比自然基础概率
# ─────────────────────────────────────────────────────────

def audit_by_side(match_data, target_cid=80, cid_name="澳门", threshold=0.02):
    """
    关键分析：
    对HIGH_BIAS（澳门概率>基准+阈值）按方向分解，
    对比"该方向的自然不出率"
    """
    print("\n" + "═"*80)
    print(f"【第二步】{cid_name} HIGH_BIAS 按方向分解  (概率delta > {threshold:.0%})")
    print("═"*80)
    print(f"\n说明：'自然不出率' = 该方向在全样本中不出现的基础概率")
    print(f"       '规则命中率' = 触发HIGH_BIAS时，该方向实际不出率")
    print(f"       '真实提升'   = 规则命中率 - 自然不出率（这才是规则的真实价值）")

    # 自然基础概率
    base_rates = {'home': 0, 'draw': 0, 'away': 0}
    base_total  = 0
    for mid, companies in match_data.items():
        result = result_of(companies)
        if result:
            base_total += 1
            base_rates[result] += 1
    natural_not_out = {
        side: 1 - (base_rates[side] / base_total)
        for side in ['home', 'draw', 'away']
    }
    print(f"\n  全样本自然概率: 主赢={base_rates['home']/base_total:.1%} "
          f"平={base_rates['draw']/base_total:.1%} "
          f"客赢={base_rates['away']/base_total:.1%}")
    print(f"  对应自然不出率: 主={natural_not_out['home']:.1%} "
          f"平={natural_not_out['draw']:.1%} 客={natural_not_out['away']:.1%}")

    # 按方向统计HIGH_BIAS
    side_stats = {s: {'total': 0, 'hit': 0, 'target_odds': [], 'bench_odds': []}
                  for s in ['home', 'draw', 'away']}

    for mid, companies in match_data.items():
        bench = golden_prob(companies)
        row = companies.get(target_cid)
        if not bench or not row:
            continue
        result = result_of(companies)
        if result is None:
            continue
        mh, md, ma = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
        if mh is None:
            continue

        for side, prob, b_prob, cur_odds in [
            ('home', mh, bench['home'], float(row['current_home'])),
            ('draw', md, bench['draw'], float(row['current_draw'])),
            ('away', ma, bench['away'], float(row['current_away'])),
        ]:
            delta = prob - b_prob
            if delta > threshold:
                side_stats[side]['total'] += 1
                if result != side:
                    side_stats[side]['hit'] += 1
                side_stats[side]['target_odds'].append(cur_odds)
                # 基准隐含赔率
                side_stats[side]['bench_odds'].append(1.0/b_prob if b_prob > 0 else 0)

    print(f"\n{'方向':>6} {'触发数':>7} {'规则命中率':>11} {'自然不出率':>11} {'真实提升':>10} {'平均目标赔率':>12} {'平均基准赔率':>12} 结论")
    print("─"*100)

    grand_total, grand_hit = 0, 0
    for side in ['home', 'draw', 'away']:
        st = side_stats[side]
        n = st['total']
        if n == 0:
            continue
        rate = st['hit'] / n
        natural = natural_not_out[side]
        lift = rate - natural
        avg_target = sum(st['target_odds'])/len(st['target_odds']) if st['target_odds'] else 0
        avg_bench  = sum(st['bench_odds'])/len(st['bench_odds']) if st['bench_odds'] else 0

        # 澳门概率>基准 → 澳门赔率<基准（澳门给的赔率更低）
        direction_note = "澳门赔率低于基准（澳门更看好此方向）"

        marker = " ✦✦" if lift > 0.10 else (" ✦" if lift > 0.05 else (" →" if lift > 0.01 else " ⚠️基础概率"))
        print(f"{side:>6} {n:>7}   {rate:>9.1%}   {natural:>9.1%}   {lift:>+9.1%}   {avg_target:>10.3f}   {avg_bench:>10.3f}{marker}")
        grand_total += n
        grand_hit   += st['hit']

    if grand_total:
        grand_rate = grand_hit / grand_total
        # 加权自然基础
        weighted_natural = sum(
            side_stats[s]['total'] * natural_not_out[s]
            for s in ['home', 'draw', 'away']
        ) / grand_total
        print(f"{'合计':>6} {grand_total:>7}   {grand_rate:>9.1%}   {weighted_natural:>9.1%}   {grand_rate-weighted_natural:>+9.1%}")
        print(f"\n  ⚡ 加权自然基础概率 = {weighted_natural:.1%}")
        print(f"  ⚡ 规则整体命中率   = {grand_rate:.1%}")
        print(f"  ⚡ 真实有效提升     = {grand_rate-weighted_natural:+.1%}  {'← 有意义' if grand_rate-weighted_natural > 0.05 else '← ⚠️ 提升不显著'}")


# ─────────────────────────────────────────────────────────
# 第三步：搞清楚是"高赔方不出"还是"低赔方不出"
# ─────────────────────────────────────────────────────────

def audit_favorite_vs_underdog(match_data, target_cid=80, cid_name="澳门"):
    """
    HIGH_BIAS触发时（澳门概率>基准，即澳门赔率<基准）：
    - 澳门正在给"上盘（热门）"更低的赔率（更愿意接）
    - 还是给"下盘"更低的赔率？
    统计触发信号的那个方向，它是当场比赛的"上盘"还是"下盘"
    """
    print("\n" + "═"*80)
    print(f"【第三步】HIGH_BIAS信号的方向是「上盘」还是「下盘」?")
    print(f"  上盘 = 该比赛中赔率最低（概率最高）的方向")
    print(f"  下盘 = 该比赛中赔率最高（概率最低）的方向")
    print("═"*80)

    THRESHOLD = 0.02
    is_fav_counts = {'favorite': 0, 'middle': 0, 'underdog': 0}
    fav_result   = {'favorite': {'hit':0,'total':0}, 'middle': {'hit':0,'total':0}, 'underdog': {'hit':0,'total':0}}

    for mid, companies in match_data.items():
        bench = golden_prob(companies)
        row = companies.get(target_cid)
        if not bench or not row:
            continue
        result = result_of(companies)
        if result is None:
            continue
        mh, md, ma = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
        if mh is None:
            continue

        # 按基准概率排序：最大=热门，最小=冷门
        sorted_sides = sorted(
            [('home', bench['home']), ('draw', bench['draw']), ('away', bench['away'])],
            key=lambda x: -x[1]
        )
        rank_map = {sorted_sides[0][0]: 'favorite',
                    sorted_sides[1][0]: 'middle',
                    sorted_sides[2][0]: 'underdog'}

        for side, prob, b_prob in [
            ('home', mh, bench['home']),
            ('draw', md, bench['draw']),
            ('away', ma, bench['away']),
        ]:
            delta = prob - b_prob
            if delta > THRESHOLD:
                role = rank_map[side]
                is_fav_counts[role] += 1
                fav_result[role]['total'] += 1
                if result != side:
                    fav_result[role]['hit'] += 1

    total_signals = sum(is_fav_counts.values())
    print(f"\n  触发HIGH_BIAS时，信号方向的身份分布（共{total_signals}条信号）：")
    print(f"\n  {'身份':<10} {'占比':>8} {'命中率(不出)':>14} 说明")
    print("─"*60)
    labels = {'favorite': '上盘(热门)', 'middle': '中间项', 'underdog': '下盘(冷门)'}
    for role in ['favorite', 'middle', 'underdog']:
        n = fav_result[role]['total']
        if n == 0:
            continue
        pct = is_fav_counts[role] / total_signals
        rate = fav_result[role]['hit'] / n
        print(f"  {labels[role]:<10} {pct:>7.1%}  {rate:>12.1%}")


# ─────────────────────────────────────────────────────────
# 第四步：对比你当前规则（用户的规则是什么？）
# ─────────────────────────────────────────────────────────

def audit_correct_high_bias(match_data, target_cid=80, cid_name="澳门"):
    """
    按用户定义的"高偏型"：澳门赔率 > 基准赔率（澳门赔率高，赔付大）
    这在概率上意味着：澳门概率 < 基准概率 → delta < 0

    所以正确的HIGH_BIAS应该是 delta < -threshold
    验证这个方向是否才是"诱导型"
    """
    print("\n" + "═"*80)
    print(f"【第四步】按用户定义重跑：澳门赔率>基准（澳门给高赔）-> 该向不出率")
    print(f"  即：澳门概率 < 基准概率（delta < -0.02）")
    print("═"*80)

    THRESHOLD = -0.02  # 澳门概率低于基准 = 澳门赔率高于基准

    natural = {'home': 1-0.433, 'draw': 1-0.259, 'away': 1-0.307}

    side_stats = {s: {'total': 0, 'hit': 0, 'target_odds': [], 'bench_implied': []}
                  for s in ['home', 'draw', 'away']}

    for mid, companies in match_data.items():
        bench = golden_prob(companies)
        row = companies.get(target_cid)
        if not bench or not row:
            continue
        result = result_of(companies)
        if result is None:
            continue
        mh, md, ma = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
        if mh is None:
            continue

        for side, prob, b_prob, cur_odds in [
            ('home', mh, bench['home'], float(row['current_home'])),
            ('draw', md, bench['draw'], float(row['current_draw'])),
            ('away', ma, bench['away'], float(row['current_away'])),
        ]:
            delta = prob - b_prob
            if delta < THRESHOLD:   # 澳门概率更低 = 澳门赔率更高
                side_stats[side]['total'] += 1
                if result != side:
                    side_stats[side]['hit'] += 1
                side_stats[side]['target_odds'].append(cur_odds)
                side_stats[side]['bench_implied'].append(1.0/b_prob if b_prob > 0 else 0)

    print(f"\n{'方向':>6} {'触发数':>7} {'命中率(不出)':>12} {'自然不出率':>11} {'真实提升':>10} {'澳门赔率':>10} {'基准赔率':>10}")
    print("─"*90)

    grand_total, grand_hit = 0, 0
    for side in ['home', 'draw', 'away']:
        st = side_stats[side]
        n = st['total']
        if n == 0:
            continue
        rate = st['hit'] / n
        nat = natural[side]
        lift = rate - nat
        avg_target = sum(st['target_odds'])/len(st['target_odds']) if st['target_odds'] else 0
        avg_bench  = sum(st['bench_implied'])/len(st['bench_implied']) if st['bench_implied'] else 0
        marker = " ✦✦" if lift > 0.08 else (" ✦" if lift > 0.03 else " ⚠️")
        print(f"{side:>6} {n:>7}   {rate:>10.1%}   {nat:>9.1%}  {lift:>+9.1%}  {avg_target:>9.3f}  {avg_bench:>9.3f}{marker}")
        grand_total += n
        grand_hit   += st['hit']

    if grand_total:
        grand_rate = grand_hit / grand_total
        weighted_nat = sum(side_stats[s]['total'] * natural[s] for s in ['home','draw','away']) / grand_total
        print(f"{'合计':>6} {grand_total:>7}   {grand_rate:>10.1%}   {weighted_nat:>9.1%}  {grand_rate-weighted_nat:>+9.1%}")


# ─────────────────────────────────────────────────────────
# 第五步：澳门赔率绝对高低（上盘/下盘）与结果的基础关系
# ─────────────────────────────────────────────────────────

def audit_simple_underdog_rate(match_data):
    """
    最简单的基础检验：
    不看任何偏差，就看"上盘不出率" vs "下盘不出率"的自然基础
    这是任何规则必须超越的基准线
    """
    print("\n" + "═"*80)
    print("【第五步】最简单基准：只看赔率高低，不出率是多少（零规则基准）")
    print("═"*80)

    fav_results   = {'fav': {'total':0,'hit':0}, 'mid': {'total':0,'hit':0}, 'dog': {'total':0,'hit':0}}

    for mid, companies in match_data.items():
        bench = golden_prob(companies)
        if not bench:
            continue
        result = result_of(companies)
        if result is None:
            continue
        sorted_sides = sorted(bench.items(), key=lambda x: -x[1])
        roles = {sorted_sides[0][0]: 'fav', sorted_sides[1][0]: 'mid', sorted_sides[2][0]: 'dog'}

        for side, role in roles.items():
            fav_results[role]['total'] += 1
            if result != side:
                fav_results[role]['hit'] += 1

    print(f"\n  {'身份':<8} {'样本数':>7} {'自然不出率':>12} 说明")
    print("─"*50)
    labels = {'fav': '上盘(热门)', 'mid': '中间项', 'dog': '下盘(冷门)'}
    for role in ['fav', 'mid', 'dog']:
        n = fav_results[role]['total']
        rate = fav_results[role]['hit'] / n
        print(f"  {labels[role]:<8} {n:>7}   {rate:>10.1%}")

    print(f"\n  结论：任何规则如果只是在预测上盘不出，")
    print(f"        它需要超越 {fav_results['fav']['hit']/fav_results['fav']['total']:.1%} 的基础概率才有意义。")


def main():
    print("="*80)
    print("  基础概率审计 —— 排查规则是否只是在复现自然基础概率")
    print("="*80)

    db = get_db()
    match_data = load_data(db)
    db.close()
    print(f"\n  有效样本: {len(match_data)} 场\n")

    # 第一步：澄清delta方向
    audit_delta_direction(match_data)

    # 第二步：按方向分解，对比自然基础概率（我之前的定义）
    print("\n\n=== 我原来代码的定义（delta>0 = 澳门概率>基准 = 澳门赔率<基准）===")
    audit_by_side(match_data, 80, "澳门", threshold=0.02)
    audit_by_side(match_data, 545, "皇冠", threshold=0.02)

    # 第三步：信号方向是上盘还是下盘
    audit_favorite_vs_underdog(match_data, 80, "澳门")
    audit_favorite_vs_underdog(match_data, 545, "皇冠")

    # 第四步：用用户正确定义重跑
    print("\n\n=== 用户正确定义（delta<-0.02 = 澳门赔率>基准）===")
    audit_correct_high_bias(match_data, 80, "澳门")
    audit_correct_high_bias(match_data, 545, "皇冠")

    # 第五步：零规则基准
    audit_simple_underdog_rate(match_data)

    print("\n" + "="*80)
    print("审计完成。")


if __name__ == '__main__':
    main()
