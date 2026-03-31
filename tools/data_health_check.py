#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Operations report for monitoring match/odds data freshness."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import List, Dict, Any

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from database.connection import DatabaseConnection
from app_database import execute_query


def format_timedelta(delta) -> str:
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0
    minutes, sec = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if not parts:
        parts.append(f"{sec}s")
    return ' '.join(parts)


def get_last_match_update(conn: DatabaseConnection) -> Dict[str, Any]:
    row = conn.execute_query("SELECT MAX(updated_at) AS last_update FROM matches", fetch='one')
    last_update = row['last_update'] if row else None
    now = datetime.now(timezone.utc)
    if last_update and last_update.tzinfo is None:
        last_update = last_update.replace(tzinfo=timezone.utc)
    delta = format_timedelta(now - last_update) if last_update else 'N/A'
    return {
        'last_update': last_update.isoformat() if last_update else 'N/A',
        'age': delta,
    }


def get_finished_without_final_odds(conn: DatabaseConnection, limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT 
            m.match_id,
            m.league_id,
            m.match_time,
            m.updated_at,
            m.home_team_name,
            m.away_team_name
        FROM matches m
        WHERE m.match_status = 'finished'
          AND m.updated_at >= DATE_SUB(NOW(), INTERVAL 30 DAY)
          AND NOT EXISTS (
              SELECT 1 FROM european_odds eo
              WHERE eo.match_id = m.match_id
          )
        ORDER BY m.updated_at DESC
        LIMIT %s
    """
    rows = conn.execute_query(sql, (limit,), fetch='all') or []
    return rows


def get_pending_odds_sync(limit: int) -> List[Dict[str, Any]]:
    sql = """
        SELECT 
            m.match_id,
            m.updated_at AS match_updated_at,
            MAX(oc.last_updated) AS odds_last_updated
        FROM matches m
        LEFT JOIN odds_changes oc ON oc.match_id = m.match_id
        WHERE m.match_status IN ('scheduled', 'live')
          AND m.match_time BETWEEN DATE_SUB(NOW(), INTERVAL 1 DAY) AND DATE_ADD(NOW(), INTERVAL 3 DAY)
        GROUP BY m.match_id, m.updated_at
        HAVING odds_last_updated IS NULL OR TIMESTAMPDIFF(MINUTE, odds_last_updated, m.updated_at) > 15
        ORDER BY m.updated_at DESC
        LIMIT %s
    """
    return execute_query(sql, (limit,)) or []


def main():
    parser = argparse.ArgumentParser(description="Match/Odds data health report")
    parser.add_argument('--limit', type=int, default=20, help='Maximum rows to show for missing odds data')
    args = parser.parse_args()

    conn = DatabaseConnection()

    summary = get_last_match_update(conn)
    missing_final_odds = get_finished_without_final_odds(conn, args.limit)
    pending_sync = get_pending_odds_sync(args.limit)

    print("=== Matches table freshness ===")
    print(f"Last match update : {summary['last_update']}")
    print(f"Age since update  : {summary['age']}")

    print("\n=== Finished matches without european_odds ===")
    if not missing_final_odds:
        print("All recent finished matches have final odds.")
    else:
        for row in missing_final_odds:
            print(f"Match {row['match_id']} league {row['league_id']} updated {row['updated_at']} - {row['home_team_name']} vs {row['away_team_name']}")

    print("\n=== Upcoming matches pending odds sync ===")
    if not pending_sync:
        print("No scheduled/live matches waiting for odds sync.")
    else:
        for row in pending_sync:
            print(f"Match {row['match_id']} updated {row['match_updated_at']} latest odds {row['odds_last_updated']}")


if __name__ == '__main__':
    main()
