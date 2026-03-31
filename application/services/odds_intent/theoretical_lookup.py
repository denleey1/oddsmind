#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
理论区间(骨架)查询 v2.0

使用 standard_odds_v2.json:
  1. 细分等级 → 粗等级映射（"人强1" → "人强"）
  2. 对战矩阵 matrix[主队等级][客队等级] → 区间标识（如"主5"或"客3"）
  3. 区间标识 → 让球盘口 + zone编号 + swap_odds
  4. zone编号 → 多行标准赔率 → 按实际返还率匹配89/92/94中最近的一套
  5. 如果 swap_odds=true（客让），主客赔率互换
  6. 从同zone多行中选最接近实际初盘的那行
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger

logger = get_logger(__name__)

_DATA: Optional[Dict[str, Any]] = None


def _load_data() -> Dict[str, Any]:
    global _DATA
    if _DATA is not None:
        return _DATA

    json_path = Path(__file__).resolve().parents[3] / "static" / "js" / "standard_odds_v2.json"
    _DATA = json.loads(json_path.read_text(encoding="utf-8"))
    logger.info("已加载标准赔率表 v2.0: %d 个区间", len(_DATA.get("odds", {})))
    return _DATA


def _to_coarse_tier(fine_tier: str) -> str:
    """细分等级 → 粗等级（"人强1" → "人强"）"""
    data = _load_data()
    mapping = data.get("tier_mapping", {})
    if fine_tier in mapping:
        return mapping[fine_tier]
    # 没有映射的直接用（可能已经是粗等级）
    if fine_tier in data.get("strength_levels", []):
        return fine_tier
    return fine_tier


def match_system_by_return_rate(return_rate: float) -> str:
    """按实际返还率匹配最近的体系: 89/92/94

    分界线：
      ≤ 90.5% → "89"
      90.5% ~ 93.0% → "92"
      ≥ 93.0% → "94"
    """
    if return_rate <= 90.5:
        return "89"
    elif return_rate <= 93.0:
        return "92"
    else:
        return "94"


def calc_return_rate(h: float, d: float, a: float) -> float:
    """计算实际返还率（百分比）"""
    if h <= 0 or d <= 0 or a <= 0:
        return 89.0  # 默认
    return 1.0 / (1.0/h + 1.0/d + 1.0/a) * 100


def choose_best_skeleton_range(
    home_strength: str,
    away_strength: str,
    odds_open: Dict[str, float],
    return_rate: Optional[float] = None,
    company_id: Optional[int] = None,
    company_name: Optional[str] = None,
) -> Dict[str, Any]:
    """
    v2.0 理论区间查询

    Args:
        home_strength: 主队广义实力等级（细分或粗）
        away_strength: 客队广义实力等级
        odds_open: 初盘 {"H": 1.85, "D": 3.40, "A": 4.20}
        return_rate: 实际返还率(%)，若为None则从odds_open计算
        company_id: 兼容旧接口，不再使用
        company_name: 兼容旧接口，不再使用

    Returns:
        标准赔率骨架 + 让球信息
    """
    data = _load_data()

    # 1. 粗等级
    home_tier = _to_coarse_tier(home_strength)
    away_tier = _to_coarse_tier(away_strength)

    # 2. 对战矩阵 → 区间标识
    matrix = data["matrix"]
    section = (matrix.get(home_tier) or {}).get(away_tier)
    if not section:
        raise ValueError(f"找不到 {home_tier} vs {away_tier} 的对战矩阵映射")

    # 3. 区间标识 → zone + 让球 + swap
    zones = data["zones"]
    zone_info = zones.get(section)
    if not zone_info:
        raise ValueError(f"区间标识 {section} 不在 zones 表中")

    zone_key = zone_info["zone"]        # "5" or "0~1"
    handicap = zone_info["handicap"]    # "一球"
    handicap_value = zone_info["value"] # -1.0
    swap = zone_info["swap_odds"]       # True/False

    # 4. 计算返还率 → 匹配体系
    h_open = odds_open.get("H", 0)
    d_open = odds_open.get("D", 0)
    a_open = odds_open.get("A", 0)

    if return_rate is None:
        return_rate = calc_return_rate(h_open, d_open, a_open)
    system = match_system_by_return_rate(return_rate)

    # 5. 取该zone的所有行，按匹配体系取赔率
    odds_rows = data["odds"].get(zone_key, [])
    if not odds_rows:
        raise ValueError(f"zone={zone_key} 无赔率数据")

    # 6. 从多行中选最接近实际初盘的
    best_row = None
    best_dist = float("inf")

    for row in odds_rows:
        triple = row.get(system)
        if not triple or len(triple) != 3:
            continue

        ref_h, ref_d, ref_a = triple
        if swap:
            ref_h, ref_a = ref_a, ref_h

        dist = 0
        if h_open > 0:
            dist += abs(h_open - ref_h) / max(ref_h, 0.01)
        if d_open > 0:
            dist += abs(d_open - ref_d) / max(ref_d, 0.01)
        if a_open > 0:
            dist += abs(a_open - ref_a) / max(ref_a, 0.01)

        if dist < best_dist:
            best_dist = dist
            best_row = (ref_h, ref_d, ref_a)

    if best_row is None:
        raise ValueError(f"zone={zone_key} 体系={system} 无可用赔率行")

    return {
        "type": "standard",
        "H": best_row[0],
        "D": best_row[1],
        "A": best_row[2],
        "handicap": handicap,
        "handicapValue": handicap_value,
        "system": system,
        "returnRate": round(return_rate, 1),
        "_meta": {
            "home_strength_raw": home_strength,
            "away_strength_raw": away_strength,
            "home_tier": home_tier,
            "away_tier": away_tier,
            "section": section,
            "zone": zone_key,
            "swap_odds": swap,
        },
    }


# 兼容旧接口
def company_id_to_system_name(company_id: int, company_name: Optional[str] = None) -> str:
    """已废弃，保留兼容。新代码请用 match_system_by_return_rate()"""
    return "89"


def lookup_candidates(home_strength: str, away_strength: str, system: str) -> list:
    """已废弃，保留兼容。新代码请用 choose_best_skeleton_range()"""
    return []
