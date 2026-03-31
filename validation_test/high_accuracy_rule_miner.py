#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
高精度规则挖掘器 v2.0
======================
从历史已结算比赛中挖掘"让方不输"高准确率规则。

设计原则:
  1. 特征与线上系统完全一致 (odds_changes 优先, european_odds 回退)
  2. 时间分割 OOS: 训练集=早于 TRAIN_CUTOFF, 验证集=之后
  3. 严格过滤:  训练准确率 >= TRAIN_ACC  且  OOS样本 >= OOS_MIN_N  且  OOS准确率 >= OOS_ACC
  4. 同根去重:  相同特征对只保留阈值最优组合
  5. 输出即可直接粘贴进 auto_rule_matcher_logic_ops.py

公司映射:
  115 = 威廉希尔 (William Hill)  前缀 w
   80 = 澳门               (Macau)      前缀 m
   82 = 立博               (Ladbrokes)  前缀 l
"""
import os
import sys, json, time
from pathlib import Path
from collections import defaultdict
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple, Any
import itertools

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

import pymysql

# ==================== 超参数 ====================
DB_CFG = dict(host='localhost', user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
              database='oddsmind', charset='utf8mb4')

# 时间分割
TRAIN_CUTOFF = '2025-11-01'   # 训练集截止（不含）
OOS_START    = '2025-11-01'   # OOS 开始

# 过滤条件
TRAIN_MIN_N   = 60    # 训练样本下限
TRAIN_ACC     = 0.87  # 训练准确率下限
OOS_MIN_N     = 30    # OOS 样本下限
OOS_ACC       = 0.83  # OOS 准确率下限 (稍低，允许小幅衰减)

# 竞争区间: 让方赔率下限 (与线上保持一致)
MIN_H_ODDS = 1.70

COMPANY_MAP = {115: 'w', 80: 'm', 82: 'l'}


# ==================== 数据加载 ====================

def load_data(db: pymysql.connections.Connection) -> List[Dict]:
    """
    加载所有已结算比赛的特征 + 标签 (让方不输=1, 让方输=0)。
    """
    cur = db.cursor(pymysql.cursors.DictCursor)

    print("[1/4] 加载已结算比赛...", flush=True)
    cur.execute("""
        SELECT match_id, match_time, league_id,
               home_score, away_score
        FROM matches
        WHERE match_status='finished'
          AND home_score IS NOT NULL
          AND away_score IS NOT NULL
        ORDER BY match_time
    """)
    matches = {r['match_id']: r for r in cur.fetchall()}
    print(f"      共 {len(matches)} 场")

    print("[2/4] 加载赔率 (odds_changes)...", flush=True)
    cur.execute("""
        SELECT match_id, company_id,
               initial_home, initial_draw, initial_away, initial_return_rate,
               current_home, current_draw, current_away, current_return_rate
        FROM odds_changes
        WHERE company_id IN (115, 80, 82)
          AND initial_home > 1.0
          AND current_home > 1.0
    """)
    oc_rows = cur.fetchall()
    oc: Dict[int, Dict[str,Dict]] = defaultdict(dict)
    for r in oc_rows:
        pfx = COMPANY_MAP[r['company_id']]
        oc[r['match_id']][pfx] = r
    print(f"      {len(oc_rows)} 条记录, 覆盖 {len(oc)} 场")

    print("[3/4] 加载赔率 (european_odds 补全缺失)...", flush=True)
    cur.execute("""
        SELECT match_id, company_id,
               initial_home, initial_draw, initial_away, initial_return_rate,
               current_home, current_draw, current_away, current_return_rate,
               kelly_home, kelly_draw, kelly_away
        FROM european_odds
        WHERE company_id IN (115, 80, 82)
          AND initial_home > 1.0
          AND current_home > 1.0
    """)
    eo_rows = cur.fetchall()
    eo: Dict[int, Dict[str,Dict]] = defaultdict(dict)
    for r in eo_rows:
        pfx = COMPANY_MAP[r['company_id']]
        eo[r['match_id']][pfx] = r
    print(f"      {len(eo_rows)} 条记录")

    print("[4/4] 特征工程...", flush=True)
    records = []
    skipped = 0
    for mid, m in matches.items():
        odds = {}
        for pfx in ('w','m','l'):
            if mid in oc and pfx in oc[mid]:
                odds[pfx] = oc[mid][pfx]
            elif mid in eo and pfx in eo[mid]:
                odds[pfx] = eo[mid][pfx]

        # 至少需要威廉 + (澳门 or 立博)
        if 'w' not in odds or ('m' not in odds and 'l' not in odds):
            skipped += 1
            continue

        f = float
        def _f(v):
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None

        # 让方判断: 初盘威廉低赔方
        w_ih = _f(odds['w']['initial_home'])
        w_ia = _f(odds['w']['initial_away'])
        if not w_ih or not w_ia or w_ih <= 0 or w_ia <= 0:
            skipped += 1
            continue

        home_is_h = (w_ih <= w_ia)  # True=主队是让方

        # 竞争区间检查
        h_init = w_ih if home_is_h else w_ia
        if h_init < MIN_H_ODDS:
            skipped += 1
            continue

        # 标签: 让方不输 (win or draw from 让方's perspective)
        hs, as_ = m['home_score'], m['away_score']
        if home_is_h:
            label = 1 if hs >= as_ else 0
        else:
            label = 1 if as_ >= hs else 0

        feat: Dict[str, Any] = {
            'match_id': mid,
            'match_time': m['match_time'],
            'league_id': m['league_id'],
            'home_is_h': home_is_h,
            'label': label,
        }

        for pfx in ('w','m','l'):
            if pfx not in odds:
                continue
            o = odds[pfx]
            ih = _f(o['initial_home'])
            ia = _f(o['initial_away'])
            id_ = _f(o['initial_draw'])
            ch = _f(o['current_home'])
            ca = _f(o['current_away'])
            cd = _f(o['current_draw'])
            irr = _f(o['initial_return_rate'])
            crr = _f(o['current_return_rate'])

            # 让方/受让方 视角
            fav_ih = ih if home_is_h else ia
            dog_ih = ia if home_is_h else ih
            fav_ch = ch if home_is_h else ca
            dog_ch = ca if home_is_h else ch

            # Kelly (仅 european_odds 有)
            fav_kh = _f(o.get('kelly_home')) if home_is_h else _f(o.get('kelly_away'))
            dog_kh = _f(o.get('kelly_away')) if home_is_h else _f(o.get('kelly_home'))

            hc = (fav_ch - fav_ih) / fav_ih if fav_ih and fav_ih > 0 else None
            rc = (dog_ch - dog_ih) / dog_ih if dog_ih and dog_ih > 0 else None
            spread_i = dog_ih - fav_ih if dog_ih and fav_ih else None
            spread_c = dog_ch - fav_ch if dog_ch and fav_ch else None
            id_ratio = id_ / fav_ih if id_ and fav_ih else None  # 初盘 平/让方比

            feat[f'{pfx}_ih']     = fav_ih      # 初盘让方赔率
            feat[f'{pfx}_ir']     = dog_ih      # 初盘受让方赔率
            feat[f'{pfx}_h']      = fav_ch      # 即时让方赔率
            feat[f'{pfx}_r']      = dog_ch      # 即时受让方赔率
            feat[f'{pfx}_id']     = id_         # 初盘平赔
            feat[f'{pfx}_d']      = cd          # 即时平赔
            feat[f'{pfx}_irr']    = irr         # 初盘返还率
            feat[f'{pfx}_crr']    = crr         # 即时返还率
            feat[f'{pfx}_hc']     = hc          # 让方变化%
            feat[f'{pfx}_rc']     = rc          # 受让方变化%
            feat[f'{pfx}_spread_i']= spread_i   # 初盘赔率差
            feat[f'{pfx}_spread_c']= spread_c   # 即时赔率差
            feat[f'{pfx}_id_ratio']= id_ratio   # 初盘平让比
            feat[f'{pfx}_kh']     = fav_kh      # 让方Kelly
            feat[f'{pfx}_kr']     = dog_kh      # 受让方Kelly

        # 多公司组合特征
        wh_irr = feat.get('w_irr') or 0.0
        mac_irr = feat.get('m_irr') or 0.0
        lb_irr  = feat.get('l_irr') or 0.0
        feat['wm_irr_diff'] = (wh_irr - mac_irr) if wh_irr and mac_irr else None
        feat['wl_irr_diff'] = (wh_irr - lb_irr)  if wh_irr and lb_irr  else None

        # 三公司让方变化均值
        hcs = [v for v in [feat.get('w_hc'), feat.get('m_hc'), feat.get('l_hc')] if v is not None]
        feat['avg_hc'] = sum(hcs)/len(hcs) if hcs else None
        rcs = [v for v in [feat.get('w_rc'), feat.get('m_rc'), feat.get('l_rc')] if v is not None]
        feat['avg_rc'] = sum(rcs)/len(rcs) if rcs else None

        # 三公司受让方均值
        rs = [v for v in [feat.get('w_r'), feat.get('m_r'), feat.get('l_r')] if v is not None]
        feat['avg_r'] = sum(rs)/len(rs) if rs else None
        hs2 = [v for v in [feat.get('w_h'), feat.get('m_h'), feat.get('l_h')] if v is not None]
        feat['avg_h'] = sum(hs2)/len(hs2) if hs2 else None

        records.append(feat)

    print(f"      有效样本: {len(records)}, 跳过: {skipped}")
    return records


# ==================== 规则挖掘 ====================

# 候选特征 + 方向 (特征名, 方向 '>' or '<', 描述)
CANDIDATE_FEATURES = [
    # 即时赔率
    ('w_h',       '<',  '威廉即时让方'),
    ('w_r',       '>',  '威廉即时受让方'),
    ('m_h',       '<',  '澳门即时让方'),
    ('m_r',       '>',  '澳门受让方'),
    ('l_h',       '<',  '立博即时让方'),
    ('l_r',       '>',  '立博受让方'),
    # 初盘赔率
    ('w_ih',      '<',  '威廉初盘让方'),
    ('w_ir',      '>',  '威廉初盘受让方'),
    ('m_ih',      '<',  '澳门初盘让方'),
    ('m_ir',      '>',  '澳门初盘受让方'),
    ('l_ir',      '>',  '立博初盘受让方'),
    # 赔率变化%
    ('w_hc',      '>',  '威廉让方变化%'),
    ('w_hc',      '<',  '威廉让方变化%'),
    ('w_rc',      '>',  '威廉受让方变化%'),
    ('w_rc',      '<',  '威廉受让方变化%'),
    ('m_hc',      '>',  '澳门让方变化%'),
    ('m_rc',      '>',  '澳门受让方变化%'),
    ('m_rc',      '<',  '澳门受让方变化%'),
    ('l_hc',      '>',  '立博让方变化%'),
    ('l_rc',      '<',  '立博受让方变化%'),
    # 赔率差
    ('w_spread_i','>', '威廉初盘赔率差'),
    ('m_spread_i','>', '澳门初盘赔率差'),
    ('l_spread_i','>', '立博初盘赔率差'),
    # 返还率差
    ('wm_irr_diff','>', '威澳返还率差'),
    ('wl_irr_diff','>', '威立返还率差'),
    # 即时返还率
    ('w_crr',     '<',  '威廉即时返还率'),
    # 三公司均值
    ('avg_rc',    '>',  '三公司受让方变化%均值'),
    ('avg_rc',    '<',  '三公司受让方变化%均值'),
    ('avg_hc',    '>',  '三公司让方变化%均值'),
    ('avg_r',     '>',  '三公司受让方均值'),
    # Kelly
    ('w_kh',      '>',  '威廉让方Kelly'),
    ('w_kr',      '<',  '威廉受让方Kelly'),
    # 平赔比
    ('w_id_ratio','<',  '威廉初盘平让比'),
]

def get_thresholds(data: List[Dict], feat: str, direction: str) -> List[float]:
    """
    从数据中提取候选阈值: 取该特征所有非空值的百分位点。
    """
    vals = sorted([r[feat] for r in data if r.get(feat) is not None])
    if len(vals) < 20:
        return []
    # 取 10%~90% 分位数, 每隔 5% 一个阈值
    percs = list(range(10, 91, 5))
    n = len(vals)
    thresholds = []
    seen = set()
    for p in percs:
        idx = int(n * p / 100)
        v = round(vals[min(idx, n-1)], 3)
        if v not in seen:
            seen.add(v)
            thresholds.append(v)
    return thresholds


def apply_cond(row: Dict, feat: str, direction: str, threshold: float) -> bool:
    v = row.get(feat)
    if v is None:
        return False
    if direction == '>':
        return v > threshold
    else:
        return v < threshold


def mine_2cond_rules(train: List[Dict], oos: List[Dict]) -> List[Dict]:
    """
    双条件规则挖掘: C(features, 2) 组合
    """
    results = []
    total_combos = len(CANDIDATE_FEATURES) * (len(CANDIDATE_FEATURES) - 1) // 2
    done = 0
    t0 = time.time()

    for i, (f1, d1, n1) in enumerate(CANDIDATE_FEATURES):
        # 预计算 f1 阈值
        t1_list = get_thresholds(train, f1, d1)
        if not t1_list:
            continue

        for j, (f2, d2, n2) in enumerate(CANDIDATE_FEATURES):
            if j <= i:
                continue
            done += 1

            t2_list = get_thresholds(train, f2, d2)
            if not t2_list:
                continue

            # 对每对 (t1, t2) 组合
            best = None
            for t1 in t1_list:
                # 先过滤 f1 条件
                sub = [r for r in train if apply_cond(r, f1, d1, t1)]
                if len(sub) < TRAIN_MIN_N:
                    continue
                for t2 in t2_list:
                    # 不允许两个条件使用完全相同特征
                    if f1 == f2:
                        continue
                    hits = [r for r in sub if apply_cond(r, f2, d2, t2)]
                    n = len(hits)
                    if n < TRAIN_MIN_N:
                        continue
                    acc = sum(r['label'] for r in hits) / n
                    if acc < TRAIN_ACC:
                        continue

                    # OOS 验证
                    oos_hits = [r for r in oos
                                if apply_cond(r, f1, d1, t1)
                                and apply_cond(r, f2, d2, t2)]
                    oos_n = len(oos_hits)
                    if oos_n < OOS_MIN_N:
                        continue
                    oos_acc = sum(r['label'] for r in oos_hits) / oos_n
                    if oos_acc < OOS_ACC:
                        continue

                    score = oos_acc * 0.6 + acc * 0.4  # 综合排序
                    if best is None or score > best['score']:
                        best = {
                            'f1': f1, 'd1': d1, 't1': t1, 'n1': n1,
                            'f2': f2, 'd2': d2, 't2': t2, 'n2': n2,
                            'train_n': n, 'train_acc': round(acc*100, 1),
                            'oos_n': oos_n, 'oos_acc': round(oos_acc*100, 1),
                            'score': score,
                        }

            if best:
                results.append(best)

        # 进度输出
        if (i+1) % 5 == 0:
            elapsed = time.time() - t0
            print(f"  进度: {i+1}/{len(CANDIDATE_FEATURES)} 特征组 | "
                  f"已找到 {len(results)} 条候选 | 耗时 {elapsed:.0f}s", flush=True)

    return results


# ==================== 去重 & 格式化 ====================

def dedup_rules(rules: List[Dict]) -> List[Dict]:
    """
    同根去重: 相同 (f1,d1,f2,d2) 只保留 score 最高的一条。
    """
    best_map: Dict[Tuple, Dict] = {}
    for r in rules:
        key = tuple(sorted([(r['f1'],r['d1']), (r['f2'],r['d2'])]))
        if key not in best_map or r['score'] > best_map[key]['score']:
            best_map[key] = r
    return sorted(best_map.values(), key=lambda x: -x['oos_acc'])


def format_rule(r: Dict, idx: int) -> str:
    def cond_str(feat, direction, threshold, name):
        sign = '>' if direction == '>' else '<='
        # 百分号字段
        if 'c' in feat and ('hc' in feat or 'rc' in feat or 'avg' in feat):
            return f"{name}{sign}{threshold*100:.1f}%"
        return f"{name}{sign}{threshold}"

    c1 = cond_str(r['f1'], r['d1'], r['t1'], r['n1'])
    c2 = cond_str(r['f2'], r['d2'], r['t2'], r['n2'])
    return (f"  NEW-HN{idx:02d}  {c1} + {c2}  "
            f"| 训练: {r['train_acc']}%(n={r['train_n']})  "
            f"OOS: {r['oos_acc']}%(n={r['oos_n']})")


def generate_rule_code(r: Dict, idx: int) -> str:
    """生成可粘贴到 logic_ops.py 的规则代码片段"""
    def cond_py(feat, direction, threshold):
        sign = '>' if direction == '>' else '<'
        return f"feat.get('{feat}') is not None and feat['{feat}'] {sign} {threshold}"
    c1 = cond_py(r['f1'], r['d1'], r['t1'])
    c2 = cond_py(r['f2'], r['d2'], r['t2'])
    
    def name_str(feat, direction, threshold, name):
        sign = '>' if direction == '>' else '<='
        if 'hc' in feat or 'rc' in feat or 'avg_hc' in feat or 'avg_rc' in feat:
            return f"{name}{sign}{threshold*100:.1f}%"
        return f"{name}{sign}{threshold}"

    desc = (f"{name_str(r['f1'],r['d1'],r['t1'],r['n1'])} + "
            f"{name_str(r['f2'],r['d2'],r['t2'],r['n2'])} → "
            f"OOS {r['oos_acc']}%(n={r['oos_n']})")
    
    return f"""    add_rule('S', 'NEW-HN{idx:02d}', '{desc}',
             lambda feat: ({c1})
                       and ({c2})),"""


# ==================== 主程序 ====================

def main():
    print("=" * 60)
    print("高精度规则挖掘器 v2.0")
    print(f"训练集: < {TRAIN_CUTOFF}  |  OOS: >= {OOS_START}")
    print(f"目标: 训练 ACC>={TRAIN_ACC*100:.0f}% n>={TRAIN_MIN_N}  "
          f"OOS ACC>={OOS_ACC*100:.0f}% n>={OOS_MIN_N}")
    print("=" * 60)

    db = pymysql.connect(**DB_CFG)

    records = load_data(db)
    db.close()

    # 按时间分割
    train = [r for r in records
             if r['match_time'] and str(r['match_time'])[:10] < TRAIN_CUTOFF]
    oos   = [r for r in records
             if r['match_time'] and str(r['match_time'])[:10] >= OOS_START]

    print(f"\n训练集: {len(train)} 场 (让方不输率: "
          f"{sum(r['label'] for r in train)/len(train)*100:.1f}%)")
    print(f"OOS集:  {len(oos)} 场 (让方不输率: "
          f"{sum(r['label'] for r in oos)/len(oos)*100:.1f}%)")

    t0 = time.time()
    print(f"\n开始挖掘规则 (特征数={len(CANDIDATE_FEATURES)}, "
          f"组合数~{len(CANDIDATE_FEATURES)*(len(CANDIDATE_FEATURES)-1)//2})...", flush=True)

    rules = mine_2cond_rules(train, oos)
    rules = dedup_rules(rules)

    elapsed = time.time() - t0
    print(f"\n挖掘完成! 耗时 {elapsed:.0f}s, 找到 {len(rules)} 条通过筛选的规则")
    print()

    print("=" * 60)
    print("TOP 规则 (按 OOS 准确率排序)")
    print("=" * 60)
    for i, r in enumerate(rules[:40], 1):
        print(format_rule(r, i))

    # 输出可以直接集成的代码
    print()
    print("=" * 60)
    print("生成代码 (可粘贴到 auto_rule_matcher_logic_ops.py)")
    print("=" * 60)
    for i, r in enumerate(rules[:20], 1):
        print(generate_rule_code(r, i))

    # 保存完整结果
    out_path = Path(__file__).parent / 'mined_rules_v2.json'
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(rules, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n完整结果已保存至: {out_path}")


if __name__ == '__main__':
    main()
