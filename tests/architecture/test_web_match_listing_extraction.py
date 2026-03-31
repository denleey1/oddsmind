#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of heavy web match-listing logic into ops module."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("application/services/web_match_listing.py")


class WebMatchListingExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_ops_module_import_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("application.services.web_match_listing_ops", imported)

    def test_wrapper_functions_delegate(self):
        tree = self._parse()
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

        expectations = {
            "dedupe_same_match_rows": "_dedupe_same_match_rows",
            "fetch_today_matches": "_fetch_today_matches",
            "format_today_matches": "_format_today_matches",
            "fetch_public_today_matches": "_fetch_public_today_matches",
            "format_public_today_matches": "_format_public_today_matches",
        }
        for func_name, helper_name in expectations.items():
            self.assertIn(func_name, functions)
            func = functions[func_name]
            helper_calls = [
                node for node in ast.walk(func)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{func_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()
