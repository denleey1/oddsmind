"""
TOP4覆盖公司 × 让方不输 规则挖掘
===================================
使用覆盖率最高的4家公司(976/16/177/104)的赔率特征，
寻找"让方不输"（初盘低赔方不输）的规律。

目标:
  - 准确率 >= 85%（测试集）
  - 样本量 >= 20 场（避免小样本伪高准确率）
  - 训练/测试准确率差距 <= 10%（避免过拟合）

数据:
  - 让方 = 初盘低赔方（home/away中初盘赔率更低的一方）
  - 让方不输 = 让方赢或平（不是让方负）
"""

import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import get_connection
from collections import defaultdict
import itertools

# 目标公司
COMPANY_IDS = [976, 16, 177, 104]
MIN_COMPANIES = 3       # 至少3家有数据才计算该比赛
MIN_SAMPLES   = 20      # 规则触发最少场数
MIN_ACC       = 0.85    # 最低准确率
MAX_OVERFIT   = 0.10    # 训练/测试准确率最大差距
TRAIN_RATIO   = 0.60    # 训练集比例


def load_data():
    db = get_connection()

    # 所有有结果的比赛
    matches = db.execute_query('''
        SELECT match_id, home_score, away_score
        FROM matches
        WHERE match_status='finished' AND home_score IS NOT NULL
        ORDER BY match_id ASC
    ''', fetch='all')

    match_ids = [m['match_id'] for m in matches]
    result_map = {m['match_id']: m for m in matches}

    ph = ','.join(['%s'] * len(match_ids))
    odds_rows = db.execute_query(f'''
        SELECT match_id, company_id,
               current_home, current_draw, current_away,
               initial_home, initial_away,
               current_return_rate
        FROM european_odds
        WHERE match_id IN ({ph})
          AND company_id IN ({','.join(map(str, COMPANY_IDS))})
          AND initial_home > 1.0 AND initial_away > 1.0
          AND current_home > 1.0 AND current_away > 1.0
    ''', match_ids, fetch='all')

    # 按 match_id 分组
    odds_by_match = defaultdict(dict)
    for o in odds_rows:
        odds_by_match[o['match_id']][o['company_id']] = {
            'ch': float(o['current_home']),
            'cd': float(o['current_draw']),
            'ca': float(o['current_away']),
            'ih': float(o['initial_home']),
            'ia': float(o['initial_away']),
            'rr': float(o['current_return_rate']) if o['current_return_rate'] else 91.0,
        }

    return match_ids, result_map, odds_by_match


