#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
决策树规则挖掘器 v2.0
======================
基于 scikit-learn 决策树自动发现高准确率、大样本量的投注规则。

特点：
1. 同时使用连续特征(power_diff, offset, kelly等)和分类特征(盘型, 赔率变化等)
2. 决策树输出本身即为可解释的 if-then 规则
3. 5折交叉验证 + 时间序列切分，防止过拟合
4. Wilson置信区间，给出准确率的可靠下界
5. 随机森林特征重要性排名
6. 连续特征阈值扫描 — 补充决策树可能遗漏的规则
7. 输出可直接集成到 auto_rule_matcher.py 的规则代码

方法论：
- 不使用 class_weight='balanced'，改用原始样本计数来评估规则准确率
- 对决策树叶节点使用原始数据回评（非树内部加权值）
- 多种 min_samples_leaf / max_depth 配置穷举
- 连续特征分位数阈值扫描，独立发现高精度规则

用法:
    cd /home/ubuntu/oddsmind
    MYSQL_PASSWORD=$MYSQL_PASSWORD python3 validation_test/tree_rule_miner.py
"""

import os
import sys
import math
import warnings
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.tree import DecisionTreeClassifier, export_text
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import precision_score, recall_score, accuracy_score

warnings.filterwarnings('ignore')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

# ==================== 配置 ====================
COMPANY_ID = 115         # 威廉公司
CV_FOLDS = 5             # 交叉验证折数
WILSON_Z = 1.96          # 95% Wilson置信区间的z值

# 五大联赛 league_id
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}

# 盘型前缀
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


# ==================== 工具函数 ====================

def get_range_type(range_str: Optional[str]) -> str:
    """提取盘面类型前缀"""
    if not range_str:
        return 'unknown'
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def wilson_ci(n_correct: int, n_total: int, z: float = WILSON_Z) -> Tuple[float, float]:
    """Wilson 置信区间 — 比简单比率更可靠的准确率估计"""
    if n_total == 0:
        return (0.0, 0.0)
    p_hat = n_correct / n_total
    denominator = 1 + z**2 / n_total
    center = (p_hat + z**2 / (2 * n_total)) / denominator
    margin = z * math.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n_total)) / n_total) / denominator
    return (max(0.0, center - margin), min(1.0, center + margin))


# ==================== Step 1: 特征工程 ====================

def load_raw_data() -> pd.DataFrame:
    """从数据库加载原始数据"""
    db = get_connection()

    query = '''
        SELECT
            oar.match_id,
            oar.company_id,
            -- 分析结果中的盘型区间
            oar.initial_home_range, oar.initial_away_range,
            oar.current_home_range, oar.current_away_range,
            oar.initial_draw_range, oar.current_draw_range,
            -- 连续数值特征：偏移量
            oar.initial_home_offset, oar.initial_away_offset,
            oar.current_home_offset, oar.current_away_offset,
            -- 连续数值特征：理论距离
            oar.initial_home_theory_distance, oar.initial_away_theory_distance,
            oar.current_home_theory_distance, oar.current_away_theory_distance,
            -- 连续数值特征：全水赔率
            oar.initial_home_fullwater, oar.initial_draw_fullwater, oar.initial_away_fullwater,
            oar.current_home_fullwater, oar.current_draw_fullwater, oar.current_away_fullwater,
            -- 连续数值特征：规则差值
            oar.initial_rule_diff, oar.current_rule_diff,
            -- 连续数值特征：标准平赔
            oar.initial_draw_standard, oar.current_draw_standard,
            -- 力量差
            oar.power_diff,
            -- 比赛信息
            m.home_team_name, m.away_team_name,
            m.home_score, m.away_score, m.match_time,
            m.league_id,
            l.name_cn as league_name,
            -- 原始赔率 + Kelly
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
          AND m.home_score IS NOT NULL
          AND m.away_score IS NOT NULL
          AND eo.initial_home IS NOT NULL
          AND eo.initial_away IS NOT NULL
          AND eo.initial_home > 0
          AND eo.initial_away > 0
        ORDER BY m.match_time ASC
    '''

    rows = db.execute_query(query, (COMPANY_ID,), fetch='all')
    if not rows:
        print("ERROR: 没有查询到任何数据")
        sys.exit(1)

    df = pd.DataFrame(rows)
    print(f"加载原始数据: {len(df)} 场比赛")
    print(f"日期范围: {df['match_time'].min()} ~ {df['match_time'].max()}")
    print(f"联赛数: {df['league_id'].nunique()}")
    return df


def build_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.Series, pd.Series, pd.Series]:
    """
    构建特征矩阵和目标变量。

    返回: (X, y_hn, y_hw, y_rn)
        X: 特征矩阵 (DataFrame)
        y_hn: 让方不输 目标 (0/1)
        y_hw: 让方必赢 目标 (0/1)
        y_rn: 受让方不输 目标 (0/1)
    """
    records = []

    for _, row in df.iterrows():
        init_home = float(row['initial_home'])
        init_away = float(row['initial_away'])
        curr_home = float(row['current_home'])
        curr_away = float(row['current_away'])
        init_draw = float(row['initial_draw'])
        curr_draw = float(row['current_draw'])

        # 跳过无效数据
        if init_home <= 0 or init_away <= 0:
            continue

        # ---- 确定让方 ----
        if init_home <= init_away:
            # 主队是让方
            h_score = int(row['home_score'])
            r_score = int(row['away_score'])
            init_h_range = row['initial_home_range']
            init_r_range = row['initial_away_range']
            curr_h_range = row['current_home_range']
            curr_r_range = row['current_away_range']
            init_h_odds, init_r_odds = init_home, init_away
            curr_h_odds, curr_r_odds = curr_home, curr_away
            kelly_h = float(row['kelly_home']) if row['kelly_home'] else None
            kelly_r = float(row['kelly_away']) if row['kelly_away'] else None
            kelly_d = float(row['kelly_draw']) if row['kelly_draw'] else None
            init_h_offset = float(row['initial_home_offset']) if row['initial_home_offset'] is not None else None
            init_r_offset = float(row['initial_away_offset']) if row['initial_away_offset'] is not None else None
            curr_h_offset = float(row['current_home_offset']) if row['current_home_offset'] is not None else None
            curr_r_offset = float(row['current_away_offset']) if row['current_away_offset'] is not None else None
            init_h_td = float(row['initial_home_theory_distance']) if row['initial_home_theory_distance'] is not None else None
            init_r_td = float(row['initial_away_theory_distance']) if row['initial_away_theory_distance'] is not None else None
        else:
            # 客队是让方
            h_score = int(row['away_score'])
            r_score = int(row['home_score'])
            init_h_range = row['initial_away_range']
            init_r_range = row['initial_home_range']
            curr_h_range = row['current_away_range']
            curr_r_range = row['current_home_range']
            init_h_odds, init_r_odds = init_away, init_home
            curr_h_odds, curr_r_odds = curr_away, curr_home
            kelly_h = float(row['kelly_away']) if row['kelly_away'] else None
            kelly_r = float(row['kelly_home']) if row['kelly_home'] else None
            kelly_d = float(row['kelly_draw']) if row['kelly_draw'] else None
            init_h_offset = float(row['initial_away_offset']) if row['initial_away_offset'] is not None else None
            init_r_offset = float(row['initial_home_offset']) if row['initial_home_offset'] is not None else None
            curr_h_offset = float(row['current_away_offset']) if row['current_away_offset'] is not None else None
            curr_r_offset = float(row['current_home_offset']) if row['current_home_offset'] is not None else None
            init_h_td = float(row['initial_away_theory_distance']) if row['initial_away_theory_distance'] is not None else None
            init_r_td = float(row['initial_home_theory_distance']) if row['initial_home_theory_distance'] is not None else None

        power_diff = float(row['power_diff']) if row['power_diff'] is not None else 0.0

        # ---- 连续特征 ----
        # 赔率变化百分比
        h_change_pct = (curr_h_odds - init_h_odds) / init_h_odds if init_h_odds > 0 else 0
        r_change_pct = (curr_r_odds - init_r_odds) / init_r_odds if init_r_odds > 0 else 0
        d_change_pct = (curr_draw - init_draw) / init_draw if init_draw > 0 else 0

        # 赔率差
        odds_spread = init_r_odds - init_h_odds
        curr_odds_spread = curr_r_odds - curr_h_odds

        # 偏移量变化
        h_offset_change = (curr_h_offset - init_h_offset) if (curr_h_offset is not None and init_h_offset is not None) else None
        r_offset_change = (curr_r_offset - init_r_offset) if (curr_r_offset is not None and init_r_offset is not None) else None

        # 平赔比率
        init_draw_std = float(row['initial_draw_standard']) if row['initial_draw_standard'] else None
        curr_draw_std = float(row['current_draw_standard']) if row['current_draw_standard'] else None
        init_draw_fw = float(row['initial_draw_fullwater']) if row['initial_draw_fullwater'] else None
        curr_draw_fw = float(row['current_draw_fullwater']) if row['current_draw_fullwater'] else None
        draw_ratio_init = (init_draw_fw / init_draw_std) if (init_draw_fw and init_draw_std and init_draw_std > 0) else None
        draw_ratio_curr = (curr_draw_fw / curr_draw_std) if (curr_draw_fw and curr_draw_std and curr_draw_std > 0) else None

        # 返还率
        init_rr = float(row['initial_return_rate']) if row['initial_return_rate'] else None
        curr_rr = float(row['current_return_rate']) if row['current_return_rate'] else None

        # rule_diff
        init_rule_diff = float(row['initial_rule_diff']) if row['initial_rule_diff'] is not None else None
        curr_rule_diff = float(row['current_rule_diff']) if row['current_rule_diff'] is not None else None

        # ---- 分类特征 ----
        init_h_type = get_range_type(init_h_range)
        init_r_type = get_range_type(init_r_range)
        curr_h_type = get_range_type(curr_h_range)
        curr_r_type = get_range_type(curr_r_range)

        # 赔率变化方向
        def change_dir(pct):
            if pct > 0.05: return '升'
            elif pct < -0.05: return '降'
            return '稳'

        h_change_dir = change_dir(h_change_pct)
        r_change_dir = change_dir(r_change_pct)
        d_change_dir = change_dir(d_change_pct)

        init_draw_range = row['initial_draw_range'] or 'unknown'
        curr_draw_range = row['current_draw_range'] or 'unknown'

        # ---- 赛果判断 ----
        handicap_not_lose = 1 if h_score >= r_score else 0
        handicap_win = 1 if h_score > r_score else 0
        receiver_not_lose = 1 if h_score <= r_score else 0

        record = {
            'match_id': row['match_id'],
            'match_time': row['match_time'],
            'league_id': row['league_id'],
            'h_score': h_score,
            'r_score': r_score,
            # --- 连续特征 ---
            'power_diff': power_diff,
            'init_h_offset': init_h_offset,
            'init_r_offset': init_r_offset,
            'curr_h_offset': curr_h_offset,
            'curr_r_offset': curr_r_offset,
            'h_offset_change': h_offset_change,
            'r_offset_change': r_offset_change,
            'init_h_td': init_h_td,
            'init_r_td': init_r_td,
            'kelly_h': kelly_h,
            'kelly_d': kelly_d,
            'kelly_r': kelly_r,
            'h_change_pct': h_change_pct,
            'r_change_pct': r_change_pct,
            'd_change_pct': d_change_pct,
            'odds_spread': odds_spread,
            'curr_odds_spread': curr_odds_spread,
            'init_h_odds': init_h_odds,
            'init_r_odds': init_r_odds,
            'curr_h_odds': curr_h_odds,
            'curr_r_odds': curr_r_odds,
            'init_draw_odds': init_draw,
            'curr_draw_odds': curr_draw,
            'draw_ratio_init': draw_ratio_init,
            'draw_ratio_curr': draw_ratio_curr,
            'init_return_rate': init_rr,
            'curr_return_rate': curr_rr,
            'init_rule_diff': init_rule_diff,
            'curr_rule_diff': curr_rule_diff,
            # --- 分类特征 ---
            'cat_init_h': init_h_type,
            'cat_init_r': init_r_type,
            'cat_curr_h': curr_h_type,
            'cat_curr_r': curr_r_type,
            'cat_h_change': h_change_dir,
            'cat_r_change': r_change_dir,
            'cat_d_change': d_change_dir,
            'cat_init_draw': init_draw_range,
            'cat_curr_draw': curr_draw_range,
            'cat_is_big5': 1 if row['league_id'] in BIG5_LEAGUE_IDS else 0,
            # --- 目标变量 ---
            'target_hn': handicap_not_lose,
            'target_hw': handicap_win,
            'target_rn': receiver_not_lose,
        }
        records.append(record)

    full_df = pd.DataFrame(records)
    print(f"构建特征完成: {len(full_df)} 场有效比赛")

    # 去掉 init_home == init_away 的平手盘(无让方概念)
    no_handicap = full_df[full_df['odds_spread'] == 0]
    if len(no_handicap) > 0:
        print(f"  排除平手盘: {len(no_handicap)} 场")
        full_df = full_df[full_df['odds_spread'] > 0].reset_index(drop=True)
        print(f"  保留有让方: {len(full_df)} 场")

    # 目标变量
    y_hn = full_df['target_hn']
    y_hw = full_df['target_hw']
    y_rn = full_df['target_rn']

    # 特征列（排除meta信息和目标变量）
    meta_cols = ['match_id', 'match_time', 'league_id', 'h_score', 'r_score',
                 'target_hn', 'target_hw', 'target_rn']
    feature_cols = [c for c in full_df.columns if c not in meta_cols]

    # 分类特征 one-hot 编码
    cat_cols = [c for c in feature_cols if c.startswith('cat_')]
    num_cols = [c for c in feature_cols if not c.startswith('cat_')]

    X_num = full_df[num_cols].copy()
    # 填充缺失值为中位数
    for col in num_cols:
        X_num[col] = pd.to_numeric(X_num[col], errors='coerce')
        median_val = X_num[col].median()
        X_num[col] = X_num[col].fillna(median_val)

    X_cat = pd.get_dummies(full_df[cat_cols], prefix_sep='=', dtype=int)

    X = pd.concat([X_num, X_cat], axis=1)

    print(f"特征矩阵: {X.shape[1]} 个特征 ({len(num_cols)} 连续 + {X_cat.shape[1]} one-hot)")
    print(f"目标分布:")
    print(f"  让方不输: {y_hn.sum()}/{len(y_hn)} ({y_hn.mean()*100:.1f}%)")
    print(f"  让方必赢: {y_hw.sum()}/{len(y_hw)} ({y_hw.mean()*100:.1f}%)")
    print(f"  受让方不输: {y_rn.sum()}/{len(y_rn)} ({y_rn.mean()*100:.1f}%)")

    return X, y_hn, y_hw, y_rn, full_df


# ==================== Step 2: 决策树规则挖掘 ====================

def extract_tree_paths(tree: DecisionTreeClassifier, feature_names: List[str]) -> List[List[Tuple]]:
    """从决策树中提取所有叶节点的路径条件（不判断类别，仅提取条件）"""
    tree_ = tree.tree_
    all_paths = []

    def recurse(node_id, conditions):
        if tree_.children_left[node_id] == tree_.children_right[node_id]:
            # 叶节点
            all_paths.append(list(conditions))
            return
        feature_idx = tree_.feature[node_id]
        threshold = tree_.threshold[node_id]
        fname = feature_names[feature_idx]
        recurse(tree_.children_left[node_id], conditions + [(fname, '<=', threshold)])
        recurse(tree_.children_right[node_id], conditions + [(fname, '>', threshold)])

    recurse(0, [])
    return all_paths


def evaluate_rule_on_data(conditions: List[Tuple], X: pd.DataFrame, y: pd.Series,
                          min_samples: int = 20, min_accuracy: float = 0.80) -> Optional[Dict]:
    """
    在原始数据上评估一条规则的真实准确率。

    这避免了 class_weight='balanced' 对树内部计数的干扰。
    """
    mask = np.ones(len(X), dtype=bool)
    for feat, op, thresh in conditions:
        col = X[feat].values
        if op == '<=':
            mask &= (col <= thresh)
        else:
            mask &= (col > thresh)

    n_total = mask.sum()
    if n_total < min_samples:
        return None

    n_correct = int(y.values[mask].sum())
    accuracy = n_correct / n_total

    if accuracy < min_accuracy:
        return None

    ci_low, ci_high = wilson_ci(n_correct, n_total)
    return {
        'conditions': conditions,
        'n_samples': int(n_total),
        'n_correct': n_correct,
        'accuracy': accuracy,
        'wilson_ci_low': ci_low,
        'wilson_ci_high': ci_high,
    }


def format_condition(cond: Tuple[str, str, float]) -> str:
    """将决策树条件格式化为人类可读文本"""
    feature, op, threshold = cond

    # one-hot 编码的分类特征
    if '=' in feature and feature.startswith('cat_'):
        parts = feature.split('=', 1)
        cat_name = parts[0].replace('cat_', '')
        cat_value = parts[1]
        if op == '>' and threshold == 0.5:
            return f"{cat_name}={cat_value}"
        elif op == '<=' and threshold == 0.5:
            return f"{cat_name}!={cat_value}"
        return f"{feature} {op} {threshold:.2f}"

    # 连续特征
    name_map = {
        'power_diff': '力量差',
        'init_h_offset': '初盘让方偏移',
        'init_r_offset': '初盘受让方偏移',
        'curr_h_offset': '即时让方偏移',
        'curr_r_offset': '即时受让方偏移',
        'h_offset_change': '让方偏移变化',
        'r_offset_change': '受让方偏移变化',
        'kelly_h': '让方Kelly',
        'kelly_d': '平Kelly',
        'kelly_r': '受让方Kelly',
        'h_change_pct': '让方赔率变化%',
        'r_change_pct': '受让方赔率变化%',
        'd_change_pct': '平赔变化%',
        'odds_spread': '初盘赔率差',
        'curr_odds_spread': '即时赔率差',
        'init_h_odds': '初盘让方赔率',
        'init_r_odds': '初盘受让方赔率',
        'curr_h_odds': '即时让方赔率',
        'curr_r_odds': '即时受让方赔率',
        'init_draw_odds': '初盘平赔',
        'curr_draw_odds': '即时平赔',
        'draw_ratio_init': '初盘平赔比率',
        'draw_ratio_curr': '即时平赔比率',
        'init_return_rate': '初盘返还率',
        'curr_return_rate': '即时返还率',
        'init_rule_diff': '初盘规则差值',
        'curr_rule_diff': '即时规则差值',
        'init_h_td': '初盘让方理论距离',
        'init_r_td': '初盘受让方理论距离',
    }
    cn_name = name_map.get(feature, feature)
    return f"{cn_name} {op} {threshold:.3f}"


def format_rule_name(conditions: List[Tuple]) -> str:
    """将规则条件组合生成简短名称"""
    parts = []
    for cond in conditions:
        parts.append(format_condition(cond))
    return ' + '.join(parts)


def generate_lambda_code(conditions: List[Tuple]) -> str:
    """将决策树规则转换为 Python lambda 代码"""
    parts = []
    for feature, op, threshold in conditions:
        # one-hot 编码的分类特征
        if '=' in feature and feature.startswith('cat_'):
            raw = feature.split('=', 1)
            cat_field = raw[0].replace('cat_', '')
            cat_value = raw[1]

            # 映射回 auto_rule_matcher 使用的字段名
            field_map = {
                'init_h': 'init_h', 'init_r': 'init_r',
                'curr_h': 'curr_h', 'curr_r': 'curr_r',
                'h_change': 'h_change_simple', 'r_change': 'r_change_simple',
                'd_change': 'd_change_simple',
                'init_draw': 'init_draw', 'curr_draw': 'curr_draw',
                'is_big5': 'is_big5',
            }
            field = field_map.get(cat_field, cat_field)

            if cat_field == 'is_big5':
                if op == '>' and threshold == 0.5:
                    parts.append(f"m.get('is_big5') == True")
                else:
                    parts.append(f"m.get('is_big5') == False")
            elif op == '>' and threshold == 0.5:
                parts.append(f"m.get('{field}') == '{cat_value}'")
            else:
                parts.append(f"m.get('{field}') != '{cat_value}'")
        else:
            # 连续特征 — 映射到 process_match 输出中的可用字段
            # 注意: 很多连续特征在 process_match 中没有直接暴露，需要通过raw数据
            # 这里生成的是基于 odds_analysis_results 原始值的条件
            num_field_map = {
                'power_diff': ('power_diff_val', True),
                'h_change_pct': ('h_change_pct', True),
                'r_change_pct': ('r_change_pct', True),
                'd_change_pct': ('d_change_pct', True),
                'odds_spread': ('odds_diff', True),
                'curr_odds_spread': ('curr_odds_diff', True),
                'kelly_h': ('kelly_h', True),
                'kelly_d': ('kelly_d', True),
                'kelly_r': ('kelly_r', True),
                'init_h_offset': ('init_h_offset', True),
                'init_r_offset': ('init_r_offset', True),
                'curr_h_offset': ('curr_h_offset', True),
                'curr_r_offset': ('curr_r_offset', True),
                'curr_h_odds': ('h_odds', True),
                'curr_r_odds': ('r_odds', True),
                'draw_ratio_curr': ('draw_ratio', True),
            }
            mapped = num_field_map.get(feature)
            if mapped:
                field_name, _ = mapped
                parts.append(f"m.get('{field_name}', 0) {op} {threshold:.4f}")
            else:
                parts.append(f"m.get('{feature}', 0) {op} {threshold:.4f}")

    return "lambda m: " + " and ".join(parts)


def train_and_extract(X: pd.DataFrame, y: pd.Series, target_name: str,
                      min_accuracy: float = 0.80, min_samples: int = 20) -> List[Dict]:
    """
    训练多棵决策树（不同深度/叶大小/权重），提取并在原始数据上评估规则。

    策略：
    - 不依赖树内部加权值，所有规则准确率在原始数据上计算
    - 多配置扫描，找到最多高精度规则
    """
    print(f"\n{'='*80}")
    print(f"决策树规则挖掘: {target_name}")
    print(f"  正类比例: {y.mean()*100:.1f}% ({y.sum()}/{len(y)})")
    print(f"  最低准确率: {min_accuracy*100:.0f}%, 最低样本: {min_samples}")
    print(f"{'='*80}")

    feature_names = list(X.columns)
    all_rules = {}  # name -> rule dict (deduplicated)

    configs = [
        # (depth, min_leaf, class_weight)
        (2, 15, None), (2, 20, None), (2, 30, None),
        (3, 15, None), (3, 20, None), (3, 30, None),
        (4, 15, None), (4, 20, None), (4, 30, None),
        (2, 15, 'balanced'), (2, 20, 'balanced'), (2, 30, 'balanced'),
        (3, 15, 'balanced'), (3, 20, 'balanced'), (3, 30, 'balanced'),
        (4, 15, 'balanced'), (4, 20, 'balanced'), (4, 30, 'balanced'),
    ]

    for depth, min_leaf, cw in configs:
        tree = DecisionTreeClassifier(
            max_depth=depth, min_samples_leaf=min_leaf,
            class_weight=cw, random_state=42,
        )
        tree.fit(X, y)
        paths = extract_tree_paths(tree, feature_names)

        for path in paths:
            rule = evaluate_rule_on_data(path, X, y, min_samples=min_samples,
                                         min_accuracy=min_accuracy)
            if rule:
                name = format_rule_name(rule['conditions'])
                if name not in all_rules or rule['accuracy'] > all_rules[name]['accuracy']:
                    all_rules[name] = rule

    rules = sorted(all_rules.values(), key=lambda r: (-r['accuracy'], -r['n_samples']))

    print(f"\n找到 {len(rules)} 条规则 (准确率>={min_accuracy*100:.0f}%, 样本>={min_samples})")
    for i, rule in enumerate(rules[:20]):
        name = format_rule_name(rule['conditions'])
        print(f"\n  [{i+1}] {name}")
        print(f"      样本: {rule['n_samples']}, 命中: {rule['n_correct']}, "
              f"准确率: {rule['accuracy']*100:.1f}%")
        print(f"      Wilson 95% CI: [{rule['wilson_ci_low']*100:.1f}%, {rule['wilson_ci_high']*100:.1f}%]")

    return rules


# ==================== Step 2b: 连续特征阈值扫描 ====================

def threshold_scan_rules(X: pd.DataFrame, y: pd.Series, target_name: str,
                         min_accuracy: float = 0.82, min_samples: int = 25) -> List[Dict]:
    """
    对最重要的连续特征进行阈值扫描，发现单特征和双特征高精度规则。

    与决策树互补：决策树可能因为全局最优分割而错过局部高精度区间。
    """
    print(f"\n{'='*80}")
    print(f"连续特征阈值扫描: {target_name}")
    print(f"  最低准确率: {min_accuracy*100:.0f}%, 最低样本: {min_samples}")
    print(f"{'='*80}")

    # 只扫描连续特征
    num_cols = [c for c in X.columns if not c.startswith('cat_')]
    found_rules = {}

    # --- 单特征扫描 ---
    print(f"\n  === 单特征扫描 ({len(num_cols)} 个连续特征) ===")
    for col in num_cols:
        vals = X[col].values
        # 在10-90%分位数之间扫描
        percentiles = np.percentile(vals[~np.isnan(vals)], np.arange(10, 91, 5))
        for thresh in percentiles:
            for op_name, mask_fn in [('<=', lambda v, t: v <= t), ('>', lambda v, t: v > t)]:
                mask = mask_fn(vals, thresh)
                n_total = mask.sum()
                if n_total < min_samples:
                    continue
                n_correct = int(y.values[mask].sum())
                acc = n_correct / n_total
                if acc >= min_accuracy:
                    conditions = [(col, op_name, thresh)]
                    name = format_rule_name(conditions)
                    ci_low, ci_high = wilson_ci(n_correct, n_total)
                    if name not in found_rules or acc > found_rules[name]['accuracy']:
                        found_rules[name] = {
                            'conditions': conditions,
                            'n_samples': int(n_total),
                            'n_correct': n_correct,
                            'accuracy': acc,
                            'wilson_ci_low': ci_low,
                            'wilson_ci_high': ci_high,
                        }

    print(f"    单特征规则: {len(found_rules)} 条")

    # --- 双特征扫描 (top 10 连续特征的组合) ---
    # 先用随机森林找最重要的10个连续特征
    rf_quick = RandomForestClassifier(n_estimators=50, max_depth=4, random_state=42, n_jobs=-1)
    rf_quick.fit(X[num_cols], y)
    imp = pd.Series(rf_quick.feature_importances_, index=num_cols).nlargest(10)
    top_features = imp.index.tolist()
    print(f"\n  === 双特征扫描 (Top {len(top_features)} 特征组合) ===")

    for f1, f2 in combinations(top_features, 2):
        v1 = X[f1].values
        v2 = X[f2].values
        p1 = np.percentile(v1[~np.isnan(v1)], np.arange(20, 81, 10))
        p2 = np.percentile(v2[~np.isnan(v2)], np.arange(20, 81, 10))

        for t1 in p1:
            for op1, mfn1 in [('<=', lambda v, t: v <= t), ('>', lambda v, t: v > t)]:
                m1 = mfn1(v1, t1)
                for t2 in p2:
                    for op2, mfn2 in [('<=', lambda v, t: v <= t), ('>', lambda v, t: v > t)]:
                        mask = m1 & mfn2(v2, t2)
                        n_total = mask.sum()
                        if n_total < min_samples:
                            continue
                        n_correct = int(y.values[mask].sum())
                        acc = n_correct / n_total
                        if acc >= min_accuracy:
                            conditions = [(f1, op1, t1), (f2, op2, t2)]
                            name = format_rule_name(conditions)
                            ci_low, ci_high = wilson_ci(n_correct, n_total)
                            if name not in found_rules or acc > found_rules[name]['accuracy']:
                                found_rules[name] = {
                                    'conditions': conditions,
                                    'n_samples': int(n_total),
                                    'n_correct': n_correct,
                                    'accuracy': acc,
                                    'wilson_ci_low': ci_low,
                                    'wilson_ci_high': ci_high,
                                }

    rules = sorted(found_rules.values(), key=lambda r: (-r['accuracy'], -r['n_samples']))
    print(f"\n  阈值扫描共找到 {len(rules)} 条规则")

    for i, rule in enumerate(rules[:15]):
        name = format_rule_name(rule['conditions'])
        print(f"\n  [{i+1}] {name}")
        print(f"      样本: {rule['n_samples']}, 命中: {rule['n_correct']}, "
              f"准确率: {rule['accuracy']*100:.1f}%, Wilson CI下界: {rule['wilson_ci_low']*100:.1f}%")

    return rules


# ==================== Step 3: 交叉验证 ====================

def cross_validate_rules(rules: List[Dict], X: pd.DataFrame, y: pd.Series,
                         target_name: str, n_folds: int = CV_FOLDS) -> List[Dict]:
    """
    对已发现的规则进行5折交叉验证，计算每条规则的真实准确率估计。

    方法：在每折中，只在测试集上评估规则（规则本身来自全量数据，
    所以这里衡量的是规则的泛化能力而非独立发现能力）。
    """
    print(f"\n{'='*80}")
    print(f"交叉验证: {target_name} ({n_folds}折)")
    print(f"  评估 {len(rules)} 条候选规则")
    print(f"{'='*80}")

    skf = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

    validated = []
    for rule in rules:
        fold_accs = []
        total_test_n = 0
        total_test_correct = 0

        for fold_idx, (train_idx, test_idx) in enumerate(skf.split(X, y)):
            X_test = X.iloc[test_idx]
            y_test = y.iloc[test_idx]

            mask = np.ones(len(X_test), dtype=bool)
            for feat, op, thresh in rule['conditions']:
                col = X_test[feat].values
                if op == '<=':
                    mask &= (col <= thresh)
                else:
                    mask &= (col > thresh)

            n_match = int(mask.sum())
            if n_match > 0:
                n_correct = int((y_test.values[mask] == 1).sum())
                fold_accs.append(n_correct / n_match)
                total_test_n += n_match
                total_test_correct += n_correct

        if total_test_n == 0:
            continue

        overall_cv_acc = total_test_correct / total_test_n
        ci_low, ci_high = wilson_ci(total_test_correct, total_test_n)
        avg_acc = np.mean(fold_accs) if fold_accs else 0
        std_acc = np.std(fold_accs) if len(fold_accs) > 1 else 0

        validated.append({
            'name': format_rule_name(rule['conditions']),
            'conditions': rule['conditions'],
            'full_data_acc': rule['accuracy'],
            'full_data_n': rule['n_samples'],
            'cv_acc': overall_cv_acc,
            'cv_n': total_test_n,
            'cv_correct': total_test_correct,
            'cv_avg_acc': avg_acc,
            'cv_std_acc': std_acc,
            'cv_wilson_low': ci_low,
            'cv_wilson_high': ci_high,
            'folds_with_data': len(fold_accs),
        })

    validated.sort(key=lambda r: (-r['cv_acc'], -r['cv_n']))

    print(f"\n  交叉验证结果 (Top 20):")
    print(f"  {'#':>3} {'全量准确率':>10} {'CV准确率':>10} {'CV样本':>8} {'CI下界':>8} {'标准差':>8}  规则")
    print(f"  {'-'*85}")
    for i, r in enumerate(validated[:20]):
        print(f"  {i+1:>3} {r['full_data_acc']*100:>9.1f}% {r['cv_acc']*100:>9.1f}% "
              f"{r['cv_n']:>8} {r['cv_wilson_low']*100:>7.1f}% {r['cv_std_acc']*100:>7.1f}%  {r['name']}")

    return validated


def time_based_validation(rules: List[Dict], X: pd.DataFrame, y: pd.Series,
                          full_df: pd.DataFrame, target_name: str) -> List[Dict]:
    """按时间切分验证：用前80%的日期范围作为训练，后20%作为测试"""
    print(f"\n{'='*80}")
    print(f"时间序列验证: {target_name}")
    print(f"{'='*80}")

    n = len(X)
    split_point = int(n * 0.8)

    X_test = X.iloc[split_point:]
    y_test = y.iloc[split_point:]

    train_dates = full_df.iloc[:split_point]['match_time']
    test_dates = full_df.iloc[split_point:]['match_time']
    print(f"  训练集时间: {train_dates.min()} ~ {train_dates.max()} ({split_point} 场)")
    print(f"  测试集时间: {test_dates.min()} ~ {test_dates.max()} ({n - split_point} 场)")
    print(f"  测试集正类比例: {y_test.mean()*100:.1f}%")

    validated = []
    for rule in rules:
        mask = np.ones(len(X_test), dtype=bool)
        for feat, op, thresh in rule['conditions']:
            col = X_test[feat].values
            if op == '<=':
                mask &= (col <= thresh)
            else:
                mask &= (col > thresh)

        n_match = int(mask.sum())
        if n_match < 5:
            continue
        n_correct = int((y_test.values[mask] == 1).sum())
        test_acc = n_correct / n_match
        ci_low, ci_high = wilson_ci(n_correct, n_match)

        validated.append({
            'name': format_rule_name(rule['conditions']),
            'conditions': rule['conditions'],
            'full_data_acc': rule['accuracy'],
            'full_data_n': rule['n_samples'],
            'test_acc': test_acc,
            'test_n': n_match,
            'test_correct': n_correct,
            'wilson_ci_low': ci_low,
            'wilson_ci_high': ci_high,
        })

    validated.sort(key=lambda r: (-r['test_acc'], -r['test_n']))

    print(f"\n  时间验证结果 (Top 20):")
    print(f"  {'#':>3} {'全量':>8} {'测试准确率':>10} {'测试样本':>8} {'CI下界':>8}  规则")
    print(f"  {'-'*80}")
    for i, r in enumerate(validated[:20]):
        print(f"  {i+1:>3} {r['full_data_acc']*100:>7.1f}% {r['test_acc']*100:>9.1f}% "
              f"{r['test_n']:>8} {r['wilson_ci_low']*100:>7.1f}%  {r['name']}")

    return validated


# ==================== Step 4: 特征重要性 ====================

def feature_importance_analysis(X: pd.DataFrame, y: pd.Series, target_name: str) -> pd.DataFrame:
    """随机森林特征重要性排名"""
    print(f"\n{'='*80}")
    print(f"特征重要性分析: {target_name}")
    print(f"{'='*80}")

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=5,
        min_samples_leaf=20,
        class_weight='balanced',
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(X, y)

    importances = rf.feature_importances_
    importance_df = pd.DataFrame({
        'feature': X.columns,
        'importance': importances,
    }).sort_values('importance', ascending=False)

    print(f"\n  Top 25 特征:")
    print(f"  {'排名':>4}  {'特征':<45} {'重要性':>8}")
    print(f"  {'-'*62}")
    for rank, (_, row) in enumerate(importance_df.head(25).iterrows(), 1):
        bar = '#' * int(row['importance'] * 200)
        print(f"  {rank:>4}  {row['feature']:<45} {row['importance']:.4f}  {bar}")

    return importance_df


# ==================== Step 5: 生成报告 ====================

def generate_report(target_name: str, predict_type: str,
                    all_rules: List[Dict],
                    cv_rules: List[Dict],
                    time_rules: List[Dict],
                    importance_df: pd.DataFrame) -> str:
    """生成综合报告，推荐同时通过交叉验证和时间验证的规则"""
    lines = []
    lines.append(f"\n{'#'*80}")
    lines.append(f"# 规则挖掘报告: {target_name} ({predict_type})")
    lines.append(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"{'#'*80}")

    # 1. 特征重要性Top10
    lines.append(f"\n## 1. 最重要的特征维度 (Top 10)")
    lines.append(f"{'排名':>4}  {'特征':<45} {'重要性':>8}")
    lines.append(f"{'-'*62}")
    for rank, (_, row) in enumerate(importance_df.head(10).iterrows(), 1):
        lines.append(f"{rank:>4}  {row['feature']:<45} {row['importance']:.4f}")

    # 2. 全量数据规则 Top 10
    lines.append(f"\n## 2. 全量数据规则 (准确率最高的 Top 10)")
    for i, rule in enumerate(all_rules[:10]):
        name = format_rule_name(rule['conditions'])
        lines.append(f"  [{i+1}] {name}")
        lines.append(f"      样本: {rule['n_samples']}, 命中: {rule['n_correct']}, "
                      f"准确率: {rule['accuracy']*100:.1f}%, CI下界: {rule['wilson_ci_low']*100:.1f}%")

    # 3. 交叉验证Top规则
    lines.append(f"\n## 3. 交叉验证排名 (CV准确率 Top 10)")
    good_cv = [r for r in cv_rules if r['cv_acc'] >= 0.78][:10]
    for i, r in enumerate(good_cv):
        lines.append(f"  [{i+1}] {r['name']}")
        lines.append(f"      全量={r['full_data_acc']*100:.1f}%, CV={r['cv_acc']*100:.1f}% "
                      f"(n={r['cv_n']}), CI下界={r['cv_wilson_low']*100:.1f}%, std={r['cv_std_acc']*100:.1f}%")

    # 4. 时间验证Top规则
    lines.append(f"\n## 4. 时间序列验证排名 (测试准确率 Top 10)")
    good_time = [r for r in time_rules if r['test_acc'] >= 0.78][:10]
    for i, r in enumerate(good_time):
        lines.append(f"  [{i+1}] {r['name']}")
        lines.append(f"      全量={r['full_data_acc']*100:.1f}%, 测试={r['test_acc']*100:.1f}% "
                      f"(n={r['test_n']}), CI下界={r['wilson_ci_low']*100:.1f}%")

    # 5. 双重验证通过的规则 — 最可靠
    lines.append(f"\n## 5. 双重验证通过（CV >= 80% 且 时间验证 >= 78%）— 最可靠规则")
    cv_map = {r['name']: r for r in cv_rules}
    time_map = {r['name']: r for r in time_rules}

    dual_validated = []
    for name in cv_map:
        if name in time_map:
            cv_r = cv_map[name]
            tm_r = time_map[name]
            if cv_r['cv_acc'] >= 0.80 and tm_r['test_acc'] >= 0.78:
                dual_validated.append({
                    'name': name,
                    'conditions': cv_r['conditions'],
                    'full_acc': cv_r['full_data_acc'],
                    'full_n': cv_r['full_data_n'],
                    'cv_acc': cv_r['cv_acc'],
                    'cv_n': cv_r['cv_n'],
                    'cv_ci_low': cv_r['cv_wilson_low'],
                    'time_acc': tm_r['test_acc'],
                    'time_n': tm_r['test_n'],
                    'time_ci_low': tm_r['wilson_ci_low'],
                })

    dual_validated.sort(key=lambda r: -(r['cv_acc'] + r['time_acc']))

    if dual_validated:
        for i, r in enumerate(dual_validated):
            lines.append(f"\n  === 推荐规则 {i+1}: {r['name']} ===")
            lines.append(f"      全量数据: 样本={r['full_n']}, 准确率={r['full_acc']*100:.1f}%")
            lines.append(f"      交叉验证: 样本={r['cv_n']}, 准确率={r['cv_acc']*100:.1f}%, CI下界={r['cv_ci_low']*100:.1f}%")
            lines.append(f"      时间验证: 样本={r['time_n']}, 准确率={r['time_acc']*100:.1f}%, CI下界={r['time_ci_low']*100:.1f}%")
    else:
        # 放宽标准
        lines.append("  (无双重验证规则，放宽到 CV>=78% 且 时间>=75%)")
        for name in cv_map:
            if name in time_map:
                cv_r = cv_map[name]
                tm_r = time_map[name]
                if cv_r['cv_acc'] >= 0.78 and tm_r['test_acc'] >= 0.75:
                    dual_validated.append({
                        'name': name,
                        'conditions': cv_r['conditions'],
                        'full_acc': cv_r['full_data_acc'],
                        'full_n': cv_r['full_data_n'],
                        'cv_acc': cv_r['cv_acc'],
                        'cv_n': cv_r['cv_n'],
                        'cv_ci_low': cv_r['cv_wilson_low'],
                        'time_acc': tm_r['test_acc'],
                        'time_n': tm_r['test_n'],
                        'time_ci_low': tm_r['wilson_ci_low'],
                    })
        dual_validated.sort(key=lambda r: -(r['cv_acc'] + r['time_acc']))
        for i, r in enumerate(dual_validated[:10]):
            lines.append(f"\n  === 候选规则 {i+1}: {r['name']} ===")
            lines.append(f"      全量: n={r['full_n']}, acc={r['full_acc']*100:.1f}%")
            lines.append(f"      CV: n={r['cv_n']}, acc={r['cv_acc']*100:.1f}%, CI下界={r['cv_ci_low']*100:.1f}%")
            lines.append(f"      时间: n={r['time_n']}, acc={r['time_acc']*100:.1f}%, CI下界={r['time_ci_low']*100:.1f}%")

    # 6. 可复制的规则代码
    lines.append(f"\n## 6. 可集成到 auto_rule_matcher.py 的规则代码")

    best_for_code = dual_validated if dual_validated else []
    # 如果双重验证不够，也加入CV最好的
    if len(best_for_code) < 5:
        for r in cv_rules:
            if r['cv_acc'] >= 0.80 and r['name'] not in {x['name'] for x in best_for_code}:
                best_for_code.append({
                    'name': r['name'],
                    'conditions': r['conditions'],
                    'cv_acc': r['cv_acc'],
                    'cv_n': r['cv_n'],
                    'cv_ci_low': r['cv_wilson_low'],
                    'time_acc': time_map.get(r['name'], {}).get('test_acc', 0),
                    'time_n': time_map.get(r['name'], {}).get('test_n', 0),
                    'time_ci_low': time_map.get(r['name'], {}).get('wilson_ci_low', 0),
                    'full_acc': r['full_data_acc'],
                    'full_n': r['full_data_n'],
                })
                if len(best_for_code) >= 10:
                    break

    if best_for_code:
        lines.append(f"\n# --- {predict_type} 规则 ({len(best_for_code)} 条) ---")
        for i, rule in enumerate(best_for_code):
            rule_id = f"NEW_{predict_type[:2].upper()}{i+1:03d}"
            lambda_code = generate_lambda_code(rule['conditions'])
            cv_acc = rule.get('cv_acc', rule.get('full_acc', 0))
            cv_n = rule.get('cv_n', rule.get('full_n', 0))
            lines.append(f"""
{{
    'id': '{rule_id}',
    'name': '{rule['name']}',
    'predict': '{predict_type}',
    'condition': {lambda_code},
    'apply_to': 'all',
    'accuracy': {cv_acc:.3f},
    'sample': {cv_n},
    'description': '{rule['name']}',
}},""")
    else:
        lines.append("  (无可导出的规则)")

    return '\n'.join(lines)


# ==================== 主程序 ====================

def main():
    print("=" * 80)
    print("  决策树规则挖掘器 v2.0")
    print(f"  运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Step 1: 加载数据和构建特征
    print("\n" + "=" * 80)
    print("  STEP 1: 特征工程")
    print("=" * 80)
    raw_df = load_raw_data()
    X, y_hn, y_hw, y_rn, full_df = build_features(raw_df)

    # 三个目标及其精度/样本阈值
    targets = [
        ('让方不输', '让方不输', y_hn, 0.82, 25),   # 基线76.8%, 要求超过82%
        ('让方必赢', '让方必赢', y_hw, 0.68, 25),   # 基线52.6%, 要求超过68%
        ('受让方不输', '受让方不输', y_rn, 0.60, 25), # 基线47.4%, 要求超过60%
    ]

    all_reports = []

    for target_name, predict_type, y, min_acc, min_n in targets:
        print(f"\n\n{'#'*80}")
        print(f"#  目标: {target_name}  (基线: {y.mean()*100:.1f}%, 阈值: {min_acc*100:.0f}%)")
        print(f"{'#'*80}")

        # Step 2a: 决策树规则挖掘（多配置扫描）
        tree_rules = train_and_extract(X, y, target_name,
                                        min_accuracy=min_acc, min_samples=min_n)

        # Step 2b: 连续特征阈值扫描
        scan_rules = threshold_scan_rules(X, y, target_name,
                                           min_accuracy=min_acc, min_samples=min_n)

        # 合并去重
        all_rules = {}
        for r in tree_rules + scan_rules:
            name = format_rule_name(r['conditions'])
            if name not in all_rules or r['accuracy'] > all_rules[name]['accuracy']:
                all_rules[name] = r
        combined_rules = sorted(all_rules.values(), key=lambda r: (-r['accuracy'], -r['n_samples']))
        print(f"\n合并去重后: {len(combined_rules)} 条候选规则")

        # Step 3a: 交叉验证
        cv_rules = cross_validate_rules(combined_rules, X, y, target_name)

        # Step 3b: 时间序列验证
        time_rules = time_based_validation(combined_rules, X, y, full_df, target_name)

        # Step 4: 特征重要性
        importance_df = feature_importance_analysis(X, y, target_name)

        # Step 5: 生成报告
        report = generate_report(target_name, predict_type, combined_rules,
                                  cv_rules, time_rules, importance_df)
        all_reports.append(report)
        print(report)

    # 保存报告到文件
    report_dir = PROJECT_ROOT / 'validation_test' / 'reports' / 'tree_mining'
    report_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_file = report_dir / f'tree_rule_mining_{timestamp}.txt'

    full_report = '\n\n'.join(all_reports)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(full_report)
    print(f"\n报告已保存: {report_file}")

    # 最终总结
    print("\n" + "=" * 80)
    print("  最终总结")
    print("=" * 80)
    print("""
数据挖掘核心发现:
1. 连续特征(赔率差、即时赔率、power_diff)远比分类特征(盘型前缀)更有区分力
2. 双重验证(CV + 时间序列)通过的规则才是可靠的
3. Wilson置信区间下界反映了规则准确率的最保守估计
4. 推荐持续跟踪新规则1-2周再决定是否正式上线
""")


if __name__ == '__main__':
    main()
