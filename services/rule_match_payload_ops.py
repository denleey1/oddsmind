#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API Payload 构建器 — 竞争区间规则引擎 v3.1
=============================================
为 rule_match_api.py 提供数据组装逻辑。

更新日期: 2026-02-11
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List

from utils.timezone_utils import now as tz_now

from services.auto_rule_matcher_logic_ops import (
    RULES as _ENGINE_RULES,
    classify_odds_change_detailed,
    classify_power,
)


# ===================== 规则历史记录 (自动从 v3.1 引擎解析) =====================

import re as _re

def _build_rule_history() -> dict:
    """从 auto_rule_matcher_logic_ops.RULES 自动解析准确率和样本数。

    每条规则的 desc 格式示例:
      '威廉受让方>4.000 + 立博平赔变化>3.3% → OOS 90.7%(n=43)'
      '[V1] 即时让方<=1.850 + 让方偏移变化<=-0.400 → OOS 85.2%(n=81)'
      '[V1] 赔率差>0.710+受让方实开+... → CV 86.2%(n=123)'
    """
    pattern = _re.compile(r'(\d+\.?\d*)%\(n=(\d+)\)')
    history = {}
    for r in _ENGINE_RULES:
        m = pattern.search(r['desc'])
        if m:
            accuracy = float(m.group(1)) / 100.0
            sample = int(m.group(2))
        else:
            accuracy = 0.0
            sample = 0
        history[r['id']] = {
            'grade': r['grade'],
            'side': r['side'],
            'requires': r['requires'],
            'sample': sample,
            'accuracy': accuracy,
        }
    return history

RULE_HISTORY = _build_rule_history()

BIG5_IDS = {36, 31, 34, 8, 11}
BIG5_NAMES = {36: '英超', 31: '西甲', 34: '意甲', 8: '德甲', 11: '法甲'}

MODE_CN = {'wml': '三公司(威廉+澳门+立博)', 'wm': '威廉+澳门', 'wl': '威廉+立博'}
GRADE_CN = {'S': 'S级(最高)', 'A': 'A级(高)', 'B': 'B级(较高)'}
SIGNAL_ICON = {'重仓': '🔴', '强烈': '🟠', '参考': '🟡', '标准': '🟡'}

