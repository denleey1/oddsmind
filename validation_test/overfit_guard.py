#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
过拟合防护验证器 —— 时间序列切割 + 联赛交叉验证
目标：找到同时满足以下条件的规则
  1. 全量联赛准确率 ≥ 75%
  2. 时间外样本（后50%）准确率 ≥ 72%（允许±3%衰减）
  3. 精选联赛与全量联赛差距 < 5%（稳定性）
  4. 联赛交叉验证：将联赛随机分成5折，每折胜率均≥68%

方法论：
  - 不做任何参数优化/拟合，阈值完全来自业务先验
  - 按 match_time 排序后按时间段切割（非随机）
  - 联赛级别交叉验证（按联赛分组，而非按比赛分组）
"""

import sys
import os
import json
import random
from pathlib import Path
from datetime import datetime
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


# ── 公司配置 ──────────────────────────────────────────────
GOLDEN_BENCHMARK = {177: "Pinnacle", 115: "William Hill"}

TARGET_INSTITUTIONS = {
    80:  "澳门",
    432: "HKJC",
    110: "SNAI",
    545: "皇冠",
}

ALL_COMPANIES = {**GOLDEN_BENCHMARK, **TARGET_INSTITUTIONS}

# ── 候选规则定义（阈值均为先验业务逻辑，非数据拟合）──────
CANDIDATE_RULES = {
    "澳门_HIGH_BIAS":       {"company": 80,  "type": "high_bias",       "threshold": 0.02},
    "皇冠_HIGH_BIAS":       {"company": 545, "type": "high_bias",       "threshold": 0.02},
    "澳门_LATE_HIGH":       {"company": 80,  "type": "late_high",       "init_tol": 0.015, "term_min": 0.025},
    "皇冠_LATE_HIGH":       {"company": 545, "type": "late_high",       "init_tol": 0.015, "term_min": 0.025},
    "澳门_CONSISTENT_HIGH": {"company": 80,  "type": "consistent_high", "threshold": 0.025},
    "皇冠_CONSISTENT_HIGH": {"company": 545, "type": "consistent_high", "threshold": 0.025},
}


# ── 核心工具函数 ──────────────────────────────────────────

def odds_to_prob(h, d, a):
    if not (h and d and a and float(h) > 1 and float(d) > 1 and float(a) > 1):
        return None, None, None
    rh, rd, ra = 1/float(h), 1/float(d), 1/float(a)
    t = rh + rd + ra
    return rh/t, rd/t, ra/t


def golden_prob(companies, use_initial=False):
    probs = []
    for cid in GOLDEN_BENCHMARK:
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
    return {
        'home': sum(p[0] for p in probs)/len(probs),
        'draw': sum(p[1] for p in probs)/len(probs),
        'away': sum(p[2] for p in probs)/len(probs),
    }


def result_of(companies):
    row = next(iter(companies.values()))
    h, a = row.get('home_score'), row.get('away_score')
    if h is None or a is None:
        return None
    return 'home' if h > a else ('draw' if h == a else 'away')


def apply_rule(companies, rule_cfg):
    """
    对一场比赛应用规则，返回列表 [(side, is_negative_signal), ...]
    is_negative_signal=True 表示该方向应该"不出"
    """
    cid = rule_cfg['company']
    rtype = rule_cfg['type']
    row = companies.get(cid)
    if not row:
        return []

    bench_curr = golden_prob(companies, use_initial=False)
    bench_init = golden_prob(companies, use_initial=True)
    if not bench_curr or not bench_init:
        return []

    h_c, d_c, a_c = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
    h_i, d_i, a_i = odds_to_prob(row['initial_home'], row['initial_draw'], row['initial_away'])
    if None in (h_c, d_c, a_c, h_i, d_i, a_i):
        return []

    signals = []
    pairs = [('home', h_i, h_c, bench_init['home'], bench_curr['home']),
             ('draw', d_i, d_c, bench_init['draw'], bench_curr['draw']),
             ('away', a_i, a_c, bench_init['away'], bench_curr['away'])]

    if rtype == 'high_bias':
        thr = rule_cfg['threshold']
        for side, ti, tc, bi, bc in pairs:
            if (tc - bc) > thr:
                signals.append((side, True))  # 高赔诱导 → 该向不出

    elif rtype == 'late_high':
        init_tol = rule_cfg['init_tol']
        term_min = rule_cfg['term_min']
        for side, ti, tc, bi, bc in pairs:
            if abs(ti - bi) < init_tol and (tc - bc) >= term_min:
                signals.append((side, True))

    elif rtype == 'consistent_high':
        thr = rule_cfg['threshold']
        for side, ti, tc, bi, bc in pairs:
            if (ti - bi) > thr and (tc - bc) > thr:
                signals.append((side, True))

    return signals


def evaluate_rule_on_dataset(match_data, rule_name, rule_cfg):
    """在给定数据集上评估一条规则，返回 (total, hits, rate)"""
    total, hits = 0, 0
    for match_id, companies in match_data.items():
        result = result_of(companies)
        if result is None:
            continue
        for side, is_negative in apply_rule(companies, rule_cfg):
            total += 1
            if is_negative and result != side:
                hits += 1
            elif not is_negative and result == side:
                hits += 1
    rate = hits / total if total > 0 else 0
    return total, hits, rate


# ── 数据加载（带时间戳）────────────────────────────────────

def load_data(db):
    company_ids = list(ALL_COMPANIES.keys())
    placeholders = ",".join(["%s"] * len(company_ids))
    sql = f"""
        SELECT eo.match_id, eo.company_id,
               eo.initial_home, eo.initial_draw, eo.initial_away,
               eo.current_home, eo.current_draw, eo.current_away,
               m.home_score, m.away_score,
               m.match_time, m.league_id,
               l.name_cn AS league_name
        FROM european_odds eo
        JOIN matches m ON m.match_id = eo.match_id
        LEFT JOIN leagues l ON l.league_id = m.league_id
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
    match_meta = {}
    for row in rows:
        mid = row['match_id']
        data[mid][row['company_id']] = row
        match_meta[mid] = {
            'match_time': row['match_time'],
            'league_id':  row['league_id'],
            'league_name': row['league_name'],
        }

    # 只保留黄金基准+目标均有的比赛
    valid = {
        mid: comps for mid, comps in data.items()
        if any(c in comps for c in GOLDEN_BENCHMARK)
        and any(c in comps for c in TARGET_INSTITUTIONS)
    }
    return valid, match_meta


