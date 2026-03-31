#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Additional extraction guards for MonitoringCoordinator internals."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/monitoring_coordinator.py")


class MonitoringCoordinatorExtractionsV2Tests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def _get_method(self, class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
        method = next(
            (node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name),
            None,
        )
        self.assertIsNotNone(method, msg=f"method missing: {name}")
        return method

    def test_helper_imports_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("services.monitoring_final_odds", imported)
        self.assertIn("services.monitoring_unanalyzed_companies", imported)

    def test_unanalyzed_and_final_odds_methods_delegate(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MonitoringCoordinator"),
            None,
        )
        self.assertIsNotNone(class_node, msg="MonitoringCoordinator class missing")

        expectations = {
            "_check_and_analyze_unanalyzed_companies": "check_and_analyze_unanalyzed_companies",
            "_verify_priority_companies_analyzed": "verify_priority_companies_analyzed",
            "_sync_final_odds": "sync_final_odds",
        }

        for method_name, helper_name in expectations.items():
            method = self._get_method(class_node, method_name)
            helper_calls = [
                node for node in ast.walk(method)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{method_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()
