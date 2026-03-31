#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Match-level operations extracted from MatchStatusUpdater."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional


def get_or_create_team_id(updater, team_name: str) -> Optional[int]:
    """Get existing team_id by name or create one if missing."""
    if not team_name:
        return None

    try:
        team = updater.db.execute_query(
            "SELECT team_id FROM teams WHERE name_cn = %s LIMIT 1",
            (team_name,),
            fetch="one",
        )
        if team:
            return team["team_id"]

        team_id = int(hashlib.md5(team_name.encode('utf-8')).hexdigest()[:8], 16) % (10 ** 9)
        if team_id < 0:
            team_id = -team_id

        try:
            updater.db.execute_query(
                """
                INSERT INTO teams (team_id, name_cn, created_at)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE name_cn = VALUES(name_cn)
                """,
                (team_id, team_name),
            )
            return team_id
        except Exception as exc:
            team = updater.db.execute_query(
                "SELECT team_id FROM teams WHERE team_id = %s LIMIT 1",
                (team_id,),
                fetch="one",
            )
            if team:
                return team["team_id"]
            team = updater.db.execute_query(
                "SELECT team_id FROM teams WHERE name_cn = %s LIMIT 1",
                (team_name,),
                fetch="one",
            )
            if team:
                return team["team_id"]
            raise exc

    except Exception as exc:
        updater.logger.error("获取或创建球队 %s 失败: %s", team_name, exc)
        return None


def ensure_team_record(updater, team_id: Optional[int], team_name: str) -> Optional[int]:
    """
    Ensure team exists in teams table.

    - Prefer explicit team_id if provided.
    - Fallback to team-name lookup/create.
    """
    try:
        if team_id:
            exists = updater.db.execute_query(
                "SELECT 1 FROM teams WHERE team_id = %s LIMIT 1",
                (team_id,),
                fetch="one",
            )
            if exists:
                return team_id

            safe_name = team_name or f"Team_{team_id}"
            updater.db.execute_query(
                """
                INSERT INTO teams (team_id, name_cn, created_at)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE name_cn = VALUES(name_cn)
                """,
                (team_id, safe_name),
            )
            return team_id

        if team_name:
            return get_or_create_team_id(updater, team_name)

        return None

    except Exception as exc:
        updater.logger.error("确保球队记录存在失败 (id=%s, name=%s): %s", team_id, team_name, exc)
        return None


def update_single_match(updater, league_id: int, match_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update one match row, creating match/team rows when needed."""
    result = {
        "updated": False,
        "status_changed": False,
        "is_new": False,
        "old_status": None,
        "new_status": None,
    }

    match_id = match_data.get("match_id")
    if not match_id:
        return result

    try:
        existing = updater.db.execute_query(
            "SELECT match_id, match_status, match_time, home_score, away_score, updated_at FROM matches WHERE match_id = %s",
            (match_id,),
            fetch="one",
        )
        new_status = match_data.get("match_status", "scheduled")
        new_match_time = match_data.get("match_time")
        new_home_score = match_data.get("home_score")
        new_away_score = match_data.get("away_score")
        new_round_status = match_data.get("round_status")

        if existing:
            old_status = existing["match_status"]
            old_home_score = existing.get("home_score")
            old_away_score = existing.get("away_score")
            new_division = match_data.get("division")
            needs_update = (
                old_status != new_status
                or str(existing["match_time"]) != str(new_match_time)
                or old_home_score != new_home_score
                or old_away_score != new_away_score
                or updater._is_outdated(existing["updated_at"])
            )
            if needs_update:
                new_season = match_data.get("season")
                new_round_number = match_data.get("round_number")
                updater.db.execute_query(
                    """
                    UPDATE matches
                    SET match_status = %s,
                        round_status = %s,
                        division = COALESCE(%s, division),
                        season = COALESCE(%s, season),
                        round_number = COALESCE(%s, round_number),
                        match_time = %s,
                        home_score = %s,
                        away_score = %s,
                        updated_at = NOW()
                    WHERE match_id = %s
                    """,
                    (new_status, new_round_status, new_division, new_season, new_round_number, new_match_time, new_home_score, new_away_score, match_id),
                )
                result["updated"] = True
                if old_status != new_status:
                    result.update({
                        "status_changed": True,
                        "old_status": old_status,
                        "new_status": new_status,
                    })
                    updater.logger.info("比赛 %s 状态变化: %s -> %s", match_id, old_status, new_status)
        else:
            home_team_name = match_data.get("home_team_name", "")
            away_team_name = match_data.get("away_team_name", "")

            home_team_id = ensure_team_record(updater, match_data.get("home_team_id"), home_team_name)
            if not home_team_id and home_team_name:
                home_team_id = get_or_create_team_id(updater, home_team_name)

            away_team_id = ensure_team_record(updater, match_data.get("away_team_id"), away_team_name)
            if not away_team_id and away_team_name:
                away_team_id = get_or_create_team_id(updater, away_team_name)

            if not home_team_id or not away_team_id:
                updater.logger.warning(
                    "无法获取team_id，跳过插入比赛 %s (home: %s, away: %s)",
                    match_id, home_team_name, away_team_name
                )
                return result

            ensure_team_record(updater, home_team_id, home_team_name)
            ensure_team_record(updater, away_team_id, away_team_name)

            division = match_data.get("division")
            season = match_data.get("season")
            round_number = match_data.get("round_number")
            insert_sql = """
                INSERT INTO matches (match_id, league_id, division, season, round_number,
                                      match_status, match_time,
                                      home_team_id, away_team_id,
                                      home_team_name, away_team_name, home_score, away_score,
                                      created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON DUPLICATE KEY UPDATE
                    match_status = VALUES(match_status),
                    division = COALESCE(VALUES(division), division),
                    season = COALESCE(VALUES(season), season),
                    round_number = COALESCE(VALUES(round_number), round_number),
                    match_time = VALUES(match_time),
                    home_score = VALUES(home_score),
                    away_score = VALUES(away_score),
                    updated_at = NOW()
            """
            params = (
                match_id,
                league_id,
                division,
                season,
                round_number,
                new_status,
                new_match_time,
                home_team_id,
                away_team_id,
                home_team_name,
                away_team_name,
                new_home_score,
                new_away_score,
            )

            try:
                updater.db.execute_query(insert_sql, params)
            except Exception as exc:
                if "foreign key constraint fails" in str(exc):
                    updater.logger.warning("插入比赛 %s 触发外键约束，尝试补齐球队后重试...", match_id)
                    ensure_team_record(updater, home_team_id, home_team_name)
                    ensure_team_record(updater, away_team_id, away_team_name)
                    updater.db.execute_query(insert_sql, params)
                else:
                    raise

            result.update({
                "updated": True,
                "is_new": True,
                "new_status": new_status,
            })
            updater.logger.info("新增比赛 %s 状态: %s", match_id, new_status)

        return result

    except Exception as exc:
        updater.logger.error("更新比赛 %s 状态失败: %s", match_id, exc)
        return result


__all__ = [
    "get_or_create_team_id",
    "ensure_team_record",
    "update_single_match",
]
