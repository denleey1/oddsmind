#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竞争区间规则挖掘器 v1.0（独立版）
==================================
只在让方赔率 >= 1.70 的竞争区间内挖掘规则。
排除大热比赛(让方赔率<1.70)，这类比赛无需规则即可预测。

无项目依赖，只需 pymysql + numpy + pandas + scikit-learn。

用法:
    cd standalone
    pip install -r requirements.txt
    MYSQL_PASSWORD='xxx' python3 competitive_rule_miner.py

可选环境变量:
    MYSQL_HOST (默认 localhost)
    MYSQL_PORT (默认 3306)
    MYSQL_USER (默认 root)
    MYSQL_PASSWORD (必填)
    MYSQL_DATABASE (默认 oddsmind)
"""

import os, sys, math, warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold

warnings.filterwarnings('ignore')

from db import get_connection

# ==================== 配置 ====================
COMPANY_ID = 115
CV_FOLDS = 5
WILSON_Z = 1.96
MIN_HANDICAP_ODDS = 1.70  # 核心过滤：只看让方赔率 >= 1.70

BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']

# 输出目录
OUTPUT_DIR = Path(__file__).parent / 'output'


def get_range_type(range_str):
    if not range_str:
        return 'unknown'
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def wilson_ci(n_correct, n_total, z=WILSON_Z):
    if n_total == 0:
        return (0.0, 0.0)
    p = n_correct / n_total
    denom = 1 + z**2 / n_total
    center = (p + z**2 / (2 * n_total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z**2 / (4 * n_total)) / n_total) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def load_competitive_data():
    """加载竞争区间数据（让方赔率 >= 1.70）"""
    db = get_connection()
    query = '''
        SELECT
            oar.match_id,
            oar.initial_home_range, oar.initial_away_range,
            oar.current_home_range, oar.current_away_range,
            oar.initial_draw_range, oar.current_draw_range,
            oar.initial_home_offset, oar.initial_away_offset,
            oar.current_home_offset, oar.current_away_offset,
            oar.initial_home_theory_distance, oar.initial_away_theory_distance,
            oar.current_home_theory_distance, oar.current_away_theory_distance,
            oar.initial_home_fullwater, oar.initial_draw_fullwater, oar.initial_away_fullwater,
            oar.current_home_fullwater, oar.current_draw_fullwater, oar.current_away_fullwater,
            oar.initial_rule_diff, oar.current_rule_diff,
            oar.initial_draw_standard, oar.current_draw_standard,
            oar.power_diff,
            m.home_team_name, m.away_team_name,
            m.home_score, m.away_score, m.match_time, m.league_id,
            l.name_cn as league_name,
            eo.initial_home, eo.initial_draw, eo.initial_away,
            eo.current_home, eo.current_draw, eo.current_away,
            eo.kelly_home, eo.kelly_draw, eo.kelly_away,
            eo.initial_return_rate, eo.current_return_rate
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        JOIN european_odds eo ON oar.match_id = eo.match_id AND oar.company_id = eo.company_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = %s
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
          AND eo.initial_home > 0 AND eo.initial_away > 0
          AND eo.current_home != eo.current_away
          AND LEAST(eo.current_home, eo.current_away) >= %s
        ORDER BY m.match_time ASC
    '''
    rows = db.execute_query(query, (COMPANY_ID, MIN_HANDICAP_ODDS), fetch='all')
    return pd.DataFrame(rows)


def build_features(df):
    """构建特征（统一转换为让方/受让方视角）"""
    records = []
    for _, row in df.iterrows():
        ih = float(row['initial_home']); ia = float(row['initial_away'])
        ch = float(row['current_home']); ca = float(row['current_away'])
        id_ = float(row['initial_draw']); cd = float(row['current_draw'])

        if ih <= ia:
            h_score, r_score = int(row['home_score']), int(row['away_score'])
            init_h_range, init_r_range = row['initial_home_range'], row['initial_away_range']
            curr_h_range, curr_r_range = row['current_home_range'], row['current_away_range']
            i_h, i_r, c_h, c_r = ih, ia, ch, ca
            kh = float(row['kelly_home']) if row['kelly_home'] else None
            kr = float(row['kelly_away']) if row['kelly_away'] else None
            kd = float(row['kelly_draw']) if row['kelly_draw'] else None
            i_h_off = float(row['initial_home_offset']) if row['initial_home_offset'] is not None else None
            i_r_off = float(row['initial_away_offset']) if row['initial_away_offset'] is not None else None
            c_h_off = float(row['current_home_offset']) if row['current_home_offset'] is not None else None
            c_r_off = float(row['current_away_offset']) if row['current_away_offset'] is not None else None
            i_h_td = float(row['initial_home_theory_distance']) if row['initial_home_theory_distance'] is not None else None
            i_r_td = float(row['initial_away_theory_distance']) if row['initial_away_theory_distance'] is not None else None
        else:
            h_score, r_score = int(row['away_score']), int(row['home_score'])
            init_h_range, init_r_range = row['initial_away_range'], row['initial_home_range']
            curr_h_range, curr_r_range = row['current_away_range'], row['current_home_range']
            i_h, i_r, c_h, c_r = ia, ih, ca, ch
            kh = float(row['kelly_away']) if row['kelly_away'] else None
            kr = float(row['kelly_home']) if row['kelly_home'] else None
            kd = float(row['kelly_draw']) if row['kelly_draw'] else None
            i_h_off = float(row['initial_away_offset']) if row['initial_away_offset'] is not None else None
            i_r_off = float(row['initial_home_offset']) if row['initial_home_offset'] is not None else None
            c_h_off = float(row['current_away_offset']) if row['current_away_offset'] is not None else None
            c_r_off = float(row['current_home_offset']) if row['current_home_offset'] is not None else None
            i_h_td = float(row['initial_away_theory_distance']) if row['initial_away_theory_distance'] is not None else None
            i_r_td = float(row['initial_home_theory_distance']) if row['initial_home_theory_distance'] is not None else None

        pd_val = float(row['power_diff']) if row['power_diff'] is not None else 0.0
        h_chg = (c_h - i_h) / i_h if i_h > 0 else 0
        r_chg = (c_r - i_r) / i_r if i_r > 0 else 0
        d_chg = (cd - id_) / id_ if id_ > 0 else 0

        odds_sp = i_r - i_h
        curr_sp = c_r - c_h

        h_off_chg = (c_h_off - i_h_off) if (c_h_off is not None and i_h_off is not None) else None
        r_off_chg = (c_r_off - i_r_off) if (c_r_off is not None and i_r_off is not None) else None

        init_d_std = float(row['initial_draw_standard']) if row['initial_draw_standard'] else None
        curr_d_std = float(row['current_draw_standard']) if row['current_draw_standard'] else None
        init_d_fw = float(row['initial_draw_fullwater']) if row['initial_draw_fullwater'] else None
        curr_d_fw = float(row['current_draw_fullwater']) if row['current_draw_fullwater'] else None
        dr_init = (init_d_fw / init_d_std) if (init_d_fw and init_d_std and init_d_std > 0) else None
        dr_curr = (curr_d_fw / curr_d_std) if (curr_d_fw and curr_d_std and curr_d_std > 0) else None

        i_rr = float(row['initial_return_rate']) if row['initial_return_rate'] else None
        c_rr = float(row['current_return_rate']) if row['current_return_rate'] else None
        i_rd = float(row['initial_rule_diff']) if row['initial_rule_diff'] is not None else None
        c_rd = float(row['current_rule_diff']) if row['current_rule_diff'] is not None else None

        def chg_dir(pct):
            if pct > 0.05: return '升'
            elif pct < -0.05: return '降'
            return '稳'

        records.append({
            'match_id': row['match_id'], 'match_time': row['match_time'],
            'league_id': row['league_id'], 'h_score': h_score, 'r_score': r_score,
            # 连续
            'power_diff': pd_val,
            'init_h_offset': i_h_off, 'init_r_offset': i_r_off,
            'curr_h_offset': c_h_off, 'curr_r_offset': c_r_off,
            'h_offset_change': h_off_chg, 'r_offset_change': r_off_chg,
            'init_h_td': i_h_td, 'init_r_td': i_r_td,
            'kelly_h': kh, 'kelly_d': kd, 'kelly_r': kr,
            'h_change_pct': h_chg, 'r_change_pct': r_chg, 'd_change_pct': d_chg,
            'odds_spread': odds_sp, 'curr_odds_spread': curr_sp,
            'init_h_odds': i_h, 'init_r_odds': i_r,
            'curr_h_odds': c_h, 'curr_r_odds': c_r,
            'init_draw_odds': id_, 'curr_draw_odds': cd,
            'draw_ratio_init': dr_init, 'draw_ratio_curr': dr_curr,
            'init_return_rate': i_rr, 'curr_return_rate': c_rr,
            'init_rule_diff': i_rd, 'curr_rule_diff': c_rd,
            # 分类
            'cat_init_h': get_range_type(init_h_range),
            'cat_init_r': get_range_type(init_r_range),
            'cat_curr_h': get_range_type(curr_h_range),
            'cat_curr_r': get_range_type(curr_r_range),
            'cat_h_change': chg_dir(h_chg),
            'cat_r_change': chg_dir(r_chg),
            'cat_d_change': chg_dir(d_chg),
            'cat_init_draw': row['initial_draw_range'] or 'unknown',
            'cat_curr_draw': row['current_draw_range'] or 'unknown',
            'cat_is_big5': 1 if row['league_id'] in BIG5_LEAGUE_IDS else 0,
            # 目标
            'target_hn': 1 if h_score >= r_score else 0,
            'target_hw': 1 if h_score > r_score else 0,
            'target_rn': 1 if h_score <= r_score else 0,
        })

    full = pd.DataFrame(records)

    meta = ['match_id', 'match_time', 'league_id', 'h_score', 'r_score',
            'target_hn', 'target_hw', 'target_rn']
    feat_cols = [c for c in full.columns if c not in meta]
    cat_cols = [c for c in feat_cols if c.startswith('cat_')]
    num_cols = [c for c in feat_cols if not c.startswith('cat_')]

    X_num = full[num_cols].copy()
    for c in num_cols:
        X_num[c] = pd.to_numeric(X_num[c], errors='coerce')
        X_num[c] = X_num[c].fillna(X_num[c].median())

    X_cat = pd.get_dummies(full[cat_cols], prefix_sep='=', dtype=int)
    X = pd.concat([X_num, X_cat], axis=1)

    return X, full['target_hn'], full['target_hw'], full['target_rn'], full


# ==================== 规则提取 + 评估 ====================

def extract_paths(tree, features):
    paths = []
    t = tree.tree_
    def walk(nid, conds):
        if t.children_left[nid] == t.children_right[nid]:
            paths.append(list(conds)); return
        f, th = features[t.feature[nid]], t.threshold[nid]
        walk(t.children_left[nid], conds + [(f, '<=', th)])
        walk(t.children_right[nid], conds + [(f, '>', th)])
    walk(0, [])
    return paths


def eval_rule(conds, X, y, min_n=20, min_acc=0.70):
    mask = np.ones(len(X), dtype=bool)
    for f, op, th in conds:
        col = X[f].values
        mask &= (col <= th) if op == '<=' else (col > th)
    n = mask.sum()
    if n < min_n: return None
    nc = int(y.values[mask].sum())
    acc = nc / n
    if acc < min_acc: return None
    ci_lo, ci_hi = wilson_ci(nc, n)
    return {'conditions': conds, 'n': int(n), 'nc': nc, 'acc': acc,
            'ci_lo': ci_lo, 'ci_hi': ci_hi}


def fmt_cond(c):
    f, op, th = c
    if '=' in f and f.startswith('cat_'):
        cat_name = f.split('=', 1)[0].replace('cat_', '')
        cat_val = f.split('=', 1)[1]
        names = {'init_h': '初盘让方', 'init_r': '初盘受让方', 'curr_h': '即时让方',
                 'curr_r': '即时受让方', 'h_change': '让方变化', 'r_change': '受让方变化',
                 'd_change': '平赔变化', 'init_draw': '初盘平局', 'curr_draw': '即时平局',
                 'is_big5': '五大联赛'}
        cn = names.get(cat_name, cat_name)
        if op == '>' and th == 0.5: return f"{cn}={cat_val}"
        else: return f"{cn}!={cat_val}"
    names = {
        'power_diff': '力量差', 'init_h_offset': '初盘让方偏移', 'init_r_offset': '初盘受让方偏移',
        'curr_h_offset': '即时让方偏移', 'curr_r_offset': '即时受让方偏移',
        'h_offset_change': '让方偏移变化', 'r_offset_change': '受让方偏移变化',
        'kelly_h': '让方Kelly', 'kelly_d': '平Kelly', 'kelly_r': '受让方Kelly',
        'h_change_pct': '让方变化%', 'r_change_pct': '受让方变化%', 'd_change_pct': '平赔变化%',
        'odds_spread': '初盘赔率差', 'curr_odds_spread': '即时赔率差',
        'init_h_odds': '初盘让方赔率', 'init_r_odds': '初盘受让方赔率',
        'curr_h_odds': '即时让方赔率', 'curr_r_odds': '即时受让方赔率',
        'init_draw_odds': '初盘平赔', 'curr_draw_odds': '即时平赔',
        'draw_ratio_init': '初盘平赔比率', 'draw_ratio_curr': '即时平赔比率',
        'init_return_rate': '初盘返还率', 'curr_return_rate': '即时返还率',
        'init_rule_diff': '初盘规则差值', 'curr_rule_diff': '即时规则差值',
        'init_h_td': '初盘让方理论距离', 'init_r_td': '初盘受让方理论距离',
    }
    cn = names.get(f, f)
    return f"{cn} {op} {th:.3f}"


def fmt_rule(conds):
    return ' + '.join(fmt_cond(c) for c in conds)


def gen_lambda(conds):
    parts = []
    for f, op, th in conds:
        if '=' in f and f.startswith('cat_'):
            raw = f.split('=', 1)
            cn = raw[0].replace('cat_', '')
            cv = raw[1]
            fmap = {'init_h': 'init_h', 'init_r': 'init_r', 'curr_h': 'curr_h',
                    'curr_r': 'curr_r', 'h_change': 'h_change_simple',
                    'r_change': 'r_change_simple', 'd_change': 'd_change_simple',
                    'init_draw': 'init_draw', 'curr_draw': 'curr_draw', 'is_big5': 'is_big5'}
            field = fmap.get(cn, cn)
            if cn == 'is_big5':
                parts.append(f"m.get('is_big5') == {'True' if op == '>' else 'False'}")
            elif op == '>' and th == 0.5:
                parts.append(f"m.get('{field}') == '{cv}'")
            else:
                parts.append(f"m.get('{field}') != '{cv}'")
        else:
            nmap = {'power_diff': 'power_diff_val', 'h_change_pct': 'h_change_pct',
                    'r_change_pct': 'r_change_pct', 'd_change_pct': 'd_change_pct',
                    'odds_spread': 'odds_diff', 'curr_odds_spread': 'curr_odds_spread',
                    'kelly_h': 'kelly_h', 'kelly_d': 'kelly_d', 'kelly_r': 'kelly_r',
                    'init_h_offset': 'init_h_offset', 'init_r_offset': 'init_r_offset',
                    'curr_h_offset': 'curr_h_offset', 'curr_r_offset': 'curr_r_offset',
                    'curr_h_odds': 'h_odds', 'curr_r_odds': 'r_odds',
                    'draw_ratio_curr': 'draw_ratio_curr', 'draw_ratio_init': 'draw_ratio_init',
                    'curr_draw_odds': 'curr_draw_odds', 'init_draw_odds': 'init_draw_odds',
                    'init_h_odds': 'init_h_odds', 'init_r_odds': 'init_r_odds',
                    'curr_return_rate': 'curr_return_rate', 'init_return_rate': 'init_return_rate',
                    'init_rule_diff': 'init_rule_diff', 'curr_rule_diff': 'curr_rule_diff',
                    'h_offset_change': 'h_offset_change', 'r_offset_change': 'r_offset_change',
                    'init_h_td': 'init_h_td', 'init_r_td': 'init_r_td'}
            fn = nmap.get(f, f)
            parts.append(f"m['{fn}'] {op} {th:.4f}")
    return "lambda m: m['h_odds'] >= 1.70 and " + " and ".join(parts)


# ==================== 挖掘 ====================

def mine_rules(X, y, target_name, min_acc, min_n=20):
    """多策略挖掘"""
    feats = list(X.columns)
    all_rules = {}

    # --- 决策树多配置 ---
    for depth in [2, 3, 4]:
        for ml in [15, 20, 30]:
            for cw in [None, 'balanced']:
                tree = DecisionTreeClassifier(max_depth=depth, min_samples_leaf=ml,
                                              class_weight=cw, random_state=42)
                tree.fit(X, y)
                for path in extract_paths(tree, feats):
                    r = eval_rule(path, X, y, min_n=min_n, min_acc=min_acc)
                    if r:
                        name = fmt_rule(r['conditions'])
                        if name not in all_rules or r['acc'] > all_rules[name]['acc']:
                            all_rules[name] = r

    # --- 连续特征阈值扫描 ---
    num_cols = [c for c in X.columns if not c.startswith('cat_')]
    # 单特征
    for col in num_cols:
        vals = X[col].values
        valid = vals[~np.isnan(vals)]
        if len(valid) < 10: continue
        percs = np.percentile(valid, np.arange(10, 91, 5))
        for th in percs:
            for op, mfn in [('<=', lambda v, t: v <= t), ('>', lambda v, t: v > t)]:
                m = mfn(vals, th)
                n = m.sum()
                if n < min_n: continue
                nc = int(y.values[m].sum())
                acc = nc / n
                if acc >= min_acc:
                    conds = [(col, op, th)]
                    name = fmt_rule(conds)
                    ci_lo, _ = wilson_ci(nc, n)
                    if name not in all_rules or acc > all_rules[name]['acc']:
                        all_rules[name] = {'conditions': conds, 'n': n, 'nc': nc,
                                           'acc': acc, 'ci_lo': ci_lo, 'ci_hi': 0}

    # 双特征 (top 12)
    rf = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42, n_jobs=-1)
    rf.fit(X[num_cols], y)
    top_feats = pd.Series(rf.feature_importances_, index=num_cols).nlargest(12).index.tolist()

    for f1, f2 in combinations(top_feats, 2):
        v1, v2 = X[f1].values, X[f2].values
        p1 = np.percentile(v1[~np.isnan(v1)], np.arange(20, 81, 10))
        p2 = np.percentile(v2[~np.isnan(v2)], np.arange(20, 81, 10))
        for t1 in p1:
            for o1, mf1 in [('<=', lambda v, t: v <= t), ('>', lambda v, t: v > t)]:
                m1 = mf1(v1, t1)
                for t2 in p2:
                    for o2, mf2 in [('<=', lambda v, t: v <= t), ('>', lambda v, t: v > t)]:
                        mask = m1 & mf2(v2, t2)
                        n = mask.sum()
                        if n < min_n: continue
                        nc = int(y.values[mask].sum())
                        acc = nc / n
                        if acc >= min_acc:
                            conds = [(f1, o1, t1), (f2, o2, t2)]
                            name = fmt_rule(conds)
                            ci_lo, _ = wilson_ci(nc, n)
                            if name not in all_rules or acc > all_rules[name]['acc']:
                                all_rules[name] = {'conditions': conds, 'n': n, 'nc': nc,
                                                   'acc': acc, 'ci_lo': ci_lo, 'ci_hi': 0}

    rules = sorted(all_rules.values(), key=lambda r: (-r['acc'], -r['n']))
    return rules


def cross_validate(rules, X, y):
    """5折交叉验证"""
    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=42)
    results = []
    for rule in rules:
        t_n = t_c = 0
        fold_accs = []
        for _, test_idx in skf.split(X, y):
            Xt, yt = X.iloc[test_idx], y.iloc[test_idx]
            mask = np.ones(len(Xt), dtype=bool)
            for f, op, th in rule['conditions']:
                col = Xt[f].values
                mask &= (col <= th) if op == '<=' else (col > th)
            nm = int(mask.sum())
            if nm > 0:
                nc = int((yt.values[mask] == 1).sum())
                fold_accs.append(nc / nm)
                t_n += nm; t_c += nc
        if t_n == 0: continue
        cv_acc = t_c / t_n
        ci_lo, ci_hi = wilson_ci(t_c, t_n)
        results.append({
            **rule, 'cv_acc': cv_acc, 'cv_n': t_n, 'cv_nc': t_c,
            'cv_ci_lo': ci_lo, 'cv_ci_hi': ci_hi,
            'cv_std': np.std(fold_accs) if len(fold_accs) > 1 else 0,
        })
    results.sort(key=lambda r: (-r['cv_acc'], -r['cv_n']))
    return results


def time_validate(rules, X, y, full_df):
    """时间序列验证（前80%训练期，后20%测试期）"""
    sp = int(len(X) * 0.8)
    Xt, yt = X.iloc[sp:], y.iloc[sp:]
    results = []
    for rule in rules:
        mask = np.ones(len(Xt), dtype=bool)
        for f, op, th in rule['conditions']:
            col = Xt[f].values
            mask &= (col <= th) if op == '<=' else (col > th)
        nm = int(mask.sum())
        if nm < 5: continue
        nc = int((yt.values[mask] == 1).sum())
        tacc = nc / nm
        ci_lo, ci_hi = wilson_ci(nc, nm)
        results.append({
            **rule, 'time_acc': tacc, 'time_n': nm, 'time_nc': nc,
            'time_ci_lo': ci_lo, 'time_ci_hi': ci_hi,
        })
    results.sort(key=lambda r: (-r['time_acc'], -r['time_n']))
    return results


def feature_importance(X, y, name):
    """随机森林特征重要性"""
    rf = RandomForestClassifier(n_estimators=200, max_depth=5, min_samples_leaf=20,
                                class_weight='balanced', random_state=42, n_jobs=-1)
    rf.fit(X, y)
    imp = pd.DataFrame({'feature': X.columns, 'importance': rf.feature_importances_})
    imp = imp.sort_values('importance', ascending=False)
    print(f"\n  特征重要性 Top 20 ({name}):")
    print(f"  {'#':>3} {'特征':<40} {'重要性':>8}")
    print(f"  {'-'*55}")
    for i, (_, r) in enumerate(imp.head(20).iterrows(), 1):
        bar = '#' * int(r['importance'] * 200)
        print(f"  {i:>3} {r['feature']:<40} {r['importance']:.4f} {bar}")
    return imp


# ==================== 主函数 ====================

def main():
    print("=" * 80)
    print(f"  竞争区间规则挖掘器 v1.0（独立版）— 只看让方赔率 >= {MIN_HANDICAP_ODDS}")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    raw = load_competitive_data()
    print(f"\n加载竞争区间数据: {len(raw)} 场 (让方赔率 >= {MIN_HANDICAP_ODDS})")

    X, y_hn, y_hw, y_rn, full = build_features(raw)
    print(f"特征矩阵: {X.shape[1]} 特征, {len(X)} 样本")
    print(f"\n竞争区间基线:")
    print(f"  让方不输: {y_hn.mean()*100:.1f}% ({y_hn.sum()}/{len(y_hn)})")
    print(f"  让方必赢: {y_hw.mean()*100:.1f}% ({y_hw.sum()}/{len(y_hw)})")
    print(f"  受让方不输: {y_rn.mean()*100:.1f}% ({y_rn.sum()}/{len(y_rn)})")

    sp = int(len(X) * 0.8)
    train_end = full.iloc[:sp]['match_time'].max()
    test_start = full.iloc[sp:]['match_time'].min()
    print(f"\n时间切分: 训练 {sp} 场 (至 {train_end}), 测试 {len(X)-sp} 场 (从 {test_start})")

    targets = [
        ('让方不输', y_hn, 0.82, 20),  # 基线~74%, 要求82%+
        ('让方必赢', y_hw, 0.60, 20),  # 基线~47%, 要求60%+
        ('受让方不输', y_rn, 0.60, 20),# 基线~53%, 要求60%+
    ]

    report_lines = []

    for name, y, min_acc, min_n in targets:
        print(f"\n\n{'#'*80}")
        print(f"#  目标: {name}  (基线: {y.mean()*100:.1f}%, 阈值: {min_acc*100:.0f}%)")
        print(f"{'#'*80}")

        # 特征重要性
        imp = feature_importance(X, y, name)

        # 挖掘
        rules = mine_rules(X, y, name, min_acc=min_acc, min_n=min_n)
        print(f"\n  找到 {len(rules)} 条候选规则")

        if not rules:
            print("  (无规则)")
            report_lines.append(f"\n# {name}: 无规则")
            continue

        # 交叉验证
        print(f"\n  === 交叉验证 ===")
        cv = cross_validate(rules, X, y)
        print(f"  CV Top 10:")
        print(f"  {'#':>3} {'全量':>7} {'CV':>7} {'样本':>6} {'CI下界':>7} {'std':>7}  规则")
        for i, r in enumerate(cv[:10]):
            print(f"  {i+1:>3} {r['acc']*100:>6.1f}% {r['cv_acc']*100:>6.1f}% {r['cv_n']:>6} "
                  f"{r['cv_ci_lo']*100:>6.1f}% {r['cv_std']*100:>6.1f}%  {fmt_rule(r['conditions'])}")

        # 时间验证
        print(f"\n  === 时间序列验证 ===")
        tv = time_validate(rules, X, y, full)
        print(f"  时间 Top 10:")
        print(f"  {'#':>3} {'全量':>7} {'测试':>7} {'样本':>6} {'CI下界':>7}  规则")
        for i, r in enumerate(tv[:10]):
            print(f"  {i+1:>3} {r['acc']*100:>6.1f}% {r['time_acc']*100:>6.1f}% {r['time_n']:>6} "
                  f"{r['time_ci_lo']*100:>6.1f}%  {fmt_rule(r['conditions'])}")

        # 双重验证
        cv_map = {fmt_rule(r['conditions']): r for r in cv}
        tv_map = {fmt_rule(r['conditions']): r for r in tv}

        cv_threshold = min_acc - 0.02
        time_threshold = min_acc - 0.05

        dual = []
        for rn in cv_map:
            if rn in tv_map:
                cr, tr = cv_map[rn], tv_map[rn]
                if cr['cv_acc'] >= cv_threshold and tr['time_acc'] >= time_threshold:
                    dual.append({
                        'name': rn, 'conditions': cr['conditions'],
                        'full_acc': cr['acc'], 'full_n': cr['n'],
                        'cv_acc': cr['cv_acc'], 'cv_n': cr['cv_n'],
                        'cv_ci_lo': cr['cv_ci_lo'], 'cv_std': cr['cv_std'],
                        'time_acc': tr['time_acc'], 'time_n': tr['time_n'],
                        'time_ci_lo': tr['time_ci_lo'],
                    })
        dual.sort(key=lambda r: -(r['cv_acc'] * 0.6 + r['time_acc'] * 0.4))

        print(f"\n  === 双重验证通过 (CV>={cv_threshold*100:.0f}% 且 时间>={time_threshold*100:.0f}%) ===")
        if dual:
            for i, d in enumerate(dual[:15]):
                print(f"\n  [{i+1}] {d['name']}")
                print(f"      全量: n={d['full_n']}, acc={d['full_acc']*100:.1f}%")
                print(f"      CV:   n={d['cv_n']}, acc={d['cv_acc']*100:.1f}%, CI下界={d['cv_ci_lo']*100:.1f}%, std={d['cv_std']*100:.1f}%")
                print(f"      时间: n={d['time_n']}, acc={d['time_acc']*100:.1f}%, CI下界={d['time_ci_lo']*100:.1f}%")
        else:
            print("  (无)")

        # 生成规则代码
        report_lines.append(f"\n# --- {name} 规则 (竞争区间: 让方赔率>={MIN_HANDICAP_ODDS}) ---")
        code_rules = dual[:10] if dual else []
        for i, d in enumerate(code_rules):
            rid = f"C{name[:2]}{i+1:03d}"
            lam = gen_lambda(d['conditions'])
            report_lines.append(f"""
{{
    'id': '{rid}',
    'name': '{d['name']}',
    'predict': '{name}',
    'condition': {lam},
    'apply_to': 'competitive',
    'accuracy': {d['cv_acc']:.3f},
    'sample': {d['cv_n']},
    'description': '竞争区间(让方>={MIN_HANDICAP_ODDS}): {d['name']}',
    'cv_ci_low': {d['cv_ci_lo']:.3f},
    'time_acc': {d['time_acc']:.3f},
    'time_n': {d['time_n']},
}},""")

    # 保存报告
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    rfile = OUTPUT_DIR / f'competitive_rules_{ts}.txt'
    with open(rfile, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report_lines))
    print(f"\n规则代码已保存: {rfile}")

    print("\n" + "=" * 80)
    print("  完成")
    print("=" * 80)


if __name__ == '__main__':
    main()
