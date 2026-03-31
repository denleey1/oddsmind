#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard extraction of repository upsert-heavy logic."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("database/repository.py")


class RepositoryUpsertExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_upsert_ops_import_present(self):
        tree = self._parse()
        imported = set()
        for node in tree.body:
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        self.assertTrue(
            {"repository_upsert_ops", "database.repository_upsert_ops"}.intersection(imported),
            msg=f"repository_upsert_ops import missing in {imported}",
        )

    def test_base_upsert_and_odds_batch_upsert_delegate(self):
        tree = self._parse()
        class_nodes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        self.assertIn("BaseRepository", class_nodes)
        self.assertIn("OddsRepository", class_nodes)

        base_methods = {
            node.name: node
            for node in class_nodes["BaseRepository"].body
            if isinstance(node, ast.FunctionDef)
        }
        odds_methods = {
            node.name: node
            for node in class_nodes["OddsRepository"].body
            if isinstance(node, ast.FunctionDef)
        }

        self.assertIn("upsert", base_methods)
        self.assertIn("_batch_upsert_odds", odds_methods)

        upsert_calls = [
            node
            for node in ast.walk(base_methods["upsert"])
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "_upsert_record"
        ]
        self.assertTrue(upsert_calls, msg="BaseRepository.upsert should call _upsert_record")

        batch_calls = [
            node
            for node in ast.walk(odds_methods["_batch_upsert_odds"])
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_batch_upsert_odds_impl"
        ]
        self.assertTrue(batch_calls, msg="OddsRepository._batch_upsert_odds should call _batch_upsert_odds_impl")


if __name__ == "__main__":
    unittest.main()
