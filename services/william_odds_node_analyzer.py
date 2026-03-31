#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
威廉赔率节点分析器

从 william_odds_history 中识别"长节点"（定义初赔）和"控赔组合"。

核心规则:
  1. 凌晨比赛（开赛时间北京时间 < 06:00）比赛日顺延至前一天
  2. 参考日 = 比赛日 - 1天
  3. 搜索窗口 = [参考日 00:00, 开赛时间]
  4. 计算每段赔率与窗口的重叠时长，重叠最长的 = 长节点
     （若参考日无变化，延续自更早的那段重叠时长为整段参考日，天然成为长节点）
  5. 长节点之后的所有变化 = 控赔阶段，control_node 取其中第一条

示例 (某赛, 03-25 20:00 开赛):
  比赛日 = 03-25, 参考日 = 03-24
  搜索窗口 = [03-24 00:00, 03-25 20:00]
  赔率A: 03-22 开始 → 03-25 00:30 结束, 窗口内重叠 = 24.5h → 长节点
  赔率B: 03-25 00:30 开始 → 03-25 20:00 结束, 窗口内重叠 = 19.5h → 控赔

示例 (凌晨赛, 03-23 00:30 开赛):
  凌晨(<6:00) → 比赛日 = 03-22, 参考日 = 03-21
  搜索窗口 = [03-21 00:00, 03-23 00:30]
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from services.draw_system_analyzer import normalize_to_94

logger = get_logger(__name__)

WILLIAM_CID = 115
EARLY_MORNING_HOUR = 6


def _compute_search_window(match_time: datetime) -> Tuple[datetime, datetime]:
    """
    计算长节点搜索窗口。

    普通比赛 (>= 06:00):
      比赛日 = 当天
      参考日 = 比赛日 - 1天
      窗口   = [参考日 00:00, 开赛时间]

    凌晨比赛 (< 06:00 北京时间):
      比赛日 = match_time.date() - 1（顺延至前一天）
      参考日 = 比赛日 - 1天
      窗口   = [参考日 00:00, 开赛时间]

    Returns:
        (window_start, window_end) 两个 datetime，window_end 即开赛时间
    """
    if match_time.hour < EARLY_MORNING_HOUR:
        match_day = match_time.date() - timedelta(days=1)
    else:
        match_day = match_time.date()

    ref_day = match_day - timedelta(days=1)
    window_start = datetime.combine(ref_day, dt_time.min)
    window_end = match_time  # 窗口终点 = 开赛时间
    return window_start, window_end


def _build_segments(records: List[Dict], match_time: datetime) -> List[Dict]:
    """
    从变化记录列表构建各段持续时间。

    每段: 从本次变化到下一次变化（最后一段到开赛时间）。
    """
    segments = []
    n = len(records)
    for i, rec in enumerate(records):
        ct = rec['change_time']
        if ct is None:
            continue
        if i + 1 < n and records[i + 1]['change_time'] is not None:
            end_t = records[i + 1]['change_time']
        else:
            end_t = match_time
        dur = (end_t - ct).total_seconds()
        segments.append({
            'index': i,
            'record': rec,
            'start': ct,
            'end': end_t,
            'duration_sec': max(dur, 0),
        })
    return segments


