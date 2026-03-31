#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
规则引擎：解析和执行YAML规则配置
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional
import simpleeval

# 安全表达式求值器
# simpleeval默认支持or和and操作符，无需额外配置
_eval = simpleeval.SimpleEval()


def load_ruleset(path: str) -> Dict[str, Any]:
    """
    加载规则集YAML文件
    
    Args:
        path: YAML文件路径
    
    Returns:
        规则集字典
    """
    ruleset_path = Path(path)
    if not ruleset_path.exists():
        raise FileNotFoundError(f"规则集文件不存在: {path}")
    
    with open(ruleset_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def eval_expr(expr: str, ctx: Dict[str, Any]) -> bool:
    """
    安全地求值表达式（不使用eval）
    
    Args:
        expr: 表达式字符串，例如 "delta_odds_live_dog <= real" 或 "True"
        ctx: 上下文字典，包含所有变量和阈值
    
    Returns:
        布尔值
    """
    try:
        # 处理特殊值"True"（字符串）
        if expr.strip() == '"True"' or expr.strip() == "'True'" or expr.strip() == "True":
            return True
        
        # 使用simpleeval求值
        # 注意：simpleeval的正确用法是先设置names属性，然后调用eval
        # 表达式应该已经转换为下划线格式（delta_odds_live_dog）
        _eval.names = ctx
        result = _eval.eval(expr)
        return bool(result)
    except Exception as e:
        # 如果求值失败，返回False
        print(f"表达式求值失败: {expr}, 错误: {e}")
        return False


def run_rules(ruleset: Dict[str, Any], ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    执行规则集，返回第一个匹配的规则
    
    Args:
        ruleset: 规则集字典
        ctx: 上下文字典（包含所有计算特征和阈值）
    
    Returns:
        匹配的规则字典，如果没有匹配则返回None
    """
    rules = ruleset.get("rules", [])
    
    for rule in rules:
        when = rule.get("when", {})
        conditions = when.get("all", [])
        
        # 检查所有条件是否都满足
        all_ok = True
        for cond in conditions:
            if not eval_expr(cond, ctx):
                all_ok = False
                break
        
        if all_ok:
            return rule
    
    return None


def format_output(output: Dict[str, Any], fav: str, dog: str, d_live: Dict[str, float], thresholds: Dict[str, float] = None) -> Dict[str, Any]:
    """
    格式化规则输出，替换占位符
    
    Args:
        output: 规则输出字典
        fav: 热门方向
        dog: 冷门方向
        d_live: 即时赔率偏移
        thresholds: 阈值字典（可选）
    
    Returns:
        格式化后的输出
    """
    if thresholds is None:
        thresholds = {"real": -0.08}
    
    pick = output.get("pick", "")
    
    # 替换占位符
    if "{fav}" in pick:
        pick = pick.format(fav=fav)
    elif "{dog}" in pick:
        pick = pick.format(dog=dog)
    elif pick == "fav_if_fav_real_else_dog":
        # 特殊逻辑：根据fav是否实盘来决定
        real_threshold = thresholds.get("real", -0.08)
        if d_live.get(fav, 0) <= real_threshold:
            pick = fav
        else:
            pick = dog
    
    # 处理hedge中的占位符
    hedge = output.get("hedge", "")
    if "D_if_draw_spill_else_1X" in hedge:
        # 这里需要检查draw_spill，暂时简化
        hedge = "D"
    elif "fav_or_draw" in hedge:
        hedge = f"{fav}或D"
    
    result = output.copy()
    result["pick"] = pick
    result["hedge"] = hedge
    
    return result

