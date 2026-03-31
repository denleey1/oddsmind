#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard task_health_tracker extraction into redis/health helper modules."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("application/services/task_health_tracker.py")


class TaskHealthTrackerExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_modules_imported(self):
        tree = self._parse()
        imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}

        self.assertTrue(
            {"task_health_tracker_redis_ops", "application.services.task_health_tracker_redis_ops"}.intersection(imported),
            msg=f"task_health_tracker_redis_ops import missing in {imported}",
        )
        self.assertTrue(
            {"task_health_tracker_health_ops", "application.services.task_health_tracker_health_ops"}.intersection(imported),
            msg=f"task_health_tracker_health_ops import missing in {imported}",
        )

    def test_module_and_class_methods_delegate(self):
        tree = self._parse()

        module_functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        module_expectations = {
            "update_service_status": "update_service_status_impl",
            "get_service_status": "get_service_status_impl",
            "_get_redis_client": "get_redis_client",
        }
        for fn_name, helper_name in module_expectations.items():
            self.assertIn(fn_name, module_functions)
            helper_calls = [
                node
                for node in ast.walk(module_functions[fn_name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{fn_name} should call {helper_name}")

        class_nodes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn("TaskStatus", class_nodes)
        self.assertIn("TaskHealthTracker", class_nodes)

        task_status_methods = {
            node.name: node for node in class_nodes["TaskStatus"].body if isinstance(node, ast.FunctionDef)
        }
        status_expectations = {
            "to_dict": "task_status_to_dict",
            "_calculate_health_status": "calculate_health_status",
            "_minutes_since_last_run": "minutes_since_last_run",
            "_next_expected_run": "next_expected_run",
        }
        for method_name, helper_name in status_expectations.items():
            self.assertIn(method_name, task_status_methods)
            helper_calls = [
                node
                for node in ast.walk(task_status_methods[method_name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"TaskStatus.{method_name} should call {helper_name}")

        tracker_methods = {
            node.name: node for node in class_nodes["TaskHealthTracker"].body if isinstance(node, ast.FunctionDef)
        }
        tracker_expectations = {
            "_save_to_redis": "save_task_to_redis_impl",
            "_load_from_redis": "load_task_from_redis_impl",
            "_get_all_task_ids_from_redis": "get_all_task_ids_from_redis_impl",
            "get_all_status": "build_tracker_snapshot",
        }
        for method_name, helper_name in tracker_expectations.items():
            self.assertIn(method_name, tracker_methods)
            helper_calls = [
                node
                for node in ast.walk(tracker_methods[method_name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"TaskHealthTracker.{method_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()
