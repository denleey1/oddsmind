#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of heavy match-detail payload logic into ops modules."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("application/services/web_match_detail_payloads.py")


class WebMatchDetailPayloadExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_ops_module_imports_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("application.services.web_match_detail_pagination_ops", imported)
        self.assertIn("application.services.web_match_detail_cache_ops", imported)

    def test_wrapper_functions_delegate(self):
        tree = self._parse()
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "build_public_match_detail_pagination_payload": "_build_public_match_detail_pagination_payload_ops",
            "build_public_match_detail_payload": "_build_public_match_detail_payload_ops",
            "build_public_match_summary_payload": "_build_public_match_summary_payload_ops",
        }
        for func_name, helper_name in expectations.items():
            self.assertIn(func_name, functions)
            func = functions[func_name]
            helper_calls = [
                node
                for node in ast.walk(func)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{func_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()

