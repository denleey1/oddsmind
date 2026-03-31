#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard optimized_repository extraction into helper ops modules."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("database/optimized_repository.py")


class OptimizedRepositoryExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_modules_imported(self):
        tree = self._parse()
        imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}

        self.assertTrue(
            {"optimized_repository_ops", "database.optimized_repository_ops"}.intersection(imported),
            msg=f"optimized_repository_ops import missing in {imported}",
        )
        self.assertTrue(
            {"optimized_repository_company_ops", "database.optimized_repository_company_ops"}.intersection(imported),
            msg=f"optimized_repository_company_ops import missing in {imported}",
        )

    def test_base_repository_methods_delegate(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "OptimizedBaseRepository"),
            None,
        )
        self.assertIsNotNone(class_node)

        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "atomic_upsert": "atomic_upsert_impl",
            "batch_atomic_upsert": "batch_atomic_upsert_impl",
            "_execute_batch_upsert": "execute_batch_upsert_impl",
            "safe_find_or_create": "safe_find_or_create_impl",
            "optimized_find_by_criteria": "optimized_find_by_criteria_impl",
        }

        for method_name, helper_name in expectations.items():
            self.assertIn(method_name, methods)
            helper_calls = [
                node
                for node in ast.walk(methods[method_name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{method_name} should call {helper_name}")

    def test_odds_repository_methods_delegate(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "OptimizedOddsRepository"),
            None,
        )
        self.assertIsNotNone(class_node)

        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "_ensure_all_companies_exist": "ensure_all_companies_exist_impl",
            "_get_existing_companies": "get_existing_companies_impl",
            "_create_missing_companies": "create_missing_companies_impl",
            "get_match_odds_with_stats": "get_match_odds_with_stats_impl",
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
