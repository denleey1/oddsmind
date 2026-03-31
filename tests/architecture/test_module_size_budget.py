#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Static guard to prevent oversized architecture modules from regressing."""

from __future__ import annotations

from pathlib import Path
import unittest

from tools.architecture.module_size_budget import check_budget, load_budget


class ModuleSizeBudgetTests(unittest.TestCase):
    def test_module_size_budget(self):
        repo_root = Path(__file__).resolve().parents[2]
        budget_path = repo_root / "tests" / "architecture" / "baselines" / "module_size_budget_v1.json"
        budget = load_budget(budget_path)
        ok, violations = check_budget(repo_root, budget)
        self.assertTrue(ok, msg=f"module size budget violations: {violations}")


if __name__ == "__main__":
    unittest.main()

