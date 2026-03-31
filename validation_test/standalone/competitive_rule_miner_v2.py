#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竞争区间规则挖掘器 v2.0（多公司 · 纯数值 · european_odds）
=============================================================
基于 european_odds 表的三公司(威廉115/澳门80/立博82)纯数值特征
挖掘高精度规则，支持时间切分 + 四重过拟合检测。

不依赖 odds_analysis_results，所有规则仅需 european_odds 或
odds_changes 即可运行。

用法:
    cd validation_test/standalone
    MYSQL_PASSWORD='xxx' python3 competitive_rule_miner_v2.py

可选环境变量:
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
"""

import os, sys, math, warnings, json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold

warnings.filterwarnings('ignore')

from db import get_connection

# ==================== 配置 ====================
COMPANIES = [(115, 'w'), (80, 'm'), (82, 'l')]
MIN_HANDICAP_ODDS = 1.70
CV_FOLDS = 5
WILSON_Z = 1.96
TRAIN_RATIO = 0.80

# 挖掘阈值
H_MIN_ACC = 0.80       # 让方不输: 基线~73%, 要求80%+
R_MIN_ACC = 0.65        # 受让不输: 基线~55%, 要求65%+
MIN_SAMPLE_TRAIN = 25   # 训练集最小样本
MIN_SAMPLE_OOS = 30     # OOS最小样本 (提高到30确保稳健)
OVERFIT_GAP = 0.05      # 训练-CV最大允许落差
BASELINE_LIFT = 0.05    # Wilson CI下界必须>基线+此值
MAX_RULES_PER_SIDE = 25 # 每个方向最多保留规则数

# 输出
OUTPUT_DIR = Path(__file__).parent / 'output'

# 特征中文名
FEAT_CN = {
    'w_ih': '威廉初盘让方', 'w_ir': '威廉初盘受让方', 'w_h': '威廉让方', 'w_r': '威廉受让方',
    'w_spread': '威廉赔率差', 'w_hc': '威廉让方变化', 'w_rc': '威廉受让方变化', 'w_dc': '威廉平赔变化',
    'w_kh': '威廉让方Kelly', 'w_kd': '威廉平Kelly', 'w_kr': '威廉受让方Kelly',
    'w_irr': '威廉初盘返还率', 'w_crr': '威廉即时返还率',
    'm_ih': '澳门初盘让方', 'm_ir': '澳门初盘受让方', 'm_h': '澳门让方', 'm_r': '澳门受让方',
    'm_spread': '澳门赔率差', 'm_hc': '澳门让方变化', 'm_rc': '澳门受让方变化', 'm_dc': '澳门平赔变化',
    'm_kh': '澳门让方Kelly', 'm_kd': '澳门平Kelly', 'm_kr': '澳门受让方Kelly',
    'm_irr': '澳门初盘返还率', 'm_crr': '澳门即时返还率',
    'l_ih': '立博初盘让方', 'l_ir': '立博初盘受让方', 'l_h': '立博让方', 'l_r': '立博受让方',
    'l_spread': '立博赔率差', 'l_hc': '立博让方变化', 'l_rc': '立博受让方变化', 'l_dc': '立博平赔变化',
    'l_kh': '立博让方Kelly', 'l_kd': '立博平Kelly', 'l_kr': '立博受让方Kelly',
    'l_irr': '立博初盘返还率', 'l_crr': '立博即时返还率',
    # 跨公司
    'wm_spread_diff': '威澳赔率差差', 'wm_h_diff': '威澳让方差', 'wm_r_diff': '威澳受让方差',
    'wm_hc_diff': '威澳让方变化差', 'wm_rc_diff': '威澳受让方变化差',
    'wm_crr_diff': '威澳返还率差', 'wm_irr_diff': '威澳初盘返还率差',
    'wl_spread_diff': '威立赔率差差', 'wl_h_diff': '威立让方差', 'wl_r_diff': '威立受让方差',
    'wl_hc_diff': '威立让方变化差', 'wl_crr_diff': '威立返还率差',
    'ml_spread_diff': '澳立赔率差差', 'ml_h_diff': '澳立让方差', 'ml_r_diff': '澳立受让方差',
    'ml_rc_diff': '澳立受让方变化差', 'ml_crr_diff': '澳立返还率差',
    'avg3_r': '三公司受让方均值', 'avg3_spread': '三公司赔率差均值',
    'avg3_hc': '三公司让方变化均值', 'std3_spread': '三公司赔率差分歧',
}


# ==================== 工具函数 ====================

def _f(v):
    if v is None:
        return np.nan
    try:
        return float(v)
    except (TypeError, ValueError):
        return np.nan


def wilson_ci(n_correct, n_total, z=WILSON_Z):
    if n_total == 0:
        return 0.0, 0.0
    p = n_correct / n_total
    denom = 1 + z ** 2 / n_total
    center = (p + z ** 2 / (2 * n_total)) / denom
    margin = z * math.sqrt((p * (1 - p) + z ** 2 / (4 * n_total)) / n_total) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def fmt_cond(f, op, th):
    cn = FEAT_CN.get(f, f)
    return f"{cn}{op}{th:.3f}"


def fmt_rule(conds):
    return ' + '.join(fmt_cond(f, op, th) for f, op, th in conds)


# ==================== 数据加载 ====================

def load_data():
    """加载所有已完赛竞争区间比赛 + 三公司赔率"""
    db = get_connection()
    print("加载比赛数据...")

    # 获取所有已完赛比赛
    matches = db.execute_query('''
        SELECT match_id, match_time, home_score, away_score, league_id
        FROM matches
        WHERE match_status = 'finished'
          AND home_score IS NOT NULL AND away_score IS NOT NULL
        ORDER BY match_time ASC
    ''', fetch='all')
    print(f"  已完赛比赛: {len(matches)}")

    # 获取三公司赔率
    print("加载 european_odds...")
    eo_rows = db.execute_query('''
        SELECT match_id, company_id,
               initial_home, initial_draw, initial_away,
               current_home, current_draw, current_away,
               initial_return_rate, current_return_rate,
               kelly_home, kelly_draw, kelly_away
        FROM european_odds
        WHERE company_id IN (115, 80, 82)
          AND initial_home > 0
    ''', fetch='all')
    print(f"  european_odds: {len(eo_rows)} 行")

    # 按 match_id 组织
    eo_map: Dict[int, Dict[int, Dict]] = {}
    for row in eo_rows:
        eo_map.setdefault(row['match_id'], {})[row['company_id']] = row

    return matches, eo_map


# ==================== 特征工程 ====================

def build_features(matches, eo_map):
    """构建多公司特征 DataFrame"""
    records = []

    for mt in matches:
        mid = mt['match_id']
        eo = eo_map.get(mid, {})

        # 至少需要威廉赔率
        if 115 not in eo:
            continue
        w = eo[115]
        w_ih_raw = _f(w.get('initial_home'))
        w_ia_raw = _f(w.get('initial_away'))
        if np.isnan(w_ih_raw) or np.isnan(w_ia_raw) or w_ih_raw <= 0 or w_ia_raw <= 0:
            continue

        # 确定让方
        home_is_h = w_ih_raw <= w_ia_raw

        hs = int(mt['home_score'])
        aws = int(mt['away_score'])

        def pick(row, hk, ak):
            h_v, a_v = _f(row.get(hk)), _f(row.get(ak))
            return (h_v, a_v) if home_is_h else (a_v, h_v)

        # 提取各公司特征
        feat = {
            'match_id': mid,
            'match_time': mt['match_time'],
            'league_id': mt['league_id'],
        }

        available = {}
        for cid, pfx in COMPANIES:
            if cid not in eo:
                continue
            o = eo[cid]
            ih, ir = pick(o, 'initial_home', 'initial_away')
            ch, cr = pick(o, 'current_home', 'current_away')
            id_ = _f(o.get('initial_draw'))
            cd = _f(o.get('current_draw'))

            hc = (ch - ih) / ih if ih and ih > 0 and not np.isnan(ch) else np.nan
            rc = (cr - ir) / ir if ir and ir > 0 and not np.isnan(cr) else np.nan
            dc = (cd - id_) / id_ if id_ and id_ > 0 and not np.isnan(cd) else np.nan

            kh, kr_v = pick(o, 'kelly_home', 'kelly_away')
            kd = _f(o.get('kelly_draw'))
            irr = _f(o.get('initial_return_rate'))
            crr = _f(o.get('current_return_rate'))
            spread = cr - ch if not np.isnan(cr) and not np.isnan(ch) else np.nan

            feat[f'{pfx}_ih'] = ih
            feat[f'{pfx}_ir'] = ir
            feat[f'{pfx}_h'] = ch
            feat[f'{pfx}_r'] = cr
            feat[f'{pfx}_spread'] = spread
            feat[f'{pfx}_hc'] = hc
            feat[f'{pfx}_rc'] = rc
            feat[f'{pfx}_dc'] = dc
            feat[f'{pfx}_kh'] = kh
            feat[f'{pfx}_kd'] = kd
            feat[f'{pfx}_kr'] = kr_v
            feat[f'{pfx}_irr'] = irr
            feat[f'{pfx}_crr'] = crr

            available[pfx] = True

        # 竞争区间过滤
        w_h = feat.get('w_h', np.nan)
        w_r = feat.get('w_r', np.nan)
        if np.isnan(w_h) or np.isnan(w_r):
            continue
        if min(w_h, w_r) < MIN_HANDICAP_ODDS:
            continue

        has_m = 'm' in available
        has_l = 'l' in available

        # 确定模式
        if has_m and has_l:
            mode = 'wml'
        elif has_m:
            mode = 'wm'
        elif has_l:
            mode = 'wl'
        else:
            continue  # 只有威廉，跳过

        feat['mode'] = mode
        feat['has_m'] = has_m
        feat['has_l'] = has_l

        # 跨公司特征
        if has_m:
            for k in ['spread', 'h', 'r', 'hc', 'rc', 'crr', 'irr']:
                wv = feat.get(f'w_{k}', np.nan)
                mv = feat.get(f'm_{k}', np.nan)
                feat[f'wm_{k}_diff'] = wv - mv if not np.isnan(wv) and not np.isnan(mv) else np.nan

        if has_l:
            for k in ['spread', 'h', 'r', 'hc', 'crr']:
                wv = feat.get(f'w_{k}', np.nan)
                lv = feat.get(f'l_{k}', np.nan)
                feat[f'wl_{k}_diff'] = wv - lv if not np.isnan(wv) and not np.isnan(lv) else np.nan

        if has_m and has_l:
            for k in ['spread', 'h', 'r', 'rc', 'crr']:
                mv = feat.get(f'm_{k}', np.nan)
                lv = feat.get(f'l_{k}', np.nan)
                feat[f'ml_{k}_diff'] = mv - lv if not np.isnan(mv) and not np.isnan(lv) else np.nan

            # 三公司均值/分歧
            for k in ['r', 'spread', 'hc']:
                vals = [feat.get(f'{p}_{k}', np.nan) for p in ['w', 'm', 'l']]
                if all(not np.isnan(v) for v in vals):
                    feat[f'avg3_{k}'] = np.mean(vals)
                    if k == 'spread':
                        feat[f'std3_{k}'] = np.std(vals)

        # 目标变量
        if home_is_h:
            h_score, r_score = hs, aws
        else:
            h_score, r_score = aws, hs
        feat['target_hn'] = 1 if h_score >= r_score else 0  # 让方不输
        feat['target_rn'] = 1 if r_score >= h_score else 0  # 受让不输

        records.append(feat)

    df = pd.DataFrame(records)
    print(f"  构建特征矩阵: {len(df)} 场比赛, {len(df.columns)} 列")
    return df


# ==================== 规则评估 ====================

def eval_rule_on(conds, X, y, min_n=20):
    """在给定数据上评估规则"""
    mask = np.ones(len(X), dtype=bool)
    for f, op, th in conds:
        if f not in X.columns:
            return None
        col = X[f].values
        if op == '<=':
            mask &= col <= th
        else:
            mask &= col > th
    n = int(mask.sum())
    if n < min_n:
        return None
    nc = int(y.values[mask].sum())
    acc = nc / n
    ci_lo, ci_hi = wilson_ci(nc, n)
    return {'n': n, 'nc': nc, 'acc': acc, 'ci_lo': ci_lo, 'ci_hi': ci_hi}


# ==================== 挖掘策略 ====================

def mine_rules(X_train, y_train, target_name, min_acc, min_n=20):
    """多策略挖掘规则"""
    feats = [c for c in X_train.columns if c not in ('match_id', 'match_time', 'league_id',
             'mode', 'has_m', 'has_l', 'target_hn', 'target_rn')]
    num_cols = [c for c in feats if X_train[c].dtype in ('float64', 'float32', 'int64')]
    all_rules: Dict[str, Dict] = {}

    def _add(conds, result):
        name = fmt_rule(conds)
        if result and (name not in all_rules or result['acc'] > all_rules[name]['acc']):
            all_rules[name] = {'conditions': conds, **result}

    # --- 1. 决策树 ---
    print(f"    决策树挖掘...")
    X_num = X_train[num_cols].copy()
    for c in num_cols:
        X_num[c] = pd.to_numeric(X_num[c], errors='coerce').fillna(X_num[c].median())

    for depth in [2, 3, 4]:
        for ml in [15, 20, 30]:
            for cw in [None, 'balanced']:
                tree = DecisionTreeClassifier(
                    max_depth=depth, min_samples_leaf=ml,
                    class_weight=cw, random_state=42
                )
                tree.fit(X_num, y_train)
                paths = _extract_paths(tree, num_cols)
                for path in paths:
                    r = eval_rule_on(path, X_train[num_cols], y_train, min_n=min_n)
                    if r and r['acc'] >= min_acc:
                        _add(path, r)

    print(f"      决策树候选: {len(all_rules)}")

    # --- 2. 单特征阈值扫描 ---
    print(f"    单特征扫描...")
    before = len(all_rules)
    for col in num_cols:
        vals = X_train[col].dropna().values
        if len(vals) < 30:
            continue
        percs = np.percentile(vals, np.arange(10, 91, 5))
        for th in percs:
            for op in ['<=', '>']:
                conds = [(col, op, float(th))]
                r = eval_rule_on(conds, X_train[num_cols], y_train, min_n=min_n)
                if r and r['acc'] >= min_acc:
                    _add(conds, r)
    print(f"      单特征新增: {len(all_rules) - before}")

    # --- 3. 双特征组合 ---
    print(f"    双特征组合...")
    before = len(all_rules)
    rf = RandomForestClassifier(n_estimators=100, max_depth=4, random_state=42, n_jobs=-1)
    X_rf = X_num.copy()
    rf.fit(X_rf, y_train)
    imp = pd.Series(rf.feature_importances_, index=num_cols)
    top_feats = imp.nlargest(15).index.tolist()

    for f1, f2 in combinations(top_feats, 2):
        v1 = X_train[f1].values
        v2 = X_train[f2].values
        valid1 = v1[~np.isnan(v1)]
        valid2 = v2[~np.isnan(v2)]
        if len(valid1) < 30 or len(valid2) < 30:
            continue
        p1 = np.percentile(valid1, np.arange(15, 86, 10))
        p2 = np.percentile(valid2, np.arange(15, 86, 10))
        for t1 in p1:
            for o1 in ['<=', '>']:
                m1 = (v1 <= t1) if o1 == '<=' else (v1 > t1)
                for t2 in p2:
                    for o2 in ['<=', '>']:
                        m2 = (v2 <= t2) if o2 == '<=' else (v2 > t2)
                        mask = m1 & m2
                        n = int(mask.sum())
                        if n < min_n:
                            continue
                        nc = int(y_train.values[mask].sum())
                        acc = nc / n
                        if acc >= min_acc:
                            conds = [(f1, o1, float(t1)), (f2, o2, float(t2))]
                            ci_lo, ci_hi = wilson_ci(nc, n)
                            _add(conds, {'n': n, 'nc': nc, 'acc': acc,
                                         'ci_lo': ci_lo, 'ci_hi': ci_hi})
    print(f"      双特征新增: {len(all_rules) - before}")

    rules = sorted(all_rules.values(), key=lambda r: (-r['acc'], -r['n']))
    print(f"    总候选: {len(rules)}")
    return rules


def _extract_paths(tree, features):
    """从决策树提取所有路径"""
    paths = []
    t = tree.tree_

    def walk(nid, conds):
        if t.children_left[nid] == t.children_right[nid]:
            paths.append(list(conds))
            return
        f = features[t.feature[nid]]
        th = float(t.threshold[nid])
        walk(t.children_left[nid], conds + [(f, '<=', th)])
        walk(t.children_right[nid], conds + [(f, '>', th)])

    walk(0, [])
    return paths


# ==================== 验证流水线 ====================

def cross_validate(rules, X, y):
    """5-fold CV 验证"""
    skf = StratifiedKFold(n_splits=CV_FOLDS, shuffle=True, random_state=42)
    num_cols = [c for c in X.columns if X[c].dtype in ('float64', 'float32', 'int64')
                and c not in ('match_id', 'match_time', 'league_id', 'mode', 'has_m', 'has_l',
                              'target_hn', 'target_rn')]
    results = []
    for rule in rules:
        t_n = t_c = 0
        fold_accs = []
        for _, test_idx in skf.split(X, y):
            Xt = X.iloc[test_idx]
            yt = y.iloc[test_idx]
            mask = np.ones(len(Xt), dtype=bool)
            for f, op, th in rule['conditions']:
                if f not in Xt.columns:
                    mask[:] = False
                    break
                col = Xt[f].values
                mask &= (col <= th) if op == '<=' else (col > th)
            nm = int(mask.sum())
            if nm > 0:
                nc = int((yt.values[mask] == 1).sum())
                fold_accs.append(nc / nm)
                t_n += nm
                t_c += nc
        if t_n == 0:
            continue
        cv_acc = t_c / t_n
        ci_lo, ci_hi = wilson_ci(t_c, t_n)
        results.append({
            **rule,
            'cv_acc': cv_acc, 'cv_n': t_n, 'cv_nc': t_c,
            'cv_ci_lo': ci_lo, 'cv_ci_hi': ci_hi,
            'cv_std': float(np.std(fold_accs)) if len(fold_accs) > 1 else 0,
        })
    results.sort(key=lambda r: (-r['cv_acc'], -r['cv_n']))
    return results


def oos_validate(rules, X_test, y_test, min_n=15):
    """OOS 测试集验证"""
    results = []
    for rule in rules:
        mask = np.ones(len(X_test), dtype=bool)
        for f, op, th in rule['conditions']:
            if f not in X_test.columns:
                mask[:] = False
                break
            col = X_test[f].values
            mask &= (col <= th) if op == '<=' else (col > th)
        nm = int(mask.sum())
        if nm < min_n:
            continue
        nc = int((y_test.values[mask] == 1).sum())
        oos_acc = nc / nm
        ci_lo, ci_hi = wilson_ci(nc, nm)
        results.append({
            **rule,
            'oos_acc': oos_acc, 'oos_n': nm, 'oos_nc': nc,
            'oos_ci_lo': ci_lo, 'oos_ci_hi': ci_hi,
        })
    results.sort(key=lambda r: (-r['oos_acc'], -r['oos_n']))
    return results


def overfit_filter(rules, baseline, target_name):
    """四重过拟合过滤"""
    passed = []
    for r in rules:
        train_acc = r['acc']
        cv_acc = r['cv_acc']
        oos_acc = r['oos_acc']
        oos_ci_lo = r['oos_ci_lo']

        # 1. 训练-CV落差
        if abs(train_acc - cv_acc) > OVERFIT_GAP:
            continue
        # 2. Wilson CI 下界 > 基线 + LIFT
        if oos_ci_lo < baseline + BASELINE_LIFT:
            continue
        # 3. OOS 精度门槛 (H要求>=80%, R要求>=65%)
        if target_name == 'H' and oos_acc < H_MIN_ACC:
            continue
        if target_name == 'R' and oos_acc < R_MIN_ACC:
            continue
        passed.append(r)
    passed.sort(key=lambda r: (-r['oos_acc'], -r['oos_n']))
    return passed


# ==================== 去重 ====================

def deduplicate_rules(rules, X, y, max_overlap=0.85):
    """去除高度重叠的规则（保留更优的）"""
    kept = []
    kept_masks = []

    for rule in rules:
        mask = np.ones(len(X), dtype=bool)
        for f, op, th in rule['conditions']:
            if f not in X.columns:
                mask[:] = False
                break
            col = X[f].values
            mask &= (col <= th) if op == '<=' else (col > th)

        is_dup = False
        for km in kept_masks:
            overlap = (mask & km).sum()
            if mask.sum() > 0 and km.sum() > 0:
                jaccard = overlap / max(1, (mask | km).sum())
                if jaccard > max_overlap:
                    is_dup = True
                    break
        if not is_dup:
            kept.append(rule)
            kept_masks.append(mask)

    return kept


# ==================== 确定规则需要的公司模式 ====================

def detect_requires(conds):
    """根据条件中使用的特征确定所需公司模式"""
    feats_used = set()
    for f, _, _ in conds:
        if f.startswith('m_') or f.startswith('wm_') or f.startswith('ml_') or f.startswith('avg3_') or f.startswith('std3_'):
            feats_used.add('m')
        if f.startswith('l_') or f.startswith('wl_') or f.startswith('ml_') or f.startswith('avg3_') or f.startswith('std3_'):
            feats_used.add('l')
    if 'm' in feats_used and 'l' in feats_used:
        return 'wml'
    elif 'm' in feats_used:
        return 'wm'
    elif 'l' in feats_used:
        return 'wl'
    else:
        return 'wm'  # 只有威廉特征，默认归入wm


# ==================== 输出生成 ====================

def gen_decorator_code(rules, side_label):
    """生成 @rule decorator 格式代码"""
    lines = []
    side_code = 'H' if side_label == '让方不输' else 'R'

    for i, r in enumerate(rules, 1):
        conds = r['conditions']
        requires = detect_requires(conds)

        # 确定规则ID前缀
        if requires == 'wml':
            prefix = 'T'
        elif requires == 'wl':
            prefix = 'WL'
        else:
            prefix = 'D'

        rid = f"{prefix}-{side_code}{i:02d}"

        # 确定等级
        oos_acc = r['oos_acc']
        oos_n = r['oos_n']
        if oos_acc >= 0.90 and oos_n >= 20:
            grade = 'S'
        elif oos_acc >= 0.80 and oos_n >= 15:
            grade = 'A'
        else:
            grade = 'B'

        # 描述
        desc = fmt_rule(conds) + f" → OOS {oos_acc*100:.1f}%(n={oos_n})"

        # 函数体
        body_parts = []
        for f, op, th in conds:
            body_parts.append(f"m['{f}'] {op} {th:.3f}")
        body = " and ".join(body_parts)

        lines.append(f"@rule('{rid}', '{side_code}', '{grade}', '{requires}',")
        lines.append(f"      '{desc}')")
        lines.append(f"def _(m):")
        lines.append(f"    return ({body})")
        lines.append("")

    return '\n'.join(lines)


def gen_report(rules, side_label, baseline, train_n, test_n):
    """生成验证报告"""
    lines = []
    lines.append(f"\n{'='*90}")
    lines.append(f"  {side_label} — 最终通过规则: {len(rules)} 条")
    lines.append(f"  基线: {baseline*100:.1f}%, 训练集: {train_n}, 测试集: {test_n}")
    lines.append(f"{'='*90}")

    if not rules:
        lines.append("  (无规则通过)")
        return '\n'.join(lines)

    lines.append(f"  {'#':>3} {'训练':>7} {'CV':>7} {'OOS':>7} {'OOS_N':>6} {'CI下':>7} {'模式':>4}  规则")
    lines.append(f"  {'-'*85}")
    for i, r in enumerate(rules, 1):
        requires = detect_requires(r['conditions'])
        lines.append(
            f"  {i:>3} {r['acc']*100:>6.1f}% {r['cv_acc']*100:>6.1f}% "
            f"{r['oos_acc']*100:>6.1f}% {r['oos_n']:>5} "
            f"{r['oos_ci_lo']*100:>6.1f}% {requires:>4}  {fmt_rule(r['conditions'])}"
        )
    return '\n'.join(lines)


# ==================== 特征重要性 ====================

EXCLUDE_COLS = {'match_id', 'match_time', 'league_id', 'mode', 'has_m', 'has_l',
                 'target_hn', 'target_rn'}


def show_importance(X, y, name):
    """随机森林特征重要性 Top 20"""
    num_cols = [c for c in X.columns if X[c].dtype in ('float64', 'float32', 'int64')
                and c not in EXCLUDE_COLS]
    X_clean = X[num_cols].copy()
    for c in num_cols:
        X_clean[c] = pd.to_numeric(X_clean[c], errors='coerce').fillna(X_clean[c].median())

    rf = RandomForestClassifier(n_estimators=200, max_depth=5, min_samples_leaf=20,
                                class_weight='balanced', random_state=42, n_jobs=-1)
    rf.fit(X_clean, y)
    imp = pd.Series(rf.feature_importances_, index=num_cols).sort_values(ascending=False)

    print(f"\n  特征重要性 Top 20 ({name}):")
    for i, (feat, val) in enumerate(imp.head(20).items(), 1):
        cn = FEAT_CN.get(feat, feat)
        bar = '#' * int(val * 200)
        print(f"  {i:>3} {cn:<30s} ({feat:<25s}) {val:.4f} {bar}")
    return imp


# ==================== 按模式分组挖掘 ====================

def mine_for_mode(df, mode_filter, target_col, target_name, side_label, min_acc):
    """对指定模式的数据进行挖掘"""
    if mode_filter == 'wml':
        sub = df[df['mode'] == 'wml'].copy()
        mode_cn = '三公司(wml)'
    elif mode_filter == 'wm':
        sub = df[df['mode'].isin(['wm', 'wml'])].copy()
        mode_cn = '威廉+澳门(wm/wml)'
    elif mode_filter == 'wl':
        sub = df[df['mode'] == 'wl'].copy()
        mode_cn = '威立(wl)'
    else:
        sub = df.copy()
        mode_cn = '全部'

    if len(sub) < 100:
        print(f"  {mode_cn}: 数据不足 ({len(sub)}), 跳过")
        return []

    # 时间切分
    sp = int(len(sub) * TRAIN_RATIO)
    train = sub.iloc[:sp]
    test = sub.iloc[sp:]

    y_train = train[target_col]
    y_test = test[target_col]
    baseline = float(y_train.mean())

    print(f"\n  --- {mode_cn} · {side_label} ---")
    print(f"  训练: {len(train)} 场 (至 {train['match_time'].max()}), "
          f"测试: {len(test)} 场 (从 {test['match_time'].min()})")
    print(f"  基线: {baseline*100:.1f}%, 阈值: {min_acc*100:.0f}%")

    # 特征重要性
    show_importance(train, y_train, f"{mode_cn}·{side_label}")

    # 挖掘
    print(f"\n  开始挖掘...")
    rules = mine_rules(train, y_train, target_name, min_acc=min_acc, min_n=MIN_SAMPLE_TRAIN)

    if not rules:
        print(f"  无候选规则")
        return []

    # CV 验证
    print(f"  CV 验证 ({CV_FOLDS}-fold)...")
    cv_rules = cross_validate(rules, train, y_train)
    cv_passed = [r for r in cv_rules if r['cv_acc'] >= min_acc - 0.02]
    print(f"  CV 通过: {len(cv_passed)}/{len(cv_rules)}")

    if not cv_passed:
        print(f"  CV 全部未通过")
        return []

    # OOS 验证
    print(f"  OOS 验证...")
    oos_rules = oos_validate(cv_passed, test, y_test, min_n=MIN_SAMPLE_OOS)
    print(f"  OOS 有数据: {len(oos_rules)}")

    if not oos_rules:
        print(f"  OOS 无规则通过最小样本")
        return []

    # 过拟合过滤
    print(f"  过拟合过滤...")
    final = overfit_filter(oos_rules, baseline, target_name)
    print(f"  最终通过: {len(final)}")

    if not final:
        return []

    # 去重
    final = deduplicate_rules(final, train, y_train, max_overlap=0.80)
    print(f"  去重后: {len(final)}")

    return final


# ==================== 主函数 ====================

def main():
    print("=" * 90)
    print(f"  竞争区间规则挖掘器 v2.0（多公司 · 纯数值 · european_odds）")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  竞争区间: 让方赔率 >= {MIN_HANDICAP_ODDS}")
    print("=" * 90)

    matches, eo_map = load_data()
    df = build_features(matches, eo_map)

    # 统计
    print(f"\n数据统计:")
    print(f"  总比赛: {len(df)}")
    for m in ['wml', 'wm', 'wl']:
        cnt = (df['mode'] == m).sum()
        print(f"  {m}: {cnt} 场")
    print(f"  让方不输基线: {df['target_hn'].mean()*100:.1f}%")
    print(f"  受让不输基线: {df['target_rn'].mean()*100:.1f}%")

    all_report = []
    all_code = []

    # === 让方不输 ===
    print(f"\n\n{'#'*90}")
    print(f"#  目标: 让方不输 (H)")
    print(f"{'#'*90}")

    h_rules_all = []
    for mode_filter in ['wml', 'wm', 'wl']:
        rules = mine_for_mode(df, mode_filter, 'target_hn', 'H', '让方不输', H_MIN_ACC)
        h_rules_all.extend(rules)

    # 去除跨模式重复
    h_rules_all = deduplicate_rules(
        sorted(h_rules_all, key=lambda r: (-r['oos_acc'], -r['oos_n'])),
        df, df['target_hn'], max_overlap=0.80
    )
    # 只保留 top N
    h_rules_all = h_rules_all[:MAX_RULES_PER_SIDE]
    sp = int(len(df) * TRAIN_RATIO)
    report = gen_report(h_rules_all, '让方不输', df['target_hn'].mean(), sp, len(df) - sp)
    print(report)
    all_report.append(report)
    if h_rules_all:
        code = gen_decorator_code(h_rules_all, '让方不输')
        all_code.append(f"# --- 让方不输规则 ---\n{code}")

    # === 受让不输 ===
    print(f"\n\n{'#'*90}")
    print(f"#  目标: 受让不输 (R)")
    print(f"{'#'*90}")

    r_rules_all = []
    for mode_filter in ['wml', 'wm', 'wl']:
        rules = mine_for_mode(df, mode_filter, 'target_rn', 'R', '受让不输', R_MIN_ACC)
        r_rules_all.extend(rules)

    r_rules_all = deduplicate_rules(
        sorted(r_rules_all, key=lambda r: (-r['oos_acc'], -r['oos_n'])),
        df, df['target_rn'], max_overlap=0.80
    )
    # 只保留 top N
    r_rules_all = r_rules_all[:MAX_RULES_PER_SIDE]
    report = gen_report(r_rules_all, '受让不输', df['target_rn'].mean(), sp, len(df) - sp)
    print(report)
    all_report.append(report)
    if r_rules_all:
        code = gen_decorator_code(r_rules_all, '受让不输')
        all_code.append(f"# --- 受让不输规则 ---\n{code}")

    # === 保存 ===
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 报告
    report_file = OUTPUT_DIR / f'v2_rules_report_{ts}.txt'
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(all_report))
    print(f"\n报告已保存: {report_file}")

    # 代码
    code_file = OUTPUT_DIR / f'v2_rules_code_{ts}.py'
    with open(code_file, 'w', encoding='utf-8') as f:
        f.write("# 竞争区间规则引擎 v2.0 — 挖掘输出\n")
        f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# 数据: {len(df)} 场竞争区间, 训练{sp}/测试{len(df)-sp}\n\n")
        f.write('\n\n'.join(all_code))
    print(f"规则代码已保存: {code_file}")

    # JSON (方便后续集成)
    json_file = OUTPUT_DIR / f'v2_rules_{ts}.json'
    export = []
    for r in h_rules_all + r_rules_all:
        export.append({
            'conditions': [(f, op, round(th, 4)) for f, op, th in r['conditions']],
            'side': 'H' if r in h_rules_all else 'R',
            'requires': detect_requires(r['conditions']),
            'train_acc': round(r['acc'], 4),
            'cv_acc': round(r['cv_acc'], 4),
            'oos_acc': round(r['oos_acc'], 4),
            'oos_n': r['oos_n'],
            'oos_ci_lo': round(r['oos_ci_lo'], 4),
            'description': fmt_rule(r['conditions']),
        })
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(export, f, ensure_ascii=False, indent=2)
    print(f"JSON 已保存: {json_file}")

    print(f"\n{'='*90}")
    print(f"  挖掘完成: 让方不输 {len(h_rules_all)} 条, 受让不输 {len(r_rules_all)} 条")
    print(f"{'='*90}")


if __name__ == '__main__':
    main()