def build_features(match_ids, result_map, odds_by_match):
    """构建特征向量"""
    records = []

    for mid in match_ids:
        cdata = odds_by_match.get(mid, {})
        valid = {cid: v for cid, v in cdata.items() if cid in COMPANY_IDS}
        if len(valid) < MIN_COMPANIES:
            continue

        # 按初盘均值判断让方
        ih_vals = [v['ih'] for v in valid.values()]
        ia_vals = [v['ia'] for v in valid.values()]
        avg_ih = sum(ih_vals) / len(ih_vals)
        avg_ia = sum(ia_vals) / len(ia_vals)

        if avg_ih <= avg_ia:
            fav_side = 'home'
            # 让方=主队
            fav = {cid: {'cur': v['ch'], 'ini': v['ih'], 'rr': v['rr']} for cid, v in valid.items()}
            und = {cid: {'cur': v['ca'], 'ini': v['ia'], 'rr': v['rr']} for cid, v in valid.items()}
        else:
            fav_side = 'away'
            fav = {cid: {'cur': v['ca'], 'ini': v['ia'], 'rr': v['rr']} for cid, v in valid.items()}
            und = {cid: {'cur': v['ch'], 'ini': v['ih'], 'rr': v['rr']} for cid, v in valid.items()}

        # 目标变量：让方不输
        r = result_map[mid]
        if fav_side == 'home':
            fav_unbeaten = r['home_score'] >= r['away_score']
        else:
            fav_unbeaten = r['away_score'] >= r['home_score']

        # ============ 特征计算 ============
        feat = {'match_id': mid, 'label': int(fav_unbeaten), 'fav_side': fav_side}

        fav_cur_list = [v['cur'] for v in fav.values()]
        fav_ini_list = [v['ini'] for v in fav.values()]
        und_cur_list = [v['cur'] for v in und.values()]
        und_ini_list = [v['ini'] for v in und.values()]
        rr_list      = [v['rr'] for v in valid.values()]

        n = len(valid)

        # --- 基础均值 ---
        feat['avg_fav_cur']  = sum(fav_cur_list) / n
        feat['avg_fav_ini']  = sum(fav_ini_list) / n
        feat['avg_und_cur']  = sum(und_cur_list) / n
        feat['avg_und_ini']  = sum(und_ini_list) / n
        feat['avg_rr']       = sum(rr_list) / n

        # --- 让方/陪方移动量（正=赔率下降=更多资金流入） ---
        feat['avg_fav_move'] = feat['avg_fav_ini'] - feat['avg_fav_cur']   # 正=让方受支持
        feat['avg_und_move'] = feat['avg_und_ini'] - feat['avg_und_cur']   # 正=陪方受支持
        feat['move_diff']    = feat['avg_fav_move'] - feat['avg_und_move'] # 正=相对更支持让方

        # --- 赔率离散度（公司间分歧） ---
        feat['fav_cur_spread']  = max(fav_cur_list) - min(fav_cur_list)
        feat['fav_ini_spread']  = max(fav_ini_list) - min(fav_ini_list)
        feat['und_cur_spread']  = max(und_cur_list) - min(und_cur_list)
        feat['und_ini_spread']  = max(und_ini_list) - min(und_ini_list)
        feat['rr_spread']       = max(rr_list) - min(rr_list)

        # --- 让方当前赔率区间 ---
        feat['fav_cur_min']  = min(fav_cur_list)
        feat['fav_cur_max']  = max(fav_cur_list)
        feat['fav_ini_min']  = min(fav_ini_list)
        feat['fav_ini_max']  = max(fav_ini_list)

        # --- 各公司移动量 ---
        moves = []
        for cid, v in fav.items():
            m = v['ini'] - v['cur']
            feat[f'c{cid}_fav_move'] = m
            moves.append(m)
        # 所有公司是否同向（都向让方流入）
        feat['all_support_fav']  = int(all(m > 0 for m in moves))
        feat['all_against_fav']  = int(all(m < 0 for m in moves))
        feat['move_consensus']   = sum(1 for m in moves if m > 0) - sum(1 for m in moves if m < 0)  # -n~+n

        # --- Pinnacle(177) 专属（最锐盘之一） ---
        if 177 in valid:
            p = valid[177]
            if fav_side == 'home':
                pf_cur, pf_ini = p['ch'], p['ih']
                pu_cur, pu_ini = p['ca'], p['ia']
            else:
                pf_cur, pf_ini = p['ca'], p['ia']
                pu_cur, pu_ini = p['ch'], p['ih']
            feat['pin_fav_move']   = pf_ini - pf_cur
            feat['pin_fav_cur']    = pf_cur
            feat['pin_und_move']   = pu_ini - pu_cur
            feat['pin_rr']         = p['rr']
            # Pinnacle vs 均值离差
            feat['pin_fav_vs_avg'] = pf_cur - feat['avg_fav_cur']
        else:
            feat['pin_fav_move'] = feat['pin_fav_cur'] = feat['pin_und_move'] = None
            feat['pin_rr']       = feat['pin_fav_vs_avg'] = None

        # --- 返还率分析 ---
        # 高RR公司的让方赔率均值（更"公正"的定价）
        high_rr = {cid: v for cid, v in valid.items() if v['rr'] >= 93.0}
        if len(high_rr) >= 2:
            if fav_side == 'home':
                feat['hirr_fav_cur'] = sum(v['ch'] for v in high_rr.values()) / len(high_rr)
            else:
                feat['hirr_fav_cur'] = sum(v['ca'] for v in high_rr.values()) / len(high_rr)
        else:
            feat['hirr_fav_cur'] = None

        feat['n_companies'] = n
        records.append(feat)

    return records


