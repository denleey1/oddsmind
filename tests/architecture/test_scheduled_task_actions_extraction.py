#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of scheduled task action implementations."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/scheduled_data_updater.py")


class ScheduledTaskActionsExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_action_module_import_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("services.scheduled_task_actions", imported)

    def test_task_methods_delegate_to_action_helpers(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ScheduledDataUpdater"),
            None,
        )
        self.assertIsNotNone(class_node, msg="ScheduledDataUpdater class not found")
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}

        expectations = {
            "_update_leagues_task": "run_update_leagues_task",
            "_update_odds_task": "run_update_odds_task",
            "_calculate_strength_task": "run_calculate_strength_task",
            "_cleanup_old_data_task": "run_cleanup_old_data_task",
        }

        for method_name, helper_name in expectations.items():
            self.assertIn(method_name, methods)
            method = methods[method_name]
            helper_calls = [
                node for node in ast.walk(method)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{method_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()
