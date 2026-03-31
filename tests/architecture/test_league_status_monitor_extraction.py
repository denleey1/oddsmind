#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Guard league_status_monitor extraction into scan/state helper modules."""

from __future__ import annotations

import ast
from pathlib import Path
import unittest


TARGET = Path("services/league_status_monitor.py")


class LeagueStatusMonitorExtractionTests(unittest.TestCase):
    def _parse(self) -> ast.Module:
        return ast.parse(TARGET.read_text(encoding="utf-8"), filename=str(TARGET))

    def test_helper_modules_imported(self):
        tree = self._parse()
        imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module}

        self.assertTrue(
            {"league_status_monitor_scan_ops", "services.league_status_monitor_scan_ops"}.intersection(imported),
            msg=f"league_status_monitor_scan_ops import missing in {imported}",
        )
        self.assertTrue(
            {"league_status_monitor_state_ops", "services.league_status_monitor_state_ops"}.intersection(imported),
            msg=f"league_status_monitor_state_ops import missing in {imported}",
        )

    def test_class_methods_delegate(self):
        tree = self._parse()
        class_node = next(
            (node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "LeagueStatusMonitor"),
            None,
        )
        self.assertIsNotNone(class_node)

        methods = {node.name: node for node in class_node.body if isinstance(node, ast.FunctionDef)}
        expectations = {
            "get_status_distribution": "get_status_distribution_impl",
            "get_monitoring_stats": "get_monitoring_stats_impl",
            "_build_league_id_map": "build_league_id_map_impl",
            "_init_status_cache_from_db": "init_status_cache_from_db_impl",
            "_monitor_loop": "monitor_loop_impl",
            "_update_league_status": "update_league_status_impl",
            "_get_leagues_to_monitor": "get_leagues_to_monitor_impl",
            "_update_single_league": "update_single_league_impl",
            "_update_match_status_in_db": "update_match_status_in_db_impl",
            "_notify_odds_monitor": "notify_odds_monitor_impl",
        }

        for method_name, helper_name in expectations.items():
            self.assertIn(method_name, methods)
            helper_calls = [
                node
                for node in ast.walk(methods[method_name])
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == helper_name
            ]
            self.assertTrue(helper_calls, msg=f"{method_name} should call {helper_name}")


if __name__ == "__main__":
    unittest.main()
