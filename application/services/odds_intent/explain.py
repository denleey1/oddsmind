#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
解释生成器：将计算结果转换为可读的解释文本
"""

from typing import Dict, Any, List


def generate_explain(
    pattern: str,
    computed: Dict[str, Any],
    rule_explain: List[str]
) -> List[str]:
    """
    生成解释文本列表
    
    Args:
        pattern: 匹配的模式ID
        computed: 所有计算特征
        rule_explain: 规则中定义的解释模板
    
    Returns:
        解释文本列表
    """
    explain_list = []
    
    d_live = computed.get("delta_odds_live", {})
    dp_live = computed.get("delta_p_live", {})
    dmove = computed.get("delta_move", {})
    fav = computed.get("fav", "H")
    dog = computed.get("dog", "A")
    
    # 1. 赔率偏移解释
    for outcome in ["H", "D", "A"]:
        delta = d_live.get(outcome, 0)
        if abs(delta) >= 0.08:
            direction = "抬升" if delta > 0 else "压低"
            label = "韬" if delta > 0 else "实"
            outcome_name = {"H": "主胜", "D": "平局", "A": "客胜"}[outcome]
            explain_list.append(
                f"{outcome_name}相对骨架{direction}({delta*100:.1f}%)={label}"
            )
    
    # 2. 概率偏移解释（平局分洪/阻平）
    dp_draw = dp_live.get("D", 0)
    if abs(dp_draw) >= 0.02:
        if dp_draw > 0:
            explain_list.append(f"Δp(D)={dp_draw*100:.2f}pp：平赔为分洪口（桥梁吸筹）")
        else:
            explain_list.append(f"Δp(D)={dp_draw*100:.2f}pp：平赔被阻（阻平拉边）")
    
    # 3. 添加规则中定义的解释
    explain_list.extend(rule_explain)
    
    return explain_list


def format_intent_summary(pattern: str, intent: str, pick: str, hedge: str) -> str:
    """
    格式化意图摘要
    
    Args:
        pattern: 模式ID
        intent: 规则中定义的意图描述
        pick: 推荐赛果
        hedge: 防守建议
    
    Returns:
        格式化的意图摘要
    """
    pick_name = {"H": "主胜", "D": "平局", "A": "客胜"}.get(pick, pick)
    
    summary = intent
    if summary:
        summary += f"；倾向{pick_name}"
        if hedge and hedge != "none" and hedge != "none_or_small":
            hedge_name = {"D": "防平", "1X": "主不败", "X2": "客不败", "12": "分胜负"}.get(hedge, hedge)
            summary += f"，{hedge_name}"
    
    return summary

