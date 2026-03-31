#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Ensure web AI orchestration keeps heavy deps lazily imported."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("application/services/web_ai_analysis.py")


class WebAiLazyImportTests(unittest.TestCase):
    def _parse(self):
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_no_heavy_imports_at_module_level(self):
        tree = self._parse()
        top_level_modules = set()
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level_modules.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top_level_modules.add(node.module)

        forbidden = {
            "application.services.odds_intent_service",
            "application.services.odds_intent_helper",
            "application.services.odds_intent_v2",
            "application.services.odds_intent_v2.adapter",
            "application.services.match_analysis_service",
        }
        self.assertFalse(forbidden.intersection(top_level_modules))

    def test_expected_lazy_imports_exist_in_builder_functions(self):
        tree = self._parse()
        functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}

        expectations = {
            "build_ai_analysis_payload": {
                "application.services.match_analysis_service",
                "application.services.odds_intent_helper",
                "application.services.odds_intent_service",
            },
            "build_ai_analysis_v2_payload": {
                "application.services.match_analysis_service",
                "application.services.odds_intent_v2",
                "application.services.odds_intent_v2.adapter",
            },
        }

        for func_name, expected_modules in expectations.items():
            func = functions[func_name]
            seen = set()
            for node in ast.walk(func):
                if isinstance(node, ast.ImportFrom) and node.module:
                    seen.add(node.module)
            self.assertTrue(expected_modules.issubset(seen))


if __name__ == "__main__":
    unittest.main()

