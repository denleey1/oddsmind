"""
TOP4覆盖公司 × 让方不输  规则挖掘 v2
========================================
修正方向：
  - 只分析竞争性比赛（让方初盘均值 1.30 ~ 2.80）
  - 排除悬殊对阵（赔率太低不需要分析）
  - 目标：找到覆盖率 >= 2%（约 490+ 场）且准确率 >= 85% 的规则
  - 过拟合检验：训练/测试差距 <= 8%

特征重心：
  - 4家公司的开盘→即时移动方向一致性
  - Pinnacle(最锐盘)的移动和定价差
  - 各公司移动量的大小和分布
  - 返还率变化（反映资金流向）
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_connection
from collections import defaultdict
import itertools, numpy as np

COMPANY_IDS   = [976, 16, 177, 104]
MIN_COMPANIES = 3
# 竞争性比赛过滤：让方初盘均值在此区间
FAV_INI_LO    = 1.30
FAV_INI_HI    = 2.80
# 规则要求
MIN_SAMPLES   = 50     # 至少50场（约训练集2%以上）
MIN_ACC       = 0.85
MAX_OVERFIT   = 0.08
TRAIN_RATIO   = 0.60


def load_data():
    db = get_connection()
    matches = db.execute_query(
        "SELECT match_id, home_score, away_score FROM matches "
        "WHERE match_status='finished' AND home_score IS NOT NULL "
        "ORDER BY match_id ASC", fetch='all')

    match_ids  = [m['match_id'] for m in matches]
    result_map = {m['match_id']: m for m in matches}

    ph = ','.join(['%s'] * len(match_ids))
    odds_rows = db.execute_query(f'''
        SELECT match_id, company_id,
               current_home, current_draw, current_away,
               initial_home, initial_away, current_return_rate
        FROM european_odds
        WHERE match_id IN ({ph})
          AND company_id IN ({','.join(map(str, COMPANY_IDS))})
          AND initial_home > 1.0 AND initial_away > 1.0
          AND current_home > 1.0 AND current_away > 1.0
    ''', match_ids, fetch='all')

    by_match = defaultdict(dict)
    for o in odds_rows:
        by_match[o['match_id']][o['company_id']] = {
            'ch': float(o['current_home']),  'cd': float(o['current_draw']),
            'ca': float(o['current_away']),  'ih': float(o['initial_home']),
            'ia': float(o['initial_away']),  'rr': float(o['current_return_rate'] or 91.0),
        }
    return match_ids, result_map, by_match


def build_features(match_ids, result_map, by_match):
    records = []
    skipped_extreme = 0

    for mid in match_ids:
        cdata = {cid: v for cid, v in by_match.get(mid, {}).items() if cid in COMPANY_IDS}
        if len(cdata) < MIN_COMPANIES:
            continue

        ih_list = [v['ih'] for v in cdata.values()]
        ia_list = [v['ia'] for v in cdata.values()]
        avg_ih  = sum(ih_list) / len(ih_list)
        avg_ia  = sum(ia_list) / len(ia_list)

        # 让方 = 初盘低赔方
        if avg_ih <= avg_ia:
            fav_side = 'home'
            fav_ini  = avg_ih
            und_ini  = avg_ia
            fav_cur  = sum(v['ch'] for v in cdata.values()) / len(cdata)
            und_cur  = sum(v['ca'] for v in cdata.values()) / len(cdata)
            per_c = {cid: {'ini': v['ih'], 'cur': v['ch'],
                            'u_ini': v['ia'], 'u_cur': v['ca'], 'rr': v['rr']}
                     for cid, v in cdata.items()}
        else:
            fav_side = 'away'
            fav_ini  = avg_ia
            und_ini  = avg_ih
            fav_cur  = sum(v['ca'] for v in cdata.values()) / len(cdata)
            und_cur  = sum(v['ch'] for v in cdata.values()) / len(cdata)
            per_c = {cid: {'ini': v['ia'], 'cur': v['ca'],
                            'u_ini': v['ih'], 'u_cur': v['ch'], 'rr': v['rr']}
                     for cid, v in cdata.items()}

        # 过滤悬殊对阵
        if not (FAV_INI_LO <= fav_ini <= FAV_INI_HI):
            skipped_extreme += 1
            continue

        r = result_map[mid]
        if fav_side == 'home':
            label = int(r['home_score'] >= r['away_score'])
        else:
            label = int(r['away_score'] >= r['home_score'])

        n = len(cdata)
        f_moves = [v['ini'] - v['cur'] for v in per_c.values()]    # 正=赔率下降=资金流入
        u_moves = [v['u_ini'] - v['u_cur'] for v in per_c.values()]

        feat = {
            'match_id': mid, 'label': label, 'fav_side': fav_side,

            # 均值赔率
            'avg_fav_ini': fav_ini,
            'avg_fav_cur': fav_cur,
            'avg_und_ini': und_ini,
            'avg_und_cur': und_cur,
            'avg_rr':      sum(v['rr'] for v in cdata.values()) / n,

            # 移动量（正=让方受支持，负=被抛弃）
            'avg_fav_move': sum(f_moves) / n,
            'avg_und_move': sum(u_moves) / n,
            'move_diff':    sum(f_moves) / n - sum(u_moves) / n,

            # 移动一致性：正数=几家向让方移动 - 几家背离
            'fav_move_consensus': sum(1 for m in f_moves if m > 0) - sum(1 for m in f_moves if m < 0),
            'und_move_consensus': sum(1 for m in u_moves if m < 0) - sum(1 for m in u_moves if m > 0),
            # 两侧一致性之和（全市场对让方的态度）
            'total_consensus': (sum(1 for m in f_moves if m > 0) +
                                sum(1 for m in u_moves if m < 0)),  # 0~2n

            # 移动量绝对值（总幅度，不管方向）
            'fav_move_magnitude': sum(abs(m) for m in f_moves) / n,
            'und_move_magnitude': sum(abs(m) for m in u_moves) / n,

            # 离散度
            'fav_cur_spread': max(v['cur'] for v in per_c.values()) - min(v['cur'] for v in per_c.values()),
            'und_cur_spread': max(v['u_cur'] for v in per_c.values()) - min(v['u_cur'] for v in per_c.values()),
            'fav_ini_spread': max(v['ini'] for v in per_c.values()) - min(v['ini'] for v in per_c.values()),

            # 赔率漂移方向（即时相对开盘）
            'fav_drifted':  int(fav_cur > fav_ini),   # 让方赔率变高=市场变不看好让方
            'und_drifted':  int(und_cur > und_ini),   # 陪方赔率变高=市场更不看好陪方

            # 数量
            'n_companies': n,
        }

        # Pinnacle(177) 专属
        if 177 in per_c:
            p = per_c[177]
            feat['pin_fav_move']    = p['ini'] - p['cur']
            feat['pin_und_move']    = p['u_ini'] - p['u_cur']
            feat['pin_fav_cur']     = p['cur']
            feat['pin_rr']          = p['rr']
            feat['pin_fav_vs_avg']  = p['cur'] - fav_cur     # 正=Pinnacle更贵=不看好让方
            feat['pin_und_vs_avg']  = p['u_cur'] - und_cur
        else:
            for k in ['pin_fav_move','pin_und_move','pin_fav_cur','pin_rr','pin_fav_vs_avg','pin_und_vs_avg']:
                feat[k] = None

        # 各公司单独移动量
        for cid in COMPANY_IDS:
            if cid in per_c:
                feat[f'c{cid}_fav_move'] = per_c[cid]['ini'] - per_c[cid]['cur']
                feat[f'c{cid}_und_move'] = per_c[cid]['u_ini'] - per_c[cid]['u_cur']
            else:
                feat[f'c{cid}_fav_move'] = None
                feat[f'c{cid}_und_move'] = None

        records.append(feat)

    return records, skipped_extreme


def scan_thresholds(data, feat, direction, min_n, min_acc):
    """扫描某特征的所有阈值，返回满足条件的(thresh, acc, n)列表"""
    vals = [(r[feat], r['label']) for r in data if r.get(feat) is not None]
    if len(vals) < min_n * 3:
        return []

    vals.sort(key=lambda x: x[0])
    unique = sorted({v[0] for v in vals})

    out = []
    for thresh in unique:
        if direction == '>':
            sub = [l for v, l in vals if v > thresh]
        else:
            sub = [l for v, l in vals if v < thresh]
        if len(sub) < min_n:
            continue
        acc = sum(sub) / len(sub)
        if acc >= min_acc:
            out.append((thresh, acc, len(sub)))
    return out


def best_thresh(data, feat, direction, min_n, min_acc):
    """返回最大化 acc*n 的阈值"""
    results = scan_thresholds(data, feat, direction, min_n, min_acc)
    if not results:
        return None
    # 优先 acc 高，acc 相同取 n 大
    return max(results, key=lambda x: (x[1], x[2]))


def evaluate(data, conditions):
    hits = total = 0
    for r in data:
        ok = True
        for feat, direction, thresh in conditions:
            v = r.get(feat)
            if v is None:
                ok = False; break
            if direction == '>' and v <= thresh:
                ok = False; break
            if direction == '<' and v >= thresh:
                ok = False; break
        if ok:
            total += 1
            hits  += r['label']
    return total, (hits / total if total else 0.0)


def main():
    print("=" * 65)
    print("  TOP4覆盖公司 × 让方不输  规则挖掘 v2")
    print(f"  竞争性区间：让方初盘均值 {FAV_INI_LO} ~ {FAV_INI_HI}")
    print("=" * 65)

    print("\n[1/5] 加载数据...")
    match_ids, result_map, by_match = load_data()

    print("\n[2/5] 构建特征矩阵...")
    records, skipped = build_features(match_ids, result_map, by_match)
    print(f"  竞争性比赛: {len(records)} 场（排除悬殊 {skipped} 场）")
    base = sum(r['label'] for r in records) / len(records)
    print(f"  基准让方不输率: {base*100:.1f}%")

    split = int(len(records) * TRAIN_RATIO)
    train = records[:split]
    test  = records[split:]
    print(f"  训练集: {len(train)} 场  测试集: {len(test)} 场")
    print(f"  训练基准: {sum(r['label'] for r in train)/len(train)*100:.1f}%  "
          f"测试基准: {sum(r['label'] for r in test)/len(test)*100:.1f}%")

    total_train = len(train)

    # 所有要扫描的特征+方向
    feature_dirs = [
        ('avg_fav_move',       '>'),   # 市场向让方流入
        ('avg_fav_move',       '<'),   # 市场背离让方
        ('avg_und_move',       '<'),   # 陪方赔率上涨（被抛弃）
        ('avg_und_move',       '>'),   # 陪方赔率下降（受支持）
        ('move_diff',          '>'),   # 让方相对更受支持
        ('move_diff',          '<'),
        ('fav_move_consensus', '>'),   # 多公司同向支持让方
        ('fav_move_consensus', '<'),
        ('und_move_consensus', '>'),   # 多公司同向抛弃陪方
        ('total_consensus',    '>'),   # 全市场对让方的支持度
        ('total_consensus',    '<'),
        ('fav_move_magnitude', '>'),   # 让方移动幅度大
        ('und_move_magnitude', '>'),   # 陪方移动幅度大
        ('avg_fav_cur',        '>'),   # 让方即时赔率高（不确定性大）
        ('avg_fav_cur',        '<'),
        ('avg_und_cur',        '>'),
        ('avg_und_cur',        '<'),
        ('fav_cur_spread',     '>'),   # 让方赔率公司间离散
        ('fav_cur_spread',     '<'),
        ('und_cur_spread',     '>'),
        ('und_cur_spread',     '<'),
        ('fav_ini_spread',     '>'),
        ('pin_fav_move',       '>'),   # Pinnacle更看好让方
        ('pin_fav_move',       '<'),
        ('pin_und_move',       '<'),   # Pinnacle不看好陪方
        ('pin_fav_vs_avg',     '<'),   # Pinnacle让方赔率比均值低（更看好）
        ('pin_fav_vs_avg',     '>'),
        ('avg_rr',             '>'),
        ('avg_rr',             '<'),
        ('c976_fav_move',      '>'),
        ('c976_fav_move',      '<'),
        ('c16_fav_move',       '>'),
        ('c16_fav_move',       '<'),
        ('c177_fav_move',      '>'),
        ('c177_fav_move',      '<'),
        ('c104_fav_move',      '>'),
        ('c104_fav_move',      '<'),
        ('c976_und_move',      '<'),
        ('c16_und_move',       '<'),
        ('c177_und_move',      '<'),
        ('c104_und_move',      '<'),
    ]

    print("\n[3/5] 单特征扫描（训练集，覆盖 >= 50 场）...")
    candidates = []
    for feat, direction in feature_dirs:
        bt = best_thresh(train, feat, direction, MIN_SAMPLES, MIN_ACC)
        if bt is None:
            continue
        thresh, acc, n = bt
        pct = n / total_train * 100
        candidates.append((feat, direction, thresh, acc, n, pct))

    candidates.sort(key=lambda x: (-x[3], -x[4]))
    print(f"  训练集通过 85%+门槛 候选: {len(candidates)} 个\n")
    print("  %-30s %-4s %-8s %-8s %-8s %-6s" % ('特征','方向','阈值','训练acc','训练N','覆盖%'))
    print("  " + "-"*66)
    for feat, direction, thresh, acc, n, pct in candidates:
        print("  %-30s %-4s %-8.3f %-8.1f %-8d %.1f%%" % (
            feat, direction, thresh, acc*100, n, pct))

    if not candidates:
        print("\n  训练集无单特征通过85%。查看最高准确率：")
        for feat, direction in feature_dirs[:10]:
            bt = best_thresh(train, feat, direction, 30, 0.0)
            if bt:
                thresh, acc, n = bt
                print(f"    {feat} {direction} {thresh:.3f}: {acc*100:.1f}% ({n}场)")
        return

    # ==================== 两两组合 ====================
    print("\n[4/5] 两两组合（训练集）...")
    top = candidates[:20]
    combo = []
    for (f1,d1,t1,a1,n1,p1),(f2,d2,t2,a2,n2,p2) in itertools.combinations(top, 2):
        if f1 == f2: continue
        conds = [(f1,d1,t1),(f2,d2,t2)]
        n, acc = evaluate(train, conds)
        if n >= MIN_SAMPLES and acc >= MIN_ACC:
            combo.append((conds, acc, n, n/total_train*100))

    # 三条件组合（只用前10个）
    for trio in itertools.combinations(top[:10], 3):
        if len({c[0] for c in trio}) < 3: continue
        conds = [(c[0],c[1],c[2]) for c in trio]
        n, acc = evaluate(train, conds)
        if n >= MIN_SAMPLES and acc >= MIN_ACC:
            combo.append((conds, acc, n, n/total_train*100))

    combo.sort(key=lambda x: (-x[1], -x[3]))
    print(f"  组合候选: {len(combo)} 个")

    # ==================== 测试集验证 ====================
    print("\n[5/5] 测试集验证 + 过拟合检验...")
    total_test = len(test)

    all_rules = []
    for feat, direction, thresh, train_acc, train_n, train_pct in candidates:
        conds = [(feat, direction, thresh)]
        test_n, test_acc = evaluate(test, conds)
        all_rules.append({
            'conds': conds, 'n_conds': 1,
            'train_acc': train_acc, 'train_n': train_n, 'train_pct': train_pct,
            'test_acc': test_acc, 'test_n': test_n, 'test_pct': test_n/total_test*100,
        })

    for conds, train_acc, train_n, train_pct in combo:
        test_n, test_acc = evaluate(test, conds)
        all_rules.append({
            'conds': conds, 'n_conds': len(conds),
            'train_acc': train_acc, 'train_n': train_n, 'train_pct': train_pct,
            'test_acc': test_acc, 'test_n': test_n, 'test_pct': test_n/total_test*100,
        })

    passed = [r for r in all_rules
              if r['test_acc']  >= MIN_ACC
              and r['test_n']   >= MIN_SAMPLES
              and abs(r['train_acc'] - r['test_acc']) <= MAX_OVERFIT]
    passed.sort(key=lambda x: (-x['test_acc'], -x['test_n']))

    print(f"\n  候选总数: {len(all_rules)}")
    print(f"  通过测试集85%+: {sum(1 for r in all_rules if r['test_acc']>=MIN_ACC and r['test_n']>=MIN_SAMPLES)}")
    print(f"  通过过拟合检验: {len(passed)}")

    # ==================== 输出 ====================
    print("\n" + "=" * 65)
    print("  最终有效规则（测试集 >= 85%，无过拟合，覆盖 >= 50 场）")
    print("=" * 65)

    if passed:
        for i, r in enumerate(passed[:20], 1):
            cond_str = '  AND\n    '.join(
                f"{f} {d} {t:.3f}" for f,d,t in r['conds'])
            print(f"\n  规则 R{i:02d}  ({r['n_conds']} 条件)")
            print(f"    {cond_str}")
            print(f"    训练: {r['train_n']:5d}场 ({r['train_pct']:.1f}%) {r['train_acc']*100:.1f}%  |  "
                  f"测试: {r['test_n']:5d}场 ({r['test_pct']:.1f}%) {r['test_acc']*100:.1f}%  |  "
                  f"差距: {abs(r['train_acc']-r['test_acc'])*100:.1f}%")
    else:
        print("\n  未找到满足全部条件的规则。")

    # 不管有没有通过，都打印完整测试集排名
    print("\n\n--- 测试集排名（所有规则，按测试acc排序）---")
    sorted_all = sorted(
        [r for r in all_rules if r['test_n'] >= MIN_SAMPLES],
        key=lambda x: (-x['test_acc'], -x['test_n'])
    )
    print("%-4s %-50s %-8s %-6s %-8s %-6s %-6s" % (
        '排名','条件（截短）','训练acc','训练N','测试acc','测试N','差距'))
    print("-" * 95)
    for i, r in enumerate(sorted_all[:30], 1):
        desc = ' & '.join(f"{f}{d}{t:.2f}" for f,d,t in r['conds'])[:50]
        flag = '' if abs(r['train_acc']-r['test_acc'])<=MAX_OVERFIT else ' ⚠过拟合'
        ok   = '✓' if r['test_acc']>=MIN_ACC else ' '
        print("%-4d %-50s %-8.1f %-6d %-8.1f %-6d %.1f%%%s%s" % (
            i, desc, r['train_acc']*100, r['train_n'],
            r['test_acc']*100, r['test_n'],
            abs(r['train_acc']-r['test_acc'])*100, flag, ok))


if __name__ == '__main__':
    main()
