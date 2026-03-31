#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of monitoring change detection from coordinator."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/monitoring_coordinator.py")


class MonitoringChangeDetectionExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_import_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("services.monitoring_change_detection", imported)

    def test_monitor_method_delegates_to_helper(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MonitoringCoordinator"),
            None,
        )
        self.assertIsNotNone(class_node)

        method = next(
            (node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == "monitor_odds_changes"),
            None,
        )
        self.assertIsNotNone(method)

        helper_calls = [
            node for node in ast.walk(method)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "collect_matches_requiring_analysis"
        ]
        self.assertTrue(helper_calls, msg="monitor_odds_changes should call collect_matches_requiring_analysis")


if __name__ == "__main__":
    unittest.main()
