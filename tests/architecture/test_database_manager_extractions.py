#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extracted DatabaseManager operations and integrity helpers."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("database/manager.py")


class DatabaseManagerExtractionsTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def _get_class(self, tree: ast.Module) -> ast.ClassDef:
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DatabaseManager"),
            None,
        )
        self.assertIsNotNone(class_node, msg="DatabaseManager class not found")
        return class_node

    def test_helper_modules_imported(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertTrue(
            {"manager_operations", "database.manager_operations"}.intersection(imported),
            msg=f"manager_operations import missing in {imported}",
        )
        self.assertTrue(
            {"manager_integrity_helpers", "database.manager_integrity_helpers"}.intersection(imported),
            msg=f"manager_integrity_helpers import missing in {imported}",
        )

    def test_extracted_methods_delegate_to_helpers(self):
        tree = self._parse()
        class_node = self._get_class(tree)
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}

        expectations = {
            "store_multiple_odds_data": "_store_multiple_odds_data",
            "store_odds_data": "_store_odds_data",
            "store_league_data": "_store_league_data",
            "get_enhanced_performance_stats": "_get_enhanced_performance_stats",
            "diagnose_database_health": "_diagnose_database_health",
            "_ensure_companies_exist": "_ensure_companies_exist_impl",
            "_ensure_teams_exist": "_ensure_teams_exist_impl",
            "_find_missing_company_ids": "_find_missing_company_ids_impl",
            "_find_company_info_by_id": "_find_company_info_by_id_impl",
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
