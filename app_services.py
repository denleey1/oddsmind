#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Compatibility facade for legacy ``app_services`` imports.

Implementation has been split into dedicated modules under ``application.services``.
This module intentionally re-exports the previous public classes/constants so
existing imports continue to work without behavior changes.
"""

from __future__ import annotations

from application.services.fundamental_analysis_service import FundamentalAnalysisService
from application.services.odds_analysis_service import OddsAnalysisService
from application.services.monitoring_initialization_service import (
    COMPANY_NAME_LOOKUP,
    MonitoringInitializationService,
)
from application.services.match_detail_service import MatchDetailService

__all__ = [
    "COMPANY_NAME_LOOKUP",
    "FundamentalAnalysisService",
    "OddsAnalysisService",
    "MonitoringInitializationService",
    "MatchDetailService",
]