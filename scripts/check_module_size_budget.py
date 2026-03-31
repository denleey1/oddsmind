#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check architecture module size budget constraints."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.architecture.module_size_budget import check_budget, load_budget


def main() -> int:
    repo_root = REPO_ROOT
    budget_path = repo_root / "tests" / "architecture" / "baselines" / "module_size_budget_v1.json"

    if not budget_path.exists():
        print(f"Budget file not found: {budget_path}")
        return 2

    budget = load_budget(budget_path)
    ok, violations = check_budget(repo_root, budget)
    if ok:
        print(f"Module size budget check passed ({len(budget)} files)")
        return 0

    print("Module size budget check failed.")
    print(json.dumps(violations, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
