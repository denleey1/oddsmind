#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Helpers for module line-count budget checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Tuple


def load_budget(path: Path) -> Dict[str, int]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_lines(path: Path) -> int:
    return path.read_text(encoding="utf-8").count("\n") + 1


def check_budget(repo_root: Path, budget: Dict[str, int]) -> Tuple[bool, Dict[str, Dict[str, int]]]:
    violations: Dict[str, Dict[str, int]] = {}
    for rel_path, max_lines in budget.items():
        full_path = repo_root / rel_path
        if not full_path.exists():
            violations[rel_path] = {"max_lines": max_lines, "actual_lines": -1}
            continue
        actual = count_lines(full_path)
        if actual > int(max_lines):
            violations[rel_path] = {"max_lines": int(max_lines), "actual_lines": actual}
    return (len(violations) == 0, violations)


__all__ = ["check_budget", "count_lines", "load_budget"]