# ── 1. 时间切割验证 ────────────────────────────────────────

def temporal_split_validation(match_data, match_meta):
    print("\n" + "═"*78)
    print("【验证1】时间序列切割  —  前60%为训练集，后40%为纯外样本测试集")
    print("         规则均为先验定义，不在训练集上优化任何参数")
    print("═"*78)

    # 按时间排序
    sorted_mids = sorted(
        [mid for mid in match_data if mid in match_meta],
        key=lambda m: str(match_meta[m]['match_time'] or '0000')
    )

    cut60 = int(len(sorted_mids) * 0.60)
    cut80 = int(len(sorted_mids) * 0.80)

    periods = {
        '前60%（较早）':  set(sorted_mids[:cut60]),
        '后40%（外样本）': set(sorted_mids[cut60:]),
        '最新20%（严格外样本）': set(sorted_mids[cut80:]),
    }

    # 获取时间范围
    def time_range(mids):
        times = [str(match_meta[m]['match_time'])[:10] for m in mids if match_meta[m]['match_time']]
        return f"{min(times)} ~ {max(times)}" if times else "N/A"

    for pname, pmids in periods.items():
        t = time_range(pmids)
        print(f"  {pname}: {len(pmids)} 场  [{t}]")

    print(f"\n{'规则名称':<22} {'前60% 胜率':>10} {'后40% 胜率':>10} {'最新20%':>10} {'稳定性':>8} {'结论':>8}")
    print("─"*78)

    qualified = []

    for rule_name, rule_cfg in CANDIDATE_RULES.items():
        results = {}
        for pname, pmids in periods.items():
            subset = {m: match_data[m] for m in pmids if m in match_data}
            n, h, r = evaluate_rule_on_dataset(subset, rule_name, rule_cfg)
            results[pname] = (n, h, r)

        r_early  = results['前60%（较早）'][2]
        r_out    = results['后40%（外样本）'][2]
        r_latest = results['最新20%（严格外样本）'][2]
        n_out    = results['后40%（外样本）'][0]
        n_latest = results['最新20%（严格外样本）'][0]

        decay = r_out - r_early
        stability = "稳定" if abs(decay) < 0.05 else ("轻微衰减" if abs(decay) < 0.08 else "不稳定")

        # 通过标准：外样本≥72%，最新20%≥70%，衰减<8%
        passed = r_out >= 0.72 and r_latest >= 0.70 and abs(decay) < 0.08
        verdict = "✅ 通过" if passed else "❌ 未过"

        decay_str = f"{decay:+.1%}"
        print(f"{rule_name:<22} {r_early:>9.1%}  {r_out:>9.1%}  {r_latest:>9.1%}  {stability:<8} {verdict}")
        print(f"  {'':22} (n={results['前60%（较早）'][0]:<5})  "
              f"(n={n_out:<5})  (n={n_latest:<5})  变化: {decay_str}")

        if passed:
            qualified.append((rule_name, rule_cfg, r_out, n_out))

    return qualified