# 新版规则列表 (用于 /api/rules 接口)
PRECISION_RULES_PAYLOAD = [
    # D- 让方不输 · 威廉+澳门
    {'id': 'D-H01', 'grade': 'S', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 0.980, 'sample': 50,
     'name': '威廉赔率差>0.71 + 威澳偏移变化差>-0.35 + 威廉返还率≤93.1 + 威澳初盘受让方差>0.575',
     'description': '威廉赔率差>0.71 + 威澳偏移变化差>-0.35 + 威廉返还率≤93.1 + 威澳初盘受让方差>0.575 → OOS 98.0%(n=50)'},
    {'id': 'D-H02', 'grade': 'S', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 1.000, 'sample': 36,
     'name': '威廉赔率差>0.71 + 威廉返还率≤92.2 + 澳门平赔降≤-1.7% + 威澳返还率差>1.85',
     'description': '威廉赔率差>0.71 + 威廉返还率≤92.2 + 澳门平赔降≤-1.7% + 威澳返还率差>1.85 → OOS 100%(n=36)'},
    {'id': 'D-H03', 'grade': 'S', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 1.000, 'sample': 12,
     'name': '澳门让方>2.04 + 威廉赔率差>1.60',
     'description': '澳门让方>2.04 + 威廉赔率差>1.60 → OOS 100%(n=12)'},
    {'id': 'D-H04', 'grade': 'A', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 0.957, 'sample': 23,
     'name': '威廉赔率差>0.71 + 威廉返还率≤92.2 + 澳门平赔变化>-1.7% + 澳门受让方理论距离>1.95',
     'description': '威廉赔率差>0.71 + 威廉返还率≤92.2 + 澳门平赔变化>-1.7% + 澳门受让方理论距离>1.95 → OOS 95.7%(n=23)'},
    {'id': 'D-H05', 'grade': 'A', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 0.900, 'sample': 10,
     'name': '威廉让方≤2.25 + 澳门让方>2.25',
     'description': '威廉让方≤2.25 + 澳门让方>2.25 → OOS 90.0%(n=10)'},
    {'id': 'D-H06', 'grade': 'A', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 0.909, 'sample': 22,
     'name': '威澳赔率差差>0.45 + 澳门赔率差≤0.66',
     'description': '威澳赔率差差>0.45 + 澳门赔率差≤0.66 → OOS 90.9%(n=22)'},
    {'id': 'D-H07', 'grade': 'A', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 0.957, 'sample': 23,
     'name': '威澳初盘平赔比差≤-0.068 + 澳门赔率差>1.558',
     'description': '威澳初盘平赔比差≤-0.068 + 澳门赔率差>1.558 → OOS 95.7%(n=23)'},
    {'id': 'D-H08', 'grade': 'A', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 1.000, 'sample': 12,
     'name': '威廉让方≤2.05 + 澳门赔率差≤0.83',
     'description': '威廉让方≤2.05 + 澳门赔率差≤0.83 → OOS 100%(n=12)'},
    {'id': 'D-H09', 'grade': 'A', 'predict': '让方不输', 'requires': 'wm', 'accuracy': 1.000, 'sample': 20,
     'name': '威廉初盘平赔比≤0.931 + 澳门让方≤1.90',
     'description': '威廉初盘平赔比≤0.931 + 澳门让方≤1.90 → 时间验证 100%(n=20)'},
    # D- 受让方不输 · 威廉+澳门
    {'id': 'D-R01', 'grade': 'S', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 0.947, 'sample': 19,
     'name': '澳门赔率差≤0.27 + 威澳让方变化差≤-4.9%',
     'description': '澳门赔率差≤0.27 + 威澳让方变化差≤-4.9% → OOS 94.7%(n=19)'},
    {'id': 'D-R02', 'grade': 'S', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 0.947, 'sample': 19,
     'name': '威澳让方变化差≤-4.9% + 澳门受让方≤2.60',
     'description': '威澳让方变化差≤-4.9% + 澳门受让方≤2.60 → OOS 94.7%(n=19)'},
    {'id': 'D-R03', 'grade': 'S', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 0.923, 'sample': 13,
     'name': '威廉赔率差≤0.30 + 威澳让方变化差≤-4.9%',
     'description': '威廉赔率差≤0.30 + 威澳让方变化差≤-4.9% → OOS 92.3%(n=13)'},
    {'id': 'D-R04', 'grade': 'S', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 1.000, 'sample': 8,
     'name': '威廉初盘让方偏移>0.80 + 澳门初盘受让方偏移≤-0.40',
     'description': '威廉初盘让方偏移>0.80 + 澳门初盘受让方偏移≤-0.40 → OOS 100%(n=8)'},
    {'id': 'D-R05', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 0.923, 'sample': 13,
     'name': '威澳让方变化差≤-4.9% + 威廉受让方≤2.75',
     'description': '威澳让方变化差≤-4.9% + 威廉受让方≤2.75 → OOS 92.3%(n=13)'},
    {'id': 'D-R06', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 0.879, 'sample': 33,
     'name': '威澳让方变化差≤-1.6% + 澳门受让方≤2.60',
     'description': '威澳让方变化差≤-1.6% + 澳门受让方≤2.60 → OOS 87.9%(n=33)'},
    {'id': 'D-R07', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 0.840, 'sample': 25,
     'name': '澳门赔率差≤0.40 + 澳门平赔变化>-6% + 平Kelly>0.885 + 威澳偏移均值≤-1.33',
     'description': '澳门赔率差≤0.40 + 澳门平赔变化>-6% + 平Kelly>0.885 + 威澳偏移均值≤-1.33 → OOS 84.0%(n=25)'},
    {'id': 'D-R08', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 0.846, 'sample': 26,
     'name': '威澳让方变化差≤-4.9% + 威廉受让方≤2.90',
     'description': '威澳让方变化差≤-4.9% + 威廉受让方≤2.90 → OOS 84.6%(n=26)'},
    {'id': 'D-R09', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wm', 'accuracy': 0.857, 'sample': 14,
     'name': '澳门初盘受让方偏移≤-0.10 + 威廉初盘让方偏移>1.10',
     'description': '澳门初盘受让方偏移≤-0.10 + 威廉初盘让方偏移>1.10 → OOS 85.7%(n=14)'},
    # T- 让方不输 · 三公司
    {'id': 'T-H01', 'grade': 'S', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 1.000, 'sample': 19,
     'name': '威廉赔率差≤1.90 + 三公司受让方均值>3.66',
     'description': '威廉赔率差≤1.90 + 三公司受让方均值>3.66 → OOS 100%(n=19)'},
    {'id': 'T-H02', 'grade': 'S', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 1.000, 'sample': 19,
     'name': '威廉让方≤2.10 + 澳门让方>2.11',
     'description': '威廉让方≤2.10 + 澳门让方>2.11 → OOS 100%(n=19)'},
    {'id': 'T-H03', 'grade': 'S', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 0.917, 'sample': 24,
     'name': '三公司赔率差均值>1.45 + 威廉让方>2.00',
     'description': '三公司赔率差均值>1.45 + 威廉让方>2.00 → OOS 91.7%(n=24)'},
    {'id': 'T-H04', 'grade': 'S', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 0.933, 'sample': 15,
     'name': '立博受让方>3.75 + 威廉让方>2.00',
     'description': '立博受让方>3.75 + 威廉让方>2.00 → OOS 93.3%(n=15)'},
    {'id': 'T-H05', 'grade': 'A', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 1.000, 'sample': 11,
     'name': '威廉让方≤1.91 + 立博初盘受让方≤3.00',
     'description': '威廉让方≤1.91 + 立博初盘受让方≤3.00 → OOS 100%(n=11)'},
    {'id': 'T-H06', 'grade': 'A', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 1.000, 'sample': 10,
     'name': '威廉赔率差>1.90 + 立博初盘受让方≤3.10',
     'description': '威廉赔率差>1.90 + 立博初盘受让方≤3.10 → OOS 100%(n=10)'},
    {'id': 'T-H07', 'grade': 'A', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 1.000, 'sample': 10,
     'name': '威澳偏移差>0.40 + 威澳偏移均值≤-1.00',
     'description': '威澳偏移差>0.40 + 威澳偏移均值≤-1.00 → OOS 100%(n=10)'},
    {'id': 'T-H08', 'grade': 'A', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 0.900, 'sample': 10,
     'name': '威廉赔率差>1.90 + 澳门初盘受让方≤3.08',
     'description': '威廉赔率差>1.90 + 澳门初盘受让方≤3.08 → OOS 90.0%(n=10)'},
    {'id': 'T-H09', 'grade': 'A', 'predict': '让方不输', 'requires': 'wml', 'accuracy': 0.839, 'sample': 31,
     'name': '威廉让方>1.91 + 三公司受让方均值>3.66',
     'description': '威廉让方>1.91 + 三公司受让方均值>3.66 → OOS 83.9%(n=31)'},
    # T- 受让方不输 · 三公司
    {'id': 'T-R01', 'grade': 'S', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 0.929, 'sample': 14,
     'name': '威立返还率差>2.50 + 威廉受让方≤2.75',
     'description': '威立返还率差>2.50 + 威廉受让方≤2.75 → OOS 92.9%(n=14)'},
    {'id': 'T-R02', 'grade': 'S', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 0.923, 'sample': 13,
     'name': '三公司让方变化分歧≤0.013 + 澳门平赔上升',
     'description': '三公司让方变化分歧≤0.013 + 澳门平赔上升 → OOS 92.3%(n=13)'},
    {'id': 'T-R03', 'grade': 'S', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 0.917, 'sample': 12,
     'name': '澳立受让方变化差≤-0.055 + 立博赔率差≤0.30',
     'description': '澳立受让方变化差≤-0.055 + 立博赔率差≤0.30 → OOS 91.7%(n=12)'},
    {'id': 'T-R04', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 1.000, 'sample': 7,
     'name': '立博赔率差≤0.30 + 澳门受让方>2.70',
     'description': '立博赔率差≤0.30 + 澳门受让方>2.70 → OOS 100%(n=7)'},
    {'id': 'T-R05', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 1.000, 'sample': 7,
     'name': '澳立赔率差差≤-0.23 + 三公司赔率差均值≤0.317',
     'description': '澳立赔率差差≤-0.23 + 三公司赔率差均值≤0.317 → OOS 100%(n=7)'},
    {'id': 'T-R06', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 0.895, 'sample': 19,
     'name': '威立返还率差>1.75 + 威廉受让方≤2.75',
     'description': '威立返还率差>1.75 + 威廉受让方≤2.75 → OOS 89.5%(n=19)'},
    {'id': 'T-R07', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 0.900, 'sample': 10,
     'name': '威廉让方>2.45 + 澳立让方变化差>0.05',
     'description': '威廉让方>2.45 + 澳立让方变化差>0.05 → OOS 90.0%(n=10)'},
    {'id': 'T-R08', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 0.889, 'sample': 9,
     'name': '立博让方变化≤-3% + 立博赔率差≤0.30',
     'description': '立博让方变化≤-3% + 立博赔率差≤0.30 → OOS 88.9%(n=9)'},
    {'id': 'T-R09', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wml', 'accuracy': 0.889, 'sample': 9,
     'name': '三公司赔率差均值≤0.317 + 威澳让方Kelly差≤0',
     'description': '三公司赔率差均值≤0.317 + 威澳让方Kelly差≤0 → OOS 88.9%(n=9)'},
    # WL- 让方不输 · 威廉+立博
    {'id': 'WL-H01', 'grade': 'A', 'predict': '让方不输', 'requires': 'wl', 'accuracy': 1.000, 'sample': 12,
     'name': '威廉初盘让方>2.30 + 威廉平Kelly>0.88',
     'description': '威廉初盘让方>2.30 + 威廉平Kelly>0.88 → OOS 100%(n=12)'},
    {'id': 'WL-H02', 'grade': 'A', 'predict': '让方不输', 'requires': 'wl', 'accuracy': 1.000, 'sample': 10,
     'name': '威立受让方变化和≤0 + 威廉平Kelly>0.89',
     'description': '威立受让方变化和≤0 + 威廉平Kelly>0.89 → OOS 100%(n=10)'},
    {'id': 'WL-H03', 'grade': 'A', 'predict': '让方不输', 'requires': 'wl', 'accuracy': 1.000, 'sample': 8,
     'name': '威廉初盘让方>2.40 + 威廉平Kelly>0.88',
     'description': '威廉初盘让方>2.40 + 威廉平Kelly>0.88 → OOS 100%(n=8)'},
    {'id': 'WL-H04', 'grade': 'A', 'predict': '让方不输', 'requires': 'wl', 'accuracy': 1.000, 'sample': 7,
     'name': '威廉初盘返还率>91.68 + 威廉初盘让方>2.30',
     'description': '威廉初盘返还率>91.68 + 威廉初盘让方>2.30 → OOS 100%(n=7)'},
    {'id': 'WL-H05', 'grade': 'A', 'predict': '让方不输', 'requires': 'wl', 'accuracy': 1.000, 'sample': 7,
     'name': '威廉即时返还率>91.68 + 威廉初盘让方>2.00',
     'description': '威廉即时返还率>91.68 + 威廉初盘让方>2.00 → OOS 100%(n=7)'},
    {'id': 'WL-H06', 'grade': 'B', 'predict': '让方不输', 'requires': 'wl', 'accuracy': 1.000, 'sample': 6,
     'name': '威立让方Kelly均值≤0.885',
     'description': '威立让方Kelly均值≤0.885 → OOS 100%(n=6)'},
    # WL- 受让方不输 · 威廉+立博
    {'id': 'WL-R01', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wl', 'accuracy': 1.000, 'sample': 9,
     'name': '威廉平赔比>0.948 + 威廉初盘让方偏移>0.50',
     'description': '威廉平赔比>0.948 + 威廉初盘让方偏移>0.50 → OOS 100%(n=9)'},
    {'id': 'WL-R02', 'grade': 'A', 'predict': '受让方不输', 'requires': 'wl', 'accuracy': 0.929, 'sample': 14,
     'name': '威廉即时返还率≤90.33 + 立博初盘返还率>89.45',
     'description': '威廉即时返还率≤90.33 + 立博初盘返还率>89.45 → OOS 92.9%(n=14)'},
    {'id': 'WL-R03', 'grade': 'B', 'predict': '受让方不输', 'requires': 'wl', 'accuracy': 0.923, 'sample': 13,
     'name': '威廉偏移变化≤-0.88 + 威立受让方差≤0.10',
     'description': '威廉偏移变化≤-0.88 + 威立受让方差≤0.10 → OOS 92.3%(n=13)'},
    {'id': 'WL-R04', 'grade': 'B', 'predict': '受让方不输', 'requires': 'wl', 'accuracy': 0.923, 'sample': 13,
     'name': '立博即时返还率≤89.25 + 威廉初盘让方偏移>0.50',
     'description': '立博即时返还率≤89.25 + 威廉初盘让方偏移>0.50 → OOS 92.3%(n=13)'},
]


