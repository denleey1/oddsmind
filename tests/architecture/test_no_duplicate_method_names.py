#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard against accidental duplicate method definitions in key classes."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET_CLASSES = [
    (Path("database/manager.py"), "DatabaseManager"),
    (Path("services/monitoring_coordinator.py"), "MonitoringCoordinator"),
    (Path("services/scheduled_data_updater.py"), "ScheduledDataUpdater"),
]


class NoDuplicateMethodNamesTests(unittest.TestCase):
    def test_no_duplicate_method_names(self):
        for path, class_name in TARGET_CLASSES:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            class_node = next(
                (
                    node
                    for node in tree.body
                    if isinstance(node, ast.ClassDef) and node.name == class_name
                ),
                None,
            )
            self.assertIsNotNone(class_node, msg=f"class {class_name} missing in {path}")

            seen = set()
            duplicates = []
            for node in class_node.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.name in seen:
                        duplicates.append(node.name)
                    seen.add(node.name)

            self.assertFalse(
                duplicates,
                msg=f"duplicate methods in {path}::{class_name}: {sorted(set(duplicates))}",
            )


if __name__ == "__main__":
    unittest.main()
