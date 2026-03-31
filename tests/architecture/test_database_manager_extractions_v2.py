#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard deep DatabaseManager extraction into query/write helper modules."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("database/manager.py")


class DatabaseManagerExtractionsV2Tests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def _get_class(self, tree: ast.Module) -> ast.ClassDef:
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DatabaseManager"),
            None,
        )
        self.assertIsNotNone(class_node, msg="DatabaseManager class not found")
        return class_node

    def test_query_write_helper_modules_imported(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertTrue(
            {"manager_query_ops", "database.manager_query_ops"}.intersection(imported),
            msg=f"manager_query_ops import missing in {imported}",
        )
        self.assertTrue(
            {"manager_write_helpers", "database.manager_write_helpers"}.intersection(imported),
            msg=f"manager_write_helpers import missing in {imported}",
        )

    def test_extracted_methods_delegate_to_query_write_helpers(self):
        tree = self._parse()
        class_node = self._get_class(tree)
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}

        expectations = {
            "store_analysis_result": "_store_analysis_result",
            "get_latest_odds_analysis": "_get_latest_odds_analysis",
            "get_all_companies_map": "_get_all_companies_map",
            "get_today_scheduled_match_ids": "_get_today_scheduled_match_ids",
            "upsert_odds_changes": "_upsert_odds_changes",
            "bulk_upsert_odds_changes": "_bulk_upsert_odds_changes",
            "bulk_upsert_over_under_odds_changes": "_bulk_upsert_over_under_odds_changes",
            "get_match_ids_by_league": "_get_match_ids_by_league",
            "get_finished_matches_with_zero_odds": "_get_finished_matches_with_zero_odds",
            "get_all_companies": "_get_all_companies",
            "add_companies": "_add_companies",
            "get_matches_needing_odds": "_get_matches_needing_odds",
            "get_matches_ready_for_odds": "_get_matches_ready_for_odds",
            "get_league_summary": "_get_league_summary",
            "get_match_with_odds": "_get_match_with_odds",
            "get_company_odds_stats": "_get_company_odds_stats",
            "log_scraping_operation": "_log_scraping_operation",
            "get_scraping_stats": "_get_scraping_stats",
            "_normalize_odds_data": "_normalize_odds_data_impl",
            "_ensure_company_exists": "_ensure_company_exists",
            "cleanup_old_logs": "_cleanup_old_logs",
            "_normalize_odds_data_enhanced": "_normalize_odds_data_enhanced_impl",
            "_get_company_from_config": "_get_company_from_config",
            "_update_avg_batch_time": "_update_avg_batch_time_impl",
        }

        for method_name, helper_name in expectations.items():
            self.assertIn(method_name, methods)
            method = methods[method_name]
            helper_calls = [
                node
                for node in ast.walk(method)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{method_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()

