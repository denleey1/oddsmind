#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard the extraction of odds-sync helpers from MonitoringCoordinator."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/monitoring_coordinator.py")


class MonitoringOddsSyncExtractionTests(unittest.TestCase):
    def _parse(self):
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def _get_class(self, tree: ast.Module) -> ast.ClassDef:
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MonitoringCoordinator"),
            None,
        )
        self.assertIsNotNone(class_node, msg="MonitoringCoordinator class not found")
        return class_node

    def test_import_from_helper_module_exists(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("services.monitoring_odds_sync", imported)

    def test_delegation_methods_call_helper_functions(self):
        tree = self._parse()
        class_node = self._get_class(tree)
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}

        expected = {
            "_sync_write_odds_changes": "sync_write_odds_changes",
            "_verify_odds_changes_in_db": "verify_odds_changes_in_db",
        }
        for method_name, helper_name in expected.items():
            self.assertIn(method_name, methods)
            method = methods[method_name]
            helper_calls = [
                node for node in ast.walk(method)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{method_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()
