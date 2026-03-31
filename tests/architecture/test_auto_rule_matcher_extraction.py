#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of auto_rule_matcher db/logic operations.

Updated 2026-02-11: Adapted for competitive rule engine v2.0 architecture.
"""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/auto_rule_matcher.py")


class AutoRuleMatcherExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_module_imports_present(self):
        """Ensure both helper modules are imported."""
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertIn("services.auto_rule_matcher_db_ops", imported)
        self.assertIn("services.auto_rule_matcher_logic_ops", imported)

    def test_core_imports_from_logic_ops(self):
        """Ensure key functions/objects are imported from logic_ops."""
        tree = self._parse()
        logic_names = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "services.auto_rule_matcher_logic_ops":
                for alias in node.names:
                    logic_names.add(alias.name)
        # v2.0 core imports
        self.assertTrue(
            {"RULES", "SIGNAL_ICON", "evaluate_match"}.issubset(
                {n.lstrip("_") for n in logic_names} | logic_names
            ),
            msg=f"Expected v2.0 imports from logic_ops, got: {logic_names}",
        )

    def test_core_imports_from_db_ops(self):
        """Ensure key functions are imported from db_ops."""
        tree = self._parse()
        db_names = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module == "services.auto_rule_matcher_db_ops":
                for alias in node.names:
                    db_names.add(alias.name)
        # v2.0 core imports
        self.assertTrue(
            {"ensure_alert_table", "get_all_scheduled_match_ids", "get_upcoming_match_ids", "save_signal_summary"}.issubset(
                {n.lstrip("_") for n in db_names} | db_names
            ),
            msg=f"Expected v2.0 imports from db_ops, got: {db_names}",
        )

    def test_auto_rule_matcher_class_exists(self):
        """Ensure the AutoRuleMatcher class is defined."""
        tree = self._parse()
        class_names = {node.name for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn("AutoRuleMatcher", class_names)


if __name__ == "__main__":
    unittest.main()
