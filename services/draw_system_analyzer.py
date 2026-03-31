#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
大小球平系对照分析服务

核心逻辑:
  1. 获取 Bet365 大小球盘口线 (over_under_odds_changes)
  2. 获取威廉欧赔 (odds_changes / european_odds)
  3. 将威廉赔率归一化到 94% 返还率体系
  4. 根据盘口线确定平系类别
  5. 用一赔方（胜负赔率较低方）查对照表获取标准平赔
  6. 比较归一化后的实际平赔与标准平赔的偏差
"""

from __future__ import annotations

import bisect
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from config.draw_system_config import (
    BET365_COMPANY_ID,
    DRAW_SYSTEM_MAPPING,
    DRAW_SYSTEM_TABLES,
    STANDARD_RETURN_RATE,
    WILLIAM_COMPANY_ID,
)

logger = get_logger(__name__)


LOW_WATER_MAX = 1.84
MID_WATER_MAX = 1.95
DEEP_LOW_WATER_MAX = 1.75


def _default_draw_system(market_line: float) -> str:
    for max_line, system_key in DRAW_SYSTEM_MAPPING:
        if market_line <= max_line:
            return system_key
    return "3.60"


def _resolve_line_bucket(market_line: float) -> float:
    if market_line <= 2.125:
        return 2.0
    if market_line <= 2.375:
        return 2.25
    if market_line <= 2.625:
        return 2.5
    if market_line <= 2.875:
        return 2.75
    return 3.0


def classify_ou_water(odds: Optional[float]) -> Optional[str]:
    if odds is None:
        return None
    if odds <= DEEP_LOW_WATER_MAX:
        return "deep_low"
    if odds <= LOW_WATER_MAX:
        return "low"
    if odds <= MID_WATER_MAX:
        return "mid"
    return "high"


def _water_band_label(band: Optional[str]) -> str:
    return {
        "deep_low": "超低水",
        "low": "低水",
        "mid": "中水",
        "high": "高水",
    }.get(band or "", "")


def build_ou_snapshot(
    market_line: float,
    over_odds: Optional[float],
    under_odds: Optional[float],
    phase: str,
    phase_label: str,
) -> Optional[Dict[str, Any]]:
    over_value = _safe_float(over_odds)
    under_value = _safe_float(under_odds)
    if over_value is None or under_value is None:
        return None

    gap = abs(over_value - under_value)
    line_bucket = _resolve_line_bucket(market_line)
    if gap <= 0.02:
        bias_side = "balanced"
        bias_label = "均水"
        favored_odds = min(over_value, under_value)
    elif over_value < under_value:
        bias_side = "over"
        bias_label = "大球"
        favored_odds = over_value
    else:
        bias_side = "under"
        bias_label = "小球"
        favored_odds = under_value

    water_band = classify_ou_water(favored_odds)
    water_label = _water_band_label(water_band)
    summary = bias_label if bias_side == "balanced" else f"{bias_label}{water_label}"

    return {
        "phase": phase,
        "phase_label": phase_label,
        "line": round(float(market_line), 2),
        "line_bucket": line_bucket,
        "line_label": f"{line_bucket:.2f}球",
        "over": round(over_value, 3),
        "under": round(under_value, 3),
        "bias_side": bias_side,
        "bias_label": bias_label,
        "water_band": water_band,
        "water_band_label": water_label,
        "favored_odds": round(favored_odds, 3),
        "odds_gap": round(gap, 3),
        "summary": summary,
        "display": f"{phase_label} {line_bucket:.2f}球 大{over_value:.2f} / 小{under_value:.2f}",
    }


def determine_draw_system_details(
    market_line: float,
    over_odds: Optional[float] = None,
    under_odds: Optional[float] = None,
    phase: str = "line",
    phase_label: str = "盘口线",
) -> Dict[str, Any]:
    snapshot = build_ou_snapshot(market_line, over_odds, under_odds, phase, phase_label)
    default_system = _default_draw_system(market_line)

    if not snapshot:
        return {
            "system_key": default_system,
            "mode": "line_only",
            "phase": phase,
            "phase_label": phase_label,
            "line_bucket": _resolve_line_bucket(market_line),
            "reason": f"{phase_label}大小球缺失，按盘口线 {market_line:.2f} 默认映射到 {default_system}体系",
            "snapshot": None,
        }

    line_bucket = snapshot["line_bucket"]
    bias_side = snapshot["bias_side"]
    water_band = snapshot["water_band"]
    system_key = default_system

    if line_bucket == 2.0:
        if bias_side == "over" and water_band == "deep_low":
            system_key = "3.10"
        elif bias_side == "over" and water_band == "low":
            system_key = "2.90"
        else:
            system_key = "3.00"
    elif line_bucket == 2.25:
        if bias_side == "under" and water_band in {"deep_low", "low"}:
            system_key = "3.10"
        elif bias_side == "over" and water_band in {"deep_low", "low"}:
            system_key = "3.25"
        else:
            system_key = "3.20"
    elif line_bucket == 2.5:
        if bias_side == "under" and water_band in {"deep_low", "low"}:
            system_key = "3.25"
        elif bias_side == "over" and water_band in {"deep_low", "low"}:
            system_key = "3.40"
        else:
            system_key = "3.30"
    elif line_bucket == 2.75:
        if bias_side == "over" and water_band in {"deep_low", "low"}:
            system_key = "3.50"
        else:
            system_key = "3.40"
    else:
        if bias_side == "under" and water_band in {"deep_low", "low"}:
            system_key = "3.50"
        else:
            system_key = "3.60"

    table_info = DRAW_SYSTEM_TABLES.get(system_key, {})
    return {
        "system_key": system_key,
        "mode": "ou_odds",
        "phase": snapshot["phase"],
        "phase_label": snapshot["phase_label"],
        "line_bucket": line_bucket,
        "reason": (
            f"{snapshot['phase_label']}{snapshot['line_label']} "
            f"{snapshot['summary']} -> {table_info.get('name', system_key)}"
        ),
        "snapshot": snapshot,
    }


# ---------------------------------------------------------------------------
#  返还率归一化
# ---------------------------------------------------------------------------

def normalize_to_94(home: float, draw: float, away: float) -> Tuple[float, float, float, float]:
    """
    将赔率归一化到 94% 返还率体系。

    威廉实际返还率通常在 91%~93% 之间，归一化后赔率会略微放大。

    Returns:
        (home_94, draw_94, away_94, actual_return_rate)
    """
    inv_sum = 1.0 / home + 1.0 / draw + 1.0 / away
    actual_rr = 1.0 / inv_sum
    factor = STANDARD_RETURN_RATE / actual_rr
    return (
        round(home * factor, 3),
        round(draw * factor, 3),
        round(away * factor, 3),
        round(actual_rr, 4),
    )


# ---------------------------------------------------------------------------
#  平系类别判定
# ---------------------------------------------------------------------------

def determine_draw_system(
    market_line: float,
    over_odds: Optional[float] = None,
    under_odds: Optional[float] = None,
) -> str:
    """
    根据大小球盘口线确定属于哪个平系（临时：默认各盘口的中水体系）。

    Args:
        market_line: Bet365 大小球盘口线 (如 2.0, 2.25, 2.5, 2.75, 3.0)

    Returns:
        平系 key: "2.90" / "3.00" / "3.10" / "3.20" / "3.25" /
                  "3.30" / "3.40" / "3.50" / "3.60"

    TODO: 接入大小球赔率后，结合大/小球方向和水位精确选列。
    """
    return determine_draw_system_details(market_line, over_odds, under_odds)["system_key"]


# ---------------------------------------------------------------------------
#  对照表查找
# ---------------------------------------------------------------------------

def lookup_standard_draw(
    system_key: str,
    favorite_odds: float,
) -> Optional[Dict[str, Any]]:
    """
    在平系对照表中查找标准平赔。

    用一赔方赔率（胜负赔率中较低的那个）作为查找键，
    找到最接近的行，返回标准平赔和区间信息。

    Args:
        system_key: 平系类型 ("low", "medium", etc.)
        favorite_odds: 归一化后的一赔方赔率 (如 1.70)

    Returns:
        dict with keys: standard_draw, standard_away, zone_name, matched_fav_odds
        or None if table not found
    """
    table = DRAW_SYSTEM_TABLES.get(system_key)
    if not table or not table.get("rows"):
        return None

    rows = table["rows"]

    fav_values = [r[0] for r in rows]
    idx = bisect.bisect_left(fav_values, favorite_odds)

    if idx == 0:
        best = rows[0]
    elif idx >= len(rows):
        best = rows[-1]
    else:
        left = rows[idx - 1]
        right = rows[idx]
        if abs(favorite_odds - left[0]) <= abs(favorite_odds - right[0]):
            best = left
        else:
            best = right

    return {
        "matched_fav_odds": best[0],
        "standard_draw": best[1],
        "standard_away": best[2],
        "zone_name": best[3],
        "water_level": best[4] if len(best) > 4 else "",
    }


# ---------------------------------------------------------------------------
#  主分析函数
# ---------------------------------------------------------------------------

def analyze_draw_deviation(match_id: int, db: Any) -> Optional[Dict[str, Any]]:
    """
    分析单场比赛的平赔偏差。

    流程:
      1. 查 over_under_odds_changes 获取 Bet365 大小球盘口线
      2. 优先从 william_odds_history 获取长节点（定义初赔），
         回退至 odds_changes / european_odds
      3. 归一化到 94% 体系
      4. 确定平系 → 查表 → 比较

    Args:
        match_id: 比赛 ID
        db: 数据库连接对象 (需有 execute_query 方法)

    Returns:
        分析结果 dict, 或 None (数据不足)
    """
    # --- Step 1: 获取 Bet365 大小球盘口线 ---
    # Try multiple company IDs in priority order: 281, 976, 545, 659, 190, 80
    OU_COMPANY_PRIORITY = [281, 976, 545, 659, 190, 80]
    ou_row = db.execute_query(
        """
        SELECT market_line, over_open, under_open, over_current, under_current, company_id
        FROM over_under_odds_changes
        WHERE match_id = %s AND company_id IN (281, 976, 545, 659, 190, 80) AND variant = 'main'
        ORDER BY FIELD(company_id, 281, 976, 545, 659, 190, 80), last_updated DESC
        LIMIT 1
        """,
        (match_id,),
        fetch='one',
    )
    if ou_row:
        _ou_company_used = ou_row.get('company_id', 'unknown')
        logger.debug(f"Match {match_id}: OU data from company_id={_ou_company_used}")
    if not ou_row or not ou_row.get('market_line'):
        logger.debug(f"Match {match_id}: 无 Bet365 大小球数据")
        return None

    market_line = float(ou_row['market_line'])
    ou_over_open = _safe_float(ou_row.get('over_open'))
    ou_under_open = _safe_float(ou_row.get('under_open'))
    ou_over_current = _safe_float(ou_row.get('over_current'))
    ou_under_current = _safe_float(ou_row.get('under_current'))
    open_snapshot = build_ou_snapshot(market_line, ou_over_open, ou_under_open, "open", "初指")
    current_snapshot = build_ou_snapshot(market_line, ou_over_current, ou_under_current, "current", "即时")

    # --- Step 2: 获取威廉欧赔 ---
    # 优先: william_odds_history 长节点（重新定义的"初赔"）
    # 回退: odds_changes / european_odds 原始初盘
    odds_source = "fallback"
    node_result = None
    control_data = None

    node_result = _try_load_long_node(match_id, db)
    if node_result:
        ln = node_result['long_node']
        raw_home = ln['home_odds']
        raw_draw = ln['draw_odds']
        raw_away = ln['away_odds']
        h94, d94, a94 = ln['home_94'], ln['draw_94'], ln['away_94']
        actual_rr = ln['return_rate']
        odds_source = "long_node"
        if node_result.get('control_node'):
            control_data = node_result['control_node']
    else:
        william_odds = _load_william_odds(match_id, db)
        if not william_odds:
            logger.debug(f"Match {match_id}: 无威廉欧赔数据")
            return None
        raw_home = william_odds['initial_home']
        raw_draw = william_odds['initial_draw']
        raw_away = william_odds['initial_away']
        h94, d94, a94, actual_rr = normalize_to_94(raw_home, raw_draw, raw_away)

    # --- Step 3: 识别一赔方 (胜负赔率较低方) ---
    if h94 <= a94:
        favorite_side = "home"
        favorite_odds_94 = h94
        favorite_odds_raw = raw_home
    else:
        favorite_side = "away"
        favorite_odds_94 = a94
        favorite_odds_raw = raw_away

    # --- Step 4: 确定平系并查表 ---
    # over_under_odds_changes 目前只有一个 market_line 字段，没有单独的 opening_line。
    # 若直接用 market_line + over_open/under_open 配对，在线路已经变盘时会把
    # “当前盘口线”和“初指水位”混用，导致 2.5 大球低水被误判成 2.75 体系。
    # 为避免这种错配，优先使用“当前盘口线 + 即时水位”做平系判定；
    # 初指水位仅保留展示，直到上游补齐初始盘口线字段。
    system_meta = determine_draw_system_details(
        market_line,
        ou_over_current,
        ou_under_current,
        phase="current",
        phase_label="即时",
    )
    if system_meta.get("mode") == "line_only":
        system_meta = determine_draw_system_details(
            market_line,
            ou_over_open,
            ou_under_open,
            phase="open_shared_line",
            phase_label="初指(共线)",
        )
        if system_meta.get("mode") != "line_only":
            system_meta["reason"] = (
                f"{system_meta.get('reason', '')}；当前库缺少初指盘口线字段，"
                "该结果为共用当前盘口线与初指水位的次优判定"
            )
    system_key = system_meta["system_key"]
    table_info = DRAW_SYSTEM_TABLES.get(system_key, {})

    lookup = lookup_standard_draw(system_key, favorite_odds_94)
    if not lookup:
        logger.debug(f"Match {match_id}: 平系 {system_key} 查表失败")
        return None

    std_draw = lookup['standard_draw']

    # --- Step 5: 偏差分析 ---
    deviation = round(d94 - std_draw, 3)
    if abs(deviation) <= 0.05:
        direction = "合理"
    elif deviation > 0:
        direction = "高"
    else:
        direction = "低"

    result = {
        "match_id": match_id,
        "odds_source": odds_source,
        # 大小球数据
        "ou_line": market_line,
        "ou_over_open": ou_over_open,
        "ou_under_open": ou_under_open,
        "ou_over_current": ou_over_current,
        "ou_under_current": ou_under_current,
        "ou_reference_phase": system_meta.get("phase"),
        "ou_reference_phase_label": system_meta.get("phase_label"),
        "ou_reference_reason": system_meta.get("reason"),
        "ou_decision_mode": system_meta.get("mode"),
        "draw_system_source": "ou_odds",
        "ou_open_snapshot": open_snapshot,
        "ou_current_snapshot": current_snapshot,
        # 平系
        "draw_system": system_key,
        "draw_system_name": table_info.get("name", system_key),
        "standard_draw_range": table_info.get("standard_draw_range", ""),
        # 一赔方
        "favorite_side": favorite_side,
        "favorite_odds_raw": round(favorite_odds_raw, 3),
        "favorite_odds_94": favorite_odds_94,
        # 返还率
        "actual_return_rate": actual_rr,
        # 平赔对比
        "standard_draw": std_draw,
        "actual_draw_raw": round(raw_draw, 3),
        "actual_draw_94": d94,
        "deviation": deviation,
        "deviation_direction": direction,
        # 长节点区间与水位
        "zone_name": lookup['zone_name'],
        "water_level": lookup.get('water_level', ''),
        "matched_fav_odds": lookup['matched_fav_odds'],
        # 完整原始赔率
        "raw_home": round(raw_home, 3),
        "raw_draw": round(raw_draw, 3),
        "raw_away": round(raw_away, 3),
        # 完整 94 体系赔率
        "home_94": h94,
        "draw_94": d94,
        "away_94": a94,
    }

    # 附加长节点/控赔信息
    if node_result:
        ln = node_result['long_node']
        result["long_node_time"] = str(ln.get('change_time', ''))
        result["long_node_duration_hours"] = ln.get('duration_hours')
        result["total_changes"] = node_result.get('total_changes')
    if control_data:
        result["control_home"] = control_data['home_odds']
        result["control_draw"] = control_data['draw_odds']
        result["control_away"] = control_data['away_odds']
        result["control_time"] = str(control_data.get('change_time', ''))
        result["control_home_94"] = control_data['home_94']
        result["control_draw_94"] = control_data['draw_94']
        result["control_away_94"] = control_data['away_94']
        # 控赔节点水位
        ctrl_water = _lookup_node_water(system_key,
                                        control_data['home_94'],
                                        control_data['draw_94'],
                                        control_data['away_94'])
        result["control_water_level"] = ctrl_water.get('water_level', '')
        result["control_zone_name"]   = ctrl_water.get('zone_name', '')
        result["control_standard_draw"] = ctrl_water.get('standard_draw')

    # 附加即时赔率（william_odds_history 最新一条）
    _attach_current_odds(match_id, db, result)

    # 即时节点水位（_attach_current_odds 已写入 current_home_94 等）
    if result.get('current_home_94') is not None:
        curr_water = _lookup_node_water(system_key,
                                        result['current_home_94'],
                                        result['current_draw_94'],
                                        result['current_away_94'])
        result["current_water_level"] = curr_water.get('water_level', '')
        result["current_zone_name"]   = curr_water.get('zone_name', '')
        result["current_standard_draw"] = curr_water.get('standard_draw')

    return result


# ---------------------------------------------------------------------------
#  批量分析
# ---------------------------------------------------------------------------

def batch_analyze(
    match_ids: List[int],
    db: Any,
) -> List[Dict[str, Any]]:
    """批量分析多场比赛的平赔偏差。"""
    results = []
    for mid in match_ids:
        try:
            result = analyze_draw_deviation(mid, db)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"Match {mid}: 平系分析异常 - {e}")
    return results


def analyze_today_matches(db: Any) -> List[Dict[str, Any]]:
    """分析今天所有有大小球数据的比赛。"""
    rows = db.execute_query(
        """
        SELECT DISTINCT ou.match_id
        FROM over_under_odds_changes ou
        JOIN matches m ON m.match_id = ou.match_id
        WHERE ou.company_id = %s
          AND ou.variant = 'main'
          AND DATE(m.match_time) = CURDATE()
          AND m.status IN ('pending', 'not_started', 'Fixture')
        """,
        (BET365_COMPANY_ID,),
        fetch='all',
    )
    if not rows:
        return []

    match_ids = [r['match_id'] for r in rows]
    logger.info(f"今日待分析平系比赛: {len(match_ids)} 场")
    return batch_analyze(match_ids, db)


# ---------------------------------------------------------------------------
#  辅助函数
# ---------------------------------------------------------------------------

def _try_load_long_node(match_id: int, db: Any) -> Optional[Dict[str, Any]]:
    """
    尝试从 william_odds_history 加载长节点数据。

    需要 match_time 才能计算 cutoff；如果 william_odds_history 无数据则返回 None。
    """
    try:
        match_row = db.execute_query(
            "SELECT match_time FROM matches WHERE match_id = %s",
            (match_id,),
            fetch='one',
        )
        if not match_row or not match_row.get('match_time'):
            return None

        from services.william_odds_node_analyzer import detect_odds_nodes
        return detect_odds_nodes(match_id, match_row['match_time'], db)
    except Exception as e:
        logger.debug(f"Match {match_id}: 长节点加载失败 - {e}")
        return None


def _load_william_odds(match_id: int, db: Any) -> Optional[Dict[str, float]]:
    """加载威廉初盘欧赔（回退方案），优先 odds_changes，回退 european_odds。"""
    for table in ('odds_changes', 'european_odds'):
        row = db.execute_query(
            f'SELECT initial_home, initial_draw, initial_away FROM {table} '
            f'WHERE match_id=%s AND company_id=%s',
            (match_id, WILLIAM_COMPANY_ID),
            fetch='one',
        )
        if row:
            h = _safe_float(row.get('initial_home'))
            d = _safe_float(row.get('initial_draw'))
            a = _safe_float(row.get('initial_away'))
            if h and d and a and h > 0 and d > 0 and a > 0:
                return {'initial_home': h, 'initial_draw': d, 'initial_away': a}
    return None


def _attach_current_odds(match_id: int, db: Any, result: Dict[str, Any]) -> None:
    """附加威廉即时赔率（william_odds_history 最新一条 或 odds_changes 即时盘）。"""
    try:
        latest = db.execute_query(
            """SELECT home_odds, draw_odds, away_odds, change_time
               FROM william_odds_history
               WHERE match_id = %s AND company_id = %s
               ORDER BY change_time DESC LIMIT 1""",
            (match_id, WILLIAM_COMPANY_ID),
            fetch='one',
        )
        if latest:
            h, d, a = float(latest['home_odds']), float(latest['draw_odds']), float(latest['away_odds'])
            h94, d94, a94, _ = normalize_to_94(h, d, a)
            result['current_home'] = h
            result['current_draw'] = d
            result['current_away'] = a
            result['current_home_94'] = h94
            result['current_draw_94'] = d94
            result['current_away_94'] = a94
            result['current_time'] = str(latest.get('change_time', ''))
            return

        oc = db.execute_query(
            """SELECT current_home, current_draw, current_away
               FROM odds_changes
               WHERE match_id = %s AND company_id = %s LIMIT 1""",
            (match_id, WILLIAM_COMPANY_ID),
            fetch='one',
        )
        if oc:
            h = _safe_float(oc.get('current_home'))
            d = _safe_float(oc.get('current_draw'))
            a = _safe_float(oc.get('current_away'))
            if h and d and a and h > 0 and d > 0 and a > 0:
                h94, d94, a94, _ = normalize_to_94(h, d, a)
                result['current_home'] = h
                result['current_draw'] = d
                result['current_away'] = a
                result['current_home_94'] = h94
                result['current_draw_94'] = d94
                result['current_away_94'] = a94
    except Exception as e:
        logger.debug("Match %s: 即时赔率加载失败 - %s", match_id, e)



def _estimate_system_from_draw94(draw94: float) -> str:
    """根据 draw_94 估算平系（无大小球数据时的降级方案）"""
    if draw94 <= 2.95:
        return "2.90"
    if draw94 <= 3.05:
        return "3.00"
    if draw94 <= 3.15:
        return "3.10"
    if draw94 <= 3.22:
        return "3.20"
    if draw94 <= 3.27:
        return "3.25"
    if draw94 <= 3.35:
        return "3.30"
    if draw94 <= 3.45:
        return "3.40"
    if draw94 <= 3.55:
        return "3.50"
    return "3.60"


def _lookup_node_water(system_key: str, h94: float, d94: float, a94: float) -> Dict:
    """
    用某节点的 94% 体系赔率查询其水位和标准平赔。
    一赔方取 h94 和 a94 中的较小值。
    """
    try:
        fav94 = min(h94, a94)
        lk = lookup_standard_draw(system_key, fav94)
        if not lk:
            return {}
        return {
            'water_level':  lk.get('water_level', ''),
            'zone_name':    lk.get('zone_name', ''),
            'standard_draw': lk.get('standard_draw'),
        }
    except Exception:
        return {}


def _safe_float(val: Any) -> Optional[float]:
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
#  格式化输出 (调试用)
# ---------------------------------------------------------------------------

def format_result(result: Dict[str, Any]) -> str:
    """将分析结果格式化为可读文本。"""
    if not result:
        return "无数据"

    lines = [
        f"比赛 {result['match_id']}:",
        f"  大小球盘口: {result['ou_line']}",
        f"  平系类别: {result['draw_system_name']}",
        f"  区间: {result['zone_name']}",
        f"  一赔方: {'主队' if result['favorite_side'] == 'home' else '客队'}"
        f" (原始={result['favorite_odds_raw']}, 94%={result['favorite_odds_94']})",
        f"  威廉返还率: {result['actual_return_rate']:.2%}",
        f"  标准平赔(94%): {result['standard_draw']}",
        f"  实际平赔(94%): {result['actual_draw_94']}",
        f"  偏差: {result['deviation']:+.3f} ({result['deviation_direction']})",
    ]
    return "\n".join(lines)