# ===================== Payload 构建器 =====================

def build_rule_alerts_payload(db: Any, date_filter: str, prediction: str, limit: int) -> Dict[str, Any]:
    """构建规则匹配列表"""
    conditions = []
    params: List[Any] = []

    if date_filter:
        conditions.append("DATE(match_time) = %s")
        params.append(date_filter)

    if prediction:
        conditions.append("prediction = %s")
        params.append(prediction)

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    query = f'''
        SELECT
            rma.id, rma.match_id, rma.rule_id, rma.rule_name,
            rma.prediction, rma.handicap_team, rma.receiver_team,
            rma.bet_suggestion, rma.rule_accuracy,
            rma.signal_level, rma.mode, rma.rule_grade,
            rma.features,
            rma.match_time, rma.match_result, rma.is_correct,
            m.home_team_name, m.away_team_name,
            l.name_cn as league_name
        FROM rule_match_alerts rma
        LEFT JOIN matches m ON rma.match_id = m.match_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        {where_clause}
        ORDER BY rma.match_time DESC
        LIMIT %s
    '''
    params.append(limit)

    results = db.execute_query(query, tuple(params), fetch='all')

    alerts = []
    for r in results:
        alerts.append({
            'id': r['id'],
            'match_id': r['match_id'],
            'rule_id': r['rule_id'],
            'rule_name': r['rule_name'],
            'prediction': r['prediction'],
            'handicap_team': r['handicap_team'],
            'receiver_team': r['receiver_team'],
            'bet_suggestion': r['bet_suggestion'],
            'rule_accuracy': float(r['rule_accuracy']) if r['rule_accuracy'] else None,
            'signal_level': r.get('signal_level', ''),
            'mode': r.get('mode', ''),
            'mode_cn': MODE_CN.get(r.get('mode', ''), ''),
            'rule_grade': r.get('rule_grade', ''),
            'features': r['features'],
            'match_time': r['match_time'].isoformat() if r['match_time'] else None,
            'match_result': r['match_result'],
            'is_correct': r['is_correct'],
            'home_team': r['home_team_name'],
            'away_team': r['away_team_name'],
            'league_name': r['league_name'],
        })

    return {'success': True, 'count': len(alerts), 'data': alerts}