def scan_single_feature(records, feature_name, direction='positive'):
    """
    扫描单特征阈值。
    direction='positive': feature > threshold 时触发
    direction='negative': feature < threshold 时触发
    返回所有满足 MIN_ACC+MIN_SAMPLES 的 (threshold, acc, n) 列表
    """
    vals = [(r[feature_name], r['label']) for r in records if r.get(feature_name) is not None]
    if len(vals) < MIN_SAMPLES * 2:
        return []

    vals.sort(key=lambda x: x[0])
    all_vals = [v[0] for v in vals]
    unique_vals = sorted(set(all_vals))

    results = []
    for thresh in unique_vals:
        if direction == 'positive':
            subset = [l for v, l in vals if v > thresh]
        else:
            subset = [l for v, l in vals if v < thresh]
        n = len(subset)
        if n < MIN_SAMPLES:
            continue
        acc = sum(subset) / n
        if acc >= MIN_ACC:
            results.append((thresh, acc, n))

    return results


def evaluate_rule(records, conditions):
    """
    评估一个规则（多条件AND）在给定数据集上的准确率。
    conditions: [(feature, direction, threshold), ...]
    Returns (n_triggered, accuracy)
    """
    hits = 0
    total = 0
    for r in records:
        triggered = True
        for feat, direction, thresh in conditions:
            v = r.get(feat)
            if v is None:
                triggered = False
                break
            if direction == 'positive' and not (v > thresh):
                triggered = False
                break
            if direction == 'negative' and not (v < thresh):
                triggered = False
                break
        if triggered:
            total += 1
            hits += r['label']
    if total == 0:
        return 0, 0.0
    return total, hits / total


