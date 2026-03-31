#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Odds analysis service extracted from legacy app_services module."""

from __future__ import annotations

from typing import Any, Dict, List

from core.logger import get_logger
from app_database import execute_query

logger = get_logger(__name__)


class OddsAnalysisService:
    """赔率分析服务"""

    def get_unanalyzed_matches(self) -> List[Dict[str, Any]]:
        """获取未分析的比赛列表"""
        unanalyzed_sql = """
        SELECT DISTINCT oc.match_id,
               m.home_team_name, m.away_team_name,
               COUNT(DISTINCT oc.company_id) as company_count
        FROM odds_changes oc
        JOIN matches m ON m.match_id = oc.match_id
        LEFT JOIN odds_analysis_results oar ON oar.match_id = oc.match_id
        WHERE oar.match_id IS NULL
        GROUP BY oc.match_id, m.home_team_name, m.away_team_name
        ORDER BY oc.match_id
        """
        return execute_query(unanalyzed_sql)

    def log_unanalyzed_matches(self, matches: List[Dict[str, Any]]) -> None:
        """记录未分析的比赛信息"""
        logger.info(f"发现 {len(matches)} 场比赛在 odds_changes 中有数据但未分析")

        for match in matches[:5]:
            logger.info(
                f"  比赛 {match['match_id']}: {match.get('home_team_name', 'N/A')} vs "
                f"{match.get('away_team_name', 'N/A')} ({match['company_count']} 家公司)"
            )

        if len(matches) > 5:
            logger.info(f"  ... 还有 {len(matches) - 5} 场比赛")

    def batch_analyze_matches(self, match_ids: List[str]) -> List[Dict[str, Any]]:
        """批量分析比赛赔率"""
        import os
        from odds_analysis.realtime_analyzer import RealtimeOddsAnalyzer

        logger.info(f"开始批量分析 {len(match_ids)} 场未分析的比赛...")
        max_workers = int(os.getenv("EXECUTOR_MAX_WORKERS", "16"))
        logger.info(f"使用 {max_workers} 个工作线程进行批量分析")

        batch_analyzer = RealtimeOddsAnalyzer(max_workers=max_workers)
        results = []

        try:
            results = batch_analyzer.batch_analyze_matches(match_ids)
            success_count = sum(1 for row in results if row.get("success"))
            logger.info(f"批量分析完成: {success_count}/{len(match_ids)} 成功")
        except Exception as exc:
            logger.error(f"批量分析失败: {exc}")
        finally:
            try:
                batch_analyzer.shutdown()
            except Exception:
                pass

        return results

    def log_analysis_results(self, matches: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> None:
        """记录分析结果"""
        for match in matches:
            match_id = match["match_id"]
            result = next((row for row in results if row.get("match_id") == match_id), None)
            if result and result.get("success"):
                logger.info(
                    f"✓ 比赛 {match_id} ({match.get('home_team_name', 'N/A')} vs "
                    f"{match.get('away_team_name', 'N/A')}) 分析完成"
                )

    def analyze_existing_odds_changes(self) -> None:
        """分析所有已存在于 odds_changes 表中但未分析的比赛"""
        try:
            logger.info("检查 odds_changes 表中未分析的比赛...")

            unanalyzed_matches = self.get_unanalyzed_matches()
            if not unanalyzed_matches:
                logger.info("所有 odds_changes 中的比赛都已完成分析")
                return

            self.log_unanalyzed_matches(unanalyzed_matches)
            match_ids = [row["match_id"] for row in unanalyzed_matches]
            results = self.batch_analyze_matches(match_ids)
            self.log_analysis_results(unanalyzed_matches, results)

        except Exception as exc:
            logger.error(f"检查未分析比赛失败: {exc}", exc_info=True)


__all__ = ["OddsAnalysisService"]