def build_today_alerts_payload(db: Any) -> Dict[str, Any]:
    """构建今日规则匹配(按比赛分组, 含信号等级)
    
    查询窗口：昨天+今天+明天（Asia/Shanghai），
    覆盖凌晨进行的欧洲赛事，避免午夜翻日后信号消失。
    """
    now_local = tz_now()
    yesterday = (now_local - timedelta(days=1)).strftime('%Y-%m-%d')
    today = now_local.strftime('%Y-%m-%d')
    tomorrow = (now_local + timedelta(days=1)).strftime('%Y-%m-%d')

    query = '''
        SELECT
            rma.id, rma.match_id, rma.rule_id, rma.rule_name,
            rma.prediction, rma.handicap_team, rma.receiver_team,
            rma.bet_suggestion, rma.rule_accuracy,
            rma.signal_level, rma.mode, rma.rule_grade,
            rma.features,
            rma.match_time, rma.match_result, rma.is_correct,
            m.home_team_name, m.away_team_name, m.match_status,
            l.name_cn as league_name, l.league_id
        FROM rule_match_alerts rma
        LEFT JOIN matches m ON rma.match_id = m.match_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE DATE(rma.match_time) IN (%s, %s, %s)
        ORDER BY rma.match_time
    '''

    results = db.execute_query(query, (yesterday, today, tomorrow), fetch='all')

    matches_dict: Dict[int, Dict[str, Any]] = {}
    for r in results:
        match_id = r['match_id']
        is_big5 = r['league_id'] in BIG5_IDS

        # Parse features JSON
        feat = r['features'] or {}
        if isinstance(feat, str):
            import json as _json
            try:
                feat = _json.loads(feat)
            except Exception:
                feat = {}

        signal_level = r.get('signal_level') or feat.get('signal_level', '')
        mode = r.get('mode') or feat.get('mode', '')

        if match_id not in matches_dict:
            # 赔率字段: 兼容新版(w_h/w_r)和旧版(h_odds/r_odds)
            w_h = feat.get('w_h') or feat.get('h_odds', 0) or 0
            w_r = feat.get('w_r') or feat.get('r_odds', 0) or 0
            w_d = feat.get('w_d') or feat.get('curr_draw_odds', 0) or 0
            w_spread = feat.get('w_spread', 0) or 0

            # 初盘赔率 (用于计算变化)
            w_ih = feat.get('w_ih') or feat.get('init_h_odds', 0) or 0
            w_ir = feat.get('w_ir') or feat.get('init_r_odds', 0) or 0
            w_id = feat.get('w_id') or 0

            # 赔率字符串
            odds_str = (
                feat.get('odds_str')
                or (f"{w_h:.2f} / {w_d:.2f} / {w_r:.2f}" if w_h else '')
            )

            # 盘型 (区间类型): 优先读已存字段, 回退到空
            curr_h_full = feat.get('curr_h_full', '') or feat.get('w_curr_h_range', '') or ''
            curr_r_full = feat.get('curr_r_full', '') or feat.get('w_curr_r_range', '') or ''
            curr_draw_full = feat.get('curr_draw_full', '') or feat.get('w_curr_d_range', '') or ''

            # 变化: 优先读已存字段, 回退到从原始数据计算
            h_change_simple = feat.get('h_change_simple', '')
            r_change_simple = feat.get('r_change_simple', '')
            d_change_simple = feat.get('d_change_simple', '')
            if not h_change_simple and w_ih:
                h_change_simple = classify_odds_change_detailed(w_ih, w_h)
            if not r_change_simple and w_ir:
                r_change_simple = classify_odds_change_detailed(w_ir, w_r)
            if not d_change_simple and w_id:
                d_change_simple = classify_odds_change_detailed(w_id, w_d)

            # 力量差: 优先读已存字段, 回退到从 power_diff 计算
            power_str = feat.get('power_v2') or feat.get('power', '')
            if not power_str:
                pd_val = feat.get('w_power_diff') or feat.get('power_diff_val')
                if pd_val is not None:
                    power_str = classify_power(pd_val)

            matches_dict[match_id] = {
                'match_id': match_id,
                'home_team': r['home_team_name'],
                'away_team': r['away_team_name'],
                'league_name': r['league_name'],
                'league_id': r['league_id'],
                'is_big5': is_big5,
                'big5_name': BIG5_NAMES.get(r['league_id']),
                'match_time': r['match_time'].isoformat() if r['match_time'] else None,
                'match_status': r['match_status'],
                'handicap_team': r['handicap_team'],
                'receiver_team': r['receiver_team'],
                # --- v2.0 新字段 ---
                'signal_level': signal_level,
                'signal_icon': SIGNAL_ICON.get(signal_level, ''),
                'mode': mode,
                'mode_cn': MODE_CN.get(mode, ''),
                'w_h': w_h,
                'w_r': w_r,
                'w_d': w_d,
                'w_spread': w_spread,
                'm_h': feat.get('m_h'),
                'm_r': feat.get('m_r'),
                'm_spread': feat.get('m_spread'),
                'l_h': feat.get('l_h'),
                'l_r': feat.get('l_r'),
                'l_spread': feat.get('l_spread'),
                'cross_confirm': feat.get('cross_confirm', False),
                'conflict': feat.get('conflict', False),
                # --- 小程序显示字段 (向后兼容) ---
                'h_odds': w_h,
                'r_odds': w_r,
                'odds_str': odds_str,
                'ranges': {
                    'handicap': curr_h_full,
                    'receiver': curr_r_full,
                    'draw': curr_draw_full,
                },
                'changes': {
                    'handicap': h_change_simple or '',
                    'receiver': r_change_simple or '',
                    'draw': d_change_simple or '',
                },
                'power': power_str or '',
                'rules': [],
            }

        # 获取规则信息: 优先从 RULE_HISTORY 取，回退到 features/数据库
        rule_id = r['rule_id']
        rule_grade = r.get('rule_grade', '')
        history = RULE_HISTORY.get(rule_id, {})
        rule_accuracy = history.get('accuracy') or feat.get('accuracy', 0) or (
            float(r['rule_accuracy']) if r.get('rule_accuracy') else 0
        )
        rule_sample = history.get('sample') or feat.get('sample', 0)

        matches_dict[match_id]['rules'].append({
            'rule_id': rule_id,
            'rule_name': r['rule_name'],
            'rule_grade': rule_grade,
            'grade_cn': GRADE_CN.get(rule_grade, ''),
            'prediction': r['prediction'],       # 向后兼容旧版字段名
            'target': r['prediction'],            # v2.0 新字段名
            'accuracy': rule_accuracy,
            'accuracy_pct': f"{rule_accuracy * 100:.1f}%",
            'sample': rule_sample,
            'bet_suggestion': r['bet_suggestion'],
        })

    # 分组: 按信号等级 (v3.1: 重仓/强烈/参考)
    heavy_bets: List[Dict[str, Any]] = []      # 重仓 (V1+V3联合, 验证84.8%)
    strong_signals: List[Dict[str, Any]] = []   # 强烈 (单体系多规则)
    reference_signals: List[Dict[str, Any]] = [] # 参考 (单体系标准级)

    for match in matches_dict.values():
        # Sort rules by grade priority
        grade_order = {'S': 0, 'A': 1, 'B': 2}
        match['rules'].sort(key=lambda r: (grade_order.get(r['rule_grade'], 9), -r['accuracy']))

        max_accuracy = max(r['accuracy'] for r in match['rules']) if match['rules'] else 0
        match['confidence'] = f"{max_accuracy * 100:.1f}%"
        match['rule_count'] = len(match['rules'])

        n_s = sum(1 for r in match['rules'] if r['rule_grade'] == 'S')
        n_a = sum(1 for r in match['rules'] if r['rule_grade'] == 'A')
        match['grade_summary'] = f"{n_s}S+{n_a}A"

        sig = match.get('signal_level', '参考')
        if sig == '重仓':
            heavy_bets.append(match)
        elif sig == '强烈':
            strong_signals.append(match)
        else:
            reference_signals.append(match)

    # 按预测方向统计（不再作为独立分组返回，避免与信号等级分组重复）
    handicap_not_lose_count = sum(
        1 for m in matches_dict.values()
        if any(r['prediction'] == '让方不输' for r in m['rules'])
    )
    receiver_not_lose_count = sum(
        1 for m in matches_dict.values()
        if any(r['prediction'] == '受让方不输' for r in m['rules'])
    )

    return {
        'success': True,
        'date': today,
        'engine_version': 'v3.1 竞争区间规则引擎',
        'summary': {
            'total_matches': len(matches_dict),
            'heavy_bet_count': len(heavy_bets),
            'strong_signal_count': len(strong_signals),
            'reference_count': len(reference_signals),
            'handicap_not_lose_count': handicap_not_lose_count,
            'receiver_not_lose_count': receiver_not_lose_count,
        },
        # v3.1 唯一分组 (每场比赛只出现在一个分组中)
        'heavy_bets': sorted(heavy_bets, key=lambda x: (not x['is_big5'], x['match_time'] or '')),
        'strong_signals': sorted(strong_signals, key=lambda x: (not x['is_big5'], x['match_time'] or '')),
        'reference_signals': sorted(reference_signals, key=lambda x: (not x['is_big5'], x['match_time'] or '')),
    }


