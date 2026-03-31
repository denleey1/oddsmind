#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
三重验证规则挖掘：
  1. 二项检验 + Benjamini-Hochberg FDR 校正
  2. 置换检验（Permutation Test）
  3. 前滚验证（Walk-Forward Validation）
"""
import os
import sys
import random
from collections import defaultdict
from itertools import combinations
from datetime import datetime
import pymysql
import pymysql.cursors
from scipy.stats import binomtest
import numpy as np

sys.stdout.reconfigure(encoding='utf-8')

RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']
COMPANY_ID = '115'
MIN_ODDS = 1.40
MIN_SAMPLE = 10
N_PERMUTATIONS = 500
FDR_ALPHA = 0.05


def get_db():
    return pymysql.connect(
        host='localhost', port=3306,
        user='root', password=os.environ.get('MYSQL_PASSWORD', ''),
        database='oddsmind', charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )


def get_range_type(range_str):
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def classify_odds_change(init, curr):
    if init is None or curr is None or float(init) == 0:
        return '未知'
    ratio = float(curr) / float(init)
    if ratio > 1.05:
        return '升'
    elif ratio < 0.95:
        return '降'
    return '稳'


def classify_power_diff(diff):
    if diff is None:
        return '未知'
    d = float(diff)
    if d > 2:
        return '强让'
    elif d > 0.5:
        return '微让'
    elif d > -0.5:
        return '平手'
    elif d > -2:
        return '微受'
    else:
        return '强受'


def load_data():
    conn = get_db()
    query = '''
        SELECT
            oar.match_id,
            oar.initial_home_range, oar.initial_away_range, oar.initial_draw_range,
            oar.current_home_range, oar.current_away_range, oar.current_draw_range,
            oar.power_diff,
            m.home_score, m.away_score, m.match_time,
            eo.initial_home, eo.initial_draw, eo.initial_away,
            eo.current_home, eo.current_draw, eo.current_away
        FROM odds_analysis_results oar
        JOIN matches m ON oar.match_id = m.match_id
        JOIN odds_changes eo ON oar.match_id = eo.match_id AND oar.company_id = eo.company_id
        WHERE oar.company_id = %s
          AND m.match_status = 'finished'
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
        ORDER BY m.match_time
    '''
    try:
        with conn.cursor() as cursor:
            cursor.execute(query, (COMPANY_ID,))
            return cursor.fetchall()
    finally:
        conn.close()


def process(rows):
    matches = []
    for row in rows:
        ih = float(row['initial_home'])
        ia = float(row['initial_away'])
        ch = float(row['current_home'])
        ca = float(row['current_away'])

        if ih <= ia:
            h_score, r_score = row['home_score'], row['away_score']
            init_h_range = row['initial_home_range']
            init_r_range = row['initial_away_range']
            curr_h_range = row['current_home_range']
            curr_r_range = row['current_away_range']
            init_h_odds, init_r_odds = ih, ia
            curr_h_odds, curr_r_odds = ch, ca
        else:
            h_score, r_score = row['away_score'], row['home_score']
            init_h_range = row['initial_away_range']
            init_r_range = row['initial_home_range']
            curr_h_range = row['current_away_range']
            curr_r_range = row['current_home_range']
            init_h_odds, init_r_odds = ia, ih
            curr_h_odds, curr_r_odds = ca, ch

        if h_score > r_score:
            result = 'handicap_win'
        elif h_score == r_score:
            result = 'draw'
        else:
            result = 'receiver_win'

        if curr_h_odds < MIN_ODDS:
            continue

        matches.append({
            'match_time': row['match_time'],
            'result': result,
            'curr_h_odds': curr_h_odds,
            'curr_h': get_range_type(curr_h_range),
            'curr_r': get_range_type(curr_r_range),
            'curr_draw': row['current_draw_range'],
            'init_h': get_range_type(init_h_range),
            'init_r': get_range_type(init_r_range),
            'init_draw': row['initial_draw_range'],
            'h_change': classify_odds_change(init_h_odds, curr_h_odds),
            'r_change': classify_odds_change(init_r_odds, curr_r_odds),
            'd_change': classify_odds_change(row['initial_draw'], row['current_draw']),
            'power': classify_power_diff(row['power_diff']),
        })
    return matches


# ====== 维度定义 ======
DIM_NAMES = [
    '即时让方', '即时受让方', '即时平局',
    '初盘让方', '初盘受让方', '初盘平局',
    '让方变化', '受让方变化', '平赔变化', '力量差',
]
DIM_KEYS = [
    'curr_h', 'curr_r', 'curr_draw',
    'init_h', 'init_r', 'init_draw',
    'h_change', 'r_change', 'd_change', 'power',
]

TARGETS = {
    '让方必赢': lambda m: m['result'] == 'handicap_win',
    '让方不输': lambda m: m['result'] in ('handicap_win', 'draw'),
    '受让方不输': lambda m: m['result'] in ('receiver_win', 'draw'),
}


def mine_rules(matches, min_sample=MIN_SAMPLE, min_acc=75.0):
    """挖掘所有1D/2D/3D规则，返回列表"""
    results = []
    n_dims = len(DIM_KEYS)

    # 1D
    for i in range(n_dims):
        key = DIM_KEYS[i]
        name = DIM_NAMES[i]
        groups = defaultdict(list)
        for m in matches:
            v = m[key]
            if v:
                groups[v].append(m)
        for val, group in groups.items():
            if len(group) < min_sample:
                continue
            for tname, tfn in TARGETS.items():
                hits = sum(1 for m in group if tfn(m))
                acc = hits / len(group) * 100
                if acc >= min_acc:
                    results.append({
                        'condition': f'{name}={val}',
                        'target': tname,
                        'sample': len(group),
                        'hits': hits,
                        'accuracy': acc,
                    })

    # 2D
    for i, j in combinations(range(n_dims), 2):
        ki, kj = DIM_KEYS[i], DIM_KEYS[j]
        ni, nj = DIM_NAMES[i], DIM_NAMES[j]
        groups = defaultdict(list)
        for m in matches:
            vi, vj = m[ki], m[kj]
            if vi and vj:
                groups[(vi, vj)].append(m)
        for (vi, vj), group in groups.items():
            if len(group) < min_sample:
                continue
            for tname, tfn in TARGETS.items():
                hits = sum(1 for m in group if tfn(m))
                acc = hits / len(group) * 100
                if acc >= min_acc:
                    results.append({
                        'condition': f'{ni}={vi} + {nj}={vj}',
                        'target': tname,
                        'sample': len(group),
                        'hits': hits,
                        'accuracy': acc,
                    })

    # 3D
    for i, j, k in combinations(range(n_dims), 3):
        ki, kj, kk = DIM_KEYS[i], DIM_KEYS[j], DIM_KEYS[k]
        ni, nj, nk = DIM_NAMES[i], DIM_NAMES[j], DIM_NAMES[k]
        groups = defaultdict(list)
        for m in matches:
            vi, vj, vk = m[ki], m[kj], m[kk]
            if vi and vj and vk:
                groups[(vi, vj, vk)].append(m)
        for (vi, vj, vk), group in groups.items():
            if len(group) < min_sample:
                continue
            for tname, tfn in TARGETS.items():
                hits = sum(1 for m in group if tfn(m))
                acc = hits / len(group) * 100
                if acc >= min_acc:
                    results.append({
                        'condition': f'{ni}={vi} + {nj}={vj} + {nk}={vk}',
                        'target': tname,
                        'sample': len(group),
                        'hits': hits,
                        'accuracy': acc,
                    })

    return results


def compute_base_rates(matches):
    """计算各目标的基准率"""
    n = len(matches)
    rates = {}
    for tname, tfn in TARGETS.items():
        rates[tname] = sum(1 for m in matches if tfn(m)) / n
    return rates


# ====== 第一重：统计检验 + FDR 校正 ======
def test_significance(rules, base_rates):
    """对每条规则做二项检验，返回带p值的规则列表"""
    for r in rules:
        p0 = base_rates[r['target']]
        # 单侧检验: H1: 真实准确率 > 基准率
        p_val = binomtest(r['hits'], r['sample'], p0, alternative='greater').pvalue
        r['p_value'] = p_val
        r['lift'] = r['accuracy'] - p0 * 100

    # Benjamini-Hochberg FDR 校正
    rules_sorted = sorted(rules, key=lambda r: r['p_value'])
    n_tests = len(rules_sorted)
    for rank, r in enumerate(rules_sorted, 1):
        r['bh_threshold'] = FDR_ALPHA * rank / n_tests
        r['fdr_pass'] = r['p_value'] <= r['bh_threshold']

    return rules


# ====== 第二重：置换检验 ======
def permutation_test(matches, real_rule_counts, n_perms=N_PERMUTATIONS):
    """
    随机打乱比赛结果，统计每次能挖到多少规则
    """
    thresholds = [75, 80, 85, 90]
    perm_counts = {t: [] for t in thresholds}

    results_list = [m['result'] for m in matches]

    for i in range(n_perms):
        if (i + 1) % 50 == 0:
            print(f"    置换检验进度: {i+1}/{n_perms}")

        # 打乱结果
        shuffled = results_list.copy()
        random.shuffle(shuffled)
        perm_matches = []
        for idx, m in enumerate(matches):
            pm = m.copy()
            pm['result'] = shuffled[idx]
            perm_matches.append(pm)

        # 用同样方法挖规则
        for thresh in thresholds:
            perm_rules = mine_rules(perm_matches, min_sample=MIN_SAMPLE, min_acc=thresh)
            perm_counts[thresh].append(len(perm_rules))

    return perm_counts


# ====== 第三重：前滚验证 ======
def walk_forward_validation(matches):
    """
    按时间切分，前段训练后段测试
    """
    # 按时间排序（已经是排序的）
    sorted_matches = sorted(matches, key=lambda m: m['match_time'])
    n = len(sorted_matches)

    # 分成4段（约各25%）
    q1 = n // 4
    q2 = n // 2
    q3 = 3 * n // 4

    splits = [
        ("前50%训练→第3段测试", sorted_matches[:q2], sorted_matches[q2:q3]),
        ("前75%训练→第4段测试", sorted_matches[:q3], sorted_matches[q3:]),
    ]

    validated = {}  # condition+target -> list of test accuracies

    for split_name, train, test in splits:
        print(f"\n  {split_name}: 训练{len(train)}场, 测试{len(test)}场")

        train_base = compute_base_rates(train)
        test_base = compute_base_rates(test)
        print(f"    训练基准: " + " | ".join(f"{k}={v*100:.1f}%" for k, v in train_base.items()))
        print(f"    测试基准: " + " | ".join(f"{k}={v*100:.1f}%" for k, v in test_base.items()))

        # 在训练集上挖规则
        train_rules = mine_rules(train, min_sample=MIN_SAMPLE, min_acc=75.0)
        print(f"    训练集挖到: {len(train_rules)} 条 >=75% 规则")

        # 构建测试集的分组索引，用于快速匹配
        # 对每条训练集规则，在测试集上计算准确率
        tested = 0
        for r in train_rules:
            # 解析条件，在测试集上匹配
            cond_parts = r['condition'].split(' + ')
            test_group = []
            for m in test:
                match = True
                for part in cond_parts:
                    dim_name, val = part.split('=', 1)
                    dim_idx = DIM_NAMES.index(dim_name)
                    dim_key = DIM_KEYS[dim_idx]
                    if m[dim_key] != val:
                        match = False
                        break
                if match:
                    test_group.append(m)

            key = (r['condition'], r['target'])
            if key not in validated:
                validated[key] = {
                    'condition': r['condition'],
                    'target': r['target'],
                    'train_results': [],
                    'test_results': [],
                }

            tfn = TARGETS[r['target']]
            test_hits = sum(1 for m in test_group if tfn(m))
            test_n = len(test_group)
            test_acc = (test_hits / test_n * 100) if test_n > 0 else None

            validated[key]['train_results'].append({
                'split': split_name,
                'sample': r['sample'],
                'hits': r['hits'],
                'accuracy': r['accuracy'],
            })
            validated[key]['test_results'].append({
                'split': split_name,
                'sample': test_n,
                'hits': test_hits,
                'accuracy': test_acc,
            })
            tested += 1

        print(f"    测试集验证: {tested} 条规则")

    return validated


def main():
    print("=" * 90)
    print("三重验证规则挖掘")
    print("=" * 90)

    rows = load_data()
    matches = process(rows)
    print(f"有效比赛: {len(matches)} 场 (让方赔率>={MIN_ODDS})")

    base_rates = compute_base_rates(matches)
    print(f"\n基准率:")
    for k, v in base_rates.items():
        print(f"  {k}: {v*100:.1f}%")

    # ============ 挖掘全量规则 ============
    print(f"\n{'=' * 90}")
    print("全量数据挖掘...")
    all_rules = mine_rules(matches)
    print(f"共挖到 {len(all_rules)} 条 >=75% 规则")

    ge80 = [r for r in all_rules if r['accuracy'] >= 80]
    ge85 = [r for r in all_rules if r['accuracy'] >= 85]
    ge90 = [r for r in all_rules if r['accuracy'] >= 90]
    print(f"  >=80%: {len(ge80)}")
    print(f"  >=85%: {len(ge85)}")
    print(f"  >=90%: {len(ge90)}")

    # ============ 第一重：统计检验 ============
    print(f"\n{'=' * 90}")
    print("【第一重】统计显著性检验 + BH-FDR校正 (α=0.05)")
    print("=" * 90)

    all_rules = test_significance(all_rules, base_rates)

    fdr_pass = [r for r in all_rules if r['fdr_pass']]
    fdr_fail = [r for r in all_rules if not r['fdr_pass']]
    print(f"  通过FDR校正: {len(fdr_pass)} / {len(all_rules)}")
    print(f"  被淘汰: {len(fdr_fail)} 条 (p值不显著或多重比较后不显著)")

    # 按目标分组统计
    for tname in TARGETS:
        t_all = [r for r in all_rules if r['target'] == tname]
        t_pass = [r for r in fdr_pass if r['target'] == tname]
        if t_all:
            print(f"\n  {tname} (基准={base_rates[tname]*100:.1f}%):")
            print(f"    原始: {len(t_all)} 条 → 通过FDR: {len(t_pass)} 条")
            if t_pass:
                t_pass_sorted = sorted(t_pass, key=lambda r: (-r['accuracy'], -r['sample']))
                print(f"    {'准确率':>7} | {'提升':>6} | {'样本':>4} | {'p值':>10} | 条件")
                for r in t_pass_sorted[:15]:
                    print(f"    {r['accuracy']:6.1f}% | +{r['lift']:4.1f}% | {r['sample']:>4} | {r['p_value']:.2e} | {r['condition']}")

    # ============ 第二重：置换检验 ============
    print(f"\n{'=' * 90}")
    print(f"【第二重】置换检验 ({N_PERMUTATIONS}次随机打乱)")
    print("=" * 90)

    real_counts = {}
    for thresh in [75, 80, 85, 90]:
        real_counts[thresh] = len([r for r in all_rules if r['accuracy'] >= thresh])

    print("  正在运行置换检验 (这需要一些时间)...")
    perm_counts = permutation_test(matches, real_counts)

    print(f"\n  {'阈值':>6} | {'真实':>6} | {'随机均值':>8} | {'随机最大':>8} | {'p值':>8} | 结论")
    print("  " + "-" * 75)
    for thresh in [75, 80, 85, 90]:
        real = real_counts[thresh]
        perm_arr = perm_counts[thresh]
        perm_mean = np.mean(perm_arr)
        perm_max = np.max(perm_arr)
        # p值: 随机中>=真实数量的比例
        p_perm = np.mean([1 for c in perm_arr if c >= real]) / len(perm_arr) if perm_arr else 1
        if p_perm == 0:
            p_str = "<0.002"
            conclusion = "真实 >> 随机"
        elif p_perm < 0.05:
            p_str = f"{p_perm:.3f}"
            conclusion = "有真实信号"
        else:
            p_str = f"{p_perm:.3f}"
            conclusion = "可能全是噪声"
        print(f"  >={thresh}% | {real:>6} | {perm_mean:>8.1f} | {perm_max:>8} | {p_str:>8} | {conclusion}")

    # ============ 第三重：前滚验证 ============
    print(f"\n{'=' * 90}")
    print("【第三重】前滚验证 (Walk-Forward)")
    print("=" * 90)

    wf_results = walk_forward_validation(matches)

    # 筛选在所有测试期都维持高准确率的规则
    # 条件: 每个测试期样本>=3 且准确率>=60%（允许一定衰减）
    stable_rules = []
    for key, info in wf_results.items():
        all_valid = True
        test_accs = []
        train_accs = []
        total_test_sample = 0
        total_test_hits = 0

        for tr in info['test_results']:
            if tr['sample'] < 3 or tr['accuracy'] is None:
                all_valid = False
                break
            test_accs.append(tr['accuracy'])
            total_test_sample += tr['sample']
            total_test_hits += tr['hits']

        for tr in info['train_results']:
            train_accs.append(tr['accuracy'])

        if not all_valid or not test_accs:
            continue

        avg_test_acc = total_test_hits / total_test_sample * 100 if total_test_sample > 0 else 0
        avg_train_acc = np.mean(train_accs)
        min_test_acc = min(test_accs)
        degradation = avg_train_acc - avg_test_acc

        stable_rules.append({
            'condition': info['condition'],
            'target': info['target'],
            'train_acc': avg_train_acc,
            'test_acc': avg_test_acc,
            'min_test_acc': min_test_acc,
            'test_sample': total_test_sample,
            'test_hits': total_test_hits,
            'degradation': degradation,
            'n_valid_periods': len(test_accs),
        })

    # 按测试准确率排序
    stable_rules.sort(key=lambda r: (-r['test_acc'], -r['test_sample']))

    # 显示测试准确率>=70%的规则
    good_wf = [r for r in stable_rules if r['min_test_acc'] >= 65]
    print(f"\n  前滚验证结果: {len(stable_rules)} 条规则有足够测试样本")
    print(f"  所有测试期>=65%的规则: {len(good_wf)} 条")

    if good_wf:
        print(f"\n  {'训练':>6} | {'测试':>6} | {'衰减':>6} | {'测试样本':>8} | {'目标':<10} | 条件")
        print("  " + "-" * 90)
        for r in good_wf[:30]:
            print(f"  {r['train_acc']:5.1f}% | {r['test_acc']:5.1f}% | {r['degradation']:+5.1f}% | {r['test_sample']:>8} | {r['target']:<10} | {r['condition']}")

    # ============ 最终交叉验证：三重都通过 ============
    print(f"\n{'=' * 90}")
    print("【最终结果】三重验证交叉筛选")
    print("=" * 90)

    # 通过FDR的规则key集合
    fdr_pass_keys = set()
    for r in fdr_pass:
        fdr_pass_keys.add((r['condition'], r['target']))

    # 通过前滚验证的规则key集合 (测试期>=65%)
    wf_pass_keys = set()
    for r in good_wf:
        wf_pass_keys.add((r['condition'], r['target']))

    # 交集
    both_pass = fdr_pass_keys & wf_pass_keys

    if not both_pass:
        print("\n  没有规则同时通过统计检验和前滚验证。")
        print("  结论: 当前数据量(917场)下，未能找到统计上可靠的规则。")

        # 退一步: 只通过FDR但前滚验证有衰减的规则
        print(f"\n  --- 退一步分析: 通过FDR但前滚有衰减的规则 ---")
        near_miss = []
        for r in stable_rules:
            key = (r['condition'], r['target'])
            if key in fdr_pass_keys and r['test_acc'] >= 55:
                near_miss.append(r)
        near_miss.sort(key=lambda r: (-r['test_acc'], -r['test_sample']))
        if near_miss:
            print(f"  通过FDR且测试>=55%: {len(near_miss)} 条")
            print(f"\n  {'训练':>6} | {'测试':>6} | {'衰减':>6} | {'测试样本':>8} | {'目标':<10} | 条件")
            print("  " + "-" * 90)
            for r in near_miss[:20]:
                print(f"  {r['train_acc']:5.1f}% | {r['test_acc']:5.1f}% | {r['degradation']:+5.1f}% | {r['test_sample']:>8} | {r['target']:<10} | {r['condition']}")
    else:
        print(f"\n  通过三重验证的规则: {len(both_pass)} 条")

        # 合并详细信息
        final_rules = []
        for r in stable_rules:
            key = (r['condition'], r['target'])
            if key in both_pass:
                # 找对应的FDR信息
                for fr in fdr_pass:
                    if fr['condition'] == r['condition'] and fr['target'] == r['target']:
                        r['p_value'] = fr['p_value']
                        r['lift'] = fr['lift']
                        r['full_acc'] = fr['accuracy']
                        r['full_sample'] = fr['sample']
                        break
                final_rules.append(r)

        final_rules.sort(key=lambda r: (-r['test_acc'], -r['test_sample']))

        print(f"\n  {'全量准确率':>10} | {'测试准确率':>10} | {'衰减':>6} | {'提升':>6} | {'p值':>10} | {'目标':<10} | 条件")
        print("  " + "-" * 100)
        for r in final_rules:
            full_acc_str = f"{r.get('full_acc', 0):.1f}%({r.get('full_sample', 0)})"
            test_acc_str = f"{r['test_acc']:.1f}%({r['test_sample']})"
            print(f"  {full_acc_str:>10} | {test_acc_str:>10} | {r['degradation']:+5.1f}% | +{r.get('lift', 0):4.1f}% | {r.get('p_value', 1):.2e} | {r['target']:<10} | {r['condition']}")

    print(f"\n{'=' * 90}")


if __name__ == '__main__':
    main()
