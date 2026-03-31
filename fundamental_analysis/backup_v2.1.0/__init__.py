#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fundamental analysis package exposing the legacy-compatible calculator and helpers."""

from fundamental_analysis.calculator import FundamentalCalculator
from fundamental_analysis.scraper import FundamentalDataFetcher, FundamentalScraper, FundamentalParser
from fundamental_analysis.league_manager import get_league_name

__all__ = [
    'FundamentalCalculator',
    'FundamentalDataFetcher',
    'FundamentalScraper',
    'FundamentalParser',
    'get_league_name',
]

__version__ = '2.1.0'
__author__ = 'OddsMind'
