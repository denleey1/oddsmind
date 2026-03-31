#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Company related helper services."""

from __future__ import annotations

from typing import Dict, Any, List

from application.context import PROJECT_ROOT, get_logger_for
from app_business import CompanySummaryCalculator

_logger = get_logger_for(__name__)
_calculator = CompanySummaryCalculator(PROJECT_ROOT)


def calculate_company_summary(companies: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Proxy to :class:`CompanySummaryCalculator` for compatibility."""
    return _calculator.calculate_company_summary(companies)


def get_company_summary_calculator() -> CompanySummaryCalculator:
    """Expose the underlying calculator when detailed access is needed."""
    return _calculator
