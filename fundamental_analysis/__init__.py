#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fundamental analysis package.

v3.0 新增基于《欧赔基本面信心值_技术实现方案》的信心值计算引擎：
  - ConfidenceDataParser  : 从 titan007 分析页提取统计数据
  - ConfidenceCalculator  : S6-S12 完整计算流程
  - format_as_legacy_result : 兼容旧版输出格式

旧版（v2.x）组件仍保留，供回退使用：
  - FundamentalCalculator / FundamentalDataFetcher / etc.
"""

from fundamental_analysis.calculator import FundamentalCalculator
from fundamental_analysis.scraper import FundamentalDataFetcher, FundamentalScraper, FundamentalParser
from fundamental_analysis.league_manager import get_league_name
from fundamental_analysis.confidence_parser import ConfidenceDataParser, ConfidenceParseResult
from fundamental_analysis.confidence_calculator import (
    ConfidenceCalculator,
    ConfidenceResult,
    format_as_legacy_result,
)
from fundamental_analysis.confidence_engine import ConfidenceEngine
from fundamental_analysis.distribution_analyzer import (
    DistributionAnalyzer,
    DistributionResult,
    DistributionNode,
    TeamPower,
    TeamPowerResult,
)

__all__ = [
    # v3.0 新版
    'ConfidenceEngine',
    # 分布评估（基于近一场+主客场转换）
    'DistributionAnalyzer',
    'DistributionResult',
    'DistributionNode',
    'TeamPower',
    'TeamPowerResult',
    'ConfidenceDataParser',
    'ConfidenceParseResult',
    'ConfidenceCalculator',
    'ConfidenceResult',
    'format_as_legacy_result',
    # v2.x 旧版
    'FundamentalCalculator',
    'FundamentalDataFetcher',
    'FundamentalScraper',
    'FundamentalParser',
    'get_league_name',
]

__version__ = '3.0.0'
__author__ = 'OddsMind'
