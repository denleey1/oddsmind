#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Formatting helpers for odds-intent API responses."""

from __future__ import annotations

from typing import Dict


def format_analysis_text(result: Dict, match_data: Dict) -> str:
    """Format intent analysis data into text output."""
    lines = []
    lines.append("=" * 60)
    lines.append("欧赔意图分析结果")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"模式: {result.get('pattern', 'N/A')}")
    lines.append(f"规则版本: {result.get('rule_version', 'N/A')}")
    lines.append("")
    pick = result.get("pick", "N/A")
    pick_name = {"H": "主胜", "D": "平局", "A": "客胜"}.get(pick, pick)
    lines.append(f"推荐赛果: {pick_name} ({pick})")
    if result.get("exclude"):
        exclude = result.get("exclude")
        exclude_name = {"H": "主胜", "D": "平局", "A": "客胜"}.get(exclude, exclude)
        lines.append(f"排除选项: {exclude_name} ({exclude})")
    lines.append(f"推荐原因: {result.get('pick_reason', 'N/A')}")
    lines.append(f"防守建议: {result.get('hedge', 'N/A')}")
    lines.append(f"置信度: {result.get('confidence', 0)}%")
    lines.append("")
    lines.append(f"意图摘要: {result.get('intent_summary', '')}")
    lines.append("")
    lines.append("计算特征:")
    computed = result.get("computed", {})
    if computed:
        lines.append(
            f"  骨架点: H={computed.get('skeleton_point', {}).get('H', 'N/A'):.3f}, "
            f"D={computed.get('skeleton_point', {}).get('D', 'N/A'):.3f}, "
            f"A={computed.get('skeleton_point', {}).get('A', 'N/A'):.3f}"
        )
        lines.append(
            f"  Δodds(即时): H={computed.get('delta_odds_live', {}).get('H', 0)*100:.1f}%, "
            f"D={computed.get('delta_odds_live', {}).get('D', 0)*100:.1f}%, "
            f"A={computed.get('delta_odds_live', {}).get('A', 0)*100:.1f}%"
        )
        lines.append(
            f"  Δp(即时): H={computed.get('delta_p_live', {}).get('H', 0)*100:.2f}pp, "
            f"D={computed.get('delta_p_live', {}).get('D', 0)*100:.2f}pp, "
            f"A={computed.get('delta_p_live', {}).get('A', 0)*100:.2f}pp"
        )
        lines.append(
            f"  变盘幅度: H={computed.get('delta_move', {}).get('H', 0)*100:.1f}%, "
            f"D={computed.get('delta_move', {}).get('D', 0)*100:.1f}%, "
            f"A={computed.get('delta_move', {}).get('A', 0)*100:.1f}%"
        )
        lines.append(f"  返还率: {computed.get('rtp_live', 0)*100:.2f}%")
    lines.append("")
    lines.append("解释:")
    for explain in result.get("explain", []):
        lines.append(f"  - {explain}")
    lines.append("")
    lines.append("=" * 60)
    return "\n".join(lines)


def extract_final_judgment(analysis_text: str) -> str:
    """Extract the final recommendation section from analysis text."""
    if not analysis_text:
        return None

    lines = analysis_text.strip().split("\n")
    final_lines = []

    keywords = ["结论", "判断", "预测", "建议", "推荐", "最终", "综合"]
    for i in range(len(lines) - 1, max(0, len(lines) - 10), -1):
        line = lines[i].strip()
        if any(keyword in line for keyword in keywords) or len(line) > 20:
            final_lines.insert(0, line)
            if len(final_lines) >= 3:
                break

    if final_lines:
        result = "\n".join(final_lines)
        if len(result) > 500:
            result = result[:497] + "..."
        return result

    last_paragraph = analysis_text.strip()[-500:]
    if len(analysis_text) > 500:
        last_paragraph = "..." + last_paragraph
    return last_paragraph


__all__ = ["format_analysis_text", "extract_final_judgment"]

