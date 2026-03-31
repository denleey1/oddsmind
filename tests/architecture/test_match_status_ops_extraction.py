#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of match-level update ops from MatchStatusUpdater."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/match_status_updater.py")


class MatchStatusOpsExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_module_import_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("services.match_status_match_ops", imported)

    def test_delegate_methods_call_extracted_helpers(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "MatchStatusUpdater"),
            None,
        )
        self.assertIsNotNone(class_node, msg="MatchStatusUpdater class missing")
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}

        expectations = {
            "_get_or_create_team_id": "_get_or_create_team_id_impl",
            "_ensure_team_record": "_ensure_team_record_impl",
            "_update_single_match": "_update_single_match_impl",
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
