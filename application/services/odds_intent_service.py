#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
欧赔意图分析服务
提供自动化的"输入→计算→规则引擎→自动输出"方案
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, Literal, Tuple, Union
from core.logger import get_logger

from .odds_intent.features import compute_all_features
from .odds_intent.rules import load_ruleset, run_rules, format_output
from .odds_intent.explain import generate_explain, format_intent_summary

logger = get_logger(__name__)

Outcome = Literal["H", "D", "A"]

# 规则集路径
RULESET_PATH = Path(__file__).parent / "odds_intent" / "rulesets" / "ruleset_v1.yaml"

# 全局规则集缓存
_ruleset_cache = None


def get_ruleset():
    """获取规则集（带缓存）"""
    global _ruleset_cache
    if _ruleset_cache is None:
        _ruleset_cache = load_ruleset(str(RULESET_PATH))
    return _ruleset_cache


def analyze_odds_intent(
    match_id: str,
    skeleton: Dict,
    odds_open: Dict[str, float],
    odds_live: Dict[str, float],
    context: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    分析欧赔意图
    
    Args:
        match_id: 比赛ID
        skeleton: 骨架定义 {"type": "range", "H": [1.69, 1.88], ...} 或 {"type": "point", "H": 1.785, ...}
        odds_open: 初赔 {"H": 2.10, "D": 3.10, "A": 3.40}
        odds_live: 即时赔 {"H": 2.20, "D": 3.00, "A": 3.30}
        context: 可选上下文信息
    
    Returns:
        分析结果字典
    """
    try:
        # 1. 计算所有特征
        computed = compute_all_features(skeleton, odds_open, odds_live)
        
        # 2. 加载规则集
        ruleset = get_ruleset()
        thresholds = ruleset.get("thresholds", {})
        
        # 3. 构建规则执行上下文
        ctx = {
            # 阈值
            **thresholds,
            # 计算特征（展开字典以便规则表达式访问）
            "delta_odds_live": computed["delta_odds_live"],
            "delta_p_live": computed["delta_p_live"],
            "delta_move": computed["delta_move"],
            "fav": computed["fav"],
            "dog": computed["dog"],
        }
        
        # 展开字典键以便表达式访问
        for key in ["delta_odds_live", "delta_p_live", "delta_move"]:
            for subkey in ["H", "D", "A"]:
                ctx[f"{key}_{subkey}"] = ctx[key][subkey]
        
        # fav和dog的特殊处理
        ctx["delta_odds_live_fav"] = ctx["delta_odds_live"][computed["fav"]]
        ctx["delta_odds_live_dog"] = ctx["delta_odds_live"][computed["dog"]]
        
        # 4. 执行规则
        matched_rule = run_rules(ruleset, ctx)
        
        if not matched_rule:
            # 如果没有匹配的规则，使用fallback
            logger.warning(f"比赛 {match_id} 未匹配到任何规则，使用fallback")
            # 基于最大Δp选择
            dp_live = computed["delta_p_live"]
            pick = max(["H", "D", "A"], key=lambda k: dp_live[k])
            hedge = "1X2_mix"
            pattern = "FallbackByDeltaP"
            intent = "基于概率偏移最大项判断"
            explain_list = ["未匹配到明确结构，基于Δp最大项判断"]
            confidence_base = 50
        else:
            # 格式化输出
            output = matched_rule.get("output", {})
            
            # 处理特殊pick值
            pick_raw = output.get("pick", "H")
            if pick_raw == "max_delta_p":
                # Fallback规则：基于最大Δp
                dp_live = computed["delta_p_live"]
                pick = max(["H", "D", "A"], key=lambda k: dp_live[k])
            else:
                formatted_output = format_output(
                    output,
                    computed["fav"],
                    computed["dog"],
                    computed["delta_odds_live"],
                    thresholds
                )
                pick = formatted_output.get("pick", "H")
            
            hedge = output.get("hedge", "none")
            if hedge == "D_if_draw_spill_else_1X":
                # 检查是否draw_spill
                if computed["delta_p_live"]["D"] >= thresholds.get("draw_spill_pp", 0.02):
                    hedge = "D"
                else:
                    hedge = "1X" if pick == "H" else "X2"
            
            pattern = matched_rule.get("id", "Unknown")
            intent = output.get("intent", "")
            explain_list = output.get("explain", [])
            confidence_base = output.get("confidence_base", 60)
        
        # 5. 计算置信度
        confidence = calculate_confidence(
            pick,
            computed,
            confidence_base,
            thresholds
        )
        
        # 6. 生成解释
        full_explain = generate_explain(pattern, computed, explain_list)
        
        # 7. 格式化意图摘要
        intent_summary = format_intent_summary(pattern, intent, pick, hedge)
        
        # 8. 确定单项推荐（或排除最不可能的）
        # 默认返回最优单项，如果context中指定exclude_mode=True则返回排除模式
        exclude_mode = context.get("exclude_mode", False) if context else False
        single_result = determine_single_pick(pick, computed, exclude_mode)
        
        # 从context中获取公司信息
        company_id = context.get("company_id") if context else None
        company_name = context.get("company_name") if context else None
        
        return {
            "match_id": match_id,
            "rule_version": ruleset.get("version", "unknown"),
            "pattern": pattern,
            "intent_summary": intent_summary,
            "pick": single_result["pick"],  # 单项推荐
            "exclude": single_result.get("exclude"),  # 排除的选项（如果有）
            "pick_reason": single_result.get("reason"),  # 推荐原因
            "hedge": hedge,  # 保留原始hedge信息
            "confidence": confidence,
            "company_id": company_id,  # 使用的公司ID
            "company_name": company_name,  # 使用的公司名称（可选）
            "computed": {
                "skeleton_point": computed["skeleton_point"],
                "delta_odds_open": computed["delta_odds_open"],
                "delta_odds_live": computed["delta_odds_live"],
                "z_live": computed["z_live"],
                "p_skeleton": computed["p_skeleton"],
                "p_live": computed["p_live"],
                "delta_p_live": computed["delta_p_live"],
                "delta_move": computed["delta_move"],
                "rtp_live": computed["rtp_live"],
            },
            "explain": full_explain
        }
        
    except Exception as e:
        logger.error(f"分析欧赔意图失败: {e}", exc_info=True)
        raise


def calculate_confidence(
    pick: str,
    computed: Dict[str, Any],
    confidence_base: int,
    thresholds: Dict[str, float]
) -> int:
    """
    计算置信度
    
    Args:
        pick: 推荐赛果
        computed: 所有计算特征
        confidence_base: 基础置信度
        thresholds: 阈值字典
    
    Returns:
        置信度（0-100）
    """
    confidence = confidence_base
    
    # 1. 偏移强度加分
    dp_live = computed.get("delta_p_live", {})
    dp_pick = abs(dp_live.get(pick, 0))
    confidence += int(min(20, dp_pick * 200))
    
    # 2. 变盘确认/反做
    dmove = computed.get("delta_move", {})
    move_confirm = thresholds.get("move_confirm", -0.03)
    move_reverse = thresholds.get("move_reverse", 0.03)
    
    if pick in ["H", "D", "A"]:
        move_pick = dmove.get(pick, 0)
        if move_pick <= move_confirm:
            confidence += 10  # 继续走强，确认
        elif move_pick >= move_reverse:
            confidence -= 10  # 反做/诱导
    
    # 3. RTP异常惩罚
    rtp_live = computed.get("rtp_live", 0.95)
    if rtp_live < 0.86 or rtp_live > 0.98:
        confidence -= 8
    
    # 限制在0-100
    confidence = max(0, min(100, confidence))
    
    return confidence


def determine_single_pick(
    pick: str,
    computed: Dict[str, Any],
    exclude_mode: bool = False
) -> Dict[str, Any]:
    """
    确定单项推荐或排除最不可能的选项
    
    Args:
        pick: 规则推荐的赛果（可能是组合）
        computed: 所有计算特征
        exclude_mode: 如果True，返回排除最不可能的；如果False，返回最优单项
    
    Returns:
        {
            "pick": "H" | "D" | "A",  # 单项推荐
            "exclude": "H" | "D" | "A" | None,  # 排除的选项（如果exclude_mode=True）
            "reason": "推荐原因"
        }
    """
    dp_live = computed.get("delta_p_live", {})
    d_live = computed.get("delta_odds_live", {})
    
    if exclude_mode:
        # 排除模式：找出最不可能的选项
        # 最不可能 = Δp最小（概率偏移最小，说明庄家最不看好）
        exclude = min(["H", "D", "A"], key=lambda k: dp_live.get(k, 0))
        exclude_delta = dp_live.get(exclude, 0)
        
        # 从剩余两个选项中选择最优的
        remaining = [k for k in ["H", "D", "A"] if k != exclude]
        best = max(remaining, key=lambda k: dp_live.get(k, 0))
        
        return {
            "pick": best,
            "exclude": exclude,
            "reason": f"排除{exclude}（Δp={exclude_delta*100:.2f}pp最小，最不可能），推荐{best}"
        }
    else:
        # 单项模式：直接返回最优单项
        # 如果pick已经是单项，直接返回
        if pick in ["H", "D", "A"]:
            return {
                "pick": pick,
                "exclude": None,
                "reason": f"推荐{pick}（基于规则匹配）"
            }
        
        # 如果pick是组合（如"1X"），选择概率偏移最大的单项
        if pick in ["1X", "X2", "12"]:
            if pick == "1X":
                # 主不败：选择H或D中Δp更大的
                best = max(["H", "D"], key=lambda k: dp_live.get(k, 0))
            elif pick == "X2":
                # 客不败：选择A或D中Δp更大的
                best = max(["A", "D"], key=lambda k: dp_live.get(k, 0))
            elif pick == "12":
                # 分胜负：选择H或A中Δp更大的
                best = max(["H", "A"], key=lambda k: dp_live.get(k, 0))
            else:
                best = max(["H", "D", "A"], key=lambda k: dp_live.get(k, 0))
            
            return {
                "pick": best,
                "exclude": None,
                "reason": f"从组合{pick}中选择最优单项{best}"
            }
        
        # 默认：选择Δp最大的
        best = max(["H", "D", "A"], key=lambda k: dp_live.get(k, 0))
        return {
            "pick": best,
            "exclude": None,
            "reason": f"基于Δp最大选择{best}"
        }