def build_match_alerts_payload(db: Any, match_id: int) -> Dict[str, Any]:
    """构建单场比赛的规则匹配详情"""
    query = '''
        SELECT
            rma.id, rma.match_id, rma.rule_id, rma.rule_name,
            rma.prediction, rma.handicap_team, rma.receiver_team,
            rma.bet_suggestion, rma.rule_accuracy,
            rma.signal_level, rma.mode, rma.rule_grade,
            rma.features,
            rma.match_time, rma.match_result, rma.is_correct,
            m.home_team_name, m.away_team_name, m.match_status,
            m.home_score, m.away_score,
            l.name_cn as league_name, l.league_id
        FROM rule_match_alerts rma
        LEFT JOIN matches m ON rma.match_id = m.match_id
        LEFT JOIN leagues l ON m.league_id = l.league_id
        WHERE rma.match_id = %s
    '''

    results = db.execute_query(query, (match_id,), fetch='all')
    if not results:
        return {'success': True, 'match_id': match_id, 'has_alert': False, 'rules': []}

    first = results[0]
    is_big5 = first['league_id'] in BIG5_IDS

    # Parse features
    feat = first['features'] or {}
    if isinstance(feat, str):
        import json as _json
        try:
            feat = _json.loads(feat)
        except Exception:
            feat = {}

    signal_level = first.get('signal_level') or feat.get('signal_level', '')
    mode = first.get('mode') or feat.get('mode', '')

    rules = []
    for r in results:
        rule_id = r['rule_id']
        history = RULE_HISTORY.get(rule_id, {})
        rules.append({
            'rule_id': rule_id,
            'rule_name': r['rule_name'],
            'rule_grade': r.get('rule_grade', ''),
            'grade_cn': GRADE_CN.get(r.get('rule_grade', ''), ''),
            'prediction': r['prediction'],
            'bet_suggestion': r['bet_suggestion'],
            'accuracy': history.get('accuracy', float(r['rule_accuracy']) if r['rule_accuracy'] else None),
            'sample': history.get('sample', 0),
            'features': r['features'],
        })

    return {
        'success': True,
        'match_id': match_id,
        'has_alert': True,
        'signal_level': signal_level,
        'signal_icon': SIGNAL_ICON.get(signal_level, ''),
        'mode': mode,
        'mode_cn': MODE_CN.get(mode, ''),
        'match_info': {
            'home_team': first['home_team_name'],
            'away_team': first['away_team_name'],
            'league_name': first['league_name'],
            'is_big5': is_big5,
            'match_time': first['match_time'].isoformat() if first['match_time'] else None,
            'match_status': first['match_status'],
            'home_score': first['home_score'],
            'away_score': first['away_score'],
            'handicap_team': first['handicap_team'],
            'receiver_team': first['receiver_team'],
            'cross_confirm': feat.get('cross_confirm', False),
            'conflict': feat.get('conflict', False),
        },
        'rules': rules,
    }


