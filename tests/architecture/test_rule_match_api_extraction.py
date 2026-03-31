#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of heavy rule-match API payload assembly."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/rule_match_api.py")


class RuleMatchApiExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_payload_ops_import_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("services.rule_match_payload_ops", imported)

    def test_route_handlers_delegate_to_payload_builders(self):
        tree = self._parse()
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "get_rule_alerts": "build_rule_alerts_payload",
            "get_today_alerts": "build_today_alerts_payload",
            "get_match_alerts": "build_match_alerts_payload",
            "get_rules": "build_rules_payload",
        }
        for func_name, helper_name in expectations.items():
            self.assertIn(func_name, functions)
            func = functions[func_name]
            helper_calls = [
                node
                for node in ast.walk(func)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{func_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()

