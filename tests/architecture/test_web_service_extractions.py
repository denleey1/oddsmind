#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Regression guards for extracted web service modules."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from application.services.web_match_listing import dedupe_same_match_rows, validate_match_status
from application.services import web_match_detail_payloads


class _LoggerStub:
    def __init__(self) -> None:
        self.messages = []

    def debug(self, message, *args):
        if args:
            self.messages.append(message % args)
        else:
            self.messages.append(message)

    def warning(self, message, *args):
        if args:
            self.messages.append(message % args)
        else:
            self.messages.append(message)


class _SummaryCalculatorStub:
    @staticmethod
    def calculate_company_summary(all_analyses_raw):
        return {"total": len(all_analyses_raw)}


class _MatchDetailServiceStub:
    def __init__(self):
        self.summary_calculator = _SummaryCalculatorStub()

    def get_odds_analyses(self, match_id):
        return [
            {"companyId": 1, "companyName": "A"},
            {"companyId": 2, "companyName": "B"},
        ]

    def sort_analyses_by_priority(self, analyses, limit=10):
        return analyses

    def format_analysis_data(self, analysis):
        return {"company_id": analysis["companyId"], "company_name": analysis["companyName"]}

    def get_top_analyses(self, all_analyses):
        return all_analyses[:1]

    def get_complete_match_detail(self, match_id, include_poisson=False):
        return {"success": True, "data": {"matchId": int(match_id)}}


def _match_detail_success():
    return {
        "success": True,
        "data": {
            "matchId": 99,
            "leagueName": "League",
            "roundNumber": 3,
            "totalRounds": 34,
            "matchTime": "2026-01-01T10:00:00",
            "homeTeam": "Home",
            "awayTeam": "Away",
            "homeTeamLogo": "h.png",
            "awayTeamLogo": "a.png",
            "matchStatus": "scheduled",
            "homeScore": None,
            "awayScore": None,
            "standings": {},
            "fundamentalAnalysis": {},
            "poissonPrediction": {"home": 1.2},
        },
    }


class WebServiceExtractionTests(unittest.TestCase):
    def test_validate_match_status_normalizes_and_rejects_invalid(self):
        logger = _LoggerStub()
        self.assertEqual(validate_match_status(" LIVE ", logger), "live")
        self.assertEqual(validate_match_status("BAD", logger), "")
        self.assertTrue(logger.messages)

    def test_dedupe_same_match_rows_prefers_more_complete_row(self):
        ts = datetime.utcnow()
        rows = [
            {
                "match_id": 10,
                "league_id": 1,
                "match_time": ts,
                "home_team_id": 100,
                "away_team_id": 200,
                "match_updated_at": ts,
                "has_odds_analysis": 0,
                "has_odds_changes": 0,
                "has_fundamental": 1,
            },
            {
                "match_id": 11,
                "league_id": 1,
                "match_time": ts,
                "home_team_id": 100,
                "away_team_id": 200,
                "match_updated_at": ts + timedelta(minutes=1),
                "has_odds_analysis": 1,
                "has_odds_changes": 1,
                "has_fundamental": 1,
            },
        ]
        deduped = dedupe_same_match_rows(rows)
        self.assertEqual(len(deduped), 1)
        self.assertEqual(deduped[0]["match_id"], 11)

    def test_pagination_full_keeps_legacy_all_companies_behavior(self):
        service = _MatchDetailServiceStub()
        with patch.object(web_match_detail_payloads, "get_match_detail", return_value=_match_detail_success()):
            payload, status = web_match_detail_payloads.build_public_match_detail_pagination_payload(
                match_id=99,
                load_type="full",
                page=3,
                page_size=1,
                requested_fields=None,
                match_detail_service=service,
            )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["data"]["company_analyses"]), 2)
        self.assertEqual(payload["data"]["pagination"]["page"], 1)
        self.assertEqual(payload["data"]["pagination"]["page_size"], 2)

    def test_pagination_non_standard_type_uses_paginated_branch(self):
        service = _MatchDetailServiceStub()
        with patch.object(web_match_detail_payloads, "get_match_detail", return_value=_match_detail_success()):
            payload, status = web_match_detail_payloads.build_public_match_detail_pagination_payload(
                match_id=99,
                load_type="other",
                page=2,
                page_size=1,
                requested_fields=None,
                match_detail_service=service,
            )
        self.assertEqual(status, 200)
        self.assertEqual(len(payload["data"]["company_analyses"]), 1)
        self.assertEqual(payload["data"]["pagination"]["page"], 2)
        self.assertEqual(payload["data"]["pagination"]["page_size"], 1)

    def test_public_match_detail_payload_cache_hit(self):
        service = _MatchDetailServiceStub()
        logger = _LoggerStub()
        cached = {"success": True, "data": {"matchId": 123}}
        with (
            patch.object(web_match_detail_payloads, "get_cache_key", return_value="key"),
            patch.object(web_match_detail_payloads, "cache_get", return_value=cached),
        ):
            payload, status, headers = web_match_detail_payloads.build_public_match_detail_payload(
                match_id=123,
                no_cache=False,
                match_detail_service=service,
                logger=logger,
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, cached)
        self.assertEqual(headers.get("X-Cache"), "HIT")


if __name__ == "__main__":
    unittest.main()