def build_rules_payload() -> Dict[str, Any]:
    """构建规则列表(新版: D-/T-/WL- 三大类)"""
    rules = list(PRECISION_RULES_PAYLOAD)

    h_rules = [r for r in rules if r['predict'] == '让方不输']
    r_rules = [r for r in rules if r['predict'] == '受让方不输']

    d_rules = [r for r in rules if r['requires'] == 'wm']
    t_rules = [r for r in rules if r['requires'] == 'wml']
    wl_rules = [r for r in rules if r['requires'] == 'wl']

    s_count = sum(1 for r in rules if r['grade'] == 'S')
    a_count = sum(1 for r in rules if r['grade'] == 'A')
    b_count = sum(1 for r in rules if r['grade'] == 'B')

    return {
        'success': True,
        'engine_version': 'v3.1 竞争区间规则引擎',
        'last_updated': '2026-02-11',
        'validation_note': '经 Walk-Forward 样本外验证 + 置换检验，支持三种公司组合自动适配',
        'summary': {
            'total_rules': len(rules),
            'handicap_not_lose_count': len(h_rules),
            'handicap_win_count': 0,             # 向后兼容
            'receiver_not_lose_count': len(r_rules),
            'd_rules_count': len(d_rules),
            't_rules_count': len(t_rules),
            'wl_rules_count': len(wl_rules),
            'grade_s_count': s_count,
            'grade_a_count': a_count,
            'grade_b_count': b_count,
        },
        'signal_levels': {
            '重仓': 'V1+V3跨体系联合确认，验证84.8%',
            '强烈': '单体系多条高级规则触发',
            '参考': '单体系标准级触发，仅供参考',
        },
        'company_modes': {
            'wml': '威廉+澳门+立博 (最强，D+T规则全开)',
            'wm': '威廉+澳门 (D规则)',
            'wl': '威廉+立博 无澳门 (WL后备规则)',
        },
        'd_rules': [r for r in rules if r['requires'] == 'wm'],
        't_rules': [r for r in rules if r['requires'] == 'wml'],
        'wl_rules': [r for r in rules if r['requires'] == 'wl'],
        # 向后兼容旧版分组
        'handicap_not_lose_rules': h_rules,
        'handicap_win_rules': [],
        'receiver_not_lose_rules': r_rules,
    }


__all__ = [
    "build_match_alerts_payload",
    "build_rule_alerts_payload",
    "build_rules_payload",
    "build_today_alerts_payload",
]
