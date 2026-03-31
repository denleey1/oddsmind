#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard against re-introducing direct MatchDetailService construction in route layer."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGETS = [
    Path("application/routes/web.py"),
    Path("application/services/analytics.py"),
]


class MatchDetailProviderUsageTests(unittest.TestCase):
    def test_no_direct_match_detail_service_instantiation(self):
        for path in TARGETS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    self.assertNotEqual(node.func.id, "MatchDetailService", msg=f"direct ctor in {path}")

    def test_provider_imported_in_targets(self):
        expected_imports = {
            "application/routes/web.py": "application.services.match_detail_service_provider",
            "application/services/analytics.py": "application.services.match_detail_service_provider",
        }
        for path in TARGETS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            seen_modules = set()
            for node in tree.body:
                if isinstance(node, ast.ImportFrom) and node.module:
                    seen_modules.add(node.module)
            self.assertIn(expected_imports[str(path).replace("\\", "/")], seen_modules)


if __name__ == "__main__":
    unittest.main()

