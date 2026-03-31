#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compatibility checks for the legacy app_services facade module."""

from __future__ import annotations

import unittest

import app_services
from application.services.fundamental_analysis_service import FundamentalAnalysisService
from application.services.odds_analysis_service import OddsAnalysisService
from application.services.monitoring_initialization_service import (
    COMPANY_NAME_LOOKUP,
    MonitoringInitializationService,
)
from application.services.match_detail_service import MatchDetailService


class AppServicesFacadeTests(unittest.TestCase):
    def test_reexports_match_new_modules(self):
        self.assertIs(app_services.FundamentalAnalysisService, FundamentalAnalysisService)
        self.assertIs(app_services.OddsAnalysisService, OddsAnalysisService)
        self.assertIs(app_services.MonitoringInitializationService, MonitoringInitializationService)
        self.assertIs(app_services.MatchDetailService, MatchDetailService)
        self.assertIs(app_services.COMPANY_NAME_LOOKUP, COMPANY_NAME_LOOKUP)

    def test_all_exports(self):
        expected = {
            "COMPANY_NAME_LOOKUP",
            "FundamentalAnalysisService",
            "OddsAnalysisService",
            "MonitoringInitializationService",
            "MatchDetailService",
        }
        self.assertEqual(set(app_services.__all__), expected)


if __name__ == "__main__":
    unittest.main()

