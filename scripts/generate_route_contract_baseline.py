#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate static route contract baseline used by architecture guardrails."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.architecture.route_contract import collect_route_contract, save_contract


def main() -> int:
    repo_root = REPO_ROOT
    out_path = repo_root / "tests" / "architecture" / "baselines" / "route_contract_static_v1.json"
    contracts = collect_route_contract(repo_root)
    save_contract(out_path, contracts)
    print(f"Generated route contract baseline: {out_path} ({len(contracts)} routes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
