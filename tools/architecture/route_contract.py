#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Static route contract extraction and comparison helpers.

This module intentionally avoids importing the Flask app so it can run in
minimal CI/dev environments where optional runtime dependencies are not
installed.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


@dataclass(frozen=True)
class RouteContract:
    rule: str
    methods: Tuple[str, ...]
    module: str
    function: str

    @property
    def key(self) -> Tuple[str, str, str]:
        return (self.rule, self.module, self.function)

    def to_dict(self) -> Dict[str, object]:
        payload = asdict(self)
        payload["methods"] = list(self.methods)
        return payload


def _normalise_methods(value: ast.AST | None) -> Tuple[str, ...]:
    if value is None:
        return ("GET",)
    if isinstance(value, (ast.List, ast.Tuple, ast.Set)):
        methods: List[str] = []
        for node in value.elts:
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                methods.append(node.value.upper())
        return tuple(sorted(set(methods))) or ("GET",)
    return ("GET",)


def _extract_rule(value: ast.AST | None) -> str | None:
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return value.value
    return None


def _is_route_decorator(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    return isinstance(func, ast.Attribute) and func.attr == "route"


def extract_routes_from_file(repo_root: Path, file_path: Path) -> List[RouteContract]:
    rel_module = file_path.relative_to(repo_root).as_posix().replace("/", ".")
    if rel_module.endswith(".py"):
        rel_module = rel_module[:-3]

    tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    contracts: List[RouteContract] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        for deco in node.decorator_list:
            if not _is_route_decorator(deco):
                continue

            call = deco
            assert isinstance(call, ast.Call)

            rule = _extract_rule(call.args[0]) if call.args else None
            if not rule:
                continue

            methods_arg = None
            for kw in call.keywords:
                if kw.arg == "methods":
                    methods_arg = kw.value
                    break

            contracts.append(
                RouteContract(
                    rule=rule,
                    methods=_normalise_methods(methods_arg),
                    module=rel_module,
                    function=node.name,
                )
            )

    return contracts


def discover_route_files(repo_root: Path) -> List[Path]:
    files: List[Path] = []
    routes_dir = repo_root / "application" / "routes"
    if routes_dir.exists():
        files.extend(sorted(routes_dir.rglob("*.py")))
    auth_file = repo_root / "auth.py"
    if auth_file.exists():
        files.append(auth_file)
    return files


def collect_route_contract(repo_root: Path) -> List[RouteContract]:
    all_contracts: List[RouteContract] = []
    for file_path in discover_route_files(repo_root):
        all_contracts.extend(extract_routes_from_file(repo_root, file_path))
    return sorted(all_contracts, key=lambda c: (c.rule, ",".join(c.methods), c.module, c.function))


def save_contract(path: Path, contracts: Sequence[RouteContract]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [c.to_dict() for c in contracts]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_contract(path: Path) -> List[RouteContract]:
    data = json.loads(path.read_text(encoding="utf-8"))
    contracts: List[RouteContract] = []
    for item in data:
        contracts.append(
            RouteContract(
                rule=item["rule"],
                methods=tuple(item["methods"]),
                module=item["module"],
                function=item["function"],
            )
        )
    return contracts


def diff_contract(
    baseline: Sequence[RouteContract],
    current: Sequence[RouteContract],
) -> Dict[str, List[Dict[str, object]]]:
    baseline_map = {c.key: c for c in baseline}
    current_map = {c.key: c for c in current}

    missing: List[Dict[str, object]] = []
    unexpected: List[Dict[str, object]] = []
    method_changes: List[Dict[str, object]] = []

    for key, old in baseline_map.items():
        now = current_map.get(key)
        if now is None:
            missing.append(old.to_dict())
            continue
        if set(old.methods) != set(now.methods):
            method_changes.append(
                {
                    "rule": old.rule,
                    "module": old.module,
                    "function": old.function,
                    "baseline_methods": list(old.methods),
                    "current_methods": list(now.methods),
                }
            )

    for key, now in current_map.items():
        if key not in baseline_map:
            unexpected.append(now.to_dict())

    return {
        "missing": missing,
        "unexpected": unexpected,
        "method_changes": method_changes,
    }

