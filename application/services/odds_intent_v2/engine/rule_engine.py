#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三阶段规则引擎：结构标签 → 更优解加权 → 输出决策
"""

from typing import Dict

import simpleeval

from application.services.odds_intent_v2.config import config
from application.services.odds_intent_v2.engine.rule_engine_ops import (
    build_context_impl,
    eval_expr_impl,
    execute_stage_a_impl,
    execute_stage_b_impl,
    execute_stage_c_impl,
    expand_functions_impl,
    match_rule_impl,
    resolve_pick_impl,
)
from core.logger import get_logger

logger = get_logger(__name__)

_eval = simpleeval.SimpleEval()


class RuleEngine:
    """三阶段规则引擎"""

    def __init__(self):
        self.config = config
        self.ruleset = config.get_ruleset()
        self.thresholds = config.get_thresholds()
        self.weights = config.get_weights()

    def execute(self, features: Dict, draw_structure: Dict, intent_result: Dict) -> Dict:
        """执行三阶段规则"""
        ctx = self._build_context(features, draw_structure, intent_result)

        stage_a_result = self._execute_stage_a(ctx, draw_structure)
        stage_b_result = self._execute_stage_b(ctx, intent_result, stage_a_result)
        stage_c_result = self._execute_stage_c(ctx, intent_result, stage_a_result, stage_b_result)

        return {
            "tags": stage_a_result.get("tags", []),
            "structure": stage_a_result.get("structure"),
            "solutions_boost": stage_b_result.get("solutions_boost", {}),
            "final_pick": stage_c_result.get("final_pick"),
            "status": stage_c_result.get("status", "ok"),
            "matched_rules": stage_a_result.get("matched_rules", [])
            + stage_b_result.get("matched_rules", [])
            + stage_c_result.get("matched_rules", []),
        }

    def _build_context(self, features: Dict, draw_structure: Dict, intent_result: Dict):
        """构建规则执行上下文"""
        return build_context_impl(self, features, draw_structure, intent_result)

    def _execute_stage_a(self, ctx: Dict, draw_structure: Dict) -> Dict:
        """Stage A: 结构标签规则"""
        return execute_stage_a_impl(self, ctx, draw_structure)

    def _execute_stage_b(self, ctx: Dict, intent_result: Dict, stage_a_result: Dict) -> Dict:
        """Stage B: 更优解加权规则"""
        return execute_stage_b_impl(self, ctx, intent_result, stage_a_result)

    def _execute_stage_c(
        self,
        ctx: Dict,
        intent_result: Dict,
        stage_a_result: Dict,
        stage_b_result: Dict,
    ) -> Dict:
        """Stage C: 输出决策规则"""
        return execute_stage_c_impl(self, ctx, intent_result, stage_a_result, stage_b_result)

    def _match_rule(self, rule: Dict, ctx: Dict) -> bool:
        """匹配规则条件"""
        return match_rule_impl(self, rule, ctx)

    def _eval_expr(self, expr: str, ctx: Dict) -> bool:
        """安全求值表达式"""
        return eval_expr_impl(expr, ctx, _eval, logger)

    def _expand_functions(self, expr: str) -> str:
        """展开函数调用（如 is_real(fav)）"""
        return expand_functions_impl(expr)

    def _resolve_pick(self, pick: str, ctx: Dict, intent_result: Dict):
        """解析pick占位符"""
        return resolve_pick_impl(pick, ctx, intent_result)
