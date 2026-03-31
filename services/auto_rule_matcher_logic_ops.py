#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
竞争区间规则引擎 v3.4 — 数据挖掘版 + V1兼容规则 + 同根因子去重 + P4高覆盖规则 + NEW-HN高精度规则
====================================================
基于 15,075 场历史比赛 european_odds 数据挖掘，
时间序列 80/20 切分 + 四重过拟合检测 (CV/OOS/落差/Wilson CI)。

支持三种公司组合，自动适配:
  ① 威廉+澳门+立博 (最强，D+T+WL+V1规则全开)
  ② 威廉+立博 无澳门 (D+WL+V1规则)
  ③ 威廉+澳门 无立博 (D+V1规则)

规则类型:
  D-  : 威廉+澳门 (requires='wm')
  T-  : 三公司 威廉+澳门+立博 (requires='wml')
  WL- : 威廉+立博 (requires='wl')
  V1- : 威廉单公司+OAR分析 (requires='w', OAR可选增强)

信号等级:
  重仓 — 多方案共振，最高可靠性
  强烈 — 多条高精度规则触发
  标准 — 有可靠规则触发
  无信号 — 不满足任何规则

v3.0 集成日期: 2026-02-11 (48条数据挖掘规则)
v3.1 集成日期: 2026-02-11 (新增20条V1兼容规则, 来源verified_rules.py)
v3.2 集成日期: 2026-02-24 (同根因子去重: wm_crr_diff组最多计1条S级, 历史命中率76%→修正)
v3.3 集成日期: 2026-02-24 (新增P4高覆盖规则: 18Bet/10Bet/Pinnacle/Interwetten四公司陪方移动量)
v3.4 集成日期: 2026-03-02 (新增16条NEW-HN高精度规则: 15951场历史OOS验证 avg86-90%, 新增avg3_rc/w_id_ratio特征)
v3.5 集成日期: 2026-03-02 (30天真实验证: 禁用WL-H07/WL-H16过拟合规则; V1-HN01/02/03/08/09降级B; NEW-HN16降级A)
数据来源: competitive_rule_miner_v2.py + verified_rules.py + top4_rule_finder_v2.py
"""

from __future__ import annotations

import math
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple


# ===================== 同根因子规则组 =====================
# 这些规则的核心驱动因子都是 wm_crr_diff (威澳返还率差)。
# 同一场比赛中无论触发多少条，信号等级计算时只计1条S级贡献，
# 防止同一因子被多条规则重复放大而虚高信号等级。
# 注: 触发列表 (triggered) 仍完整展示所有命中规则，不影响透明度。
_WM_CRR_DIFF_GROUP: frozenset = frozenset({
    'T-H02', 'T-H03', 'T-H11', 'T-H17',  # wml: wm_crr_diff > 4.307
    'D-H04', 'D-H08', 'D-H22',            # wm:  wm_crr_diff > 4.307
    'D-H19', 'D-H21',                      # wm:  wm_crr_diff > 3.690
})

# P4 规则组: 18Bet/10Bet/Pinnacle/Interwetten 四公司规则
# 设计原则:
#   1. 同根去重 — P4规则无论触发多少条，S级最多贡献1条、A级最多贡献1条
#   2. 纯P4信号上限 — 若无任何 W/M/L 规则同时触发，P4信号最高仅为"参考"
#   3. 跨体系共振加成 — P4 + W/M/L 同时触发，可在原有等级上升一级
_P4_RULE_IDS: frozenset = frozenset({
    'P4-H01', 'P4-H02', 'P4-H03', 'P4-H04',   # S级
    'P4-H05', 'P4-H06', 'P4-H07',               # A级
    'P4-H08', 'P4-H09',                          # B级
})

# NEW-HN 同根去重分组 (v3.4 新增):
#   两大子组: avg3_rc 组 (受让方变化率均值) 和 m_rc 组 (澳门受让方变化)
#   同一子组内的规则共享核心驱动因子，最多贡献 1 条 S 级
_NEW_HN_AVG_RC_GROUP: frozenset = frozenset({
    'NEW-HN05', 'NEW-HN06', 'NEW-HN09', 'NEW-HN10', 'NEW-HN11', 'NEW-HN14',
})
_NEW_HN_MAC_RC_GROUP: frozenset = frozenset({
    'NEW-HN02', 'NEW-HN03', 'NEW-HN07', 'NEW-HN12',
})
_NEW_HN_WH_R_GROUP: frozenset = frozenset({
    'NEW-HN01', 'NEW-HN15',
})


def _effective_grade_count(fired: List[Dict]) -> Tuple[int, int]:
    """
    计算信号等级用的有效 S/A 级规则数，对两类同根规则组去重:
      1. _WM_CRR_DIFF_GROUP: 威澳返还率差组，无论多少条只贡献1条最高等级
      2. _P4_RULE_IDS:       P4公司组，无论多少条，S级最多贡献1，A级最多贡献1
    返回 (effective_n_s, effective_n_a)
    """
    _all_dedup = (_WM_CRR_DIFF_GROUP | _P4_RULE_IDS
                  | _NEW_HN_AVG_RC_GROUP | _NEW_HN_MAC_RC_GROUP | _NEW_HN_WH_R_GROUP)
    crr_rules       = [r for r in fired if r['id'] in _WM_CRR_DIFF_GROUP]
    p4_rules        = [r for r in fired if r['id'] in _P4_RULE_IDS]
    new_avg_rules   = [r for r in fired if r['id'] in _NEW_HN_AVG_RC_GROUP]
    new_mac_rules   = [r for r in fired if r['id'] in _NEW_HN_MAC_RC_GROUP]
    new_whr_rules   = [r for r in fired if r['id'] in _NEW_HN_WH_R_GROUP]
    base_rules      = [r for r in fired if r['id'] not in _all_dedup]

    n_s = sum(1 for r in base_rules if r['grade'] == 'S')
    n_a = sum(1 for r in base_rules if r['grade'] == 'A')

    # 威澳返还率组: 组内所有规则只计1条最高等级
    if crr_rules:
        if any(r['grade'] == 'S' for r in crr_rules):
            n_s += 1
        else:
            n_a += 1

    # P4组: S级最多计1条，A级最多计1条（内部条件相互嵌套，去重）
    if p4_rules:
        if any(r['grade'] == 'S' for r in p4_rules):
            n_s += 1
        if any(r['grade'] == 'A' for r in p4_rules):
            n_a += 1

    # NEW-HN 同根子组: 各组内共享核心驱动因子，最多贡献1条S级
    for grp in (new_avg_rules, new_mac_rules, new_whr_rules):
        if grp:
            if any(r['grade'] == 'S' for r in grp):
                n_s += 1
            else:
                n_a += 1

    return n_s, n_a


# ===================== 规则注册 =====================
RULES: List[Dict[str, Any]] = []


def rule(rid: str, side: str, grade: str, requires: str, desc: str) -> Callable:
    """
    装饰器注册规则
    rid: 规则ID (如 'D-H01', 'T-R03', 'WL-H02')
    side: 'H'=让方不输, 'R'=受让方不输
    grade: 'S'=最高, 'A'=次高, 'B'=较高
    requires: 'wm'=需要威廉+澳门, 'wml'=需要三公司, 'wl'=威廉+立博(无需澳门)
    desc: 规则描述(含回测结果)
    """
    def wrap(fn: Callable) -> Callable:
        RULES.append({
            'id': rid, 'side': side, 'grade': grade,
            'requires': requires, 'fn': fn, 'desc': desc,
        })
        return fn
    return wrap


# =====================================================================
#  让方不输 (H) 规则 — 数据挖掘 v3.0
#  训练 12,060 场 / 测试 3,015 场 / 基线 73.0%
#  全部通过: 5-fold CV + OOS + 过拟合落差<5% + Wilson CI
# =====================================================================

# --- 让方不输 · 威廉+立博 · S级 ---

@rule('WL-H01', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博让方变化>4.9% → OOS 95.8%(n=48)')
def _(m):
    return m['w_r'] > 4.000 and m['l_hc'] > 0.049

@rule('WL-H06', 'H', 'S', 'wl',
      '威廉赔率差>2.170 + 立博让方变化>4.9% → OOS 92.7%(n=55)')
def _(m):
    return m['w_spread'] > 2.170 and m['l_hc'] > 0.049

# WL-H07 已禁用: 30天验证 62.5%(n=16), 声称92.1%, 差值-29.6%, 严重过拟合
# @rule('WL-H07', 'H', 'S', 'wl', ...)  →  DISABLED 2026-03-02

@rule('WL-H10', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博受让方变化<=-9.3% → OOS 91.9%(n=37)')
def _(m):
    return m['w_r'] > 4.000 and m['l_rc'] <= -0.093

@rule('WL-H13', 'H', 'S', 'wl',
      '立博受让方>3.900 + 立博受让方变化<=-5.4% → OOS 91.2%(n=57)')
def _(m):
    return m['l_r'] > 3.900 and m['l_rc'] <= -0.054

@rule('WL-H15', 'H', 'S', 'wl',
      '立博赔率差>2.100 + 立博让方变化>5.1% → OOS 90.9%(n=44)')
def _(m):
    return m['l_spread'] > 2.100 and m['l_hc'] > 0.051

# WL-H16 已禁用: 30天验证 67.7%(n=31), 声称90.7%, 差值-23.0%, 严重过拟合
# @rule('WL-H16', 'H', 'S', 'wl', ...)  →  DISABLED 2026-03-02

@rule('WL-H18', 'H', 'S', 'wl',
      '立博受让方>3.900 + 威廉受让方变化<=-9.3% → OOS 90.5%(n=42)')
def _(m):
    return m['l_r'] > 3.900 and m['w_rc'] <= -0.093

@rule('WL-H20', 'H', 'S', 'wl',
      '威廉受让方>4.000 + 立博受让方变化<=-5.4% → OOS 90.4%(n=52)')
def _(m):
    return m['w_r'] > 4.000 and m['l_rc'] <= -0.054

# --- 让方不输 · 三公司 · S级 ---

@rule('T-H02', 'H', 'S', 'wml',
      '立博受让方>3.400 + 威澳返还率差>4.307 → OOS 95.2%(n=62)')
def _(m):
    return m['l_r'] > 3.400 and m['wm_crr_diff'] > 4.307

@rule('T-H03', 'H', 'S', 'wml',
      '立博赔率差>1.750 + 威澳返还率差>4.307 → OOS 94.0%(n=50)')
def _(m):
    return m['l_spread'] > 1.750 and m['wm_crr_diff'] > 4.307

@rule('T-H05', 'H', 'S', 'wml',
      '澳门赔率差>1.840 + 立博让方变化>5.1% → OOS 93.3%(n=30)')
def _(m):
    return m['m_spread'] > 1.840 and m['l_hc'] > 0.051

@rule('T-H11', 'H', 'S', 'wml',
      '立博让方<=1.800 + 威澳返还率差>4.307 → OOS 91.7%(n=36)')
def _(m):
    return m['l_h'] <= 1.800 and m['wm_crr_diff'] > 4.307

@rule('T-H17', 'H', 'S', 'wml',
      '三公司受让方均值>3.183 + 威澳返还率差>4.307 → OOS 90.5%(n=74)')
def _(m):
    return m['avg3_r'] > 3.183 and m['wm_crr_diff'] > 4.307

# --- 让方不输 · 威廉+澳门 · S级 ---

@rule('D-H04', 'H', 'S', 'wm',
      '澳门受让方>3.150 + 威澳返还率差>4.307 → OOS 93.8%(n=48)')
def _(m):
    return m['m_r'] > 3.150 and m['wm_crr_diff'] > 4.307

@rule('D-H08', 'H', 'S', 'wm',
      '澳门赔率差>1.450 + 威澳返还率差>4.307 → OOS 92.1%(n=38)')
def _(m):
    return m['m_spread'] > 1.450 and m['wm_crr_diff'] > 4.307

@rule('D-H09', 'H', 'S', 'wm',
      '威廉让方变化<=0 + 威廉初盘受让方>4.200 → OOS 92.1%(n=38)')
def _(m):
    return m['w_hc'] <= 0.000 and m['w_ir'] > 4.200

@rule('D-H12', 'H', 'S', 'wm',
      '澳门赔率差>1.840 + 威廉让方变化>2.9% → OOS 91.3%(n=46)')
def _(m):
    return m['m_spread'] > 1.840 and m['w_hc'] > 0.029

@rule('D-H14', 'H', 'S', 'wm',
      '威廉让方<=1.850 + 威廉受让方变化<=-13.3% → OOS 90.9%(n=44)')
def _(m):
    return m['w_h'] <= 1.850 and m['w_rc'] <= -0.133

@rule('D-H19', 'H', 'S', 'wm',
      '澳门初盘受让方>3.650 + 威澳返还率差>3.690 → OOS 90.5%(n=42)')
def _(m):
    return m['m_ir'] > 3.650 and m['wm_crr_diff'] > 3.690

@rule('D-H21', 'H', 'S', 'wm',
      '澳门赔率差>1.840 + 威澳返还率差>3.690 → OOS 90.0%(n=50)')
def _(m):
    return m['m_spread'] > 1.840 and m['wm_crr_diff'] > 3.690

# --- 让方不输 · A级 ---

@rule('D-H22', 'H', 'A', 'wm',
      '澳门让方<=1.900 + 威澳返还率差>4.307 → OOS 89.8%(n=59)')
def _(m):
    return m['m_h'] <= 1.900 and m['wm_crr_diff'] > 4.307

@rule('T-H23', 'H', 'A', 'wml',
      '立博让方<=1.800 + 三公司让方变化均值>4.9% → OOS 89.8%(n=49)')
def _(m):
    return m['l_h'] <= 1.800 and m['avg3_hc'] > 0.049

@rule('D-H24', 'H', 'A', 'wm',
      '澳门赔率差>1.840 + 威廉让方变化>0 → OOS 89.7%(n=68)')
def _(m):
    return m['m_spread'] > 1.840 and m['w_hc'] > 0.000

@rule('T-H25', 'H', 'A', 'wml',
      '三公司让方变化均值>0.7% + 澳门赔率差>1.840 → OOS 89.6%(n=67)')
def _(m):
    return m['avg3_hc'] > 0.007 and m['m_spread'] > 1.840


# =====================================================================
#  受让不输 (R) 规则 — 数据挖掘 v3.0
#  训练 12,060 场 / 测试 3,015 场 / 基线 55.3%
# =====================================================================

# --- 受让不输(R) 规则全部移除 ---
# V3 R规则 (23条) 于 2026-02-11 移除
# 原因: 单独触发仅 66% 准确率，无V1交叉确认支撑
# 系统现仅输出让方不输(H)信号


# =====================================================================
#  V1 兼容规则 — 来源: verified_rules.py (经验证可用规则)
#  基于公司 115(威廉) 单公司赔率 + OAR分析数据
#  requires='w' — 所有模式均有威廉，均可触发
#  OAR 特征不可用时，依赖 OAR 的规则自动跳过 (返回 False)
#  数据来源: 2676场竞争区间 (让方赔率>=1.70)，验证日期 2026-02-10
# =====================================================================

# --- A类: 让方不输 (基线 73.5%) ---

@rule('V1-HN01', 'H', 'B', 'w',
      '[V1↓B] 即时让方<=1.850 + 让方偏移变化<=-0.400 → 30天验证78.8%(n=66), 降级')
def _(m):
    hoc = m.get('w_h_off_chg')
    if hoc is None:
        return False
    return m['w_h'] <= 1.850 and hoc <= -0.400

@rule('V1-HN02', 'H', 'B', 'w',
      '[V1↓B] 受让方变化%>4.2% + 初盘受让方理论距离>1.700 → 30天验证77.5%(n=40), 降级')
def _(m):
    rt = m.get('w_rt')
    if rt is None:
        return False
    return m['w_rc'] > 0.042 and rt > 1.700

@rule('V1-HN03', 'H', 'B', 'w',
      '[V1↓B] 受让方变化%>4.2% + 初盘赔率差>1.950 → 30天验证76.9%(n=26), 降级')
def _(m):
    i_sp = m.get('w_i_spread')
    if i_sp is None:
        return False
    return m['w_rc'] > 0.042 and i_sp > 1.950

@rule('V1-HN04', 'H', 'A', 'w',
      '[V1] 即时受让方>3.900 + 受让方变化%<=-9.7% → OOS 89.7%(n=29)')
def _(m):
    return m['w_r'] > 3.900 and m['w_rc'] <= -0.097

@rule('V1-HN05', 'H', 'S', 'w',
      '[V1] 赔率差>0.710+受让方实开+受让方偏移变化<=-0.150+Kelly<=0.895 → CV 86.2%(n=123)')
def _(m):
    roc = m.get('w_r_off_chg')
    kr = m.get('w_kr')
    rng = m.get('w_curr_r_range')
    if roc is None or kr is None or rng is None:
        return False
    return (m['w_spread'] > 0.710
            and '实开' in str(rng)
            and roc <= -0.150
            and kr <= 0.895)

@rule('V1-HN06', 'H', 'S', 'w',
      '[V1] 初盘平赔比<=0.925 + 初盘让方<=1.850 → CV 85.1%(n=87)')
def _(m):
    dri = m.get('w_dri')
    if dri is None:
        return False
    return dri <= 0.925 and m['w_ih'] <= 1.850

@rule('V1-HN07', 'H', 'S', 'w',
      '[V1] 即时受让方>3.100 + 初盘受让方<=2.800 → CV 82.4%(n=68)')
def _(m):
    return m['w_r'] > 3.100 and m['w_ir'] <= 2.800

@rule('V1-HN08', 'H', 'B', 'w',
      '[V1↓B] 即时返还率<=90.658 + 初盘受让方理论距离>1.700 → 30天验证78.8%(n=52), 降级')
def _(m):
    rt = m.get('w_rt')
    if rt is None:
        return False
    crr = m.get('w_crr')
    if crr is None:
        return False
    return crr <= 90.658 and rt > 1.700

@rule('V1-HN09', 'H', 'B', 'w',
      '[V1↓B] 即时让方<=1.850 + 让方偏移变化<=-0.900 → 30天验证72.4%(n=29), 降级')
def _(m):
    hoc = m.get('w_h_off_chg')
    if hoc is None:
        return False
    return m['w_h'] <= 1.850 and hoc <= -0.900

@rule('V1-HN10', 'H', 'S', 'w',
      '[V1] 即时受让方>3.900 + 让方变化%>10% → CV 85.7%(n=35)')
def _(m):
    return m['w_r'] > 3.900 and m['w_hc'] > 0.100

# --- 让方不输 · NEW-HN系列 · 2026-03-02 高精度挖掘 ---
# 来源: 15951场历史数据 时间分割OOS验证 (训练<2025-11-01, OOS>=2025-11-01)
# 特征: avg3_rc=多公司受让方变化%均值, w_id_ratio=威廉初盘平让比
# 核心发现: ①澳门让方极低赔率(<1.7)+受让方赔率大幅上升 ②受让方高赔+返还率低 极强组合

@rule('NEW-HN01', 'H', 'S', 'w',
      '威廉即时受让方>4.5 + 威廉即时返还率<=90.72 → OOS 90.1%(n=111)')
def _(m):
    return (m.get('w_r') is not None and m['w_r'] > 4.5) and (m.get('w_crr') is not None and m['w_crr'] < 90.72)

@rule('NEW-HN02', 'H', 'S', 'wm',
      '澳门初盘让方<=1.79 + 澳门受让方变化%>15.0% → OOS 90.0%(n=70)')
def _(m):
    return (m.get('m_ih') is not None and m['m_ih'] < 1.79) and (m.get('m_rc') is not None and m['m_rc'] > 0.15)

@rule('NEW-HN03', 'H', 'S', 'wm',
      '澳门受让方变化%>15.0% + 澳门初盘赔率差>1.82 → OOS 89.0%(n=73)')
def _(m):
    return (m.get('m_rc') is not None and m['m_rc'] > 0.15) and (m.get('m_i_spread') is not None and m['m_i_spread'] > 1.82)

@rule('NEW-HN04', 'H', 'S', 'wl',
      '立博受让方>4.33 + 威廉即时返还率<=89.67 → OOS 88.9%(n=63)')
def _(m):
    return (m.get('l_r') is not None and m['l_r'] > 4.33) and (m.get('w_crr') is not None and m['w_crr'] < 89.67)

@rule('NEW-HN05', 'H', 'S', 'wm',
      '澳门即时让方<=1.7 + 三公司受让方变化%均值>19.0% → OOS 88.8%(n=98)')
def _(m):
    return (m.get('m_h') is not None and m['m_h'] < 1.7) and (m.get('avg3_rc') is not None and m['avg3_rc'] > 0.19)

@rule('NEW-HN06', 'H', 'S', 'wml',
      '立博初盘赔率差>2.09 + 三公司受让方变化%均值>19.0% → OOS 88.1%(n=84)')
def _(m):
    return (m.get('l_i_spread') is not None and m['l_i_spread'] > 2.09) and (m.get('avg3_rc') is not None and m['avg3_rc'] > 0.19)

@rule('NEW-HN07', 'H', 'S', 'wm',
      '澳门即时让方<=1.7 + 澳门受让方变化%>15.0% → OOS 88.0%(n=133)')
def _(m):
    return (m.get('m_h') is not None and m['m_h'] < 1.7) and (m.get('m_rc') is not None and m['m_rc'] > 0.15)

@rule('NEW-HN08', 'H', 'S', 'w',
      '威廉初盘让方<=1.83 + 威廉受让方变化%>15.2% → OOS 88.0%(n=92)')
def _(m):
    return (m.get('w_ih') is not None and m['w_ih'] < 1.83) and (m.get('w_rc') is not None and m['w_rc'] > 0.152)

@rule('NEW-HN09', 'H', 'S', 'wm',
      '澳门初盘让方<=1.85 + 三公司受让方变化%均值>19.0% → OOS 87.7%(n=81)')
def _(m):
    return (m.get('m_ih') is not None and m['m_ih'] < 1.85) and (m.get('avg3_rc') is not None and m['avg3_rc'] > 0.19)

@rule('NEW-HN10', 'H', 'S', 'wml',
      '立博初盘受让方>4.0 + 三公司受让方变化%均值>19.0% → OOS 87.5%(n=56)')
def _(m):
    return (m.get('l_ir') is not None and m['l_ir'] > 4.0) and (m.get('avg3_rc') is not None and m['avg3_rc'] > 0.19)

@rule('NEW-HN11', 'H', 'S', 'wm',
      '澳门受让方>4.0 + 三公司受让方变化%均值>19.0% → OOS 87.4%(n=111)')
def _(m):
    return (m.get('m_r') is not None and m['m_r'] > 4.0) and (m.get('avg3_rc') is not None and m['avg3_rc'] > 0.19)

@rule('NEW-HN12', 'H', 'S', 'wml',
      '立博即时让方<=1.7 + 澳门受让方变化%>15.0% → OOS 87.2%(n=109)')
def _(m):
    return (m.get('l_h') is not None and m['l_h'] < 1.7) and (m.get('m_rc') is not None and m['m_rc'] > 0.15)

@rule('NEW-HN13', 'H', 'S', 'w',
      '威廉让方变化%<=-7.1% + 威廉初盘赔率差>2.42 → OOS 86.9%(n=84)')
def _(m):
    return (m.get('w_hc') is not None and m['w_hc'] < -0.071) and (m.get('w_i_spread') is not None and m['w_i_spread'] > 2.42)

@rule('NEW-HN14', 'H', 'S', 'wm',
      '威廉初盘让方<=1.85 + 三公司受让方变化%均值>19.0% → OOS 86.8%(n=76)')
def _(m):
    return (m.get('w_ih') is not None and m['w_ih'] < 1.85) and (m.get('avg3_rc') is not None and m['avg3_rc'] > 0.19)

@rule('NEW-HN15', 'H', 'S', 'wm',
      '威廉即时受让方>4.5 + 澳门受让方变化%>10.9% → OOS 86.7%(n=135)')
def _(m):
    return (m.get('w_r') is not None and m['w_r'] > 4.5) and (m.get('m_rc') is not None and m['m_rc'] > 0.109)

@rule('NEW-HN16', 'H', 'A', 'wm',
      '澳门受让方>4.0 + 澳门受让方变化%>10.9% → OOS 86.5%(n=185), 30天76.9%(n=13)↓A级')
def _(m):
    return (m.get('m_r') is not None and m['m_r'] > 4.0) and (m.get('m_rc') is not None and m['m_rc'] > 0.109)

# --- B类: 受让方不输 — 已关闭 (全量验证仅53-61%，低于实用标准) ---
# V1-RN01~RN10 已于 2026-02-11 关闭，全量 15531 场验证准确率远低于预期


# ===================== 数据加载 =====================

def _f(v: Any) -> Optional[float]:
    """安全转换为 float"""
    if v is None:
        return None
    return float(v) if isinstance(v, (Decimal, int, float)) else float(v)


def load_match_features(match_id: Any, db: Any) -> Tuple[Optional[Dict], Optional[str]]:
    """
    加载比赛特征，自动适配公司组合。

    赔率数据源 (按优先级):
      1. odds_changes  — 实时赔率，未开赛/进行中比赛 (无kelly)
      2. european_odds — 终盘赔率，完赛后入库 (有kelly)
    辅助数据源:
      3. odds_analysis_results — 偏移/理论距离，可选
    
    数据可用性与规则覆盖:
      有 odds_changes (无kelly无OAR): 29条纯赔率规则可用
      有 european_odds (有kelly无OAR): 35条规则可用
      有 european_odds + OAR:          46条规则全部可用

    返回 (feat_dict, mode) 或 (None, None)
    mode: 'wml'=三公司, 'wm'=威澳, 'wl'=威立
    """
    mt = db.execute_query(
        'SELECT * FROM matches WHERE match_id=%s', (match_id,), fetch='one'
    )
    if not mt:
        return None, None

    # 加载赔率: 115=威廉, 80=澳门, 82=立博, 281=bet365, 177=平博
    # 优先 odds_changes (实时)，回退 european_odds (完赛)
    odds: Dict[str, Dict] = {}
    for cid, pfx in [(115, 'w'), (80, 'm'), (82, 'l'), (281, 'b3'), (177, 'pb')]:
        # 先查 odds_changes
        row = db.execute_query(
            'SELECT * FROM odds_changes WHERE match_id=%s AND company_id=%s',
            (match_id, cid), fetch='one'
        )
        if row and _f(row.get('initial_home')) and _f(row['initial_home']) > 0:
            odds[pfx] = row
        else:
            # 回退到 european_odds (完赛后数据)
            row = db.execute_query(
                'SELECT * FROM european_odds WHERE match_id=%s AND company_id=%s',
                (match_id, cid), fetch='one'
            )
            if row and _f(row.get('initial_home')) and _f(row['initial_home']) > 0:
                odds[pfx] = row

    # 加载 OAR (odds_analysis_results) — 可选，有则加分
    oar: Dict[str, Dict] = {}
    for cid, pfx in [(115, 'w'), (80, 'm'), (82, 'l')]:
        row = db.execute_query(
            'SELECT * FROM odds_analysis_results WHERE match_id=%s AND company_id=%s',
            (match_id, cid), fetch='one'
        )
        if row:
            oar[pfx] = row

    # 确定模式: 只需要赔率数据，不强制要求 OAR
    if 'w' not in odds:
        return None, None  # 至少需要威廉赔率

    has_m = 'm' in odds   # 有澳门赔率即可
    has_l = 'l' in odds   # 有立博赔率即可
    has_b3 = 'b3' in odds  # 有bet365赔率
    has_pb = 'pb' in odds  # 有平博赔率

    if has_m and has_l:
        mode = 'wml'
    elif has_m:
        mode = 'wm'
    elif has_l:
        mode = 'wl'
    else:
        return None, None  # 只有威廉单独，无足够规则

    # 判断让方
    w_ih = _f(odds['w']['initial_home'])
    w_ia = _f(odds['w']['initial_away'])
    if not w_ih or not w_ia or w_ih <= 0 or w_ia <= 0:
        return None, None
    home_is_h = w_ih <= w_ia

    def pick(pfx: str, hk: str, ak: str) -> Tuple[Optional[float], Optional[float]]:
        o = odds[pfx]
        return (_f(o.get(hk)), _f(o.get(ak))) if home_is_h else (_f(o.get(ak)), _f(o.get(hk)))

    def pick_oar(pfx: str, hk: str, ak: str) -> Tuple[Optional[float], Optional[float]]:
        """安全读取 OAR 数据，无 OAR 时返回 (None, None)"""
        if pfx not in oar:
            return None, None
        o = oar[pfx]
        return (_f(o.get(hk)), _f(o.get(ak))) if home_is_h else (_f(o.get(ak)), _f(o.get(hk)))

    feat: Dict[str, Any] = {
        'match_id': match_id,
        'home_is_h': home_is_h,
        'mode': mode,
        'has_m': has_m,
        'has_lb': has_l,
        'has_b3': has_b3,
        'has_pb': has_pb,
    }

    # 剪刀差信号所需的原始赔率（不经过让方转换）
    has_sc = has_pb and has_b3 and has_l  # 需要平博+bet365+立博(+威廉已有)
    feat['has_sc'] = has_sc
    for _sc_pfx in ['w', 'l', 'b3', 'pb']:
        if _sc_pfx in odds:
            _sc_o = odds[_sc_pfx]
            feat[f'{_sc_pfx}_raw_ih'] = _f(_sc_o.get('initial_home'))
            feat[f'{_sc_pfx}_raw_id'] = _f(_sc_o.get('initial_draw'))
            feat[f'{_sc_pfx}_raw_ia'] = _f(_sc_o.get('initial_away'))
            feat[f'{_sc_pfx}_raw_ch'] = _f(_sc_o.get('current_home'))
            feat[f'{_sc_pfx}_raw_cd'] = _f(_sc_o.get('current_draw'))
            feat[f'{_sc_pfx}_raw_ca'] = _f(_sc_o.get('current_away'))
    feat['match_time'] = mt.get('match_time')
    feat['league_id'] = mt.get('league_id')
    feat['home_team_id'] = mt.get('home_team_id')
    feat['away_team_id'] = mt.get('away_team_id')
    feat['match_status'] = mt.get('match_status')

    available = ['w']
    if has_m:
        available.append('m')
    if has_l:
        available.append('l')

    for pfx in available:
        o = odds[pfx]
        a = oar.get(pfx)  # 可能为 None
        ih, ir = pick(pfx, 'initial_home', 'initial_away')
        ch, cr = pick(pfx, 'current_home', 'current_away')
        id_ = _f(o['initial_draw'])
        cd = _f(o['current_draw'])

        hc = (ch - ih) / ih if ih and ih > 0 else 0
        rc = (cr - ir) / ir if ir and ir > 0 else 0
        dc = (cd - id_) / id_ if id_ and id_ > 0 else 0

        # OAR 特征: 偏移、理论距离 — 无 OAR 时全部为 None
        iho, iro = pick_oar(pfx, 'initial_home_offset', 'initial_away_offset')
        cho, cro = pick_oar(pfx, 'current_home_offset', 'current_away_offset')
        iht, irt = pick_oar(pfx, 'initial_home_theory_distance', 'initial_away_theory_distance')
        hoc = (cho - iho) if cho is not None and iho is not None else None
        roc = (cro - iro) if cro is not None and iro is not None else None

        kh, kr = pick(pfx, 'kelly_home', 'kelly_away')
        kh = _f(kh)
        kr = _f(kr)
        kd = _f(o.get('kelly_draw'))

        # 平赔比 (draw ratio) — 无 OAR 时为 None
        ids_v = _f(a.get('initial_draw_standard')) if a else None
        idf_v = _f(a.get('initial_draw_fullwater')) if a else None
        dri = idf_v / ids_v if idf_v and ids_v and ids_v > 0 else None

        irr = _f(o.get('initial_return_rate'))
        crr = _f(o.get('current_return_rate'))

        feat[f'{pfx}_ih'] = ih
        feat[f'{pfx}_ir'] = ir
        feat[f'{pfx}_id'] = id_       # 初盘平赔
        feat[f'{pfx}_h'] = ch
        feat[f'{pfx}_r'] = cr
        feat[f'{pfx}_d'] = cd         # 即时平赔
        feat[f'{pfx}_spread'] = cr - ch if cr is not None and ch is not None else None
        feat[f'{pfx}_hc'] = hc
        feat[f'{pfx}_rc'] = rc
        feat[f'{pfx}_dc'] = dc
        feat[f'{pfx}_iho'] = iho
        feat[f'{pfx}_iro'] = iro
        feat[f'{pfx}_ho'] = cho
        feat[f'{pfx}_ro'] = cro
        feat[f'{pfx}_h_off_chg'] = hoc
        feat[f'{pfx}_r_off_chg'] = roc
        feat[f'{pfx}_ht'] = iht
        feat[f'{pfx}_rt'] = irt
        feat[f'{pfx}_kh'] = kh
        feat[f'{pfx}_kd'] = kd
        feat[f'{pfx}_kr'] = kr
        feat[f'{pfx}_dri'] = dri
        feat[f'{pfx}_irr'] = irr
        feat[f'{pfx}_crr'] = crr

        # 初盘赔率差 (verified_rules V1 所需 odds_diff)
        feat[f'{pfx}_i_spread'] = ir - ih if ir is not None and ih is not None else None

        # OAR 额外特征: power_diff, 开盘区间 (V1 兼容规则所需)
        if a:
            feat[f'{pfx}_power_diff'] = _f(a.get('power_diff'))
            # 让方/受让方/平局 当前区间类型: 如 '实开', '高开', '韬光' 等
            if home_is_h:
                feat[f'{pfx}_curr_h_range'] = a.get('current_home_range')
                feat[f'{pfx}_curr_r_range'] = a.get('current_away_range')
                feat[f'{pfx}_init_h_range'] = a.get('initial_home_range')
                feat[f'{pfx}_init_r_range'] = a.get('initial_away_range')
            else:
                feat[f'{pfx}_curr_h_range'] = a.get('current_away_range')
                feat[f'{pfx}_curr_r_range'] = a.get('current_home_range')
                feat[f'{pfx}_init_h_range'] = a.get('initial_away_range')
                feat[f'{pfx}_init_r_range'] = a.get('initial_home_range')
            feat[f'{pfx}_curr_d_range'] = a.get('current_draw_range')
            feat[f'{pfx}_init_d_range'] = a.get('initial_draw_range')
        else:
            feat[f'{pfx}_power_diff'] = None
            feat[f'{pfx}_curr_h_range'] = None
            feat[f'{pfx}_curr_r_range'] = None
            feat[f'{pfx}_init_h_range'] = None
            feat[f'{pfx}_init_r_range'] = None
            feat[f'{pfx}_curr_d_range'] = None
            feat[f'{pfx}_init_d_range'] = None

    # 竞争区间检查: 威廉必须在竞争区间
    if feat.get('w_h') is None or feat.get('w_r') is None:
        return None, None
    if min(feat['w_h'], feat['w_r']) < 1.70:
        return None, None

    # ---- P4高覆盖公司特征 (v3.3 新增) ----
    # 公司: 18Bet(976) / 10Bet(16) / Pinnacle(177) / Interwetten(104)
    # 只需 3 家有完整开盘+即时赔率即可启用
    _P4_CIDS = [976, 16, 177, 104]
    p4_data = {}
    for _cid in _P4_CIDS:
        _row = db.execute_query(
            'SELECT initial_home, initial_away, current_home, current_away '
            'FROM european_odds WHERE match_id=%s AND company_id=%s',
            (match_id, _cid), fetch='one'
        )
        if (_row and _f(_row.get('initial_home')) and _f(_row.get('initial_home')) > 1.0
                and _f(_row.get('current_home')) and _f(_row.get('current_home')) > 1.0):
            p4_data[_cid] = {
                'ih': _f(_row['initial_home']), 'ia': _f(_row['initial_away']),
                'ch': _f(_row['current_home']), 'ca': _f(_row['current_away']),
            }

    feat['has_p4'] = len(p4_data) >= 3

    if feat['has_p4']:
        _n = len(p4_data)

        # P4 用自己四家公司的开盘均值来独立判断让方（不依赖威廉）
        _p4_avg_ih = sum(v['ih'] for v in p4_data.values()) / _n
        _p4_avg_ia = sum(v['ia'] for v in p4_data.values()) / _n
        _p4_home_is_h = _p4_avg_ih <= _p4_avg_ia  # P4自己判断：主场是否为让方

        # 如果P4与威廉对让方判断不一致，禁用P4规则（避免方向混乱）
        feat['p4_agrees_with_wh'] = (_p4_home_is_h == home_is_h)
        if not feat['p4_agrees_with_wh']:
            feat['has_p4'] = False
            for _k in ['p4_avg_fav_move', 'p4_avg_und_move', 'p4_move_diff',
                       'p4_und_move_magnitude', 'p4_avg_fav_ini', 'p4_avg_und_ini',
                       'p4_avg_fav_cur', 'p4_avg_und_cur', 'p4_n_companies']:
                feat[_k] = None

        if feat['has_p4']:
            if _p4_home_is_h:
                _fav_ini  = _p4_avg_ih
                _und_ini  = _p4_avg_ia
                _fav_cur  = sum(v['ch'] for v in p4_data.values()) / _n
                _und_cur  = sum(v['ca'] for v in p4_data.values()) / _n
                _f_moves  = [v['ih'] - v['ch'] for v in p4_data.values()]
                _u_moves  = [v['ia'] - v['ca'] for v in p4_data.values()]
            else:
                _fav_ini  = _p4_avg_ia
                _und_ini  = _p4_avg_ih
                _fav_cur  = sum(v['ca'] for v in p4_data.values()) / _n
                _und_cur  = sum(v['ch'] for v in p4_data.values()) / _n
                _f_moves  = [v['ia'] - v['ca'] for v in p4_data.values()]
                _u_moves  = [v['ih'] - v['ch'] for v in p4_data.values()]

            # 核心特征（正值=赔率下降=资金流入，负值=赔率上涨=资金逃离）
            feat['p4_avg_fav_move']       = sum(_f_moves) / _n
            feat['p4_avg_und_move']       = sum(_u_moves) / _n
            feat['p4_move_diff']          = feat['p4_avg_fav_move'] - feat['p4_avg_und_move']
            feat['p4_und_move_magnitude'] = sum(abs(m) for m in _u_moves) / _n
            feat['p4_avg_fav_ini']        = _fav_ini
            feat['p4_avg_und_ini']        = _und_ini
            feat['p4_avg_fav_cur']        = _fav_cur
            feat['p4_avg_und_cur']        = _und_cur
            feat['p4_n_companies']        = _n
    else:
        feat['p4_agrees_with_wh'] = None
        for _k in ['p4_avg_fav_move', 'p4_avg_und_move', 'p4_move_diff',
                   'p4_und_move_magnitude', 'p4_avg_fav_ini', 'p4_avg_und_ini',
                   'p4_avg_fav_cur', 'p4_avg_und_cur', 'p4_n_companies']:
            feat[_k] = None

    # ---- 跨公司衍生特征 (v3.0 数据挖掘规则所需) ----
    def _safe_diff(a, b):
        return (a - b) if a is not None and b is not None else None

    # 威澳返还率差
    feat['wm_crr_diff'] = _safe_diff(feat.get('w_crr'), feat.get('m_crr'))

    # 威立让方变化差
    feat['wl_hc_diff'] = _safe_diff(feat.get('w_hc'), feat.get('l_hc'))

    # 三公司均值 (仅三公司齐全时计算)
    if mode == 'wml':
        w_r, m_r, l_r = feat.get('w_r'), feat.get('m_r'), feat.get('l_r')
        if w_r is not None and m_r is not None and l_r is not None:
            feat['avg3_r'] = (w_r + m_r + l_r) / 3
        else:
            feat['avg3_r'] = None

        w_sp, m_sp, l_sp = feat.get('w_spread'), feat.get('m_spread'), feat.get('l_spread')
        if w_sp is not None and m_sp is not None and l_sp is not None:
            feat['avg3_spread'] = (w_sp + m_sp + l_sp) / 3
        else:
            feat['avg3_spread'] = None

        w_hc, m_hc, l_hc = feat.get('w_hc'), feat.get('m_hc'), feat.get('l_hc')
        if w_hc is not None and m_hc is not None and l_hc is not None:
            feat['avg3_hc'] = (w_hc + m_hc + l_hc) / 3
        else:
            feat['avg3_hc'] = None
    else:
        feat['avg3_r'] = None
        feat['avg3_spread'] = None
        feat['avg3_hc'] = None

    # ---- 新增特征 (v3.4 高精度规则所需) ----
    # avg3_rc: 多公司受让方变化%均值 (所有可用公司取均值，不限wml)
    _rcs = [v for v in [feat.get('w_rc'), feat.get('m_rc'), feat.get('l_rc')]
            if v is not None]
    feat['avg3_rc'] = sum(_rcs) / len(_rcs) if len(_rcs) >= 2 else None

    # w_id_ratio: 威廉初盘 平赔/让方赔率 比值 (平让比)
    _w_id = feat.get('w_id')   # 初盘平赔
    _w_ih = feat.get('w_ih')   # 初盘让方赔率
    feat['w_id_ratio'] = (_w_id / _w_ih) if (_w_id and _w_ih and _w_ih > 0) else None

    return feat, mode


# ===================== 规则评估 =====================

def _rule_compatible(rule_requires: str, mode: str, feat: Optional[Dict] = None) -> bool:
    """规则是否兼容当前模式
    
    v3.0 更新: WL规则在三公司模式下也可触发 (所需特征 w_/l_ 均可用)
    v3.1 新增: 'w' 仅需威廉 (所有模式均有威廉, V1兼容规则用)
    v3.3 新增: 'p4' 仅需四家高覆盖公司(976/16/177/104)中至少3家有数据
    """
    if rule_requires == 'w':
        return True                    # 仅需威廉，所有模式都有
    elif rule_requires == 'wm':
        return mode in ('wm', 'wml')  # 有澳门就行
    elif rule_requires == 'wml':
        return mode == 'wml'           # 必须三公司齐全
    elif rule_requires == 'wl':
        return mode in ('wl', 'wml')   # 有立博就行 (v3.0: 三公司也可触发)
    elif rule_requires == 'p4':
        return feat is not None and bool(feat.get('has_p4'))  # v3.3: 四公司数据可用
    elif rule_requires == 'sc':
        return feat is not None and bool(feat.get('has_sc'))  # v3.6: 剪刀差(需平博+bet365+威廉+立博)
    return False


# =====================================================================
#  P4 高覆盖公司规则 (v3.3) — 让方不输
#  数据: 18Bet(976) / 10Bet(16) / Pinnacle(177) / Interwetten(104)
#  挖掘: 23,106 场竞争性比赛 (让方初盘均值 1.30-2.80)
#        训练集 13,863 场 / 测试集 9,243 场 / 基准 76.4%
#        时序 60/40 分割, 过拟合检验: 训练/测试差距 <= 8%
#
#  核心信号: p4_avg_und_move（陪方赔率漂移量）
#    = 四公司开盘均值 - 四公司即时均值
#    负值 = 陪方赔率上涨 = 市场资金逃离陪方 = 让方更安全
#
#  阈值参考:
#    < -0.5  → 85.1% (26.5% 覆盖)  [Grade B]
#    < -1.0  → 89.0% (12.6% 覆盖)  [Grade A]
#    < -1.5  → 92.5% (6.8%  覆盖)  [Grade S]
#  p4_move_diff = (让方移动量均值) - (陪方移动量均值)
#    > 1.0   → 87.0% (16.4% 覆盖)  [Grade A]
#    > 2.0   → 92.7% (5.2%  覆盖)  [Grade S]
# =====================================================================

# --- P4 · 让方不输 · S 级 ---

@rule('P4-H01', 'H', 'S', 'p4',
      '四公司陪方赔率漂移<-1.5(资金大幅逃离陪方) → 测试92.5%(n=624, 覆盖6.8%)')
def _(m):
    v = m.get('p4_avg_und_move')
    return v is not None and v < -1.5

@rule('P4-H02', 'H', 'S', 'p4',
      '四公司陪方漂移<-1.5 且 让方初盘均值<1.80(中等偏强热门) → 测试93.3%(n=462, 覆盖5.0%)')
def _(m):
    v = m.get('p4_avg_und_move')
    f = m.get('p4_avg_fav_ini')
    return v is not None and f is not None and v < -1.5 and f < 1.80

@rule('P4-H03', 'H', 'S', 'p4',
      '四公司让/陪方移动量差值>2.0(让方相对大幅更受支持) → 测试92.7%(n=478, 覆盖5.2%)')
def _(m):
    v = m.get('p4_move_diff')
    return v is not None and v > 2.0

@rule('P4-H04', 'H', 'S', 'p4',
      '四公司陪方漂移<-0.5 且 移动总幅度>2.0(大幅重定价) → 测试92.8%(n=387, 覆盖4.2%)')
def _(m):
    u = m.get('p4_avg_und_move')
    mag = m.get('p4_und_move_magnitude')
    return u is not None and mag is not None and u < -0.5 and mag > 2.0

# --- P4 · 让方不输 · A 级 ---

@rule('P4-H05', 'H', 'A', 'p4',
      '四公司陪方赔率漂移<-1.0(资金明显逃离陪方) → 测试89.0%(n=1163, 覆盖12.6%)')
def _(m):
    v = m.get('p4_avg_und_move')
    return v is not None and v < -1.0

@rule('P4-H06', 'H', 'A', 'p4',
      '四公司让/陪方移动量差值>1.5(让方明显更受支持) → 测试90.4%(n=819, 覆盖8.9%)')
def _(m):
    v = m.get('p4_move_diff')
    return v is not None and v > 1.5

@rule('P4-H07', 'H', 'A', 'p4',
      '四公司陪方漂移<-0.5 且 让方初盘<1.80 → 测试88.6%(n=1207, 覆盖13.1%)')
def _(m):
    u = m.get('p4_avg_und_move')
    f = m.get('p4_avg_fav_ini')
    return u is not None and f is not None and u < -0.5 and f < 1.80

# --- P4 · 让方不输 · B 级 ---

@rule('P4-H08', 'H', 'B', 'p4',
      '四公司陪方赔率漂移<-0.5(资金轻度逃离陪方) → 测试85.1%(n=2453, 覆盖26.5%)')
def _(m):
    v = m.get('p4_avg_und_move')
    return v is not None and v < -0.5

@rule('P4-H09', 'H', 'B', 'p4',
      '四公司让/陪方移动量差值>1.0 → 测试87.0%(n=1514, 覆盖16.4%)')
def _(m):
    v = m.get('p4_move_diff')
    return v is not None and v > 1.0


# =====================================================================
#  剪刀差信号 (Scissor Signal) v1.0 — 2026-03-22
#  数据: 6903 场历史验证 (odds_changes 全量)
#  核心逻辑: 情绪派(bet365+威廉+立博)降赔 + 精算派(平博)升赔
#            = 该方向被诱导，大概率打不出
#  验证: 时间序列 70/30 切分，训练/验证偏差 < 8%
#
#  side='XH' 排除主胜, 'XA' 排除客胜, 'XD' 排除平局
#  requires='sc' — 需要 bet365+威廉+立博+平博 四家数据
# =====================================================================

_SCISSOR_GROUP: frozenset = frozenset({
    'SC-H01', 'SC-H02', 'SC-H03',  # 排除主胜
    'SC-A01', 'SC-A02', 'SC-A03',  # 排除客胜
    'SC-D01', 'SC-D02', 'SC-D03',  # 排除平局
})


def _sc_check(m, side, avg_threshold, pb_threshold):
    """
    剪刀差检测:
    - 三庄(bet365+威廉+立博)在指定方向的平均降幅 >= avg_threshold
    - 每家至少降 0.03（确认方向一致）
    - 平博在指定方向的升幅 >= pb_threshold
    """
    s = {'h': 'ih', 'd': 'id', 'a': 'ia'}[side]
    e = {'h': 'ch', 'd': 'cd', 'a': 'ca'}[side]
    drops = []
    for pfx in ['b3', 'w', 'l']:
        ini = m.get(f'{pfx}_raw_{s}')
        cur = m.get(f'{pfx}_raw_{e}')
        if ini is None or cur is None:
            return False
        drop = ini - cur
        if drop < 0.03:
            return False
        drops.append(drop)
    avg_drop = sum(drops) / len(drops)
    if avg_drop < avg_threshold:
        return False
    pb_ini = m.get(f'pb_raw_{s}')
    pb_cur = m.get(f'pb_raw_{e}')
    if pb_ini is None or pb_cur is None:
        return False
    return pb_cur - pb_ini >= pb_threshold


# --- 排除主胜 ---

@rule('SC-H01', 'XH', 'S', 'sc',
      '主胜剪刀差(重仓) — 三庄主胜均降≥0.20+平博升≥0.15 → 不打出88.5%(n=52)')
def _(m):
    return _sc_check(m, 'h', avg_threshold=0.20, pb_threshold=0.15)

@rule('SC-H02', 'XH', 'A', 'sc',
      '主胜剪刀差(强烈) — 三庄主胜均降≥0.15+平博升≥0.10 → 不打出86.6%(n=67)')
def _(m):
    return _sc_check(m, 'h', avg_threshold=0.15, pb_threshold=0.10)

@rule('SC-H03', 'XH', 'B', 'sc',
      '主胜剪刀差(标准) — 三庄主胜均降≥0.08+平博升≥0.05 → 不打出73.6%(n=110)')
def _(m):
    return _sc_check(m, 'h', avg_threshold=0.08, pb_threshold=0.05)

# --- 排除客胜 ---

@rule('SC-A01', 'XA', 'S', 'sc',
      '客胜剪刀差(重仓) — 三庄客胜均降≥0.20+平博升≥0.15 → 不打出80.8%(n=125)')
def _(m):
    return _sc_check(m, 'a', avg_threshold=0.20, pb_threshold=0.15)

@rule('SC-A02', 'XA', 'A', 'sc',
      '客胜剪刀差(强烈) — 三庄客胜均降≥0.15+平博升≥0.10 → 不打出79.5%(n=151)')
def _(m):
    return _sc_check(m, 'a', avg_threshold=0.15, pb_threshold=0.10)

@rule('SC-A03', 'XA', 'B', 'sc',
      '客胜剪刀差(标准) — 三庄客胜均降≥0.08+平博升≥0.05 → 不打出81.5%(n=216)')
def _(m):
    return _sc_check(m, 'a', avg_threshold=0.08, pb_threshold=0.05)

# --- 排除平局 ---

@rule('SC-D01', 'XD', 'S', 'sc',
      '平局剪刀差(重仓) — 三庄平赔均降≥0.15+平博升≥0.10 → 不打出83.3%(n=30)')
def _(m):
    return _sc_check(m, 'd', avg_threshold=0.15, pb_threshold=0.10)

@rule('SC-D02', 'XD', 'A', 'sc',
      '平局剪刀差(强烈) — 三庄平赔均降≥0.08+平博升≥0.05 → 不打出80.7%(n=88)')
def _(m):
    return _sc_check(m, 'd', avg_threshold=0.08, pb_threshold=0.05)

@rule('SC-D03', 'XD', 'B', 'sc',
      '平局剪刀差(标准) — 三庄平赔均降≥0.05+平博升≥0.03 → 不打出78.3%(n=152)')
def _(m):
    return _sc_check(m, 'd', avg_threshold=0.05, pb_threshold=0.03)


def evaluate_match(match_id: Any, db: Any) -> Dict[str, Any]:
    """
    评估一场比赛。

    返回字典:
      signal     : '重仓'|'强烈'|'标准'|'无信号'|'无数据'
      side       : 'H'|'R'|None
      side_cn    : '让方不输'|'受让方不输'|None
      conflict   : bool   两方向同时触发(让方不输+受让方不输)
      triggered  : list   获胜方向的触发规则列表
      mode       : 'wml'|'wm'|'wl'|None
      features   : dict   特征数据
    """
    feat, mode = load_match_features(match_id, db)
    if feat is None:
        return {
            'match_id': match_id, 'signal': '无数据', 'side': None,
            'side_cn': None, 'triggered': [], 'features': None, 'mode': None,
            'conflict': False, 'score': 0,
            'triggered_h': [], 'triggered_r': [],
            'h_score': 0, 'r_score': 0, 'cross_confirm': False,
            'summary': f'比赛 {match_id} 无足够数据(需威廉+澳门或威廉+立博在竞争区间)',
        }

    mode_cn = {'wml': '三公司', 'wm': '威廉+澳门', 'wl': '威廉+立博'}[mode]

    triggered_h: List[Dict] = []
    triggered_r: List[Dict] = []
    triggered_sc: List[Dict] = []  # 剪刀差信号(排除型)

    for r in RULES:
        if not _rule_compatible(r['requires'], mode, feat):
            continue
        try:
            if r['fn'](feat):
                hit = {'id': r['id'], 'grade': r['grade'], 'desc': r['desc'], 'side': r['side']}
                if r['side'] == 'H':
                    triggered_h.append(hit)
                elif r['side'] in ('XH', 'XA', 'XD'):
                    triggered_sc.append(hit)
                else:
                    triggered_r.append(hit)
        except Exception:
            pass

    def score(lst: List[Dict]) -> int:
        return sum({'S': 3, 'A': 2, 'B': 1}.get(r['grade'], 0) for r in lst)

    def has_cross(lst: List[Dict]) -> bool:
        ids = [r['id'] for r in lst]
        prefixes = set(i.split('-')[0] for i in ids)
        return len(prefixes) >= 2

    h_score = score(triggered_h)
    r_score = score(triggered_r)

    if h_score == 0 and r_score == 0 and not triggered_sc:
        return {
            'match_id': match_id, 'signal': '无信号', 'side': None,
            'side_cn': None, 'triggered': [], 'features': feat, 'mode': mode,
            'conflict': False, 'score': 0,
            'triggered_h': triggered_h, 'triggered_r': triggered_r,
            'triggered_sc': [],
            'h_score': h_score, 'r_score': r_score, 'cross_confirm': False,
            'summary': f'比赛 {match_id} [{mode_cn}] 不满足任何规则',
        }
    
    # 如果只有剪刀差信号没有H/R信号，设置基本的信号框架
    if h_score == 0 and r_score == 0 and triggered_sc:
        sc_sides = set(r['side'] for r in triggered_sc)
        sc_labels = {'XH': '排除主胜', 'XA': '排除客胜', 'XD': '排除平局'}
        sc_parts = []
        for s in sorted(sc_sides):
            sc_rules = [r for r in triggered_sc if r['side'] == s]
            best = max(sc_rules, key=lambda x: {'S': 3, 'A': 2, 'B': 1}.get(x['grade'], 0))
            sc_parts.append(f"{sc_labels[s]}({best['grade']}级)")
        
        sc_summary = f"【剪刀差预警】{', '.join(sc_parts)} [{mode_cn}]"
        return {
            'match_id': match_id, 'signal': '剪刀差', 'side': None,
            'side_cn': None, 'triggered': [], 'features': feat, 'mode': mode,
            'conflict': False, 'score': 0,
            'triggered_h': triggered_h, 'triggered_r': triggered_r,
            'triggered_sc': triggered_sc,
            'h_score': h_score, 'r_score': r_score, 'cross_confirm': False,
            'summary': sc_summary,
        }

    # ---- 冲突检测 ----
    conflict = h_score > 0 and r_score > 0

    if h_score >= r_score:
        side, side_cn, fired, sc = 'H', '让方不输', triggered_h, h_score
    else:
        side, side_cn, fired, sc = 'R', '受让方不输', triggered_r, r_score

    # 使用同根因子去重后的有效计数(用于信号等级判断)
    # 原始计数仍保留在 triggered 列表中，确保展示透明
    n_s, n_a = _effective_grade_count(fired)
    cross = has_cross(fired)

    # ---- 信号等级 (v3.2 修订: S规则甜蜜区间驱动 + 同根因子去重) ----
    # 30天验证 (882场):
    #   n_s 2~4 条: 80场 91.2%  ← 甜蜜区，最可靠
    #   n_s >= 5:   40场 82.5%  ← 极端赔率，反而有陷阱
    #   n_s == 1:  122场 78.7%
    #
    # 策略: 2-4条S级=重仓, 5+条或1S+A=强烈, 其余=参考
    if 2 <= n_s <= 4:
        signal = '重仓'      # 甜蜜区 → 验证 91.2%
    elif n_s >= 5:
        signal = '强烈'      # 规则过多, 可能极端盘 → 验证 82.5%
    elif n_s >= 1 and n_a >= 1:
        signal = '强烈'      # 1S+1A 混合 → 有参考价值
    else:
        signal = '参考'      # 单条规则 → 仅供参考

    # 冲突时降级
    if conflict:
        if signal == '重仓':
            signal = '强烈'
        elif signal == '强烈':
            signal = '参考'

    # ---- P4 辅助信号处理 ----
    # 判断哪些规则来自 P4，哪些来自 W/M/L 体系
    p4_fired  = [r for r in fired if r['id'] in _P4_RULE_IDS]
    wml_fired = [r for r in fired if r['id'] not in _P4_RULE_IDS]
    p4_only   = len(p4_fired) > 0 and len(wml_fired) == 0

    if p4_only:
        # 纯P4触发：上限为"参考"（辅助信号，不单独决策）
        signal = '参考'
    elif len(p4_fired) > 0 and len(wml_fired) > 0:
        # 跨体系共振：P4 与 W/M/L 同时触发，升一级
        _upgrade_map = {'参考': '强烈', '强烈': '重仓', '重仓': '重仓'}
        signal = _upgrade_map.get(signal, signal)

    # ---- 汇总 ----
    h_is = '主队' if feat['home_is_h'] else '客队'
    ids_str = ','.join(r['id'] for r in fired)
    conflict_tag = ' ⚡冲突' if conflict else ''
    cross_tag = ' ★共振' if cross else ''
    p4_tag = ' 🔵P4辅助' if p4_only else (' 🔵P4共振' if len(p4_fired) > 0 else '')

    summary = (f"【{signal}】{side_cn} [{mode_cn}] | "
               f"让方={h_is} | "
               f"触发{len(fired)}条({n_s}S+{n_a}A){cross_tag}{conflict_tag}{p4_tag} | "
               f"{ids_str}")

    # ---- 剪刀差信号处理 (独立于H/R体系) ----
    sc_summary_parts = []
    if triggered_sc:
        _sc_sides = set(r['side'] for r in triggered_sc)
        _sc_labels = {'XH': '排除主胜', 'XA': '排除客胜', 'XD': '排除平局'}
        for _s in sorted(_sc_sides):
            _sc_rules = [r for r in triggered_sc if r['side'] == _s]
            _best = max(_sc_rules, key=lambda x: {'S': 3, 'A': 2, 'B': 1}.get(x['grade'], 0))
            sc_summary_parts.append(f"{_sc_labels[_s]}({_best['grade']}级)")
        summary += f" | 剪刀差: {', '.join(sc_summary_parts)}"

    return {
        'match_id': match_id, 'signal': signal, 'side': side,
        'side_cn': side_cn, 'score': sc,
        'triggered': fired, 'triggered_h': triggered_h, 'triggered_r': triggered_r,
        'triggered_sc': triggered_sc,  # 剪刀差触发列表
        'h_score': h_score, 'r_score': r_score,
        'cross_confirm': cross, 'features': feat, 'mode': mode,
        'conflict': conflict,
        'p4_only': p4_only,
        'p4_fired': p4_fired,
        'wml_fired': wml_fired,
        'summary': summary,
    }


# ===================== 信号图标 =====================
SIGNAL_ICON = {'重仓': '🔴', '强烈': '🟠', '参考': '🟡', '标准': '🟡', '无信号': '⚪', '无数据': '⬜'}


# ===================== 向后兼容 (旧API可能用到) =====================

def get_range_type(range_str: str, range_prefixes: Sequence[str]) -> Optional[str]:
    """旧版区间分类(保留向后兼容)"""
    if not range_str:
        return None
    for p in range_prefixes:
        if range_str.startswith(p):
            return p
    return '其他'


def classify_odds_change(init: float, curr: float) -> str:
    """简单分类：升/降/稳 (保留向后兼容)"""
    if init == 0:
        return '未知'
    if curr > init * 1.05:
        return '升'
    elif curr < init * 0.95:
        return '降'
    return '稳'


def classify_odds_change_detailed(init: float, curr: float) -> str:
    """细化分类 (保留向后兼容)"""
    if init <= 0:
        return '未知'
    change_pct = (curr - init) / init
    if change_pct > 0.15:
        return '暴升(>15%)'
    elif change_pct > 0.10:
        return '大升(10-15%)'
    elif change_pct > 0.05:
        return '小升(5-10%)'
    elif change_pct > 0.02:
        return '微升(2-5%)'
    elif change_pct >= -0.02:
        return '稳定(±2%)'
    elif change_pct >= -0.05:
        return '微降(2-5%)'
    elif change_pct >= -0.10:
        return '小降(5-10%)'
    elif change_pct >= -0.15:
        return '大降(10-15%)'
    else:
        return '暴降(>15%)'


def classify_power(diff: Any) -> str:
    """分类力量差 (保留向后兼容)"""
    if diff is None:
        return '未知'
    diff = float(diff)
    if diff >= 2.5:
        return '强让'
    elif diff >= 1.5:
        return '微让'
    elif diff >= -1.5:
        return '平手'
    elif diff >= -2.5:
        return '微受'
    return '强受'


def process_match(*args, **kwargs) -> Optional[Dict]:
    """旧版 process_match 不再使用，保留签名避免导入错误"""
    raise NotImplementedError(
        "process_match 已被新版 evaluate_match 替代。"
        "请使用 evaluate_match(match_id, db) 代替。"
    )


def check_rules(*args, **kwargs) -> List[Dict]:
    """旧版 check_rules 不再使用，保留签名避免导入错误"""
    raise NotImplementedError(
        "check_rules 已被新版 evaluate_match 替代。"
        "请使用 evaluate_match(match_id, db) 代替。"
    )


__all__ = [
    "RULES",
    "SIGNAL_ICON",
    "classify_odds_change",
    "classify_odds_change_detailed",
    "classify_power",
    "evaluate_match",
    "get_range_type",
    "load_match_features",
]
