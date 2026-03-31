#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard match_detail_optimized extraction into query/format helpers."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("application/services/match_detail_optimized.py")


class MatchDetailOptimizedExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_modules_imported(self):
        tree = self._parse()
        imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}

        self.assertTrue(
            {"match_detail_optimized_query_ops", "application.services.match_detail_optimized_query_ops"}.intersection(imported),
            msg=f"match_detail_optimized_query_ops import missing in {imported}",
        )
        self.assertTrue(
            {"match_detail_optimized_format_ops", "application.services.match_detail_optimized_format_ops"}.intersection(imported),
            msg=f"match_detail_optimized_format_ops import missing in {imported}",
        )

    def test_service_methods_delegate(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "OptimizedMatchDetailService"),
            None,
        )
        self.assertIsNotNone(class_node)

        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "_get_match_with_standings": "get_match_with_standings_impl",
            "_get_top_company_analyses": "get_top_company_analyses_impl",
            "_get_company_count": "get_company_count_impl",
            "_safe_float": "safe_float_impl",
            "_format_analysis": "format_analysis_impl",
            "_build_response": "build_response_impl",
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
