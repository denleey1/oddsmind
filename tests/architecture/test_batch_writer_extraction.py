#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard batch_writer extraction into queue/flush helper modules."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("database/batch_writer.py")


class BatchWriterExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_modules_imported(self):
        tree = self._parse()
        imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}

        self.assertTrue(
            {"batch_writer_queue_ops", "database.batch_writer_queue_ops"}.intersection(imported),
            msg=f"batch_writer_queue_ops import missing in {imported}",
        )
        self.assertTrue(
            {"batch_writer_flush_ops", "database.batch_writer_flush_ops"}.intersection(imported),
            msg=f"batch_writer_flush_ops import missing in {imported}",
        )

    def test_methods_delegate_to_helpers(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "BatchWriter"),
            None,
        )
        self.assertIsNotNone(class_node)

        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "enqueue_odds_changes": "enqueue_odds_changes_impl",
            "enqueue_over_under": "enqueue_over_under_impl",
            "enqueue_odds": "enqueue_odds_impl",
            "_flush_all": "flush_all_impl",
            "_write_batch_with_retry": "write_batch_with_retry_impl",
            "_process_retries": "process_retries_impl",
            "get_stats": "get_stats_impl",
            "wait_for_empty": "wait_for_empty_impl",
            "get_queue_depths": "get_queue_depths_impl",
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
