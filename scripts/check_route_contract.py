#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Check current static route contract against baseline."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.architecture.route_contract import collect_route_contract, diff_contract, load_contract


def main() -> int:
    repo_root = REPO_ROOT
    baseline_path = repo_root / "tests" / "architecture" / "baselines" / "route_contract_static_v1.json"
    if not baseline_path.exists():
        print(f"Baseline not found: {baseline_path}")
        return 2

    baseline = load_contract(baseline_path)
    current = collect_route_contract(repo_root)
    result = diff_contract(baseline, current)

    has_diff = any(result.values())
    if has_diff:
        print("Route contract drift detected:")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1

    print(f"Route contract check passed ({len(current)} routes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
