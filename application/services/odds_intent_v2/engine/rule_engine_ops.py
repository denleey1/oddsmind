#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Operational helpers extracted from odds_intent_v2 RuleEngine."""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_context_impl(engine, features: Dict, draw_structure: Dict, intent_result: Dict) -> Dict[str, Any]:
    ctx = {}

    ctx.update(engine.thresholds)

    delta_odds_live = features.get("delta_odds_live", {})
    delta_p_live = features.get("delta_p_live", {})
    delta_move = features.get("delta_move", {})

    ctx.update(
        {
            "delta_odds_live_H": delta_odds_live.get("H", 0),
            "delta_odds_live_D": delta_odds_live.get("D", 0),
            "delta_odds_live_A": delta_odds_live.get("A", 0),
            "delta_p_live_H": delta_p_live.get("H", 0),
            "delta_p_live_D": delta_p_live.get("D", 0),
            "delta_p_live_A": delta_p_live.get("A", 0),
        }
    )

    fav = features.get("fav", "H")
    dog = features.get("dog", "A")
    ctx["fav"] = fav
    ctx["dog"] = dog
    ctx["delta_odds_live_fav"] = delta_odds_live.get(fav, 0)
    ctx["delta_odds_live_dog"] = delta_odds_live.get(dog, 0)

    if delta_move:
        ctx.update(
            {
                "delta_move_H": delta_move.get("H", 0),
                "delta_move_D": delta_move.get("D", 0),
                "delta_move_A": delta_move.get("A", 0),
            }
        )
        ctx["delta_move_fav"] = delta_move.get(fav, 0)
        ctx["delta_move_dog"] = delta_move.get(dog, 0)
    else:
        ctx.update({"delta_move_H": 0, "delta_move_D": 0, "delta_move_A": 0})
        ctx["delta_move_fav"] = 0
        ctx["delta_move_dog"] = 0

    import math

    ctx["abs"] = abs
    ctx["math"] = math

    ctx["draw_role"] = draw_structure.get("draw_role", "neutral")
    ctx["split_type"] = draw_structure.get("split_type", "none")

    solutions = intent_result.get("solutions", [])
    ctx["two_solutions"] = intent_result.get("two_solutions", False)
    if solutions:
        ctx["real_solution_score"] = (
            solutions[0].score
            if solutions[0].name == "REAL_solution"
            else (solutions[1].score if len(solutions) > 1 and solutions[1].name == "REAL_solution" else 0)
        )
        ctx["tao_solution_score"] = (
            solutions[0].score
            if solutions[0].name == "TAO_solution"
            else (solutions[1].score if len(solutions) > 1 and solutions[1].name == "TAO_solution" else 0)
        )

    return ctx


def execute_stage_a_impl(engine, ctx: Dict, draw_structure: Dict) -> Dict:
    rules = engine.ruleset.get("stageA_structure", [])
    tags = []
    structure = draw_structure.get("structure")
    matched_rules = []

    for rule in rules:
        if engine._match_rule(rule, ctx):
            matched_rules.append(rule.get("id", "unknown"))
            add = rule.get("add", {})
            tags.extend(add.get("tags", []))
            if "structure" in add:
                structure = add.get("structure")

    return {"tags": tags, "structure": structure, "matched_rules": matched_rules}


def execute_stage_b_impl(engine, ctx: Dict, intent_result: Dict, stage_a_result: Dict) -> Dict:
    del intent_result, stage_a_result

    rules = engine.ruleset.get("stageB_solutions", [])
    solutions_boost = {}
    matched_rules = []

    for rule in rules:
        if engine._match_rule(rule, ctx):
            matched_rules.append(rule.get("id", "unknown"))
            add = rule.get("add", {})
            boost = add.get("solution_boost", {})
            solutions_boost.update(boost)

    return {"solutions_boost": solutions_boost, "matched_rules": matched_rules}


