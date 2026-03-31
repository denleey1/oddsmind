#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard enhanced_manager extraction into helper ops modules."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("database/enhanced_manager.py")


class EnhancedManagerExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_modules_imported(self):
        tree = self._parse()
        imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}

        expected_modules = {
            "enhanced_manager_odds_ops",
            "database.enhanced_manager_odds_ops",
            "enhanced_manager_diagnostics_ops",
            "database.enhanced_manager_diagnostics_ops",
            "enhanced_manager_league_ops",
            "database.enhanced_manager_league_ops",
        }
        self.assertTrue(expected_modules.intersection(imported), msg=f"helper imports missing in {imported}")

    def test_public_methods_delegate_to_helpers(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "EnhancedDatabaseManager"),
            None,
        )
        self.assertIsNotNone(class_node)

        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "store_odds_data_enhanced": "store_odds_data_enhanced_impl",
            "store_multiple_odds_data_enhanced": "store_multiple_odds_data_enhanced_impl",
            "ensure_company_exists_enhanced": "ensure_company_exists_enhanced_impl",
            "get_enhanced_database_stats": "get_enhanced_database_stats_impl",
            "diagnose_database_issues": "diagnose_database_issues_impl",
            "_normalize_odds_data_enhanced": "normalize_odds_data_enhanced_impl",
            "_get_company_from_config": "get_company_from_config_impl",
            "_update_avg_batch_time": "update_avg_batch_time_impl",
            "store_league_data": "store_league_data_impl",
            "_normalize_match_data": "normalize_match_data_impl",
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