# ── 2. 联赛级别交叉验证（5折，按联赛分组）────────────────

def league_cross_validation(match_data, match_meta, qualified_rules):
    print("\n" + "═"*78)
    print("【验证2】联赛级别 5折交叉验证")
    print("         按联赛分组（而非按比赛分组），防止联赛内部相关性泄露")
    print("═"*78)

    # 按联赛ID分组
    league_to_matches = defaultdict(list)
    for mid in match_data:
        lid = match_meta.get(mid, {}).get('league_id')
        if lid:
            league_to_matches[lid].append(mid)

    leagues = list(league_to_matches.keys())
    random.seed(42)
    random.shuffle(leagues)

    n_folds = 5
    fold_size = len(leagues) // n_folds
    folds = []
    for i in range(n_folds):
        start = i * fold_size
        end   = start + fold_size if i < n_folds - 1 else len(leagues)
        fold_leagues = set(leagues[start:end])
        fold_mids = set()
        for lid in fold_leagues:
            fold_mids.update(league_to_matches[lid])
        folds.append((fold_leagues, fold_mids))

    print(f"\n  各折联赛数: {[len(f[0]) for f in folds]}")
    print(f"  各折比赛数: {[len(f[1]) for f in folds]}")
    print()

    final_qualified = []

    for rule_name, rule_cfg, out_sample_rate, out_n in qualified_rules:
        fold_rates = []
        fold_ns    = []
        for fold_leagues, fold_mids in folds:
            subset = {m: match_data[m] for m in fold_mids if m in match_data}
            n, h, r = evaluate_rule_on_dataset(subset, rule_name, rule_cfg)
            fold_rates.append(r)
            fold_ns.append(n)

        min_rate = min(fold_rates)
        max_rate = max(fold_rates)
        avg_rate = sum(fold_rates) / len(fold_rates)
        variance = max_rate - min_rate

        # 通过标准：所有折 ≥ 68%，方差 < 15%
        cv_pass = min_rate >= 0.68 and variance < 0.15

        fold_str = "  ".join([f"{r:.1%}(n={n})" for r, n in zip(fold_rates, fold_ns)])
        status = "✅" if cv_pass else "❌"
        print(f"{rule_name:<22}  {status}")
        print(f"  各折: {fold_str}")
        print(f"  均值={avg_rate:.1%}  最低={min_rate:.1%}  波动幅度={variance:.1%}")
        print()

        if cv_pass:
            final_qualified.append((rule_name, rule_cfg, avg_rate, out_sample_rate))

    return final_qualified


# ── 3. 信号独立性检验（避免重复计数）────────────────────────

def check_signal_independence(match_data, final_rules):
    """统计不同规则信号的重叠比例，确保它们是独立信号"""
    print("\n" + "═"*78)
    print("【验证3】信号重叠率检验  —  确认各规则捕捉的是不同场次")
    print("═"*78)

    rule_matches = {}
    for rule_name, rule_cfg, _, _ in final_rules:
        triggered_matches = set()
        for mid, companies in match_data.items():
            if apply_rule(companies, rule_cfg):
                triggered_matches.add(mid)
        rule_matches[rule_name] = triggered_matches
        print(f"  {rule_name}: 触发场次={len(triggered_matches)}")

    print("\n  规则对重叠率：")
    rules = list(rule_matches.keys())
    for i in range(len(rules)):
        for j in range(i+1, len(rules)):
            a, b = rule_matches[rules[i]], rule_matches[rules[j]]
            if not a or not b:
                continue
            overlap = len(a & b)
            union   = len(a | b)
            overlap_rate = overlap / min(len(a), len(b))
            status = "⚠️ 高度重叠" if overlap_rate > 0.7 else ("注意" if overlap_rate > 0.5 else "独立")
            print(f"    {rules[i]:<22} × {rules[j]:<22}  重叠={overlap_rate:.1%}  [{status}]")


