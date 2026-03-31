#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Structural guards for scheduled updater task orchestration."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/scheduled_data_updater.py")
TASK_METHODS = [
    "_update_leagues_task",
    "_update_odds_task",
    "_calculate_strength_task",
    "_cleanup_old_data_task",
]


def _called_method_names(func: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(func):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            names.add(node.func.attr)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            names.add(node.func.id)
    return names


class ScheduledDataUpdaterStructureTests(unittest.TestCase):
    def _parse_class(self) -> ast.ClassDef:
        tree = ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ScheduledDataUpdater"),
            None,
        )
        self.assertIsNotNone(class_node, msg="ScheduledDataUpdater class not found")
        return class_node

    def test_task_methods_use_common_lifecycle_helpers(self):
        class_node = self._parse_class()
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        delegate_helpers = {
            "_update_leagues_task": "run_update_leagues_task",
            "_update_odds_task": "run_update_odds_task",
            "_calculate_strength_task": "run_calculate_strength_task",
            "_cleanup_old_data_task": "run_cleanup_old_data_task",
        }

        for method_name in TASK_METHODS:
            self.assertIn(method_name, methods, msg=f"missing task method: {method_name}")
            called = _called_method_names(methods[method_name])
            has_direct_lifecycle = "_ensure_scheduler_running" in called and "_start_task" in called
            has_delegate = delegate_helpers[method_name] in called
            self.assertTrue(
                has_direct_lifecycle or has_delegate,
                msg=f"{method_name} must call lifecycle helpers or delegate action helper",
            )

    def test_subprocess_run_is_centralized(self):
        class_node = self._parse_class()
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}

        for name, func in methods.items():
            if name == "_run_main_command":
                continue
            for node in ast.walk(func):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    is_subprocess_run = (
                        node.func.attr == "run"
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "subprocess"
                    )
                    self.assertFalse(is_subprocess_run, msg=f"direct subprocess.run in {name}")


if __name__ == "__main__":
    unittest.main()
