#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard MatchDetailService delegations to extracted query/format modules."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("application/services/match_detail_service.py")


class MatchDetailServiceExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_extracted_module_imports_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("application.services.match_detail_queries", imported)
        self.assertIn("application.services.match_detail_formatting_ops", imported)

    def test_service_methods_delegate_to_helpers(self):
        tree = self._parse()
        class_node = next(
            node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MatchDetailService"
        )
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "get_match_basic_info": "_get_match_basic_info",
            "_resolve_canonical_match_id": "_resolve_canonical_match_id",
            "get_team_standings": "_get_team_standings",
            "get_team_standings_batch": "_get_team_standings_batch",
            "get_odds_analyses": "_get_odds_analyses",
            "safe_float": "_safe_float",
            "sort_analyses_by_priority": "_sort_analyses_by_priority",
            "format_analysis_data": "_format_analysis_data",
            "get_top_analyses": "_get_top_analyses",
            "build_fundamental_analysis_data": "_build_fundamental_analysis_data",
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

