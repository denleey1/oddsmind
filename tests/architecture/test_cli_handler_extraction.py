#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of heavy CLI handlers out of cli_app module."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("application/cli/cli_app.py")


class CliHandlerExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_cli_command_handlers_import_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("application.cli.cli_command_handlers", imported)

    def test_heavy_methods_delegate_to_extracted_helpers(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "OddsMindCLI"),
            None,
        )
        self.assertIsNotNone(class_node, msg="OddsMindCLI class not found")
        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}

        expectations = {
            "handle_scrape_odds": "_handle_scrape_odds",
            "handle_analyze_odds": "_handle_analyze_odds",
            "handle_analyze_fundamental": "_handle_analyze_fundamental",
            "handle_calculate_strength": "_handle_calculate_strength",
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
