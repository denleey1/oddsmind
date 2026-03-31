#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
欧赔意图分析模块 v2
"""

from application.services.odds_intent_v2.analyzer import OddsIntentAnalyzer
from application.services.odds_intent_v2.schemas import AnalyzeRequest, AnalyzeResponse

__all__ = ['OddsIntentAnalyzer', 'AnalyzeRequest', 'AnalyzeResponse']

