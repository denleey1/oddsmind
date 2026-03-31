#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
===========================================================================
  竞争区间规则引擎 v2.0 — 生产环境即用（全覆盖版）
===========================================================================
支持三种公司组合，自动适配:
  ① 威廉+澳门+立博 (最强，D+T规则全开)
  ② 威廉+立博 无澳门 (WL规则，覆盖无澳门的比赛)
  ③ 威廉+澳门 无立博 (D规则，极少数情况)

用法:
  1. 直接调用: MYSQL_PASSWORD='xxx' python3 rule_engine.py
  2. 指定比赛: MYSQL_PASSWORD='xxx' python3 rule_engine.py 2702235
  3. 作为模块: from rule_engine import evaluate_match, scan_upcoming

信号等级:
  🔴 重仓  — 多方案共振，最高可靠性 (回测97.9%)
  🟠 强烈  — 多条高精度规则触发     (回测100%)
  🟡 标准  — 有可靠规则触发          (回测88.3%)
  ⚪ 无信号 — 不满足任何规则，不操作

依赖: pymysql (pip install pymysql)
===========================================================================
"""

import os, sys, math
from decimal import Decimal
from datetime import datetime, timedelta

import pymysql
from pymysql.cursors import DictCursor


# ===================== 数据库 =====================
def _db():
    return pymysql.connect(
        host=os.environ.get('MYSQL_HOST', 'localhost'),
        port=int(os.environ.get('MYSQL_PORT', '3306')),
        user=os.environ.get('MYSQL_USER', 'root'),
        password=os.environ.get('MYSQL_PASSWORD', ''),
        database=os.environ.get('MYSQL_DATABASE', 'oddsmind'),
        charset='utf8mb4', cursorclass=DictCursor,
    )


def _q(sql, params=None, fetch='all'):
    conn = _db()
    try:
        with conn.cursor() as c:
            c.execute(sql, params or ())
            return c.fetchall() if fetch == 'all' else c.fetchone()
    finally:
        conn.close()


# ===================== 规则注册 =====================
RULES = []

def rule(rid, side, grade, requires, desc):
    """
    装饰器注册规则
    requires: 'wm'=需要威廉+澳门, 'wml'=需要三公司, 'wl'=威廉+立博(无需澳门)
    """
    def wrap(fn):
        RULES.append({'id': rid, 'side': side, 'grade': grade,
                      'requires': requires, 'fn': fn, 'desc': desc})
        return fn
    return wrap


# =====================================================================
#  D- 规则: 威廉+澳门 (requires='wm')
# =====================================================================

# --- 让方不输 · 威廉+澳门 · S级 ---

@rule('D-H01', 'H', 'S', 'wm',
      '威廉赔率差>0.71 + 威澳偏移变化差>-0.35 + 威廉返还率≤93.1 + 威澳初盘受让方差>0.575 → OOS 98.0%(n=50)')
def _(m):
    return (m['w_spread'] > 0.710
            and (m['w_h_off_chg'] - m['m_h_off_chg']) > -0.350
            and m['w_irr'] <= 93.095
            and (m['w_ir'] - m['m_ir']) > 0.575)

@rule('D-H02', 'H', 'S', 'wm',
      '威廉赔率差>0.71 + 威廉返还率≤92.2 + 澳门平赔降≤-1.7% + 威澳返还率差>1.85 → OOS 100%(n=36)')
def _(m):
    return (m['w_spread'] > 0.710 and m['w_crr'] <= 92.175
            and m['m_dc'] <= -0.017 and (m['w_crr'] - m['m_crr']) > 1.850)

@rule('D-H03', 'H', 'S', 'wm',
      '澳门让方>2.04 + 威廉赔率差>1.60 → OOS 100%(n=12)')
def _(m):
    return m['m_h'] > 2.040 and m['w_spread'] > 1.600

# --- 让方不输 · 威廉+澳门 · A级 ---

@rule('D-H04', 'H', 'A', 'wm',
      '威廉赔率差>0.71 + 威廉返还率≤92.2 + 澳门平赔变化>-1.7% + 澳门受让方理论距离>1.95 → OOS 95.7%(n=23)')
def _(m):
    return (m['w_spread'] > 0.710 and m['w_crr'] <= 92.175
            and m['m_dc'] > -0.017 and m['m_rt'] is not None and m['m_rt'] > 1.950)

@rule('D-H05', 'H', 'A', 'wm',
      '威廉让方≤2.25 + 澳门让方>2.25 → OOS 90.0%(n=10)')
def _(m):
    return m['w_h'] <= 2.250 and m['m_h'] > 2.250

@rule('D-H06', 'H', 'A', 'wm',
      '威澳赔率差差>0.45 + 澳门赔率差≤0.66 → OOS 90.9%(n=22)')
def _(m):
    return (m['w_spread'] - m['m_spread']) > 0.450 and m['m_spread'] <= 0.660

@rule('D-H07', 'H', 'A', 'wm',
      '威澳初盘平赔比差≤-0.068 + 澳门赔率差>1.558 → OOS 95.7%(n=23)')
def _(m):
    return ((m['w_dri'] - m['m_dri']) <= -0.068 if m['w_dri'] and m['m_dri'] else False) and m['m_spread'] > 1.558

@rule('D-H08', 'H', 'A', 'wm',
      '威廉让方≤2.05 + 澳门赔率差≤0.83 → OOS 100%(n=12)')
def _(m):
    return m['w_h'] <= 2.050 and m['m_spread'] <= 0.830

@rule('D-H09', 'H', 'A', 'wm',
      '威廉初盘平赔比≤0.931 + 澳门让方≤1.90 → 时间验证 100%(n=20)')
def _(m):
    return (m['w_dri'] is not None and m['w_dri'] <= 0.931) and m['m_h'] <= 1.900

# --- 受让方不输 · 威廉+澳门 · S级 ---

@rule('D-R01', 'R', 'S', 'wm',
      '澳门赔率差≤0.27 + 威澳让方变化差≤-4.9% → OOS 94.7%(n=19)')
def _(m):
    return m['m_spread'] <= 0.270 and (m['w_hc']-m['m_hc']) <= -0.049

@rule('D-R02', 'R', 'S', 'wm',
      '威澳让方变化差≤-4.9% + 澳门受让方≤2.60 → OOS 94.7%(n=19)')
def _(m):
    return (m['w_hc']-m['m_hc']) <= -0.049 and m['m_r'] <= 2.600

@rule('D-R03', 'R', 'S', 'wm',
      '威廉赔率差≤0.30 + 威澳让方变化差≤-4.9% → OOS 92.3%(n=13)')
def _(m):
    return m['w_spread'] <= 0.300 and (m['w_hc']-m['m_hc']) <= -0.049

@rule('D-R04', 'R', 'S', 'wm',
      '威廉初盘让方偏移>0.80 + 澳门初盘受让方偏移≤-0.40 → OOS 100%(n=8)')
def _(m):
    return (m['w_iho'] is not None and m['w_iho'] > 0.800
            and m['m_iro'] is not None and m['m_iro'] <= -0.400)

# --- 受让方不输 · 威廉+澳门 · A级 ---

@rule('D-R05', 'R', 'A', 'wm',
      '威澳让方变化差≤-4.9% + 威廉受让方≤2.75 → OOS 92.3%(n=13)')
def _(m):
    return (m['w_hc']-m['m_hc']) <= -0.049 and m['w_r'] <= 2.750

@rule('D-R06', 'R', 'A', 'wm',
      '威澳让方变化差≤-1.6% + 澳门受让方≤2.60 → OOS 87.9%(n=33)')
def _(m):
    return (m['w_hc']-m['m_hc']) <= -0.016 and m['m_r'] <= 2.600

@rule('D-R07', 'R', 'A', 'wm',
      '澳门赔率差≤0.40 + 澳门平赔变化>-6% + 平Kelly>0.885 + 威澳偏移均值≤-1.33 → OOS 84.0%(n=25)')
def _(m):
    return (m['m_spread'] <= 0.395 and m['m_dc'] > -0.060
            and m['m_kd'] is not None and m['m_kd'] > 0.885
            and m['w_ho'] is not None and m['m_ho'] is not None
            and (m['w_ho']+m['m_ho'])/2 <= -1.325)

@rule('D-R08', 'R', 'A', 'wm',
      '威澳让方变化差≤-4.9% + 威廉受让方≤2.90 → OOS 84.6%(n=26)')
def _(m):
    return (m['w_hc']-m['m_hc']) <= -0.049 and m['w_r'] <= 2.900

@rule('D-R09', 'R', 'A', 'wm',
      '澳门初盘受让方偏移≤-0.10 + 威廉初盘让方偏移>1.10 → OOS 85.7%(n=14)')
def _(m):
    return (m['m_iro'] is not None and m['m_iro'] <= -0.100
            and m['w_iho'] is not None and m['w_iho'] > 1.100)


# =====================================================================
#  T- 规则: 三公司 威廉+澳门+立博 (requires='wml')
# =====================================================================

# --- 让方不输 · 三公司 · S级 ---

@rule('T-H01', 'H', 'S', 'wml',
      '威廉赔率差≤1.90 + 三公司受让方均值>3.66 → OOS 100%(n=19)')
def _(m):
    return (m['w_spread'] <= 1.900
            and (m['w_r']+m['m_r']+m['l_r'])/3 > 3.661)

@rule('T-H02', 'H', 'S', 'wml',
      '威廉让方≤2.10 + 澳门让方>2.11 → OOS 100%(n=19)')
def _(m):
    return m['w_h'] <= 2.100 and m['m_h'] > 2.110

@rule('T-H03', 'H', 'S', 'wml',
      '三公司赔率差均值>1.45 + 威廉让方>2.00 → OOS 91.7%(n=24) 零落差')
def _(m):
    return ((m['w_spread']+m['m_spread']+m['l_spread'])/3 > 1.450
            and m['w_h'] > 2.000)

@rule('T-H04', 'H', 'S', 'wml',
      '立博受让方>3.75 + 威廉让方>2.00 → OOS 93.3%(n=15)')
def _(m):
    return m['l_r'] > 3.750 and m['w_h'] > 2.000

# --- 让方不输 · 三公司 · A级 ---

@rule('T-H05', 'H', 'A', 'wml',
      '威廉让方≤1.91 + 立博初盘受让方≤3.00 → OOS 100%(n=11)')
def _(m):
    return m['w_h'] <= 1.910 and m['l_ir'] <= 3.000

@rule('T-H06', 'H', 'A', 'wml',
      '威廉赔率差>1.90 + 立博初盘受让方≤3.10 → OOS 100%(n=10)')
def _(m):
    return m['w_spread'] > 1.900 and m['l_ir'] <= 3.100

@rule('T-H07', 'H', 'A', 'wml',
      '威澳偏移差>0.40 + 威澳偏移均值≤-1.00 → OOS 100%(n=10)')
def _(m):
    return (m['w_ho'] is not None and m['m_ho'] is not None
            and (m['w_ho']-m['m_ho']) > 0.400
            and (m['w_ho']+m['m_ho'])/2 <= -1.000)

@rule('T-H08', 'H', 'A', 'wml',
      '威廉赔率差>1.90 + 澳门初盘受让方≤3.08 → OOS 90.0%(n=10)')
def _(m):
    return m['w_spread'] > 1.900 and m['m_ir'] <= 3.080

@rule('T-H09', 'H', 'A', 'wml',
      '威廉让方>1.91 + 三公司受让方均值>3.66 → OOS 83.9%(n=31)')
def _(m):
    return (m['w_h'] > 1.910
            and (m['w_r']+m['m_r']+m['l_r'])/3 > 3.661)

# --- 受让方不输 · 三公司 · S级 ---

@rule('T-R01', 'R', 'S', 'wml',
      '威立返还率差>2.50 + 威廉受让方≤2.75 → OOS 92.9%(n=14)')
def _(m):
    return (m['l_crr'] is not None
            and (m['w_crr']-m['l_crr']) > 2.500 and m['w_r'] <= 2.750)

@rule('T-R02', 'R', 'S', 'wml',
      '三公司让方变化分歧≤0.013 + 澳门平赔上升 → OOS 92.3%(n=13)')
def _(m):
    import numpy as np
    std = np.std([m['w_hc'],m['m_hc'],m['l_hc']])
    return std <= 0.013 and m['m_dc'] > 0.000

@rule('T-R03', 'R', 'S', 'wml',
      '澳立受让方变化差≤-0.055 + 立博赔率差≤0.30 → OOS 91.7%(n=12)')
def _(m):
    return (m['m_rc']-m['l_rc']) <= -0.055 and m['l_spread'] <= 0.300

# --- 受让方不输 · 三公司 · A级 ---

@rule('T-R04', 'R', 'A', 'wml',
      '立博赔率差≤0.30 + 澳门受让方>2.70 → OOS 100%(n=7)')
def _(m):
    return m['l_spread'] <= 0.300 and m['m_r'] > 2.700

@rule('T-R05', 'R', 'A', 'wml',
      '澳立赔率差差≤-0.23 + 三公司赔率差均值≤0.317 → OOS 100%(n=7)')
def _(m):
    return ((m['m_spread']-m['l_spread']) <= -0.230
            and (m['w_spread']+m['m_spread']+m['l_spread'])/3 <= 0.317)

@rule('T-R06', 'R', 'A', 'wml',
      '威立返还率差>1.75 + 威廉受让方≤2.75 → OOS 89.5%(n=19)')
def _(m):
    return (m['l_crr'] is not None
            and (m['w_crr']-m['l_crr']) > 1.751 and m['w_r'] <= 2.750)

@rule('T-R07', 'R', 'A', 'wml',
      '威廉让方>2.45 + 澳立让方变化差>0.05 → OOS 90.0%(n=10)')
def _(m):
    return m['w_h'] > 2.450 and (m['m_hc']-m['l_hc']) > 0.050

@rule('T-R08', 'R', 'A', 'wml',
      '立博让方变化≤-3% + 立博赔率差≤0.30 → OOS 88.9%(n=9)')
def _(m):
    return m['l_hc'] <= -0.030 and m['l_spread'] <= 0.300

@rule('T-R09', 'R', 'A', 'wml',
      '三公司赔率差均值≤0.317 + 威澳让方Kelly差≤0 → OOS 88.9%(n=9)')
def _(m):
    return ((m['w_spread']+m['m_spread']+m['l_spread'])/3 <= 0.317
            and m['w_kh'] is not None and m['m_kh'] is not None
            and (m['w_kh']-m['m_kh']) <= 0.000)


# =====================================================================
#  WL- 规则: 威廉+立博 无需澳门 (requires='wl')
#  数据: 279场(无澳门), SNR让方5.2x✓ 受让方2.5x⚠
# =====================================================================

# --- 让方不输 · 威廉+立博 · A级 (SNR=5.2x) ---

@rule('WL-H01', 'H', 'A', 'wl',
      '威廉初盘让方>2.30 + 威廉平Kelly>0.88 → OOS 100%(n=12)')
def _(m):
    return m['w_ih'] > 2.300 and m['w_kd'] is not None and m['w_kd'] > 0.880

@rule('WL-H02', 'H', 'A', 'wl',
      '威立受让方变化和≤0 + 威廉平Kelly>0.89 → OOS 100%(n=10)')
def _(m):
    return ((m['w_rc']+m['l_rc']) <= 0.000
            and m['w_kd'] is not None and m['w_kd'] > 0.890)

@rule('WL-H03', 'H', 'A', 'wl',
      '威廉初盘让方>2.40 + 威廉平Kelly>0.88 → OOS 100%(n=8)')
def _(m):
    return m['w_ih'] > 2.400 and m['w_kd'] is not None and m['w_kd'] > 0.880

@rule('WL-H04', 'H', 'A', 'wl',
      '威廉初盘返还率>91.68 + 威廉初盘让方>2.30 → OOS 100%(n=7)')
def _(m):
    return m['w_irr'] is not None and m['w_irr'] > 91.680 and m['w_ih'] > 2.300

@rule('WL-H05', 'H', 'A', 'wl',
      '威廉即时返还率>91.68 + 威廉初盘让方>2.00 → OOS 100%(n=7)')
def _(m):
    return m['w_crr'] is not None and m['w_crr'] > 91.680 and m['w_ih'] > 2.000

@rule('WL-H06', 'H', 'B', 'wl',
      '威立让方Kelly均值≤0.885 → OOS 100%(n=6)')
def _(m):
    return (m['w_kh'] is not None and m['l_kh'] is not None
            and (m['w_kh']+m['l_kh'])/2 <= 0.885)

# --- 受让方不输 · 威廉+立博 · A级 (SNR=2.5x, 谨慎使用) ---

@rule('WL-R01', 'R', 'A', 'wl',
      '威廉平赔比>0.948 + 威廉初盘让方偏移>0.50 → OOS 100%(n=9)')
def _(m):
    return (m['w_dri'] is not None and m['w_dri'] > 0.948
            and m['w_iho'] is not None and m['w_iho'] > 0.500)

@rule('WL-R02', 'R', 'A', 'wl',
      '威廉即时返还率≤90.33 + 立博初盘返还率>89.45 → OOS 92.9%(n=14)')
def _(m):
    return (m['w_crr'] is not None and m['w_crr'] <= 90.328
            and m['l_irr'] is not None and m['l_irr'] > 89.450)

@rule('WL-R03', 'R', 'B', 'wl',
      '威廉偏移变化≤-0.88 + 威立受让方差≤0.10 → OOS 92.3%(n=13)')
def _(m):
    return (m['w_h_off_chg'] is not None and m['w_h_off_chg'] <= -0.880
            and (m['w_r']-m['l_r']) <= 0.100)

@rule('WL-R04', 'R', 'B', 'wl',
      '立博即时返还率≤89.25 + 威廉初盘让方偏移>0.50 → OOS 92.3%(n=13)')
def _(m):
    return (m['l_crr'] is not None and m['l_crr'] <= 89.250
            and m['w_iho'] is not None and m['w_iho'] > 0.500)


# ===================== 数据加载 =====================
def _f(v):
    if v is None: return None
    return float(v) if isinstance(v, (Decimal, int, float)) else float(v)


def load_match_features(match_id):
    """
    加载比赛特征，自动适配公司组合。
    返回 (feat_dict, mode) 或 (None, None)
    mode: 'wml'=三公司, 'wm'=威澳, 'wl'=威立
    """
    mt = _q('SELECT * FROM matches WHERE match_id=%s', (match_id,), 'one')
    if not mt: return None, None

    # 加载赔率
    odds = {}
    for cid, pfx in [(115,'w'),(80,'m'),(82,'l')]:
        row = _q('SELECT * FROM european_odds WHERE match_id=%s AND company_id=%s',
                 (match_id, cid), 'one')
        if row and _f(row['initial_home']) and _f(row['initial_home']) > 0:
            odds[pfx] = row

    # 加载OAR
    oar = {}
    for cid, pfx in [(115,'w'),(80,'m'),(82,'l')]:
        row = _q('SELECT * FROM odds_analysis_results WHERE match_id=%s AND company_id=%s',
                 (match_id, cid), 'one')
        if row:
            oar[pfx] = row

    # 确定模式: 至少需要威廉
    if 'w' not in odds or 'w' not in oar:
        return None, None

    has_m = 'm' in odds and 'm' in oar
    has_l = 'l' in odds and 'l' in oar

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

    def pick(pfx, hk, ak):
        o = odds[pfx]
        return (_f(o[hk]), _f(o[ak])) if home_is_h else (_f(o[ak]), _f(o[hk]))

    def pick_oar(pfx, hk, ak):
        o = oar[pfx]
        return (_f(o[hk]), _f(o[ak])) if home_is_h else (_f(o[ak]), _f(o[hk]))

    feat = {'match_id': match_id, 'home_is_h': home_is_h, 'mode': mode,
            'has_m': has_m, 'has_lb': has_l}
    feat['match_time'] = mt.get('match_time')
    feat['league_id'] = mt.get('league_id')
    feat['home_team_id'] = mt.get('home_team_id')
    feat['away_team_id'] = mt.get('away_team_id')
    feat['match_status'] = mt.get('match_status')

    available = ['w']
    if has_m: available.append('m')
    if has_l: available.append('l')

    for pfx in available:
        o = odds[pfx]; a = oar[pfx]
        ih, ir = pick(pfx, 'initial_home', 'initial_away')
        ch, cr = pick(pfx, 'current_home', 'current_away')
        id_ = _f(o['initial_draw']); cd = _f(o['current_draw'])

        hc = (ch-ih)/ih if ih and ih>0 else 0
        rc = (cr-ir)/ir if ir and ir>0 else 0
        dc = (cd-id_)/id_ if id_ and id_>0 else 0

        iho, iro = pick_oar(pfx, 'initial_home_offset', 'initial_away_offset')
        cho, cro = pick_oar(pfx, 'current_home_offset', 'current_away_offset')
        iht, irt = pick_oar(pfx, 'initial_home_theory_distance', 'initial_away_theory_distance')
        hoc = (cho-iho) if cho is not None and iho is not None else None
        roc = (cro-iro) if cro is not None and iro is not None else None

        kh, kr = pick(pfx, 'kelly_home', 'kelly_away')
        kh = _f(kh); kr = _f(kr); kd = _f(o['kelly_draw'])

        ids_v = _f(a['initial_draw_standard'])
        idf_v = _f(a['initial_draw_fullwater'])
        dri = idf_v/ids_v if idf_v and ids_v and ids_v>0 else None

        irr = _f(o['initial_return_rate']); crr = _f(o['current_return_rate'])

        feat[f'{pfx}_ih'] = ih; feat[f'{pfx}_ir'] = ir
        feat[f'{pfx}_h'] = ch; feat[f'{pfx}_r'] = cr
        feat[f'{pfx}_spread'] = cr - ch
        feat[f'{pfx}_hc'] = hc; feat[f'{pfx}_rc'] = rc; feat[f'{pfx}_dc'] = dc
        feat[f'{pfx}_iho'] = iho; feat[f'{pfx}_iro'] = iro
        feat[f'{pfx}_ho'] = cho; feat[f'{pfx}_ro'] = cro
        feat[f'{pfx}_h_off_chg'] = hoc; feat[f'{pfx}_r_off_chg'] = roc
        feat[f'{pfx}_ht'] = iht; feat[f'{pfx}_rt'] = irt
        feat[f'{pfx}_kh'] = kh; feat[f'{pfx}_kd'] = kd; feat[f'{pfx}_kr'] = kr
        feat[f'{pfx}_dri'] = dri
        feat[f'{pfx}_irr'] = irr; feat[f'{pfx}_crr'] = crr

    # 竞争区间检查: 威廉必须在竞争区间
    if feat['w_h'] is None or min(feat['w_h'], feat['w_r']) < 1.70:
        return None, None

    return feat, mode


# ===================== 规则评估 =====================
def _rule_compatible(rule_requires, mode):
    """规则是否兼容当前模式"""
    if rule_requires == 'wm':
        return mode in ('wm', 'wml')  # 有澳门就行
    elif rule_requires == 'wml':
        return mode == 'wml'           # 必须三公司齐全
    elif rule_requires == 'wl':
        return mode == 'wl'            # 仅在无澳门时使用(后备规则)
    return False


def evaluate_match(match_id):
    """
    评估一场比赛。

    返回字典:
      signal     : '重仓'|'强烈'|'标准'|'无信号'|'无数据'
      side       : 'H'|'R'|None
      side_cn    : '让方不输'|'受让方不输'|None
      conflict   : bool   两方向同时触发(让方不输+受让方不输)
    """
    feat, mode = load_match_features(match_id)
    if feat is None:
        return {'match_id': match_id, 'signal': '无数据', 'side': None,
                'side_cn': None, 'triggered': [], 'features': None, 'mode': None,
                'conflict': False,
                'summary': f'比赛 {match_id} 无足够数据(需威廉+澳门或威廉+立博在竞争区间)'}

    mode_cn = {'wml':'三公司','wm':'威廉+澳门','wl':'威廉+立博'}[mode]

    triggered_h = []
    triggered_r = []

    for r in RULES:
        if not _rule_compatible(r['requires'], mode):
            continue
        try:
            if r['fn'](feat):
                hit = {'id': r['id'], 'grade': r['grade'], 'desc': r['desc']}
                if r['side'] == 'H':
                    triggered_h.append(hit)
                else:
                    triggered_r.append(hit)
        except Exception:
            pass

    def score(lst):
        return sum({'S':3,'A':2,'B':1}.get(r['grade'],0) for r in lst)

    def has_cross(lst):
        ids = [r['id'] for r in lst]
        prefixes = set(i.split('-')[0] for i in ids)
        return len(prefixes) >= 2

    h_score = score(triggered_h)
    r_score = score(triggered_r)

    if h_score == 0 and r_score == 0:
        return {'match_id': match_id, 'signal': '无信号', 'side': None,
                'side_cn': None, 'triggered': [], 'features': feat, 'mode': mode,
                'conflict': False,
                'summary': f'比赛 {match_id} [{mode_cn}] 不满足任何规则'}

    # ---- 冲突检测 ----
    conflict = h_score > 0 and r_score > 0

    if h_score >= r_score:
        side, side_cn, fired, sc = 'H', '让方不输', triggered_h, h_score
    else:
        side, side_cn, fired, sc = 'R', '受让方不输', triggered_r, r_score

    n_s = sum(1 for r in fired if r['grade'] == 'S')
    n_a = sum(1 for r in fired if r['grade'] == 'A')
    cross = has_cross(fired)

    # ---- 信号等级 ----
    if cross and n_s >= 2:
        signal = '重仓'
    elif cross and (n_s >= 1 or sc >= 8):
        signal = '重仓'
    elif n_s >= 2 or (n_s >= 1 and n_a >= 2):
        signal = '强烈'
    elif n_s >= 1 or n_a >= 2:
        signal = '标准'
    else:
        signal = '标准'

    if mode == 'wl':
        if signal == '重仓': signal = '强烈'
        elif signal == '强烈': signal = '标准'

    # 冲突时降级
    if conflict:
        if signal == '重仓': signal = '强烈'
        elif signal == '强烈': signal = '标准'

    # ---- 汇总 ----
    h_is = '主队' if feat['home_is_h'] else '客队'
    ids_str = ','.join(r['id'] for r in fired)
    conflict_tag = ' ⚡冲突' if conflict else ''
    cross_tag = ' ★共振' if cross else ''

    summary = (f"【{signal}】{side_cn} [{mode_cn}] | "
               f"让方={h_is} | "
               f"触发{len(fired)}条({n_s}S+{n_a}A){cross_tag}{conflict_tag} | "
               f"{ids_str}")

    return {
        'match_id': match_id, 'signal': signal, 'side': side,
        'side_cn': side_cn, 'score': sc,
        'triggered': fired, 'triggered_h': triggered_h, 'triggered_r': triggered_r,
        'h_score': h_score, 'r_score': r_score,
        'cross_confirm': cross, 'features': feat, 'mode': mode,
        'conflict': conflict,
        'summary': summary,
    }


# ===================== 扫描 =====================
def scan_upcoming(hours=48):
    now = datetime.now()
    end = now + timedelta(hours=hours)
    rows = _q('''
        SELECT m.match_id, m.match_time, m.home_team_id, m.away_team_id,
               m.league_id, l.name_cn as league_name,
               th.name_cn as home_name, ta.name_cn as away_name
        FROM matches m
        LEFT JOIN leagues l ON m.league_id = l.league_id
        LEFT JOIN teams th ON m.home_team_id = th.team_id
        LEFT JOIN teams ta ON m.away_team_id = ta.team_id
        WHERE m.match_time BETWEEN %s AND %s
          AND m.match_status IN ('pending','not_started','upcoming')
        ORDER BY m.match_time ASC
    ''', (now.strftime('%Y-%m-%d %H:%M:%S'), end.strftime('%Y-%m-%d %H:%M:%S')))

    results = []
    for row in rows:
        r = evaluate_match(row['match_id'])
        if r['signal'] not in ('无信号', '无数据'):
            r['match_time'] = row['match_time']
            r['league'] = row.get('league_name') or ''
            r['home'] = row.get('home_name') or str(row['home_team_id'])
            r['away'] = row.get('away_name') or str(row['away_team_id'])
            results.append(r)

    results.sort(key=lambda x: ({'重仓':0,'强烈':1,'标准':2}.get(x['signal'],9), -x.get('score',0)))
    return results


# ===================== 输出 =====================
SIGNAL_ICON = {'重仓':'🔴','强烈':'🟠','标准':'🟡','无信号':'⚪','无数据':'⬜'}

def print_result(r):
    icon = SIGNAL_ICON.get(r['signal'], '⬜')
    print(f"\n{icon} {r['summary']}")

    # 触发规则
    if r.get('triggered'):
        for t in r['triggered']:
            g = {'S':'★★★','A':'★★','B':'★'}.get(t['grade'],'')
            print(f"   {g} [{t['id']}] {t['desc']}")

    # 冲突时也显示另一方向的规则
    if r.get('conflict'):
        other = r.get('triggered_r') if r['side'] == 'H' else r.get('triggered_h')
        other_name = '受让方不输' if r['side'] == 'H' else '让方不输'
        if other:
            print(f"   ⚡ 同时触发 {other_name}:")
            for t in other:
                g = {'S':'★★★','A':'★★','B':'★'}.get(t['grade'],'')
                print(f"      {g} [{t['id']}] {t['desc']}")


def print_scan(results):
    if not results:
        print("暂无信号"); return
    print(f"\n{'='*100}")
    print(f"  竞争区间规则引擎 v2.2 — 扫描结果 ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"{'='*100}")
    cur_signal = None
    for r in results:
        if r['signal'] != cur_signal:
            cur_signal = r['signal']
            print(f"\n  {SIGNAL_ICON.get(cur_signal,'')} ━━━ {cur_signal} ━━━")
        t = r.get('match_time')
        tstr = t.strftime('%m/%d %H:%M') if t else '?'
        n_s = sum(1 for x in r['triggered'] if x['grade']=='S')
        n_a = sum(1 for x in r['triggered'] if x['grade']=='A')
        cross = ' ★共振' if r.get('cross_confirm') else ''
        conflict = ' ⚡冲突' if r.get('conflict') else ''
        mode_short = {'wml':'三','wm':'威澳','wl':'威立'}.get(r.get('mode',''),'?')
        side_cn = r.get('side_cn','?')
        league = r.get('league','')[:8]
        home = r.get('home','')[:10]; away = r.get('away','')[:10]
        print(f"  {tstr} [{mode_short}] {league:<8} {home:>10} vs {away:<10} "
              f"→ {side_cn} ({n_s}S+{n_a}A){cross}{conflict}")

    print(f"\n{'='*100}")
    cnt = {}
    for r in results: cnt[r['signal']] = cnt.get(r['signal'],0)+1
    for s in ['重仓','强烈','标准']:
        if s in cnt: print(f"  {SIGNAL_ICON[s]} {s}: {cnt[s]} 场")
    print(f"  合计: {len(results)} 场有信号")
    print(f"{'='*100}")


# ===================== 入口 =====================
if __name__ == '__main__':
    if len(sys.argv) > 1:
        for mid in sys.argv[1:]:
            r = evaluate_match(mid.strip())
            print_result(r)
    else:
        print("扫描未来48小时比赛...")
        results = scan_upcoming(48)
        print_scan(results)
        if not results:
            print("\n(无未来比赛, 用最近已完成比赛演示)")
            recent = _q('''
                SELECT m.match_id FROM matches m
                JOIN odds_analysis_results oar ON m.match_id=oar.match_id AND oar.company_id=115
                JOIN european_odds ew ON m.match_id=ew.match_id AND ew.company_id=115
                WHERE m.match_status='finished'
                  AND ew.current_home!=ew.current_away
                  AND LEAST(ew.current_home,ew.current_away)>=1.70
                ORDER BY m.match_time DESC LIMIT 30
            ''')
            demo = []
            for row in recent:
                r = evaluate_match(row['match_id'])
                if r['signal'] not in ('无信号','无数据'): demo.append(r)
            demo.sort(key=lambda x: ({'重仓':0,'强烈':1,'标准':2}.get(x['signal'],9), -x.get('score',0)))
            for r in demo[:15]: print_result(r)