def main():
    print("=" * 65)
    print("  TOP4覆盖公司 × 让方不输  规则挖掘")
    print("  公司: 18Bet(976) / 10Bet(16) / Pinnacle(177) / Interwetten(104)")
    print("=" * 65)

    print("\n[1/5] 加载数据...")
    match_ids, result_map, odds_by_match = load_data()
    print(f"  共 {len(match_ids)} 场有结果的比赛")

    print("\n[2/5] 构建特征矩阵...")
    records = build_features(match_ids, result_map, odds_by_match)
    print(f"  有效特征记录: {len(records)} 场")
    print(f"  让方不输率（基准）: {sum(r['label'] for r in records)/len(records)*100:.1f}%")

    # 时间分割（match_id升序=时间升序）
    split = int(len(records) * TRAIN_RATIO)
    train = records[:split]
    test  = records[split:]
    print(f"  训练集: {len(train)} 场  测试集: {len(test)} 场")
    print(f"  训练集让方不输率: {sum(r['label'] for r in train)/len(train)*100:.1f}%")
    print(f"  测试集让方不输率: {sum(r['label'] for r in test)/len(test)*100:.1f}%")

    # ==================== 单特征扫描 ====================
    print("\n[3/5] 单特征阈值扫描（训练集）...")

    feature_directions = [
        ('avg_fav_move',     'positive',  '让方均值移动>阈值（市场支持让方）'),
        ('avg_und_move',     'negative',  '陪方均值移动<阈值（陪方无支撑）'),
        ('move_diff',        'positive',  '移动量差值>阈值（让方相对更受支持）'),
        ('fav_cur_spread',   'positive',  '让方当前赔率离散>阈值（公司间分歧大）'),
        ('fav_cur_spread',   'negative',  '让方当前赔率离散<阈值（公司间一致）'),
        ('und_cur_spread',   'positive',  '陪方当前赔率离散>阈值'),
        ('rr_spread',        'positive',  '返还率离散>阈值（公司间差异大）'),
        ('rr_spread',        'negative',  '返还率离散<阈值（公司定价一致）'),
        ('avg_fav_cur',      'negative',  '让方均值当前赔率<阈值（强热门）'),
        ('avg_fav_cur',      'positive',  '让方均值当前赔率>阈值（弱热门）'),
        ('avg_fav_ini',      'negative',  '让方均值开盘赔率<阈值'),
        ('move_consensus',   'positive',  '移动共识>阈值（多公司同向支持让方）'),
        ('move_consensus',   'negative',  '移动共识<阈值（多公司同向背离让方）'),
        ('all_support_fav',  'positive',  '所有公司都向让方移动'),
        ('all_against_fav',  'negative',  '没有公司向陪方移动'),
        ('pin_fav_move',     'positive',  'Pinnacle让方移动>阈值'),
        ('pin_fav_move',     'negative',  'Pinnacle让方移动<阈值'),
        ('pin_fav_vs_avg',   'negative',  'Pinnacle让方赔率低于均值（Pinnacle更看好让方）'),
        ('pin_fav_vs_avg',   'positive',  'Pinnacle让方赔率高于均值（Pinnacle不看好让方）'),
        ('hirr_fav_cur',     'negative',  '高RR公司让方赔率<阈值'),
        ('avg_rr',           'positive',  '均值返还率>阈值（高返还率环境）'),
        ('avg_und_cur',      'positive',  '陪方当前赔率>阈值（陪方赔率高）'),
        # 单公司
        ('c976_fav_move',    'positive',  '18Bet让方移动>阈值'),
        ('c976_fav_move',    'negative',  '18Bet让方移动<阈值'),
        ('c16_fav_move',     'positive',  '10Bet让方移动>阈值'),
        ('c16_fav_move',     'negative',  '10Bet让方移动<阈值'),
        ('c177_fav_move',    'positive',  'Pinnacle让方移动>阈值'),
        ('c177_fav_move',    'negative',  'Pinnacle让方移动<阈值'),
        ('c104_fav_move',    'positive',  'Interwetten让方移动>阈值'),
        ('c104_fav_move',    'negative',  'Interwetten让方移动<阈值'),
    ]

    # 对每个特征在训练集扫描，取最佳阈值
    candidate_conditions = []  # (feat, dir, thresh, train_acc, train_n, desc)

    for feat, direction, desc in feature_directions:
        results = scan_single_feature(train, feat, direction)
        if not results:
            continue
        # 取 acc 最高的同时 n 最大的（优先acc，acc相同取n最大）
        best = sorted(results, key=lambda x: (x[1], x[2]))[-1]
        thresh, acc, n = best
        candidate_conditions.append((feat, direction, thresh, acc, n, desc))

    candidate_conditions.sort(key=lambda x: -x[3])

    print(f"\n  训练集通过 85% 门槛的单特征候选: {len(candidate_conditions)} 个")
    print()
    print("  %-30s %-10s %-10s %-8s %-8s" % ('特征','方向','阈值','训练准确率','触发场数'))
    print("  " + "-" * 70)
    for feat, direction, thresh, acc, n, desc in candidate_conditions[:20]:
        dirstr = '>阈值' if direction == 'positive' else '<阈值'
        print("  %-30s %-10s %-10.3f %-8.1f%%  %-6d" % (feat, dirstr, thresh, acc*100, n))

    if not candidate_conditions:
        print("  未找到满足条件的单特征规则。")
        return

    # ==================== 组合规则搜索 ====================
    print("\n[4/5] 组合规则搜索（训练集，2-3条件AND）...")

    # 只取训练集acc最高的前15个候选进行组合
    top_cands = candidate_conditions[:15]
    combo_results = []

    # 两两组合
    for (f1, d1, t1, a1, n1, desc1), (f2, d2, t2, a2, n2, desc2) in itertools.combinations(top_cands, 2):
        if f1 == f2:
            continue
        conds = [(f1, d1, t1), (f2, d2, t2)]
        n, acc = evaluate_rule(train, conds)
        if n >= MIN_SAMPLES and acc >= MIN_ACC:
            combo_results.append((conds, acc, n, 2))

    # 三条件组合（只用acc最高的前8个）
    top8 = top_cands[:8]
    for trio in itertools.combinations(top8, 3):
        feats = [c[0] for c in trio]
        if len(set(feats)) < 3:
            continue
        conds = [(c[0], c[1], c[2]) for c in trio]
        n, acc = evaluate_rule(train, conds)
        if n >= MIN_SAMPLES and acc >= MIN_ACC:
            combo_results.append((conds, acc, n, 3))

    combo_results.sort(key=lambda x: (-x[1], -x[2]))
    print(f"  组合候选: {len(combo_results)} 个")

    # ==================== 测试集验证 ====================
    print("\n[5/5] 测试集验证 + 过拟合检验...")

    # 所有候选：单特征 + 组合
    all_candidates = []

    # 单特征
    for feat, direction, thresh, train_acc, train_n, desc in candidate_conditions:
        conds = [(feat, direction, thresh)]
        test_n, test_acc = evaluate_rule(test, conds)
        all_candidates.append({
            'conds': conds, 'train_acc': train_acc, 'train_n': train_n,
            'test_acc': test_acc,  'test_n': test_n,
            'n_conds': 1, 'desc': desc,
        })

    # 组合规则
    for conds, train_acc, train_n, n_conds in combo_results:
        test_n, test_acc = evaluate_rule(test, conds)
        desc = ' AND '.join(f'{f}{">" if d=="positive" else "<"}{t:.3f}' for f,d,t in conds)
        all_candidates.append({
            'conds': conds, 'train_acc': train_acc, 'train_n': train_n,
            'test_acc': test_acc,  'test_n': test_n,
            'n_conds': n_conds,    'desc': desc,
        })

    # 过滤：测试集 acc >= 85% 且样本足够 且 训练/测试差距 <= MAX_OVERFIT
    passed = [c for c in all_candidates
              if c['test_acc']  >= MIN_ACC
              and c['test_n']   >= MIN_SAMPLES
              and abs(c['train_acc'] - c['test_acc']) <= MAX_OVERFIT]

    passed.sort(key=lambda x: (-x['test_acc'], -x['test_n']))

    print(f"\n  候选总数: {len(all_candidates)}")
    print(f"  通过测试集85%+门槛: {sum(1 for c in all_candidates if c['test_acc']>=MIN_ACC and c['test_n']>=MIN_SAMPLES)}")
    print(f"  通过过拟合检验: {len(passed)}")

    # ==================== 输出最终规则 ====================
    print("\n" + "=" * 65)
    print("  最终有效规则（测试集 >= 85%，无过拟合）")
    print("=" * 65)

    if not passed:
        print("\n  未找到满足全部条件的规则。")
        print("\n  放宽标准查看接近规则（测试集>=80%，差距<=12%）：")
        relaxed = [c for c in all_candidates
                   if c['test_acc'] >= 0.80
                   and c['test_n']  >= MIN_SAMPLES
                   and abs(c['train_acc'] - c['test_acc']) <= 0.12]
        relaxed.sort(key=lambda x: (-x['test_acc'], -x['test_n']))
        for i, c in enumerate(relaxed[:10], 1):
            print(f"\n  # 规则 R{i:02d}（测试={c['test_acc']*100:.1f}%）")
            for feat, direction, thresh in c['conds']:
                dirstr = '>' if direction == 'positive' else '<'
                print(f"    {feat} {dirstr} {thresh:.3f}")
            print(f"    训练: {c['train_n']}场 {c['train_acc']*100:.1f}%  |  "
                  f"测试: {c['test_n']}场 {c['test_acc']*100:.1f}%  |  "
                  f"差距: {abs(c['train_acc']-c['test_acc'])*100:.1f}%")
    else:
        for i, c in enumerate(passed[:15], 1):
            print(f"\n  规则 R{i:02d}  ({c['n_conds']}条件)")
            for feat, direction, thresh in c['conds']:
                dirstr = '>' if direction == 'positive' else '<'
                # 找描述
                desc_text = next((desc for f,d,t,a,n,desc in candidate_conditions
                                  if f==feat and d==direction), feat)
                print(f"    {feat} {dirstr} {thresh:.3f}   # {desc_text}")
            print(f"    训练: {c['train_n']:4d}场  {c['train_acc']*100:.1f}%  | "
                  f" 测试: {c['test_n']:4d}场  {c['test_acc']*100:.1f}%  | "
                  f" 差距: {abs(c['train_acc']-c['test_acc'])*100:.1f}%")

    # 额外：打印所有候选的测试集排名（不管有没有通过）
    print("\n\n--- 测试集准确率排名（所有候选 TOP30，含未通过过拟合的）---")
    top_test = sorted(all_candidates, key=lambda x: (-x['test_acc'] if x['test_n']>=MIN_SAMPLES else 0, -x['test_n']))
    print("%-6s %-45s %-8s %-8s %-8s %-8s %-6s" % (
        '排名','条件描述','训练acc','训练N','测试acc','测试N','差距'))
    print("-" * 95)
    for i, c in enumerate(top_test[:30], 1):
        if c['test_n'] < MIN_SAMPLES:
            continue
        desc = ' & '.join(f'{f}{">" if d=="positive" else "<"}{t:.2f}' for f,d,t in c['conds'])
        flag = '' if abs(c['train_acc']-c['test_acc']) <= MAX_OVERFIT else '⚠过拟合'
        flag += '' if c['test_acc'] >= MIN_ACC else ''
        print("%-6d %-45s %-8.1f %-8d %-8.1f %-8d %-6s" % (
            i, desc[:45], c['train_acc']*100, c['train_n'],
            c['test_acc']*100, c['test_n'], flag))


if __name__ == '__main__':
    main()