def execute_stage_c_impl(
    engine,
    ctx: Dict,
    intent_result: Dict,
    stage_a_result: Dict,
    stage_b_result: Dict,
) -> Dict:
    del stage_a_result, stage_b_result

    rules = engine.ruleset.get("stageC_decision", [])
    matched_rules = []

    for rule in rules:
        if engine._match_rule(rule, ctx):
            matched_rules.append(rule.get("id", "unknown"))
            output = rule.get("output", {})

            if output.get("status") == "nobet":
                return {"status": "nobet", "final_pick": None, "matched_rules": matched_rules}

            pick = output.get("pick")
            if pick:
                final_pick = engine._resolve_pick(pick, ctx, intent_result)
                result = {
                    "status": output.get("status", "ok"),
                    "final_pick": final_pick,
                    "matched_rules": matched_rules,
                }
                if "market_pick" in output:
                    result["market_pick"] = output.get("market_pick")
                if "confidence_base" in output:
                    result["confidence_base"] = output.get("confidence_base")
                if "intent" in output:
                    result["intent"] = output.get("intent")
                if "explain" in output:
                    result["explain"] = output.get("explain")
                return result

    solutions = intent_result.get("solutions", [])
    if solutions:
        best_solution = max(solutions, key=lambda solution: solution.score)
        return {"status": "ok", "final_pick": best_solution.target, "matched_rules": matched_rules}

    return {"status": "nobet", "final_pick": None, "matched_rules": matched_rules}


def match_rule_impl(engine, rule: Dict, ctx: Dict) -> bool:
    when = rule.get("when", [])
    if not when:
        return True

    conditions = when if isinstance(when, list) else [when]

    if isinstance(conditions, dict):
        if "all" in conditions:
            for cond in conditions["all"]:
                if not engine._eval_expr(cond, ctx):
                    return False
            return True
        if "any" in conditions:
            for cond in conditions["any"]:
                if engine._eval_expr(cond, ctx):
                    return True
            return False

        for key, value in conditions.items():
            if not engine._eval_expr(f"{key} == {value}", ctx):
                return False
        return True

    for cond in conditions:
        if not engine._eval_expr(cond, ctx):
            return False

    return True


def eval_expr_impl(expr: str, ctx: Dict, evaluator, logger) -> bool:
    try:
        if expr.strip() == "True" or expr.strip() == "1==1":
            return True

        expanded = expand_functions_impl(expr)
        evaluator.names = ctx
        result = evaluator.eval(expanded)
        return bool(result)
    except Exception as exc:
        logger.warning(f"表达式求值失败: {expr}, 错误: {exc}")
        return False


def expand_functions_impl(expr: str) -> str:
    import re

    def replace_is_real(match):
        arg = match.group(1)
        if arg in ["fav", "dog"]:
            return f"delta_odds_live_{arg} <= real"
        if arg in ["H", "D", "A"]:
            return f"delta_odds_live_{arg} <= real"
        return match.group(0)

    expr = re.sub(r"is_real\((\w+)\)", replace_is_real, expr)

    def replace_is_tao(match):
        arg = match.group(1)
        if arg in ["fav", "dog"]:
            return f"delta_odds_live_{arg} >= tao"
        if arg in ["H", "D", "A"]:
            return f"delta_odds_live_{arg} >= tao"
        return match.group(0)

    expr = re.sub(r"is_tao\((\w+)\)", replace_is_tao, expr)
    return expr


def resolve_pick_impl(pick: str, ctx: Dict, intent_result: Dict) -> Optional[str]:
    if pick == "{fav}":
        return ctx.get("fav", "H")
    if pick == "{dog}":
        return ctx.get("dog", "A")
    if pick == "best_solution_target":
        solutions = intent_result.get("solutions", [])
        if solutions:
            best = max(solutions, key=lambda solution: solution.score)
            return best.target
        return None
    if pick == "max_delta_p":
        delta_p_live = {
            "H": ctx.get("delta_p_live_H", 0),
            "D": ctx.get("delta_p_live_D", 0),
            "A": ctx.get("delta_p_live_A", 0),
        }
        return max(delta_p_live.keys(), key=lambda key: delta_p_live[key])
    if pick == "max_delta_p_edge":
        fav = ctx.get("fav", "H")
        dog = ctx.get("dog", "A")
        delta_p_fav = ctx.get(f"delta_p_live_{fav}", 0)
        delta_p_dog = ctx.get(f"delta_p_live_{dog}", 0)
        return fav if delta_p_fav >= delta_p_dog else dog
    if pick == "fav_if_fav_soft_real_else_dog":
        fav = ctx.get("fav", "H")
        dog = ctx.get("dog", "A")
        real_soft = ctx.get("real_soft", -0.05)
        delta_odds_fav = ctx.get(f"delta_odds_live_{fav}", 0)
        return fav if delta_odds_fav <= real_soft else dog

    return pick


__all__ = [
    "build_context_impl",
    "eval_expr_impl",
    "execute_stage_a_impl",
    "execute_stage_b_impl",
    "execute_stage_c_impl",
    "expand_functions_impl",
    "match_rule_impl",
    "resolve_pick_impl",
]