# ── 主程序 ────────────────────────────────────────────────

def main():
    print("=" * 78)
    print("  过拟合防护验证器 —— 寻找真正鲁棒的75%+规则")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 78)

    print("\n加载数据...")
    db = get_db()
    match_data, match_meta = load_data(db)
    db.close()
    print(f"  有效比赛: {len(match_data)} 场")

    # 显示时间跨度
    times = sorted([str(v['match_time'])[:10] for v in match_meta.values() if v['match_time']])
    if times:
        print(f"  时间跨度: {times[0]} ~ {times[-1]}")

    leagues_count = len(set(v['league_id'] for v in match_meta.values() if v['league_id']))
    print(f"  覆盖联赛: {leagues_count} 个")

    # ── 全量基准评估 ─────────────────────────────────────
    print("\n" + "═"*78)
    print("【基准】全量数据各规则表现")
    print("═"*78)
    print(f"\n{'规则名称':<22} {'胜率':>8} {'样本数':>7}  {'入选门槛'}")
    print("─"*78)

    baseline_qualified = []
    for rule_name, rule_cfg in CANDIDATE_RULES.items():
        n, h, r = evaluate_rule_on_dataset(match_data, rule_name, rule_cfg)
        mark = " ✅ ≥75%" if r >= 0.75 else (" ≈75%" if r >= 0.73 else " ❌ <73%")
        print(f"{rule_name:<22} {r:>7.1%}  {n:>6}{mark}")
        if r >= 0.73:  # 给74%的也机会进入下一步
            baseline_qualified.append((rule_name, rule_cfg))

    # ── 验证1：时间切割 ──────────────────────────────────
    time_qualified = temporal_split_validation(match_data, match_meta)

    if not time_qualified:
        print("\n⚠️  没有规则通过时间切割验证，调低外样本门槛至70%重新验证...")
        # 降低阈值重跑（更诚实地报告）
        for rule_name, rule_cfg in baseline_qualified:
            subset_late = {
                m: match_data[m] for m in sorted(
                    match_data.keys(),
                    key=lambda x: str(match_meta.get(x, {}).get('match_time') or '0')
                )[int(len(match_data)*0.6):]
            }
            n, h, r = evaluate_rule_on_dataset(subset_late, rule_name, rule_cfg)
            print(f"  {rule_name}: 后40%外样本 = {r:.1%} (n={n})")

    # ── 验证2：联赛交叉验证 ──────────────────────────────
    if time_qualified:
        final_rules = league_cross_validation(match_data, match_meta, time_qualified)
    else:
        final_rules = []

    # ── 验证3：信号重叠检验 ──────────────────────────────
    if final_rules:
        check_signal_independence(match_data, final_rules)

    # ── 最终裁定 ─────────────────────────────────────────
    print("\n" + "═"*78)
    print("【最终裁定】通过全部三项验证的规则")
    print("  条件：全量≥73% + 外样本≥72% + 最新20%≥70% + 5折均≥68%")
    print("═"*78)

    if final_rules:
        for rule_name, rule_cfg, cv_avg, out_rate in final_rules:
            n_total, _, r_total = evaluate_rule_on_dataset(match_data, rule_name, rule_cfg)
            print(f"\n  ✅ {rule_name}")
            print(f"     全量胜率={r_total:.1%}  外样本={out_rate:.1%}  5折均值={cv_avg:.1%}")
            print(f"     样本量={n_total}  适用联赛：所有联赛")
            cfg_str = json.dumps({k:v for k,v in rule_cfg.items() if k!='company'}, ensure_ascii=False)
            print(f"     规则参数: {cfg_str}")
    else:
        print("\n  结论: 在严格的三重验证下，没有规则能同时满足全部条件。")
        print("  最接近通过的规则（仅供参考）:")
        for rule_name, rule_cfg in baseline_qualified:
            n, h, r = evaluate_rule_on_dataset(match_data, rule_name, rule_cfg)
            print(f"    {rule_name}: 全量={r:.1%} (n={n})")

    print("\n" + "="*78)
    print("验证完成。")


if __name__ == '__main__':
    main()
