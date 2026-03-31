#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard rule_engine extraction into rule_engine_ops helper."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("application/services/odds_intent_v2/engine/rule_engine.py")


class RuleEngineExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_module_imported(self):
        tree = self._parse()
        imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}
        self.assertTrue(
            {
                "application.services.odds_intent_v2.engine.rule_engine_ops",
                "rule_engine_ops",
            }.intersection(imported),
            msg=f"rule_engine_ops import missing in {imported}",
        )

    def test_methods_delegate(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "RuleEngine"),
            None,
        )
        self.assertIsNotNone(class_node)

        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "_build_context": "build_context_impl",
            "_execute_stage_a": "execute_stage_a_impl",
            "_execute_stage_b": "execute_stage_b_impl",
            "_execute_stage_c": "execute_stage_c_impl",
            "_match_rule": "match_rule_impl",
            "_eval_expr": "eval_expr_impl",
            "_expand_functions": "expand_functions_impl",
            "_resolve_pick": "resolve_pick_impl",
        }

        for method_name, helper_name in expectations.items():
            self.assertIn(method_name, methods)
            helper_calls = [
                node
                for node in ast.walk(methods[method_name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{method_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()
