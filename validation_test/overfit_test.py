#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
过拟合检测器
============
两种严格测试，量化规则的真实可靠性：

测试1: 真正的时间外样本 (Walk-Forward)
  - 只在前60%数据上发现规则
  - 在后40%数据上验证（规则发现过程从未见过这些数据）
  - 对比"发现集准确率" vs "纯样本外准确率"

测试2: 随机打乱标签 (Permutation Test)
  - 把赛果随机打乱
  - 用同样的挖掘方法去找"高准确率规则"
  - 如果随机标签也能找到很多"好规则"，说明方法本身在过拟合

用法:
    cd /home/ubuntu/oddsmind
    MYSQL_PASSWORD=$MYSQL_PASSWORD python3 validation_test/overfit_test.py
"""

import os, sys, math, warnings
from pathlib import Path
from datetime import datetime
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import RandomForestClassifier

warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))
from database.connection import get_connection

COMPANY_ID = 115
MIN_HANDICAP_ODDS = 1.70
BIG5 = {36, 31, 34, 8, 11}
RANGE_PFX = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


def get_rt(s):
    if not s: return 'unknown'
    for p in RANGE_PFX:
        if s.startswith(p): return p
    return '其他'


def wilson_ci(nc, n, z=1.96):
    if n == 0: return (0., 0.)
    p = nc / n
    d = 1 + z**2 / n
    c = (p + z**2 / (2*n)) / d
    m = z * math.sqrt((p*(1-p) + z**2/(4*n)) / n) / d
    return (max(0, c-m), min(1, c+m))


def load_data():
    db = get_connection()
    q = '''
        SELECT oar.match_id,
            oar.initial_home_range, oar.initial_away_range,
            oar.current_home_range, oar.current_away_range,
            oar.initial_draw_range, oar.current_draw_range,
            oar.initial_home_offset, oar.initial_away_offset,
            oar.current_home_offset, oar.current_away_offset,
            oar.initial_home_theory_distance, oar.initial_away_theory_distance,
            oar.initial_home_fullwater, oar.initial_draw_fullwater, oar.initial_away_fullwater,
            oar.current_home_fullwater, oar.current_draw_fullwater, oar.current_away_fullwater,
            oar.initial_rule_diff, oar.current_rule_diff,
            oar.initial_draw_standard, oar.current_draw_standard,
            oar.power_diff,
            m.home_score, m.away_score, m.match_time, m.league_id,
            eo.initial_home, eo.initial_draw, eo.initial_away,
            eo.current_home, eo.current_draw, eo.current_away,
            eo.kelly_home, eo.kelly_draw, eo.kelly_away,
            eo.initial_return_rate, eo.current_return_rate
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        JOIN european_odds eo ON oar.match_id = eo.match_id AND oar.company_id = eo.company_id
        JOIN leagues l ON m.league_id = l.league_id
        WHERE oar.company_id = %s AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL AND m.away_score IS NOT NULL
          AND eo.initial_home > 0 AND eo.initial_away > 0
          AND eo.current_home != eo.current_away
          AND LEAST(eo.current_home, eo.current_away) >= %s
        ORDER BY m.match_time ASC
    '''
    return pd.DataFrame(db.execute_query(q, (COMPANY_ID, MIN_HANDICAP_ODDS), fetch='all'))


def build_features(df):
    recs = []
    for _, r in df.iterrows():
        ih, ia = float(r['initial_home']), float(r['initial_away'])
        ch, ca = float(r['current_home']), float(r['current_away'])
        id_, cd = float(r['initial_draw']), float(r['current_draw'])
        if ih <= ia:
            hs, rs = int(r['home_score']), int(r['away_score'])
            ihr, irr = r['initial_home_range'], r['initial_away_range']
            chr_, crr = r['current_home_range'], r['current_away_range']
            i_h, i_r, c_h, c_r = ih, ia, ch, ca
            kh = float(r['kelly_home']) if r['kelly_home'] else None
            kr = float(r['kelly_away']) if r['kelly_away'] else None
            kd = float(r['kelly_draw']) if r['kelly_draw'] else None
            iho = float(r['initial_home_offset']) if r['initial_home_offset'] is not None else None
            iro = float(r['initial_away_offset']) if r['initial_away_offset'] is not None else None
            cho = float(r['current_home_offset']) if r['current_home_offset'] is not None else None
            cro = float(r['current_away_offset']) if r['current_away_offset'] is not None else None
            iht = float(r['initial_home_theory_distance']) if r['initial_home_theory_distance'] is not None else None
            irt = float(r['initial_away_theory_distance']) if r['initial_away_theory_distance'] is not None else None
        else:
            hs, rs = int(r['away_score']), int(r['home_score'])
            ihr, irr = r['initial_away_range'], r['initial_home_range']
            chr_, crr = r['current_away_range'], r['current_home_range']
            i_h, i_r, c_h, c_r = ia, ih, ca, ch
            kh = float(r['kelly_away']) if r['kelly_away'] else None
            kr = float(r['kelly_home']) if r['kelly_home'] else None
            kd = float(r['kelly_draw']) if r['kelly_draw'] else None
            iho = float(r['initial_away_offset']) if r['initial_away_offset'] is not None else None
            iro = float(r['initial_home_offset']) if r['initial_home_offset'] is not None else None
            cho = float(r['current_away_offset']) if r['current_away_offset'] is not None else None
            cro = float(r['current_home_offset']) if r['current_home_offset'] is not None else None
            iht = float(r['initial_away_theory_distance']) if r['initial_away_theory_distance'] is not None else None
            irt = float(r['initial_home_theory_distance']) if r['initial_home_theory_distance'] is not None else None

        pd_ = float(r['power_diff']) if r['power_diff'] is not None else 0.
        hcp = (c_h - i_h) / i_h if i_h > 0 else 0
        rcp = (c_r - i_r) / i_r if i_r > 0 else 0
        dcp = (cd - id_) / id_ if id_ > 0 else 0
        hoc = (cho - iho) if (cho is not None and iho is not None) else None
        roc = (cro - iro) if (cro is not None and iro is not None) else None
        ids = float(r['initial_draw_standard']) if r['initial_draw_standard'] else None
        idf = float(r['initial_draw_fullwater']) if r['initial_draw_fullwater'] else None
        cds = float(r['current_draw_standard']) if r['current_draw_standard'] else None
        cdf = float(r['current_draw_fullwater']) if r['current_draw_fullwater'] else None
        dri = (idf/ids) if (idf and ids and ids > 0) else None
        drc = (cdf/cds) if (cdf and cds and cds > 0) else None

        def cd_(p):
            if p > 0.05: return '升'
            elif p < -0.05: return '降'
            return '稳'

        recs.append({
            'match_time': r['match_time'], 'h_score': hs, 'r_score': rs,
            'power_diff': pd_, 'init_h_offset': iho, 'init_r_offset': iro,
            'curr_h_offset': cho, 'curr_r_offset': cro,
            'h_offset_change': hoc, 'r_offset_change': roc,
            'init_h_td': iht, 'init_r_td': irt,
            'kelly_h': kh, 'kelly_d': kd, 'kelly_r': kr,
            'h_change_pct': hcp, 'r_change_pct': rcp, 'd_change_pct': dcp,
            'odds_spread': i_r - i_h, 'curr_odds_spread': c_r - c_h,
            'init_h_odds': i_h, 'init_r_odds': i_r,
            'curr_h_odds': c_h, 'curr_r_odds': c_r,
            'init_draw_odds': id_, 'curr_draw_odds': cd,
            'draw_ratio_init': dri, 'draw_ratio_curr': drc,
            'init_return_rate': float(r['initial_return_rate']) if r['initial_return_rate'] else None,
            'curr_return_rate': float(r['current_return_rate']) if r['current_return_rate'] else None,
            'init_rule_diff': float(r['initial_rule_diff']) if r['initial_rule_diff'] is not None else None,
            'curr_rule_diff': float(r['current_rule_diff']) if r['current_rule_diff'] is not None else None,
            'cat_init_h': get_rt(ihr), 'cat_init_r': get_rt(irr),
            'cat_curr_h': get_rt(chr_), 'cat_curr_r': get_rt(crr),
            'cat_h_change': cd_(hcp), 'cat_r_change': cd_(rcp), 'cat_d_change': cd_(dcp),
            'cat_init_draw': r['initial_draw_range'] or 'unknown',
            'cat_curr_draw': r['current_draw_range'] or 'unknown',
            'cat_is_big5': 1 if r['league_id'] in BIG5 else 0,
            'target_hn': 1 if hs >= rs else 0,
            'target_hw': 1 if hs > rs else 0,
            'target_rn': 1 if hs <= rs else 0,
        })

    full = pd.DataFrame(recs)
    meta = ['match_time', 'h_score', 'r_score', 'target_hn', 'target_hw', 'target_rn']
    fc = [c for c in full.columns if c not in meta]
    cc = [c for c in fc if c.startswith('cat_')]
    nc = [c for c in fc if not c.startswith('cat_')]
    Xn = full[nc].copy()
    for c in nc:
        Xn[c] = pd.to_numeric(Xn[c], errors='coerce')
        Xn[c] = Xn[c].fillna(Xn[c].median())
    Xc = pd.get_dummies(full[cc], prefix_sep='=', dtype=int)
    X = pd.concat([Xn, Xc], axis=1)
    return X, full['target_hn'], full['target_hw'], full['target_rn'], full


def extract_paths(tree, features):
    paths = []
    t = tree.tree_
    def walk(n, c):
        if t.children_left[n] == t.children_right[n]:
            paths.append(list(c)); return
        f, th = features[t.feature[n]], t.threshold[n]
        walk(t.children_left[n], c + [(f, '<=', th)])
        walk(t.children_right[n], c + [(f, '>', th)])
    walk(0, [])
    return paths


def mine_on_subset(X, y, min_acc, min_n=20):
    """在给定数据上挖掘规则（与 competitive_rule_miner 相同逻辑）"""
    feats = list(X.columns)
    found = {}

    # 决策树
    for d in [2, 3, 4]:
        for ml in [15, 20, 30]:
            for cw in [None, 'balanced']:
                tree = DecisionTreeClassifier(max_depth=d, min_samples_leaf=ml,
                                              class_weight=cw, random_state=42)
                tree.fit(X, y)
                for path in extract_paths(tree, feats):
                    mask = np.ones(len(X), dtype=bool)
                    for f, op, th in path:
                        col = X[f].values
                        mask &= (col <= th) if op == '<=' else (col > th)
                    n = mask.sum()
                    if n < min_n: continue
                    nc = int(y.values[mask].sum())
                    acc = nc / n
                    if acc >= min_acc:
                        key = str(path)
                        if key not in found or acc > found[key]['acc']:
                            found[key] = {'conds': path, 'n': n, 'nc': nc, 'acc': acc}

    # 阈值扫描
    num_cols = [c for c in X.columns if not c.startswith('cat_')]
    for col in num_cols:
        vals = X[col].values
        valid = vals[~np.isnan(vals)]
        if len(valid) < 10: continue
        percs = np.percentile(valid, np.arange(10, 91, 5))
        for th in percs:
            for op, mf in [('<=', lambda v, t: v <= t), ('>', lambda v, t: v > t)]:
                m = mf(vals, th)
                n = m.sum()
                if n < min_n: continue
                nc = int(y.values[m].sum())
                acc = nc / n
                if acc >= min_acc:
                    path = [(col, op, th)]
                    key = str(path)
                    if key not in found or acc > found[key]['acc']:
                        found[key] = {'conds': path, 'n': n, 'nc': nc, 'acc': acc}

    # 双特征
    rf = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42, n_jobs=-1)
    rf.fit(X[num_cols], y)
    top = pd.Series(rf.feature_importances_, index=num_cols).nlargest(10).index.tolist()
    for f1, f2 in combinations(top, 2):
        v1, v2 = X[f1].values, X[f2].values
        p1 = np.percentile(v1[~np.isnan(v1)], np.arange(20, 81, 15))
        p2 = np.percentile(v2[~np.isnan(v2)], np.arange(20, 81, 15))
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
                            path = [(f1, o1, t1), (f2, o2, t2)]
                            key = str(path)
                            if key not in found or acc > found[key]['acc']:
                                found[key] = {'conds': path, 'n': n, 'nc': nc, 'acc': acc}

    return sorted(found.values(), key=lambda r: (-r['acc'], -r['n']))


def eval_on_holdout(rules, X, y):
    """在样本外数据上评估规则"""
    results = []
    for rule in rules:
        mask = np.ones(len(X), dtype=bool)
        for f, op, th in rule['conds']:
            if f not in X.columns:
                mask[:] = False; break
            col = X[f].values
            mask &= (col <= th) if op == '<=' else (col > th)
        n = mask.sum()
        if n == 0:
            results.append({**rule, 'oos_n': 0, 'oos_nc': 0, 'oos_acc': None})
            continue
        nc = int(y.values[mask].sum())
        acc = nc / n
        results.append({**rule, 'oos_n': n, 'oos_nc': nc, 'oos_acc': acc})
    return results


def fmt_conds(conds):
    parts = []
    for f, op, th in conds:
        if '=' in f and f.startswith('cat_'):
            cn = f.split('=', 1)[0].replace('cat_', '')
            cv = f.split('=', 1)[1]
            if op == '>' and th == 0.5: parts.append(f"{cn}={cv}")
            else: parts.append(f"{cn}!={cv}")
        else:
            parts.append(f"{f} {op} {th:.3f}")
    return ' + '.join(parts)


def main():
    print("=" * 80)
    print("  过拟合检测器")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    raw = load_data()
    X, y_hn, y_hw, y_rn, full = build_features(raw)
    print(f"\n数据: {len(X)} 场竞争区间比赛 (让方赔率 >= {MIN_HANDICAP_ODDS})")

    targets = [
        ('让方不输', y_hn, 0.82),
        ('让方必赢', y_hw, 0.60),
        ('受让方不输', y_rn, 0.60),
    ]

    for tname, y, min_acc in targets:
        base = y.mean()
        print(f"\n\n{'#'*80}")
        print(f"#  {tname}  (基线: {base*100:.1f}%, 挖掘阈值: {min_acc*100:.0f}%)")
        print(f"{'#'*80}")

        # ============================================
        # 测试1: Walk-Forward 真正样本外验证
        # ============================================
        print(f"\n{'='*60}")
        print(f"  测试1: Walk-Forward 样本外验证")
        print(f"{'='*60}")

        sp = int(len(X) * 0.60)  # 前60%发现，后40%验证
        X_disc, y_disc = X.iloc[:sp], y.iloc[:sp]
        X_hold, y_hold = X.iloc[sp:], y.iloc[sp:]

        disc_dates = full.iloc[:sp]['match_time']
        hold_dates = full.iloc[sp:]['match_time']
        print(f"  发现集: {sp} 场 ({disc_dates.min()} ~ {disc_dates.max()})")
        print(f"  验证集: {len(X)-sp} 场 ({hold_dates.min()} ~ {hold_dates.max()})")
        print(f"  发现集基线: {y_disc.mean()*100:.1f}%, 验证集基线: {y_hold.mean()*100:.1f}%")

        # 只在发现集上挖掘
        disc_rules = mine_on_subset(X_disc, y_disc, min_acc=min_acc, min_n=15)
        print(f"\n  发现集找到: {len(disc_rules)} 条规则")

        if not disc_rules:
            print("  (无规则可验证)")
            continue

        # 在验证集上评估
        oos = eval_on_holdout(disc_rules, X_hold, y_hold)

        # 统计
        has_oos = [r for r in oos if r['oos_n'] and r['oos_n'] >= 5]

        print(f"\n  样本外验证结果 (验证集样本>=5的规则):")
        print(f"  {'#':>3} {'发现准确率':>10} {'验证准确率':>10} {'验证样本':>8} {'落差':>8}  规则")
        print(f"  {'-'*85}")

        drops = []
        for i, r in enumerate(has_oos[:20]):
            disc_acc = r['acc'] * 100
            oos_acc = r['oos_acc'] * 100 if r['oos_acc'] is not None else 0
            drop = disc_acc - oos_acc
            drops.append(drop)
            marker = ' !!!' if drop > 15 else (' !' if drop > 10 else '')
            print(f"  {i+1:>3} {disc_acc:>9.1f}% {oos_acc:>9.1f}% {r['oos_n']:>8} {drop:>+7.1f}%  "
                  f"{fmt_conds(r['conds'])}{marker}")

        if drops:
            avg_drop = np.mean(drops)
            med_drop = np.median(drops)
            print(f"\n  过拟合统计 (样本外落差):")
            print(f"    平均落差: {avg_drop:+.1f}% (发现集→验证集的准确率下降)")
            print(f"    中位落差: {med_drop:+.1f}%")
            print(f"    落差>10%的规则: {sum(1 for d in drops if d > 10)}/{len(drops)}")
            print(f"    落差>15%的规则: {sum(1 for d in drops if d > 15)}/{len(drops)}")

            # 验证集上仍超过基线的规则
            still_good = [r for r in has_oos if r['oos_acc'] is not None and r['oos_acc'] > base + 0.05]
            print(f"    验证集仍超基线5%+的规则: {len(still_good)}/{len(has_oos)}")

            if still_good:
                print(f"\n  === 样本外验证仍然有效的规则 ===")
                still_good.sort(key=lambda r: -r['oos_acc'])
                for i, r in enumerate(still_good[:10]):
                    ci_lo, ci_hi = wilson_ci(r['oos_nc'], r['oos_n'])
                    print(f"  [{i+1}] {fmt_conds(r['conds'])}")
                    print(f"      发现: n={r['n']}, acc={r['acc']*100:.1f}%")
                    print(f"      验证: n={r['oos_n']}, acc={r['oos_acc']*100:.1f}%, "
                          f"CI=[{ci_lo*100:.1f}%, {ci_hi*100:.1f}%]")

        # ============================================
        # 测试2: 随机标签置换检验
        # ============================================
        print(f"\n{'='*60}")
        print(f"  测试2: 随机标签置换检验 (Permutation Test)")
        print(f"{'='*60}")

        n_perms = 5
        perm_counts = []

        for perm_i in range(n_perms):
            np.random.seed(perm_i * 42 + 7)
            y_shuffled = y.sample(frac=1.0).reset_index(drop=True)
            shuffled_rules = mine_on_subset(X, y_shuffled, min_acc=min_acc, min_n=20)
            perm_counts.append(len(shuffled_rules))
            print(f"    随机排列 {perm_i+1}: 找到 {len(shuffled_rules)} 条\"高准确率\"规则")

        real_count = len(disc_rules)
        avg_perm = np.mean(perm_counts)
        print(f"\n    真实数据规则数: {real_count}")
        print(f"    随机标签平均: {avg_perm:.0f} 条")

        if avg_perm > 0:
            ratio = real_count / avg_perm
            print(f"    信噪比: {ratio:.1f}x (真实/随机)")
            if ratio < 2:
                print(f"    ⚠ 信噪比 < 2, 大部分规则可能是噪声!")
            elif ratio < 5:
                print(f"    ⚠ 信噪比一般, 部分规则可能是噪声")
            else:
                print(f"    信噪比良好, 规则大概率有真实信号")
        else:
            print(f"    随机标签找不到规则 = 真实规则是可靠的")


    print(f"\n\n{'='*80}")
    print("  总结")
    print("=" * 80)
    print("""
解读指南:
- Walk-Forward落差 < 5%: 规则可靠
- Walk-Forward落差 5-10%: 有轻微过拟合，实际准确率打9折
- Walk-Forward落差 > 10%: 明显过拟合，规则不可直接使用
- 置换信噪比 > 5: 规则可靠
- 置换信噪比 2-5: 需要谨慎
- 置换信噪比 < 2: 大部分规则是噪声

核心建议:
只有同时满足以下条件的规则才是可靠的:
1. Walk-Forward样本外准确率仍 > 基线 + 5%
2. Wilson CI下界 > 基线
3. 样本外验证样本 >= 20
""")


if __name__ == '__main__':
    main()
