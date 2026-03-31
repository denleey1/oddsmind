#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
一次性修复：合并/标记 matches 表中的“同场重复 match_id”问题。

背景
----
Titan007 的 matchResult 数据偶发同一场比赛 match_id 变更，导致我们数据库出现：
  同 league_id + match_time + home_team_id + away_team_id 的两条 matches 记录

风险与策略
----------
本脚本默认采用“最保守”的修复策略：
1) 选择 canonical_match_id（优先有 odds_analysis_results / odds_changes / fundamental_analysis）
2) 将旧 match_id 在关联表中的记录迁移到 canonical（UPDATE ... SET match_id = canonical）
3) 将旧 match_id 对应的 matches 记录标记为 is_deleted=1（不直接删除，便于回滚）

可回滚
------
如果你只执行到“标记 is_deleted”，回滚只需把 is_deleted 置回 0。
如果执行了关联表迁移，回滚需要反向更新（建议先备份/导出相关表）。

用法
----
在服务器环境变量里已有 MYSQL_* 配置（oddsmind.env），直接运行：

    /home/ubuntu/oddsmind/venv/bin/python tools/dedupe_duplicate_matches.py --league-id 17 --dry-run
    /home/ubuntu/oddsmind/venv/bin/python tools/dedupe_duplicate_matches.py --league-id 17 --apply

可选参数：
    --start-date / --end-date  仅处理某个时间区间的比赛（match_time）
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from app_database import execute_query, execute_update


@dataclass(frozen=True)
class MatchKey:
    league_id: int
    match_time: str
    home_team_id: int
    away_team_id: int


def _pick_canonical(rows: List[Dict]) -> Dict:
    def score(r: Dict):
        return (
            int(r.get("has_odds_analysis") or 0),
            int(r.get("has_odds_changes") or 0),
            int(r.get("has_fundamental") or 0),
            r.get("match_updated_at"),
            int(r.get("match_id") or 0),
        )

    return max(rows, key=score)


def find_duplicate_groups(league_id: Optional[int], start_date: Optional[str], end_date: Optional[str]) -> List[MatchKey]:
    where = []
    params: List = []
    if league_id is not None:
        where.append("league_id = %s")
        params.append(league_id)
    if start_date:
        where.append("match_time >= %s")
        params.append(start_date)
    if end_date:
        where.append("match_time <= %s")
        params.append(end_date)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    sql = f"""
        SELECT league_id, match_time, home_team_id, away_team_id
        FROM matches
        {where_sql}
        GROUP BY league_id, match_time, home_team_id, away_team_id
        HAVING COUNT(*) > 1
        ORDER BY league_id, match_time
    """
    rows = execute_query(sql, tuple(params))
    return [
        MatchKey(
            league_id=int(r["league_id"]),
            match_time=str(r["match_time"]),
            home_team_id=int(r["home_team_id"]),
            away_team_id=int(r["away_team_id"]),
        )
        for r in rows
    ]


def load_group_matches(key: MatchKey) -> List[Dict]:
    sql = """
        SELECT
            m.match_id,
            m.updated_at as match_updated_at,
            m.is_deleted,
            CASE WHEN oar_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_analysis,
            CASE WHEN oc_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_changes,
            CASE WHEN fa_exists.match_id IS NULL THEN 0 ELSE 1 END as has_fundamental
        FROM matches m
        LEFT JOIN (SELECT DISTINCT match_id FROM odds_analysis_results) oar_exists
            ON oar_exists.match_id = m.match_id
        LEFT JOIN (SELECT DISTINCT match_id FROM odds_changes) oc_exists
            ON oc_exists.match_id = m.match_id
        LEFT JOIN (SELECT DISTINCT match_id FROM fundamental_analysis) fa_exists
            ON fa_exists.match_id = m.match_id
        WHERE m.league_id = %s
          AND m.match_time = %s
          AND m.home_team_id = %s
          AND m.away_team_id = %s
    """
    return execute_query(sql, (key.league_id, key.match_time, key.home_team_id, key.away_team_id))


def migrate_related_tables(old_id: int, new_id: int, dry_run: bool) -> List[str]:
    """
    将旧 match_id 的关联表记录迁移到新 match_id。
    注意：如目标表存在唯一约束，可能需要额外去重策略；目前以“尽量迁移”为主。
    """
    statements = [
        ("UPDATE odds_changes SET match_id=%s WHERE match_id=%s", (new_id, old_id)),
        ("UPDATE over_under_odds_changes SET match_id=%s WHERE match_id=%s", (new_id, old_id)),
        ("UPDATE european_odds SET match_id=%s WHERE match_id=%s", (new_id, old_id)),
        ("UPDATE odds_analysis_results SET match_id=%s WHERE match_id=%s", (new_id, old_id)),
        ("UPDATE fundamental_analysis SET match_id=%s WHERE match_id=%s", (new_id, old_id)),
        ("UPDATE match_ai_analysis SET match_id=%s WHERE match_id=%s", (str(new_id), str(old_id))),
    ]
    executed = []
    for sql, params in statements:
        executed.append(sql % tuple(["?"] * len(params)))
        if not dry_run:
            execute_update(sql, params)
    return executed


def mark_deleted(match_id: int, dry_run: bool) -> None:
    if dry_run:
        return
    execute_update("UPDATE matches SET is_deleted=1, updated_at=NOW() WHERE match_id=%s", (match_id,))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--league-id", type=int, default=None, help="仅处理指定联赛（例如 17=荷乙）")
    parser.add_argument("--start-date", type=str, default=None, help="match_time >= start_date (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default=None, help="match_time <= end_date (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="仅打印将执行的动作，不落库")
    parser.add_argument("--apply", action="store_true", help="实际执行落库变更")
    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        raise SystemExit("必须指定 --dry-run 或 --apply")
    if args.dry_run and args.apply:
        raise SystemExit("--dry-run 与 --apply 只能选其一")

    groups = find_duplicate_groups(args.league_id, args.start_date, args.end_date)
    print(f"发现重复组: {len(groups)}")
    changed = 0

    for key in groups:
        rows = load_group_matches(key)
        if len(rows) < 2:
            continue
        canonical = _pick_canonical(rows)
        canonical_id = int(canonical["match_id"])
        olds = [int(r["match_id"]) for r in rows if int(r["match_id"]) != canonical_id]

        print(f"\n[{key.league_id}] {key.match_time} {key.home_team_id} vs {key.away_team_id}")
        print(f"  canonical: {canonical_id} (oa={canonical['has_odds_analysis']}, oc={canonical['has_odds_changes']}, fa={canonical['has_fundamental']})")
        print(f"  olds: {olds}")

        for old_id in olds:
            migrate_related_tables(old_id, canonical_id, dry_run=args.dry_run)
            if args.apply:
                mark_deleted(old_id, dry_run=False)
            changed += 1

    print(f"\n处理完成。涉及旧match_id数量: {changed} (dry_run={args.dry_run})")


if __name__ == "__main__":
    main()


