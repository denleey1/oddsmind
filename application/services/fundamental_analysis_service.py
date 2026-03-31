#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fundamental analysis service — v3.0 基于信心值引擎."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Tuple

from core.logger import get_logger
from app_database import execute_query, execute_update
from fundamental_analysis.confidence_engine import ConfidenceEngine

logger = get_logger(__name__)


class FundamentalAnalysisService:
    """基本面分析服务（v3.0 信心值引擎）"""

    def __init__(self):
        self.engine = ConfidenceEngine()

    def has_existing_analysis(self, match_id: str) -> bool:
        """检查比赛是否已有基本面分析"""
        check_sql = "SELECT 1 FROM fundamental_analysis WHERE match_id = %s"
        result = execute_query(check_sql, (match_id,))
        return bool(result)

    def recalculate_all_fundamental(self) -> Tuple[int, int]:
        """重新计算基本面分析表中所有match_id的基本面分析（覆盖现有结果）"""
        logger.info("开始重新计算基本面分析表中所有比赛的基本面分析...")

        sql = "SELECT DISTINCT match_id FROM fundamental_analysis ORDER BY match_id"
        results = execute_query(sql)

        if not results:
            logger.info("基本面分析表中没有数据")
            return 0, 0

        match_ids = [str(row["match_id"]) for row in results]
        total_count = len(match_ids)
        logger.info(f"找到 {total_count} 场比赛需要重新计算基本面分析")

        success_count = 0
        failed_count = 0

        batch_size = 10
        for i in range(0, total_count, batch_size):
            batch = match_ids[i : i + batch_size]
            logger.info(f"处理批次 {i//batch_size + 1}/{(total_count-1)//batch_size + 1}: {len(batch)} 场比赛")

            for match_id in batch:
                try:
                    logger.info(f"重新计算比赛 {match_id} 的基本面分析...")
                    result = self.analyze_single_match(match_id)

                    if result.get("success"):
                        success_count += 1
                        logger.info(f"✓ 比赛 {match_id} 重新计算成功")
                    else:
                        failed_count += 1
                        error = result.get("error", "未知错误")
                        logger.warning(f"✗ 比赛 {match_id} 重新计算失败: {error}")

                    time.sleep(0.5)

                except Exception as exc:
                    failed_count += 1
                    logger.error(f"✗ 比赛 {match_id} 处理出错: {exc}", exc_info=True)

            if i + batch_size < total_count:
                time.sleep(2)

        logger.info(f"重新计算完成！成功: {success_count} 场，失败: {failed_count} 场，总计: {total_count} 场")
        return success_count, failed_count

    def analyze_single_match(self, match_id: str) -> Dict[str, Any]:
        """分析单场比赛的基本面数据（v3.0 信心值引擎）"""
        try:
            from config.monitoring_config import MONITORED_LEAGUES

            check_sql = """
            SELECT m.league_id, l.name_cn as league_name
            FROM matches m
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE m.match_id = %s
            """
            results = execute_query(check_sql, (match_id,))
            match_info = results[0] if results else None

            if not match_info:
                logger.debug(f"比赛 {match_id} 不存在，跳过基本面分析")
                return {"success": False, "error": "比赛不存在"}

            league_id = match_info.get("league_id")
            league_name = match_info.get("league_name", "未知")

            if league_id not in MONITORED_LEAGUES:
                logger.debug(f"比赛 {match_id} 属于非核心联赛 {league_name} (ID: {league_id})，跳过基本面分析")
                return {"success": False, "error": f"非核心联赛: {league_name}"}

            logger.info(f"开始分析比赛 {match_id} 的基本面数据（联赛: {league_name}）")

            result = self.engine.analyze(str(match_id))
            if not result:
                return {"success": False, "error": "无法获取或解析基本面数据"}

            self._persist_analysis(str(match_id), result)
            logger.info(f"成功分析并保存比赛 {match_id} 的基本面数据")
            return {"success": True, "result": result}

        except Exception as exc:
            logger.error(f"分析比赛 {match_id} 时出错: {exc}", exc_info=True)
            return {"success": False, "error": str(exc)}

    def _persist_analysis(self, match_id: str, result: Dict[str, Any]) -> None:
        """将信心值分析结果写入 fundamental_analysis 表"""
        scores = result.get("final_scores", {})
        ca = result.get("confidence_analysis", {})

        def _ser(v):
            return json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v

        bi = result.get("basic_info", {})
        home_ca = ca.get("home_win", {})
        draw_ca = ca.get("draw", {})
        away_ca = ca.get("away_win", {})
        absent_data = self._build_absent_players_json(result)

        # match_id 不是 UNIQUE 约束，用 DELETE + INSERT 保证幂等
        execute_update("DELETE FROM fundamental_analysis WHERE match_id = %s", (int(match_id),))

        # 提取分布节点数据
        dist = result.get("distribution") or {}
        distribution_node = dist.get("distribution_node") or None
        distribution_json = _ser(dist) if dist else None

        sql = """
            INSERT INTO fundamental_analysis (
                match_id, home_team, away_team, league,
                home_win_score, home_confidence_level, home_confidence_interval, home_odds_suggestions,
                draw_score, draw_confidence_level, draw_confidence_interval, draw_odds_suggestions,
                away_win_score, away_confidence_level, away_confidence_interval, away_odds_suggestions,
                confidence_level, recommended_outcome, max_score, analysis_data,
                pull_direction, pull_description, prompts_json, absent_players_json,
                briefing, upcoming_json,
                distribution_node, distribution_json,
                updated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s,
                NOW()
            )
        """

        params = (
            int(match_id),
            bi.get("home_team", ""),
            bi.get("away_team", ""),
            bi.get("league", ""),
            scores.get("home_win"),
            home_ca.get("level"),
            home_ca.get("interval"),
            _ser(home_ca.get("odds_suggestions", [])),
            scores.get("draw"),
            draw_ca.get("level"),
            draw_ca.get("interval"),
            _ser(draw_ca.get("odds_suggestions", [])),
            scores.get("away_win"),
            away_ca.get("level"),
            away_ca.get("interval"),
            _ser(away_ca.get("odds_suggestions", [])),
            result.get("confidence_level"),
            result.get("recommended_outcome"),
            result.get("max_score"),
            json.dumps(result, ensure_ascii=False, default=str),
            result.get("pull_direction"),
            result.get("pull_description"),
            _ser(result.get("prompts", [])),
            _ser(absent_data),
            result.get("briefing", ""),
            _ser(result.get("upcoming", {})),
            distribution_node,
            distribution_json,
        )

        execute_update(sql, params)

    def _build_absent_players_json(self, result: Dict[str, Any]) -> Dict[str, list]:
        """从 prompts 中提取缺阵球员信息"""
        home_absent = []
        away_absent = []
        home_team = result.get("basic_info", {}).get("home_team", "")
        prompts = result.get("prompts", [])
        for p in prompts:
            if "缺阵" not in p:
                continue
            if home_team and home_team in p:
                home_absent.append(p)
            else:
                away_absent.append(p)
        return {"home": home_absent, "away": away_absent}

    def batch_analyze_fundamental(self, match_ids: List[str]) -> Tuple[int, int]:
        """批量分析比赛的基本面数据"""
        logger.info(f"开始批量分析 {len(match_ids)} 场比赛的基本面数据...")

        success_count = 0
        failed_count = 0

        for match_id in match_ids:
            if self.has_existing_analysis(match_id):
                logger.debug(f"比赛 {match_id} 已有基本面分析，跳过")
                continue

            result = self.analyze_single_match(match_id)
            if result["success"]:
                success_count += 1
            else:
                failed_count += 1
                logger.warning(f"比赛 {match_id} 分析失败: {result.get('error')}")

            time.sleep(0.5)

        logger.info(f"批量基本面分析完成: 成功 {success_count} 场，失败 {failed_count} 场")
        return success_count, failed_count


__all__ = ["FundamentalAnalysisService"]

