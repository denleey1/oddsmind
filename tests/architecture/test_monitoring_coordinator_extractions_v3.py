#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Deep extraction guards for MonitoringCoordinator analysis-execution internals."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/monitoring_coordinator.py")


class MonitoringCoordinatorExtractionsV3Tests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def _get_method(self, class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
        method = next(
            (node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name),
            None,
        )
        self.assertIsNotNone(method, msg=f"method missing: {name}")
        return method

    def test_analysis_execution_helper_import_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("services.monitoring_analysis_execution", imported)

    def test_methods_delegate_to_analysis_execution_helpers(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MonitoringCoordinator"),
            None,
        )
        self.assertIsNotNone(class_node, msg="MonitoringCoordinator class missing")

        expectations = {
            "_find_completed_rounds": "_find_completed_rounds_impl",
            "_calculate_strength": "_calculate_strength_impl",
            "_reanalyse_league_matches": "_reanalyse_league_matches_impl",
            "_analyse_matches_with_changes": "_analyse_matches_with_changes_impl",
        }

        for method_name, helper_name in expectations.items():
            method = self._get_method(class_node, method_name)
            helper_calls = [
                node
                for node in ast.walk(method)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{method_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()

