#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
信心值计算引擎 - 统一入口

端到端流程：match_id → 抓取HTML → 解析 → 计算 → 输出

使用方式:
    from fundamental_analysis.confidence_engine import ConfidenceEngine

    engine = ConfidenceEngine()
    result = engine.analyze(match_id="2804581")
    print(result)

    # 或者直接从已有 HTML 计算
    result = engine.analyze_html(html_content, match_id="2804581")
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path

from fundamental_analysis.scraper import FundamentalScraper
from fundamental_analysis.confidence_parser import ConfidenceDataParser, ConfidenceParseResult
from fundamental_analysis.confidence_calculator import (
    ConfidenceCalculator,
    ConfidenceResult,
    format_as_legacy_result,
)
from fundamental_analysis.match_themes import detect_themes
from fundamental_analysis.distribution_analyzer import DistributionAnalyzer

logger = logging.getLogger(__name__)


class ConfidenceEngine:
    """
    信心值计算引擎 - 端到端入口

    整合 Scraper + ConfidenceDataParser + ConfidenceCalculator，
    提供从 match_id 到最终信心值的完整流程。
    """

    def __init__(self):
        self.scraper = FundamentalScraper()
        self.parser = ConfidenceDataParser()
        self.calculator = ConfidenceCalculator()
        self.distribution_analyzer = DistributionAnalyzer()
        self.logger = logging.getLogger(self.__class__.__name__)

    def analyze(
        self,
        match_id: str,
        save_html: bool = True,
        handicap_line: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """
        端到端分析：抓取 → 解析 → 计算

        Args:
            match_id: 比赛ID（titan007格式）
            save_html: 是否保存HTML快照
            handicap_line: 底层盘口让球数（主队视角），默认0.0

        Returns:
            兼容旧版格式的结果字典，若失败返回 None
        """
        html_content = self.scraper.fetch_match_analysis(match_id)
        if not html_content:
            self.logger.error(f"无法获取比赛 {match_id} 的HTML")
            return None

        if save_html:
            self._save_snapshot(match_id, html_content)

        return self.analyze_html(html_content, match_id, handicap_line=handicap_line)

    def analyze_html(
        self,
        html_content: str,
        match_id: str = "",
        handicap_line: float = 0.0,
    ) -> Optional[Dict[str, Any]]:
        """
        从 HTML 内容直接计算信心值 + 分布节点评估。

        Args:
            html_content: 分析页完整HTML
            match_id: 比赛ID（用于标识）
            handicap_line: 底层盘口让球数（主队视角，正数=主队让球）。
                           0.5=平半, 0.75=半一, 1.0=让一球

        Returns:
            兼容旧版格式的结果字典，含 distribution 字段
        """
        # 解析
        parsed = self.parser.parse(html_content, match_id)

        if not parsed.is_valid():
            self.logger.error(f"比赛 {match_id} 解析失败: {parsed.parse_errors}")
            return None

        # 信心值计算
        conf_result = self.calculator.calculate(parsed)

        # 赛事题材检测（德比、保级、争冠、复仇等）
        theme_prompts = detect_themes(parsed)
        if theme_prompts:
            conf_result.prompts = theme_prompts + conf_result.prompts

        # 分布节点评估（新增：基于近一场+主客场转换）
        try:
            dist_result = self.distribution_analyzer.analyze(parsed, handicap_line)
            distribution_dict = dist_result.to_dict()
        except Exception as exc:
            self.logger.warning("分布评估失败，跳过: %s", exc, exc_info=True)
            distribution_dict = {"distribution_node": "评估失败", "error": str(exc)}

        # 转为兼容格式
        legacy_result = format_as_legacy_result(parsed, conf_result)

        # 注入分布评估结果
        legacy_result["distribution"] = distribution_dict

        self.logger.info(
            "比赛 %s 分析完成: %s(%s) vs %s(%s) | 分布: %s",
            match_id,
            parsed.home_team, f"{conf_result.home_score:.2f}",
            parsed.away_team, f"{conf_result.away_score:.2f}",
            distribution_dict.get("distribution_node", "-"),
        )

        return legacy_result

    def analyze_raw(self, html_content: str, match_id: str = "") -> Optional[ConfidenceResult]:
        """
        返回原始 ConfidenceResult 对象（非兼容格式）

        Args:
            html_content: 分析页完整HTML
            match_id: 比赛ID

        Returns:
            ConfidenceResult 对象
        """
        parsed = self.parser.parse(html_content, match_id)
        if not parsed.is_valid():
            return None
        return self.calculator.calculate(parsed)

    def _save_snapshot(self, match_id: str, html_content: str):
        try:
            logs_dir = Path('logs/html_snapshots')
            logs_dir.mkdir(parents=True, exist_ok=True)
            path = logs_dir / f"analysis_{match_id}.html"
            path.write_text(html_content, encoding='utf-8', errors='ignore')
        except Exception as e:
            self.logger.debug(f"保存快照失败: {e}")


if __name__ == '__main__':
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
    )

    engine = ConfidenceEngine()

    if len(sys.argv) > 1:
        for arg in sys.argv[1:]:
            path = Path(arg)
            if path.exists():
                html = path.read_text(encoding='utf-8', errors='ignore')
                mid = path.stem.replace('analysis_', '')
                result = engine.analyze_html(html, mid)
            else:
                result = engine.analyze(arg)

            if result:
                import json
                print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
            else:
                print(f"分析失败: {arg}")
    else:
        print("用法: python -m fundamental_analysis.confidence_engine <match_id_or_html_path>")
        print("示例: python -m fundamental_analysis.confidence_engine 2804581")
        print("示例: python -m fundamental_analysis.confidence_engine logs/html_snapshots/analysis_2804581.html")
