#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Static lifecycle guard tests for runtime one-shot initialization flags."""

from __future__ import annotations

import ast
import unittest
from pathlib import Path



class RuntimeSlowInitGuardTest(unittest.TestCase):
    def test_runtime_contains_slow_init_guards(self) -> None:
        runtime_file = Path("core/runtime.py")
        src = runtime_file.read_text(encoding="utf-8")
        tree = ast.parse(src)

        app_runtime = None
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "AppRuntime":
                app_runtime = node
                break
        self.assertIsNotNone(app_runtime, "AppRuntime class not found")

        method_names = {n.name for n in app_runtime.body if isinstance(n, ast.FunctionDef)}
        self.assertIn("mark_slow_initialization_started", method_names)
        self.assertIn("slow_initialization_started", method_names)


if __name__ == "__main__":
    unittest.main()
