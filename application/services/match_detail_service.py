#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Match detail service extracted from legacy app_services module."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from calculation.poisson_calculator import get_poisson_prediction
from application.services.match_detail_formatting_ops import (
    build_fundamental_analysis_data as _build_fundamental_analysis_data,
    format_analysis_data as _format_analysis_data,
    get_top_analyses as _get_top_analyses,
    safe_float as _safe_float,
    sort_analyses_by_priority as _sort_analyses_by_priority,
)
from application.services.match_detail_queries import (
    get_asian_handicap_odds as _get_asian_handicap_odds,
    get_match_basic_info as _get_match_basic_info,
    get_odds_analyses as _get_odds_analyses,
    get_team_standings as _get_team_standings,
    get_team_standings_batch as _get_team_standings_batch,
    resolve_canonical_match_id as _resolve_canonical_match_id,
)

logger = get_logger(__name__)


class MatchDetailService:
    """比赛详情服务"""

    def __init__(self):
        from app_helpers import get_team_logo
        from app_business import CompanySummaryCalculator

        self.get_team_logo = get_team_logo
        self.summary_calculator = CompanySummaryCalculator(Path(__file__).parent.parent.parent)
        self._canonical_match_id_cache: Dict[str, Optional[str]] = {}

    def get_match_basic_info(self, match_id: str) -> Optional[Dict[str, Any]]:
        return _get_match_basic_info(self, match_id)

    def _resolve_canonical_match_id(self, match_id: str) -> Optional[str]:
        return _resolve_canonical_match_id(self, match_id)

    def get_team_standings(self, team_id: int, league_id: int) -> Optional[Dict[str, Any]]:
        return _get_team_standings(team_id, league_id)

    def get_team_standings_batch(self, team_ids: List[int], league_id: int) -> Dict[int, Dict[str, Any]]:
        return _get_team_standings_batch(team_ids, league_id)

    def get_odds_analyses(self, match_id: str) -> List[Dict[str, Any]]:
        return _get_odds_analyses(match_id)

    @staticmethod
    def safe_float(value: Any, default: Any = None) -> Any:
        return _safe_float(value, default)

    def sort_analyses_by_priority(self, analyses: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
        return _sort_analyses_by_priority(analyses, limit)

    def format_analysis_data(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        return _format_analysis_data(analysis)

    def get_top_analyses(self, all_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return _get_top_analyses(all_analyses)

    def build_fundamental_analysis_data(self, match: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        return _build_fundamental_analysis_data(match)

    HANDICAP_VALUE_TO_TEXT = {
        -2.5: "两球半", -2.25: "两球/两球半", -2.0: "两球", -1.75: "球半/两球",
        -1.5: "球半", -1.25: "一球/球半", -1.0: "一球", -0.75: "半球/一球",
        -0.5: "半球", -0.25: "平手/半球", 0: "平手",
        0.25: "受让平手/半球", 0.5: "受让半球", 0.75: "受让半球/一球",
        1.0: "受让一球", 1.25: "受让一球/球半", 1.5: "受让球半",
        1.75: "受让球半/两球", 2.0: "受让两球", 2.25: "受让两球/两球半", 2.5: "受让两球半",
    }

    def _get_draw_system_analysis(self, match_id: str, match: Dict) -> Optional[Dict[str, Any]]:
        """获取长节点控赔 + 平系偏差分析数据"""
        try:
            from database.connection import get_connection
            from services.draw_system_analyzer import analyze_draw_deviation
            db = get_connection()
            result = analyze_draw_deviation(int(match_id), db)
            if result:
                return result
        except Exception as exc:
            logger.debug("Match %s: 平系分析异常 - %s", match_id, exc)

        try:
            from database.connection import get_connection
            db = get_connection()
            return self._get_node_only_analysis(int(match_id), match, db)
        except Exception as exc:
            logger.debug("Match %s: 节点分析异常 - %s", match_id, exc)
            return None

    def _get_node_only_analysis(self, match_id: int, match: Dict, db) -> Optional[Dict[str, Any]]:
        """仅从长节点/控赔数据返回分析结果（无大小球数据时的降级方案）"""
        from services.draw_system_analyzer import _try_load_long_node, normalize_to_94, _lookup_node_water, _estimate_system_from_draw94

        node_result = _try_load_long_node(match_id, db)
        if not node_result:
            return None

        ln = node_result['long_node']
        h94, d94, a94 = ln['home_94'], ln['draw_94'], ln['away_94']

        # 根据 draw_94 估算平系
        system_key = _estimate_system_from_draw94(d94)
        node_water = _lookup_node_water(system_key, h94, d94, a94)

        result = {
            "match_id": match_id,
            "odds_source": "long_node",
            "raw_home": ln['home_odds'],
            "raw_draw": ln['draw_odds'],
            "raw_away": ln['away_odds'],
            "home_94": h94,
            "draw_94": d94,
            "away_94": a94,
            "actual_return_rate": ln['return_rate'],
            "long_node_time": str(ln.get('change_time', '')),
            "long_node_duration_hours": ln.get('duration_hours'),
            "total_changes": node_result.get('total_changes'),
            "draw_system_name": f"{system_key}体系",
            "draw_system_source": "node_fallback",
            "draw_system_reason": "大小球缺失，按长节点 draw_94 区间回推平系",
            "water_level": node_water.get('water_level'),
            "zone_name": node_water.get('zone_name'),
            "standard_draw": node_water.get('standard_draw'),
        }

        ctrl = node_result.get('control_node')
        if ctrl:
            ch94, cd94, ca94 = ctrl['home_94'], ctrl['draw_94'], ctrl['away_94']
            ctrl_water = _lookup_node_water(_estimate_system_from_draw94(cd94), ch94, cd94, ca94)
            result["control_home"] = ctrl['home_odds']
            result["control_draw"] = ctrl['draw_odds']
            result["control_away"] = ctrl['away_odds']
            result["control_time"] = str(ctrl.get('change_time', ''))
            result["control_home_94"] = ch94
            result["control_draw_94"] = cd94
            result["control_away_94"] = ca94
            result["control_water_level"] = ctrl_water.get('water_level')
            result["control_zone_name"] = ctrl_water.get('zone_name')
            result["control_standard_draw"] = ctrl_water.get('standard_draw')

        from services.draw_system_analyzer import _attach_current_odds, WILLIAM_COMPANY_ID
        _attach_current_odds(match_id, db, result)

        # 即时盘水位
        if result.get('current_home_94') and result.get('current_draw_94') and result.get('current_away_94'):
            cur_d94 = result['current_draw_94']
            cur_water = _lookup_node_water(
                _estimate_system_from_draw94(cur_d94),
                result['current_home_94'], cur_d94, result['current_away_94']
            )
            result["current_water_level"] = cur_water.get('water_level')
            result["current_zone_name"] = cur_water.get('zone_name')
            result["current_standard_draw"] = cur_water.get('standard_draw')

        return result

    def _format_asian_handicap(self, match_id: str) -> Optional[Dict[str, Any]]:
        """查询并格式化亚盘数据（澳门）供前端展示"""
        try:
            ah = _get_asian_handicap_odds(match_id)
            if not ah:
                return None
            sf = self.safe_float
            initial_line = sf(ah.get("initial_handicap_line"))
            current_line = sf(ah.get("current_handicap_line"))
            return {
                "initial": {
                    "homeOdds": sf(ah.get("initial_home_odds")),
                    "handicapLine": initial_line,
                    "handicapText": self.HANDICAP_VALUE_TO_TEXT.get(initial_line, str(initial_line)) if initial_line is not None else None,
                    "awayOdds": sf(ah.get("initial_away_odds")),
                },
                "current": {
                    "homeOdds": sf(ah.get("current_home_odds")),
                    "handicapLine": current_line,
                    "handicapText": self.HANDICAP_VALUE_TO_TEXT.get(current_line, str(current_line)) if current_line is not None else None,
                    "awayOdds": sf(ah.get("current_away_odds")),
                },
                "companyName": "澳门",
                "companyId": 80,
            }
        except Exception as exc:
            logger.warning("查询亚盘数据失败 match_id=%s: %s", match_id, exc)
            return None

    def get_fundamental_analysis(self, match_id: str) -> Optional[Dict[str, Any]]:
        """提供分页接口使用的基本面分析数据，复用现有构建逻辑。"""
        match = self.get_match_basic_info(match_id)
        if not match:
            return None
        return self.build_fundamental_analysis_data(match)

    def get_complete_match_detail(self, match_id: str, include_poisson: bool = False) -> Dict[str, Any]:
        """获取完整的比赛详情。"""
        start_time = time.time()

        t_basic_start = time.time()
        match = self.get_match_basic_info(match_id)
        t_basic_end = time.time()
        if not match:
            return {"success": False, "error": "Match not found"}
        logger.debug(f"Match {match_id}: 基本信息查询耗时 {t_basic_end - t_basic_start:.3f}s")

        t_standings_start = time.time()
        standings_dict = self.get_team_standings_batch([match["home_team_id"], match["away_team_id"]], match["league_id"])
        home_standings = standings_dict.get(match["home_team_id"])
        away_standings = standings_dict.get(match["away_team_id"])
        t_standings_end = time.time()
        logger.debug(f"Match {match_id}: 积分榜查询耗时 {t_standings_end - t_standings_start:.3f}s")

        t_odds_start = time.time()
        all_analyses_raw = self.get_odds_analyses(match_id)
        t_odds_end = time.time()
        logger.debug(f"Match {match_id}: 赔率分析查询耗时 {t_odds_end - t_odds_start:.3f}s")

        poisson_prediction = None
        if include_poisson:
            t_poisson_start = time.time()
            try:
                logger.info(f"开始为比赛 {match_id} 计算泊松分布预测 (使用完全增强算法)...")
                poisson_prediction = get_poisson_prediction(
                    int(match_id),
                    use_dc=True,
                    time_decay=True,
                    half_life_days=150,
                    use_bivariate=True,
                )
                t_poisson_end = time.time()
                logger.info(
                    f"比赛 {match_id} 的泊松预测计算完成 (方法: {poisson_prediction.get('method', 'Unknown')}, "
                    f"耗时: {t_poisson_end - t_poisson_start:.3f}s)"
                )
            except Exception as exc:
                logger.error(f"为比赛 {match_id} 计算泊松分布时发生错误: {exc}", exc_info=True)
                poisson_prediction = {"error": f"泊松预测计算失败: {str(exc)}"}

        t_format_start = time.time()
        all_analyses_raw = self.sort_analyses_by_priority(all_analyses_raw, limit=None)
        all_analyses_list = []
        if all_analyses_raw:
            for analysis in all_analyses_raw:
                all_analyses_list.append(self.format_analysis_data(analysis))
        t_format_end = time.time()
        logger.debug(f"Match {match_id}: 数据格式化耗时 {t_format_end - t_format_start:.3f}s")

        top_analyses_list = self.get_top_analyses(all_analyses_list)

        t_summary_start = time.time()
        summary = self.summary_calculator.calculate_company_summary(all_analyses_raw) if all_analyses_raw else {}
        t_summary_end = time.time()
        logger.debug(f"Match {match_id}: 统计摘要计算耗时 {t_summary_end - t_summary_start:.3f}s")

        from application.services.web_match_listing_format_ops import _short_league_name

        draw_system_data = self._get_draw_system_analysis(match_id, match)

        result = {
            "matchId": match["match_id"],
            "leagueName": _short_league_name(match["league_name"]),
            "roundNumber": match.get("round_number"),
            "totalRounds": match.get("total_rounds"),
            "matchTime": match["match_time"].isoformat() if match["match_time"] else None,
            "homeTeam": match["home_team_name_cn"] or match["home_team_name"],
            "awayTeam": match["away_team_name_cn"] or match["away_team_name"],
            "homeTeamLogo": self.get_team_logo(match["home_team_name_cn"] or match["home_team_name"]),
            "awayTeamLogo": self.get_team_logo(match["away_team_name_cn"] or match["away_team_name"]),
            "matchStatus": match["match_status"],
            "homeScore": match["home_score"],
            "awayScore": match["away_score"],
            "standings": {"home": home_standings, "away": away_standings},
            "fundamentalAnalysis": self.build_fundamental_analysis_data(match),
            "oddsAnalysis": top_analyses_list[0] if top_analyses_list else None,
            "companyAnalyses": all_analyses_list,
            "totalCompanyCount": len(all_analyses_list),
            "companySummary": summary,
            "poissonPrediction": poisson_prediction,
            "asianHandicap": self._format_asian_handicap(match_id),
            "drawSystemAnalysis": draw_system_data,
        }

        total_time = time.time() - start_time
        logger.info(
            f"Match {match_id} detail completed in {total_time:.3f}s "
            f"(basic={t_basic_end-t_basic_start:.3f}s, standings={t_standings_end-t_standings_start:.3f}s, "
            f"odds={t_odds_end-t_odds_start:.3f}s, format={t_format_end-t_format_start:.3f}s, "
            f"summary={t_summary_end-t_summary_start:.3f}s)"
        )
        return {"success": True, "data": result}


__all__ = ["MatchDetailService"]