def detect_odds_nodes(
    match_id: int,
    match_time: datetime,
    db: Any,
) -> Optional[Dict[str, Any]]:
    """
    检测长节点（定义初赔）和控赔组合。

    Args:
        match_id: 比赛 ID
        match_time: 比赛开始时间（datetime）
        db: 数据库对象（需有 execute_query）

    Returns:
        {
          long_node: { home/draw/away, change_time, duration_hours, home_94/draw_94/away_94 },
          control_node: { ... } or None,
          total_changes: int,
          window_start/window_end: datetime,
        }
        或 None（数据不足）
    """
    records = db.execute_query(
        """
        SELECT home_odds, draw_odds, away_odds,
               return_rate, change_time, is_opening
        FROM william_odds_history
        WHERE match_id = %s AND company_id = %s
        ORDER BY change_time ASC
        """,
        (match_id, WILLIAM_CID),
        fetch='all',
    )

    if not records or len(records) < 2:
        logger.debug("Match %s: william_odds_history 不足2条记录", match_id)
        return None

    window_start, window_end = _compute_search_window(match_time)
    segments = _build_segments(records, match_time)

    if not segments:
        return None

    # 计算每段赔率与搜索窗口 [window_start, window_end] 的重叠时长
    # 文档定义：长节点 = 参考日内重叠时间最长的那段赔率
    # 这自然处理"参考日无变化时，延续自更早的赔率段"的情形（其重叠时长 = 整个参考日）
    best_overlap = timedelta(0)
    long_seg = None
    for seg in segments:
        overlap_start = max(seg['start'], window_start)
        overlap_end = min(seg['end'], window_end)
        overlap = overlap_end - overlap_start
        if overlap > best_overlap:
            best_overlap = overlap
            long_seg = seg

    if long_seg is None:
        logger.debug(
            "Match %s: 窗口 %s~%s 内无重叠赔率段",
            match_id, window_start, window_end,
        )
        return None
    long_rec = long_seg['record']

    # 控赔 = 长节点之后的下一条记录（下一次变化）
    control_rec = None
    long_idx = long_seg['index']
    if long_idx + 1 < len(records):
        control_rec = records[long_idx + 1]

    def _node_dict(rec: Dict, dur_hours: Optional[float] = None) -> Dict[str, Any]:
        h = float(rec['home_odds'])
        d = float(rec['draw_odds'])
        a = float(rec['away_odds'])
        h94, d94, a94, rr = normalize_to_94(h, d, a)
        node = {
            'home_odds': h, 'draw_odds': d, 'away_odds': a,
            'home_94': h94, 'draw_94': d94, 'away_94': a94,
            'return_rate': round(rr, 4),
            'change_time': rec['change_time'],
        }
        if dur_hours is not None:
            node['duration_hours'] = dur_hours
        return node

    overlap_hours = round(best_overlap.total_seconds() / 3600, 2)

    result = {
        'long_node': _node_dict(
            long_rec,
            dur_hours=overlap_hours,  # 窗口内重叠时长（与文档定义一致）
        ),
        'control_node': _node_dict(control_rec) if control_rec else None,
        'total_changes': len(records),
        'window_start': window_start,
        'window_end': window_end,
        'match_time': match_time,
    }

    logger.info(
        "Match %s: 窗口 %s~%s, 长节点 %.2f/%.2f/%.2f (窗口内重叠%.2fh, 从%s), 控赔 %s",
        match_id,
        window_start.strftime('%m-%d %H:%M'),
        window_end.strftime('%m-%d %H:%M'),
        result['long_node']['home_odds'],
        result['long_node']['draw_odds'],
        result['long_node']['away_odds'],
        result['long_node']['duration_hours'],
        result['long_node']['change_time'],
        (
            f"{result['control_node']['home_odds']:.2f}/{result['control_node']['draw_odds']:.2f}/{result['control_node']['away_odds']:.2f} @ {result['control_node']['change_time']}"
            if result['control_node'] else "无"
        ),
    )
    return result


def detect_nodes_batch(
    match_rows: List[Dict],
    db: Any,
) -> Dict[int, Dict[str, Any]]:
    """
    批量检测多场比赛的长节点。

    Args:
        match_rows: [{ match_id, match_time }, ...]
        db: 数据库对象

    Returns:
        { match_id: node_result_dict, ... }
    """
    results = {}
    for row in match_rows:
        mid = row['match_id']
        mt = row['match_time']
        if isinstance(mt, str):
            mt = datetime.fromisoformat(mt)
        try:
            node = detect_odds_nodes(mid, mt, db)
            if node:
                results[mid] = node
        except Exception as e:
            logger.error("Match %s: 节点检测异常 - %s", mid, e)
    return results


def format_node_analysis(node_result: Dict[str, Any]) -> str:
    """格式化节点分析结果（调试用）。"""
    if not node_result:
        return "无数据"
    ln = node_result['long_node']
    cn = node_result.get('control_node')
    ws = node_result.get('window_start', '')
    we = node_result.get('window_end', '')
    lines = [
        f"搜索窗口: {ws} ~ {we}",
        f"长节点(定义初赔): {ln['home_odds']}/{ln['draw_odds']}/{ln['away_odds']}"
        f"  → 94%体系: {ln['home_94']}/{ln['draw_94']}/{ln['away_94']}"
        f"  持续 {ln['duration_hours']}h, 设定于 {ln['change_time']}",
    ]
    if cn:
        lines.append(
            f"控赔组合: {cn['home_odds']}/{cn['draw_odds']}/{cn['away_odds']}"
            f"  → 94%体系: {cn['home_94']}/{cn['draw_94']}/{cn['away_94']}"
            f"  变化于 {cn['change_time']}"
        )
    lines.append(f"总变化数: {node_result['total_changes']}")
    return "\n".join(lines)
