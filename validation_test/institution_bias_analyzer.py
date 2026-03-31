#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
《多维度机构赔率偏离度分析与敏感度特征提取》
Institution Odds Divergence & Sensitivity Analysis Engine

五阶段分析体系：
  Phase 1: 黄金基准构建 + 赔率归一化（去抽水处理）
  Phase 2: 三维特征提取
    - 维度A: 绝对偏离度 (Absolute Divergence)
    - 维度B: 变动惯性 (Inertia & Rigidity)
    - 维度C: 时间切片偏差 (Time-Slice Analysis)
  Phase 3: 敏感度量化模型 (Sensitivity Score)
  Phase 4: 聚类分析 + 异常捕捉 + 胜率归纳
  Phase 5: 结论输出 + 规律导出
"""

import sys
import os
import json
import math
from pathlib import Path
from datetime import datetime
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pymysql
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / "oddsmind.env")

# ─────────────────────────────────────────────────────────
# 数据库连接
# ─────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────
# 公司配置
# 黄金基准组：Pinnacle(177) + William Hill(115)
# 分析目标：澳门(80)、HKJC(432)、SNAI(110)、皇冠(545)
# ─────────────────────────────────────────────────────────
GOLDEN_BENCHMARK = {
    177: "Pinnacle",
    115: "William Hill",
}

TARGET_INSTITUTIONS = {
    80:  "澳门",
    432: "HKJC香港马会",
    110: "SNAI(意大利)",
    545: "皇冠",
}

ALL_COMPANIES = {**GOLDEN_BENCHMARK, **TARGET_INSTITUTIONS}

# ─────────────────────────────────────────────────────────
# 精选联赛白名单（五大联赛 + 全球主要一级联赛）
# ─────────────────────────────────────────────────────────
# 五大联赛
BIG5_LEAGUE_IDS = {36, 31, 8, 34, 11}

# 其他欧洲顶级联赛（1级）
EUROPE_TIER1_IDS = {
    16,   # 荷兰甲 Eredivisie
    23,   # 葡萄牙超级联赛
    30,   # 土耳其超 Süper Lig
    29,   # 苏格兰超 Scottish Premiership
    5,    # 比利时甲 Belgian Pro League
    32,   # 希腊超 Super League A
    7,    # 丹麦超 Superliga
    6,    # 波兰超 Ekstraklasa
    10,   # 俄罗斯超 Premier League
    119,  # 乌克兰超
    26,   # 瑞典超 Allsvenskan
    22,   # 挪威超 Eliteserien
    137,  # 捷克甲
    3,    # 奥地利甲
}

# 亚洲/美洲主要联赛
OTHER_TIER1_IDS = {
    25,   # 日本J1
    15,   # 韩国K League 1
    21,   # 美国MLS
    2,    # 阿根廷甲
    4,    # 巴西甲
}

ELITE_LEAGUE_IDS = BIG5_LEAGUE_IDS | EUROPE_TIER1_IDS | OTHER_TIER1_IDS

# ─────────────────────────────────────────────────────────
# Phase 1: 数据归一化 —— 去抽水，换算为理论胜率
# ─────────────────────────────────────────────────────────

def odds_to_prob(home_odds, draw_odds, away_odds):
    """
    将欧赔换算为无抽水概率（归一化理论胜率）
    raw_prob = 1 / odds
    total = sum(raw_probs)   → 含抽水总和 > 1
    normalized_prob = raw_prob / total → 真实市场概率
    """
    if not (home_odds and draw_odds and away_odds):
        return None, None, None
    if home_odds <= 1 or draw_odds <= 1 or away_odds <= 1:
        return None, None, None

    rh = 1.0 / float(home_odds)
    rd = 1.0 / float(draw_odds)
    ra = 1.0 / float(away_odds)
    total = rh + rd + ra
    return rh / total, rd / total, ra / total


def compute_golden_benchmark(match_rows_by_company):
    """
    用黄金基准组公司的即时赔率计算基准概率均值
    match_rows_by_company: {company_id: row_dict}
    返回: {'home': float, 'draw': float, 'away': float} 或 None
    """
    probs = []
    for cid in GOLDEN_BENCHMARK:
        row = match_rows_by_company.get(cid)
        if not row:
            continue
        h, d, a = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
        if h is not None:
            probs.append((h, d, a))

    if not probs:
        return None
    return {
        'home': sum(p[0] for p in probs) / len(probs),
        'draw': sum(p[1] for p in probs) / len(probs),
        'away': sum(p[2] for p in probs) / len(probs),
    }


def compute_golden_benchmark_initial(match_rows_by_company):
    """用初赔计算黄金基准（用于维度C时间切片对比）"""
    probs = []
    for cid in GOLDEN_BENCHMARK:
        row = match_rows_by_company.get(cid)
        if not row:
            continue
        h, d, a = odds_to_prob(row['initial_home'], row['initial_draw'], row['initial_away'])
        if h is not None:
            probs.append((h, d, a))

    if not probs:
        return None
    return {
        'home': sum(p[0] for p in probs) / len(probs),
        'draw': sum(p[1] for p in probs) / len(probs),
        'away': sum(p[2] for p in probs) / len(probs),
    }


# ─────────────────────────────────────────────────────────
# 数据加载
# ─────────────────────────────────────────────────────────

def load_match_odds_data(db, elite_only=False):
    """
    从 european_odds 表加载所有已完赛比赛的赔率数据（黄金基准 + 目标机构）
    european_odds 是主表，覆盖约25,000场，是 odds_changes 的5倍数据量
    elite_only=True 时只加载精选联赛（五大+主要一级）
    返回: {match_id: {company_id: row_dict}}
    """
    company_ids = list(ALL_COMPANIES.keys())
    placeholders = ",".join(["%s"] * len(company_ids))

    league_filter = ""
    params = company_ids
    if elite_only and ELITE_LEAGUE_IDS:
        league_placeholders = ",".join(["%s"] * len(ELITE_LEAGUE_IDS))
        league_filter = f"AND m.league_id IN ({league_placeholders})"
        params = company_ids + list(ELITE_LEAGUE_IDS)

    sql = f"""
        SELECT 
            eo.match_id,
            eo.company_id,
            eo.initial_home, eo.initial_draw, eo.initial_away,
            eo.initial_return_rate,
            eo.current_home, eo.current_draw, eo.current_away,
            eo.current_return_rate,
            m.home_score, m.away_score,
            m.home_team_name, m.away_team_name,
            m.match_time,
            m.league_id,
            l.name_cn AS league_name
        FROM european_odds eo
        JOIN matches m ON m.match_id = eo.match_id
        LEFT JOIN leagues l ON l.league_id = m.league_id
        WHERE eo.company_id IN ({placeholders})
          AND eo.odds_type = '1x2'
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND eo.initial_home IS NOT NULL
          AND eo.current_home IS NOT NULL
          AND eo.initial_home > 1
          AND eo.current_home > 1
          {league_filter}
    """
    with db.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    data = defaultdict(dict)
    for row in rows:
        data[row['match_id']][row['company_id']] = row

    return data


def determine_match_result(row):
    """判断比赛结果: 'home'/'draw'/'away'"""
    h, a = row.get('home_score'), row.get('away_score')
    if h is None or a is None:
        return None
    if h > a:
        return 'home'
    elif h == a:
        return 'draw'
    else:
        return 'away'


# ─────────────────────────────────────────────────────────
# Phase 2 – 维度A: 绝对偏离度
# ─────────────────────────────────────────────────────────

def analyze_dimension_a(match_data):
    """
    对每个目标机构，逐场计算即时赔率概率与黄金基准的偏差
    返回: {company_id: [record, ...]}
      record keys: match_id, side, delta, divergence_type, result
    
    阈值：
      高偏型（诱导）: delta > +0.02  → 该项通常跑不出（下盘）
      低偏型（防御）: delta < -0.03  → 该项通常稳健（上盘）
    """
    results = defaultdict(list)

    HIGH_BIAS_THRESHOLD = 0.02   # 机构高于基准2%胜率 → 诱导型
    LOW_BIAS_THRESHOLD  = -0.03  # 机构低于基准3%胜率 → 防御型

    for match_id, companies in match_data.items():
        # 需要黄金基准至少1家 + 至少1家目标机构
        benchmark = compute_golden_benchmark(companies)
        if not benchmark:
            continue

        # 取赛果（从任意一行）
        sample_row = next(iter(companies.values()))
        result = determine_match_result(sample_row)
        if result is None:
            continue

        for cid in TARGET_INSTITUTIONS:
            row = companies.get(cid)
            if not row:
                continue
            h, d, a = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
            if h is None:
                continue

            for side, target_prob, bench_prob in [
                ('home', h, benchmark['home']),
                ('draw', d, benchmark['draw']),
                ('away', a, benchmark['away']),
            ]:
                delta = target_prob - bench_prob  # 正值=高于基准（高赔→看似利好→实为诱导）

                if delta > HIGH_BIAS_THRESHOLD:
                    div_type = 'HIGH_BIAS'  # 高偏型：赔率偏高，诱导买入，该项更可能不出
                elif delta < LOW_BIAS_THRESHOLD:
                    div_type = 'LOW_BIAS'   # 低偏型：赔率压低，防御姿态，该项更可能出结果
                else:
                    div_type = 'NEUTRAL'

                results[cid].append({
                    'match_id': match_id,
                    'side': side,
                    'delta': round(delta, 4),
                    'divergence_type': div_type,
                    'result': result,
                    'home_team': sample_row.get('home_team_name', ''),
                    'away_team': sample_row.get('away_team_name', ''),
                    'match_time': str(sample_row.get('match_time', '')),
                    'league': sample_row.get('league_name', ''),
                })

    return results


def summarize_dimension_a(dim_a_results):
    """统计维度A各类型命中率"""
    print("\n" + "═" * 70)
    print("【维度A】绝对偏离度分析  —— 机构赔率 vs 黄金基准")
    print("═" * 70)
    print(f"{'机构':<14} {'偏离类型':<12} {'样本数':>6} {'目标未出':<10} {'未出率':>8}")
    print("─" * 70)

    summary = {}

    for cid, records in dim_a_results.items():
        name = TARGET_INSTITUTIONS[cid]
        for div_type in ['HIGH_BIAS', 'LOW_BIAS']:
            subset = [r for r in records if r['divergence_type'] == div_type]
            if len(subset) < 10:
                continue

            # HIGH_BIAS: 机构看似给高赔诱导 → 该方向应该不出（即result != side）
            # LOW_BIAS:  机构防御姿态 → 该方向应该出（result == side）
            if div_type == 'HIGH_BIAS':
                # 统计该方向"未跑出"的比例
                not_hit = sum(1 for r in subset if r['result'] != r['side'])
                label = "该向未出率"
                rate = not_hit / len(subset)
            else:
                # 统计该方向"跑出"的比例
                hit = sum(1 for r in subset if r['result'] == r['side'])
                not_hit = hit
                label = "该向跑出率"
                rate = hit / len(subset)

            marker = " ✦" if rate >= 0.62 else ("  " if rate >= 0.55 else "")
            print(f"{name:<14} {div_type:<12} {len(subset):>6}  {label}  {rate:>6.1%}{marker}")
            summary[f"{cid}_{div_type}"] = {
                'company': name, 'type': div_type,
                'sample': len(subset), 'rate': rate
            }

    return summary


# ─────────────────────────────────────────────────────────
# Phase 2 – 维度B: 变动惯性
# ─────────────────────────────────────────────────────────

def analyze_dimension_b(match_data):
    """
    分析各机构在基准变动时的反应模式：
    
    先计算基准初赔→终赔变动幅度：
      benchmark_delta = benchmark_current_prob - benchmark_initial_prob

    再观察目标机构的变动方向：
      target_delta = target_current_prob - target_initial_prob

    信号类型：
      REVERSE_HOLD:  基准大幅移动(|delta|>0.03)，机构几乎不动(|target_delta|<0.01) → "逆市不跟"
      LEAD_MOVE:     机构率先移动，基准还没跟上 → "提前锁死"
        判断：target_delta 方向与基准最终方向一致，且幅度 > 基准的2倍
    """
    results = defaultdict(list)

    BENCH_SIGNIFICANT = 0.025   # 基准变动显著阈值
    TARGET_RIGID      = 0.008   # 目标机构"几乎不动"阈值
    LEAD_RATIO        = 1.5     # 领先倍率

    for match_id, companies in match_data.items():
        bench_init = compute_golden_benchmark_initial(companies)
        bench_curr = compute_golden_benchmark(companies)
        if not bench_init or not bench_curr:
            continue

        sample_row = next(iter(companies.values()))
        result = determine_match_result(sample_row)
        if result is None:
            continue

        for cid in TARGET_INSTITUTIONS:
            row = companies.get(cid)
            if not row:
                continue

            h_i, d_i, a_i = odds_to_prob(row['initial_home'], row['initial_draw'], row['initial_away'])
            h_c, d_c, a_c = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
            if None in (h_i, d_i, a_i, h_c, d_c, a_c):
                continue

            for side, t_init, t_curr, b_init, b_curr in [
                ('home', h_i, h_c, bench_init['home'], bench_curr['home']),
                ('draw', d_i, d_c, bench_init['draw'], bench_curr['draw']),
                ('away', a_i, a_c, bench_init['away'], bench_curr['away']),
            ]:
                bench_delta  = b_curr - b_init   # 基准变动
                target_delta = t_curr - t_init   # 目标机构变动

                signal = None
                if abs(bench_delta) >= BENCH_SIGNIFICANT:
                    # 基准有显著变动
                    if abs(target_delta) < TARGET_RIGID:
                        signal = 'REVERSE_HOLD'   # 逆市不跟（最强信号）
                    elif (
                        bench_delta * target_delta > 0 and   # 同向
                        abs(target_delta) > abs(bench_delta) * LEAD_RATIO
                    ):
                        signal = 'OVER_FOLLOW'    # 过度跟随（羊群效应，参考信号）
                else:
                    # 基准基本没动，但目标机构提前大幅移动
                    if abs(target_delta) >= BENCH_SIGNIFICANT:
                        signal = 'LEAD_MOVE'       # 提前锁死

                if signal:
                    results[cid].append({
                        'match_id':     match_id,
                        'side':         side,
                        'bench_delta':  round(bench_delta, 4),
                        'target_delta': round(target_delta, 4),
                        'signal':       signal,
                        'result':       result,
                        'home_team':    sample_row.get('home_team_name', ''),
                        'away_team':    sample_row.get('away_team_name', ''),
                        'league':       sample_row.get('league_name', ''),
                    })

    return results


def summarize_dimension_b(dim_b_results):
    """统计维度B各信号命中率"""
    print("\n" + "═" * 70)
    print("【维度B】变动惯性分析  —— 逆市不跟 / 提前锁死")
    print("═" * 70)
    print(f"{'机构':<14} {'信号类型':<15} {'样本数':>6} {'反向出现率':>12}")
    print("─" * 70)

    summary = {}
    for cid, records in dim_b_results.items():
        name = TARGET_INSTITUTIONS[cid]
        for signal in ['REVERSE_HOLD', 'LEAD_MOVE', 'OVER_FOLLOW']:
            subset = [r for r in records if r['signal'] == signal]
            if len(subset) < 8:
                continue

            # REVERSE_HOLD: 机构不跟基准下降 → 基准方向（买压方向）实际跑反的比例
            # LEAD_MOVE: 机构提前下调 → 该方向跑出的比例
            if signal == 'REVERSE_HOLD':
                # 基准方向是 bench_delta 为负（基准降赔=买压涌入）
                # 逆市不跟 → 预期该方向不出
                hit = sum(1 for r in subset if r['result'] != r['side'])
                label = "目标方向未出"
            elif signal == 'LEAD_MOVE':
                # 机构提前降赔(target_delta<0) → 该方向概率上升 → 跑出率
                hit = sum(1 for r in subset if r['result'] == r['side'])
                label = "目标方向跑出"
            else:
                hit = sum(1 for r in subset if r['result'] == r['side'])
                label = "目标方向跑出"

            rate = hit / len(subset)
            marker = " ✦✦" if rate >= 0.65 else (" ✦" if rate >= 0.58 else "")
            print(f"{name:<14} {signal:<15} {len(subset):>6}  {label}: {rate:>6.1%}{marker}")
            summary[f"{cid}_{signal}"] = {
                'company': name, 'signal': signal,
                'sample': len(subset), 'rate': rate, 'label': label
            }

    return summary


# ─────────────────────────────────────────────────────────
# Phase 2 – 维度C: 时间切片偏差（初赔vs终赔路径）
# ─────────────────────────────────────────────────────────

def analyze_dimension_c(match_data):
    """
    核心问题：是初赔偏离还是终赔偏离更有预测价值？
    
    计算：
      initial_delta  = 目标机构初赔概率 - 基准初赔概率
      terminal_delta = 目标机构终赔概率 - 基准终赔概率
    
    关键场景："临场变节"
      初赔时持平（|initial_delta| < 0.015）
      但终赔时突然出现高/低偏（|terminal_delta| >= 0.03）
      → 临场拉升/压低 → 敏感度最高信号
    """
    results = defaultdict(list)

    INIT_NEUTRAL_MAX   = 0.015  # 初赔时被视为"持平"
    TERMINAL_BIAS_MIN  = 0.025  # 终赔时视为"有效偏离"

    for match_id, companies in match_data.items():
        bench_init = compute_golden_benchmark_initial(companies)
        bench_curr = compute_golden_benchmark(companies)
        if not bench_init or not bench_curr:
            continue

        sample_row = next(iter(companies.values()))
        result = determine_match_result(sample_row)
        if result is None:
            continue

        for cid in TARGET_INSTITUTIONS:
            row = companies.get(cid)
            if not row:
                continue

            h_i, d_i, a_i = odds_to_prob(row['initial_home'], row['initial_draw'], row['initial_away'])
            h_c, d_c, a_c = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
            if None in (h_i, d_i, a_i, h_c, d_c, a_c):
                continue

            for side, t_i, t_c, b_i, b_c in [
                ('home', h_i, h_c, bench_init['home'], bench_curr['home']),
                ('draw', d_i, d_c, bench_init['draw'], bench_curr['draw']),
                ('away', a_i, a_c, bench_init['away'], bench_curr['away']),
            ]:
                init_delta = t_i - b_i
                term_delta = t_c - b_c

                # 临场变节：初赔持平，终赔出现显著偏离
                late_betrayal = (
                    abs(init_delta) < INIT_NEUTRAL_MAX and
                    abs(term_delta) >= TERMINAL_BIAS_MIN
                )
                # 全程一致偏低（澳门全程不认可该方向）
                consistent_low = init_delta < -0.025 and term_delta < -0.025
                # 全程一致偏高（诱导型全程）
                consistent_high = init_delta > 0.025 and term_delta > 0.025

                pattern = None
                if late_betrayal:
                    pattern = 'LATE_HIGH' if term_delta > 0 else 'LATE_LOW'
                elif consistent_low:
                    pattern = 'CONSISTENT_LOW'
                elif consistent_high:
                    pattern = 'CONSISTENT_HIGH'

                if pattern:
                    results[cid].append({
                        'match_id':    match_id,
                        'side':        side,
                        'init_delta':  round(init_delta, 4),
                        'term_delta':  round(term_delta, 4),
                        'pattern':     pattern,
                        'result':      result,
                        'home_team':   sample_row.get('home_team_name', ''),
                        'away_team':   sample_row.get('away_team_name', ''),
                        'league':      sample_row.get('league_name', ''),
                    })

    return results


def summarize_dimension_c(dim_c_results):
    """统计维度C各路径模式命中率"""
    print("\n" + "═" * 70)
    print("【维度C】时间切片偏差  —— 初赔 vs 终赔路径分析")
    print("═" * 70)
    print(f"{'机构':<14} {'路径模式':<18} {'样本数':>6} {'胜率':>8}")
    print("─" * 70)

    summary = {}
    pattern_labels = {
        'LATE_HIGH':      '临场拉升（变节→高偏）→ 该向未出',
        'LATE_LOW':       '临场压低（变节→低偏）→ 该向跑出',
        'CONSISTENT_LOW': '全程一致偏低（防御）→ 该向跑出',
        'CONSISTENT_HIGH':'全程一致偏高（诱导）→ 该向未出',
    }

    for cid, records in dim_c_results.items():
        name = TARGET_INSTITUTIONS[cid]
        for pattern in ['LATE_HIGH', 'LATE_LOW', 'CONSISTENT_LOW', 'CONSISTENT_HIGH']:
            subset = [r for r in records if r['pattern'] == pattern]
            if len(subset) < 8:
                continue

            if pattern in ('LATE_HIGH', 'CONSISTENT_HIGH'):
                # 诱导型：该方向通常不出
                hit = sum(1 for r in subset if r['result'] != r['side'])
                prediction = "未出"
            else:
                # 防御型：该方向通常跑出
                hit = sum(1 for r in subset if r['result'] == r['side'])
                prediction = "跑出"

            rate = hit / len(subset)
            marker = " ✦✦" if rate >= 0.65 else (" ✦" if rate >= 0.58 else "")
            label = pattern_labels[pattern]
            print(f"{name:<14} {pattern:<18} {len(subset):>6}  {rate:>6.1%}{marker}")
            summary[f"{cid}_{pattern}"] = {
                'company': name, 'pattern': pattern, 'label': label,
                'sample': len(subset), 'rate': rate, 'prediction': prediction
            }

    return summary


# ─────────────────────────────────────────────────────────
# Phase 3: 敏感度量化模型
# 在爆冷比赛中，哪家机构提前偏离平均值最多
# ─────────────────────────────────────────────────────────

def analyze_sensitivity(match_data):
    """
    爆冷定义：强队不胜（赔率最低方向未跑出）
    在爆冷场次中，统计各机构在赛前是否已出现"提前偏离"（偏向弱队）

    敏感度得分 = 在爆冷场次中，目标机构终赔已偏离基准≥0.025的次数
    """
    print("\n" + "═" * 70)
    print("【Phase 3】敏感度量化模型  —— 爆冷比赛中的提前偏离排名")
    print("═" * 70)

    upset_count = defaultdict(int)     # 各机构检测到的爆冷场次数（分母）
    advance_detect = defaultdict(int)  # 各机构提前偏离到正确方向的次数（分子）

    THRESHOLD = 0.025

    for match_id, companies in match_data.items():
        bench_curr = compute_golden_benchmark(companies)
        if not bench_curr:
            continue

        sample_row = next(iter(companies.values()))
        result = determine_match_result(sample_row)
        if result is None:
            continue

        # 判断强队：基准概率最高的方向为"强队方向"
        bench_max_side = max(
            [('home', bench_curr['home']),
             ('draw', bench_curr['draw']),
             ('away', bench_curr['away'])],
            key=lambda x: x[1]
        )[0]

        # 爆冷：强队方向未跑出（且胜率>55%才认为是强队）
        if bench_curr[bench_max_side] <= 0.55:
            continue
        if result == bench_max_side:
            continue  # 强队赢了，不是爆冷

        # 这是一场爆冷比赛
        # 检查各机构是否已预见到真实结果方向
        for cid in TARGET_INSTITUTIONS:
            row = companies.get(cid)
            if not row:
                continue
            h_c, d_c, a_c = odds_to_prob(row['current_home'], row['current_draw'], row['current_away'])
            if h_c is None:
                continue

            upset_count[cid] += 1

            target_prob = {'home': h_c, 'draw': d_c, 'away': a_c}[result]
            bench_prob  = bench_curr[result]
            delta = target_prob - bench_prob  # 正值=机构已在提前给出更高的结果概率

            if delta >= THRESHOLD:
                advance_detect[cid] += 1

    print(f"\n{'机构':<16} {'爆冷样本':>8} {'提前识别':>8} {'敏感度得分':>10} {'排名'}")
    print("─" * 60)

    scores = []
    for cid, name in TARGET_INSTITUTIONS.items():
        total = upset_count[cid]
        hits  = advance_detect[cid]
        if total < 10:
            continue
        score = hits / total
        scores.append((cid, name, total, hits, score))

    scores.sort(key=lambda x: -x[4])
    summary = {}
    for rank, (cid, name, total, hits, score) in enumerate(scores, 1):
        marker = " ← 最敏感机构" if rank == 1 else ""
        print(f"{name:<16} {total:>8} {hits:>8}  {score:>8.1%}  #{rank}{marker}")
        summary[cid] = {'name': name, 'total': total, 'hits': hits, 'score': score, 'rank': rank}

    return summary


# ─────────────────────────────────────────────────────────
# Phase 4: 聚类分析 + 异常捕捉 + 三大场景胜率归纳
# ─────────────────────────────────────────────────────────

def analyze_odds_clusters(match_data, target_cid=80):
    """
    按赔率区间聚类，在各区间内分析澳门偏离度的意义差异
    赔率区间（以主队欧赔划分）:
      [1.2, 1.5), [1.5, 1.8), [1.8, 2.1), [2.1, 2.6), [2.6+)
    """
    name = TARGET_INSTITUTIONS.get(target_cid, f"Company_{target_cid}")
    print(f"\n" + "═" * 70)
    print(f"【Phase 4A】赔率区间聚类  —— {name} 偏离度在不同赔率区间的含金量")
    print("═" * 70)

    bins = [(1.2, 1.5), (1.5, 1.8), (1.8, 2.1), (2.1, 2.6), (2.6, 10.0)]
    bin_labels = ["1.2-1.5(强热门)", "1.5-1.8(次热门)", "1.8-2.1(均势偏主)", "2.1-2.6(均势)", "2.6+(冷门)"]

    THRESHOLD = 0.025  # 2.5%绝对偏离

    for (lo, hi), label in zip(bins, bin_labels):
        records_high = []  # 澳门高于基准（诱导型）
        records_low  = []  # 澳门低于基准（防御型）

        for match_id, companies in match_data.items():
            target_row = companies.get(target_cid)
            if not target_row:
                continue

            home_odds = float(target_row.get('current_home') or 0)
            if not (lo <= home_odds < hi):
                continue

            bench = compute_golden_benchmark(companies)
            if not bench:
                continue

            sample_row = next(iter(companies.values()))
            result = determine_match_result(sample_row)
            if result is None:
                continue

            h, d, a = odds_to_prob(
                target_row['current_home'],
                target_row['current_draw'],
                target_row['current_away']
            )
            if h is None:
                continue

            # 主队方向偏离
            delta = h - bench['home']
            if delta > THRESHOLD:
                records_high.append(result)  # 澳门给高赔诱导 → 主队应不出
            elif delta < -THRESHOLD:
                records_low.append(result)   # 澳门压低主队 → 主队应跑出

        def stat(records, target_result, label_str):
            n = len(records)
            if n < 5:
                return f"  样本不足({n})"
            hit = sum(1 for r in records if r == target_result)
            rate = hit / n
            marker = " ✦✦" if rate >= 0.65 else (" ✦" if rate >= 0.58 else "")
            return f"  n={n:>3}, {label_str}: {rate:>6.1%}{marker}"

        print(f"\n  [{label}]")
        print(f"    高偏型(主队赔率高于基准>{THRESHOLD:.0%})——主队未出率:"
              + stat(records_high, 'home', '主队未出'))
        print(f"    低偏型(主队赔率低于基准>{THRESHOLD:.0%})——主队跑出率:"
              + stat(records_low, 'home', '主队跑出'))


def analyze_three_scenarios(match_data):
    """
    第四阶段第三步：胜率归纳 —— 三大核心场景
    场景1：澳门终赔概率 > 基准 0.03 → 统计该向下盘（未出）率
    场景2：澳门初终赔均低于基准 0.10+ → 统计上盘（跑出）率
    场景3：澳门终赔变动方向与基准相反 → 统计爆冷率（强队不胜）
    """
    print("\n" + "═" * 70)
    print("【Phase 4B】三大核心场景胜率归纳")
    print("═" * 70)

    target_cid = 80  # 澳门
    THRESHOLD_HIGH  = 0.03
    THRESHOLD_LOW   = 0.08
    OPPOSITE_MIN    = 0.02

    s1_records = []   # 场景1
    s2_records = []   # 场景2
    s3_records = []   # 场景3

    for match_id, companies in match_data.items():
        bench_init = compute_golden_benchmark_initial(companies)
        bench_curr = compute_golden_benchmark(companies)
        if not bench_init or not bench_curr:
            continue

        target_row = companies.get(target_cid)
        if not target_row:
            continue

        sample_row = next(iter(companies.values()))
        result = determine_match_result(sample_row)
        if result is None:
            continue

        h_i, d_i, a_i = odds_to_prob(
            target_row['initial_home'], target_row['initial_draw'], target_row['initial_away'])
        h_c, d_c, a_c = odds_to_prob(
            target_row['current_home'], target_row['current_draw'], target_row['current_away'])
        if None in (h_i, d_i, a_i, h_c, d_c, a_c):
            continue

        # 场景1：澳门终赔概率高于基准>3%（诱导型）→ 该方向未出
        for side, prob_c, bench_c in [
            ('home', h_c, bench_curr['home']),
            ('draw', d_c, bench_curr['draw']),
            ('away', a_c, bench_curr['away']),
        ]:
            delta = prob_c - bench_c
            if delta > THRESHOLD_HIGH:
                s1_records.append({'side': side, 'result': result})

        # 场景2：澳门初赔和终赔均低于基准8%+（全程防御）→ 该方向跑出
        for side, p_i, p_c, b_i, b_c in [
            ('home', h_i, h_c, bench_init['home'], bench_curr['home']),
            ('draw', d_i, d_c, bench_init['draw'], bench_curr['draw']),
            ('away', a_i, a_c, bench_init['away'], bench_curr['away']),
        ]:
            if (b_i - p_i) > THRESHOLD_LOW and (b_c - p_c) > THRESHOLD_LOW:
                s2_records.append({'side': side, 'result': result})

        # 场景3：澳门变动方向与基准相反（背离）
        for side, t_delta, b_delta in [
            ('home', h_c - h_i, bench_curr['home'] - bench_init['home']),
            ('draw', d_c - d_i, bench_curr['draw'] - bench_init['draw']),
            ('away', a_c - a_i, bench_curr['away'] - bench_init['away']),
        ]:
            if (abs(t_delta) >= OPPOSITE_MIN and abs(b_delta) >= OPPOSITE_MIN and
                    t_delta * b_delta < 0):   # 方向相反
                # 澳门的方向应该是正确的（逆基准）
                if t_delta > 0:
                    # 澳门提高该方向概率（降赔），预测该方向跑出
                    s3_records.append({'side': side, 'result': result, 'macao_dir': side})
                else:
                    # 澳门降低该方向概率（升赔），预测该方向不出
                    opposite = {'home': ['draw', 'away'], 'draw': ['home', 'away'], 'away': ['home', 'draw']}
                    for opp_side in opposite[side]:
                        s3_records.append({'side': opp_side, 'result': result, 'macao_dir': opp_side})

    def print_scenario(label, records, mode='not_hit'):
        n = len(records)
        if n < 10:
            print(f"  {label}: 样本不足 (n={n})")
            return
        if mode == 'not_hit':
            hit = sum(1 for r in records if r['result'] != r['side'])
            rate = hit / n
            direction = "未出率"
        else:
            hit = sum(1 for r in records if r['result'] == r['side'])
            rate = hit / n
            direction = "跑出率"
        marker = " ✦✦" if rate >= 0.65 else (" ✦" if rate >= 0.58 else "")
        print(f"  {label}: n={n}, {direction}={rate:.1%}{marker}")

    print(f"\n  场景1: 澳门终赔概率高于基准>{THRESHOLD_HIGH:.0%} → 该方向下盘（未出）率")
    print_scenario("  [场景1] 澳门高偏→该向未出", s1_records, 'not_hit')

    print(f"\n  场景2: 澳门初赔+终赔均低于基准>{THRESHOLD_LOW:.0%} → 该方向上盘（跑出）率")
    print_scenario("  [场景2] 澳门全程低偏→该向跑出", s2_records, 'hit')

    print(f"\n  场景3: 澳门变动方向与基准背离 → 跟随澳门方向胜率")
    print_scenario("  [场景3] 澳门背离基准→跟澳门方向", s3_records, 'hit')


# ─────────────────────────────────────────────────────────
# Phase 5: 机构间联合信号（澳门 + HKJC 双重信号）
# ─────────────────────────────────────────────────────────

def analyze_joint_signal(match_data):
    """
    当澳门(80)和HKJC(432)同时对某方向出现"不合群高赔"时，
    该方向的排除率（不出率）
    """
    print("\n" + "═" * 70)
    print("【Phase 5】澳门 × HKJC 联合信号分析")
    print("═" * 70)
    print("场景: 澳门和马会同时给出'高于基准>2%'的概率 → 该方向几乎必死")

    JOINT_THRESHOLD = 0.02
    records = []

    for match_id, companies in match_data.items():
        bench_curr = compute_golden_benchmark(companies)
        if not bench_curr:
            continue

        macao_row = companies.get(80)
        hkjc_row  = companies.get(432)
        if not macao_row or not hkjc_row:
            continue

        sample_row = next(iter(companies.values()))
        result = determine_match_result(sample_row)
        if result is None:
            continue

        m_h, m_d, m_a = odds_to_prob(
            macao_row['current_home'], macao_row['current_draw'], macao_row['current_away'])
        k_h, k_d, k_a = odds_to_prob(
            hkjc_row['current_home'], hkjc_row['current_draw'], hkjc_row['current_away'])

        if None in (m_h, m_d, m_a, k_h, k_d, k_a):
            continue

        for side, m_p, k_p, b_p in [
            ('home', m_h, k_h, bench_curr['home']),
            ('draw', m_d, k_d, bench_curr['draw']),
            ('away', m_a, k_a, bench_curr['away']),
        ]:
            m_delta = m_p - b_p
            k_delta = k_p - b_p
            if m_delta > JOINT_THRESHOLD and k_delta > JOINT_THRESHOLD:
                records.append({'side': side, 'result': result})

    n = len(records)
    if n >= 10:
        not_hit = sum(1 for r in records if r['result'] != r['side'])
        rate = not_hit / n
        marker = " ✦✦" if rate >= 0.65 else (" ✦" if rate >= 0.58 else "")
        print(f"\n  联合高偏信号: n={n}, 该方向未出率={rate:.1%}{marker}")
    else:
        print(f"\n  联合高偏信号: 样本不足 (n={n})")


# ─────────────────────────────────────────────────────────
# 主程序
# ─────────────────────────────────────────────────────────

def run_analysis(valid_matches, label="全量联赛"):
    """对一组比赛数据执行完整分析，返回汇总结果"""
    print(f"\n{'━'*70}")
    print(f"  📊 正在分析：{label}  (有效样本: {len(valid_matches)} 场)")
    print(f"{'━'*70}")

    dim_a = analyze_dimension_a(valid_matches)
    summary_a = summarize_dimension_a(dim_a)

    dim_b = analyze_dimension_b(valid_matches)
    summary_b = summarize_dimension_b(dim_b)

    dim_c = analyze_dimension_c(valid_matches)
    summary_c = summarize_dimension_c(dim_c)

    sensitivity = analyze_sensitivity(valid_matches)
    analyze_odds_clusters(valid_matches)
    analyze_three_scenarios(valid_matches)
    analyze_joint_signal(valid_matches)

    return summary_a, summary_b, summary_c, sensitivity


def print_comparison_table(all_summary, full_summary):
    """并排对比全量 vs 精选联赛的规律强度"""
    print("\n" + "═" * 90)
    print("【最终对比】全量联赛  vs  精选联赛（五大+一级）  规律准确率变化")
    print("═" * 90)
    print(f"{'规律描述':<32} {'全量胜率':>9} {'全量n':>6}  {'精选胜率':>9} {'精选n':>6}  {'变化':>7}")
    print("─" * 90)

    # 合并所有维度的key
    all_keys = set(all_summary.keys()) | set(full_summary.keys())

    rows = []
    for k in all_keys:
        a = all_summary.get(k, {})
        f = full_summary.get(k, {})
        if not a or not f:
            continue
        if a.get('sample', 0) < 20 and f.get('sample', 0) < 20:
            continue
        change = f.get('rate', 0) - a.get('rate', 0)
        label = f"{a.get('company','')}/{k.split('_',1)[-1]}"
        rows.append((f.get('rate', 0), label,
                     a.get('rate', 0), a.get('sample', 0),
                     f.get('rate', 0), f.get('sample', 0),
                     change))

    rows.sort(key=lambda x: -x[0])
    for elite_rate, label, all_rate, all_n, elite_r, elite_n, change in rows:
        if all_n < 20 and elite_n < 20:
            continue
        arrow = f"↑{change:+.1%}" if change > 0.005 else (f"↓{change:+.1%}" if change < -0.005 else "  →  ")
        marker = " ✦✦" if elite_rate >= 0.70 else (" ✦" if elite_rate >= 0.62 else "")
        print(f"{label:<32} {all_rate:>8.1%}  {all_n:>5}   {elite_r:>8.1%}  {elite_n:>5}  {arrow}{marker}")


def main():
    print("=" * 70)
    print("  多维度机构赔率偏离度分析 & 敏感度特征提取")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    print("\n连接数据库...")
    db = get_db()

    # ── 加载全量数据 ──────────────────────────────────────
    print("\n[A] 加载全量联赛数据（189个联赛）...")
    match_data_all = load_match_odds_data(db, elite_only=False)
    for cid, name in ALL_COMPANIES.items():
        count = sum(1 for c in match_data_all.values() if cid in c)
        print(f"  {name:<18}: {count} 场")
    valid_all = {
        mid: comps for mid, comps in match_data_all.items()
        if any(cid in comps for cid in GOLDEN_BENCHMARK)
        and any(cid in comps for cid in TARGET_INSTITUTIONS)
    }
    print(f"  → 有效分析样本: {len(valid_all)} 场")

    # ── 加载精选联赛数据 ──────────────────────────────────
    elite_names = {
        36: "英超", 31: "西甲", 8: "德甲", 34: "意甲", 11: "法甲",
        16: "荷甲", 23: "葡超", 30: "土超", 29: "苏超", 5: "比甲",
        32: "希超", 7: "丹超", 6: "波超", 10: "俄超", 119: "乌超",
        26: "瑞典超", 22: "挪威超", 137: "捷克甲", 3: "奥甲",
        25: "日本J1", 15: "韩K1", 21: "美MLS", 2: "阿根廷甲", 4: "巴西甲",
    }
    print(f"\n[B] 加载精选联赛数据（{len(ELITE_LEAGUE_IDS)}个精选联赛）...")
    print(f"  包含: {', '.join(elite_names.values())}")
    match_data_elite = load_match_odds_data(db, elite_only=True)
    for cid, name in ALL_COMPANIES.items():
        count = sum(1 for c in match_data_elite.values() if cid in c)
        print(f"  {name:<18}: {count} 场")
    valid_elite = {
        mid: comps for mid, comps in match_data_elite.items()
        if any(cid in comps for cid in GOLDEN_BENCHMARK)
        and any(cid in comps for cid in TARGET_INSTITUTIONS)
    }
    print(f"  → 有效分析样本: {len(valid_elite)} 场")

    db.close()

    # ── 执行两组分析 ──────────────────────────────────────
    print("\n" + "=" * 70)
    print("  第一轮：全量联赛分析")
    print("=" * 70)
    sa_all, sb_all, sc_all, sens_all = run_analysis(valid_all, "全量联赛（189个）")

    print("\n" + "=" * 70)
    print("  第二轮：精选联赛分析")
    print("=" * 70)
    sa_elite, sb_elite, sc_elite, sens_elite = run_analysis(valid_elite, f"精选联赛（{len(ELITE_LEAGUE_IDS)}个）")

    # ── 合并摘要做对比 ────────────────────────────────────
    def merge_summaries(*summaries):
        merged = {}
        for s in summaries:
            merged.update(s)
        return merged

    all_merged   = merge_summaries(sa_all,   sb_all,   sc_all)
    elite_merged = merge_summaries(sa_elite, sb_elite, sc_elite)
    print_comparison_table(all_merged, elite_merged)

    # ── 保存结果 ──────────────────────────────────────────
    output = {
        'run_time': datetime.now().isoformat(),
        'all_leagues': {
            'sample_size': len(valid_all),
            'dim_a': sa_all, 'dim_b': sb_all, 'dim_c': sc_all,
            'sensitivity': {str(k): v for k, v in sens_all.items()},
        },
        'elite_leagues': {
            'sample_size': len(valid_elite),
            'dim_a': sa_elite, 'dim_b': sb_elite, 'dim_c': sc_elite,
            'sensitivity': {str(k): v for k, v in sens_elite.items()},
        },
    }
    out_path = Path(__file__).parent / "institution_bias_results.json"
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n\n详细结果已保存至: {out_path}")


if __name__ == '__main__':
    main()
