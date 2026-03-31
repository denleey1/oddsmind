#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Fundamental analysis calculator aligned with the legacy implementation."""

from typing import Any, Dict, List, Optional
import logging
import json

from fundamental_analysis.fundamental_analysis_analyzer import MatchAnalyzer
from app_database import execute_update
from database.manager import DatabaseManager


class FundamentalCalculator:
    """Wrapper around the legacy MatchAnalyzer to keep scores identical to the old version."""

    def __init__(self) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.analyzer = MatchAnalyzer()
        self.home_team: str = ""
        self.away_team: str = ""
        self.league_name: str = ""

    def calculate_analysis_with_storage(
        self,
        parsed_data: Dict[str, Any],
        match_id: Optional[str] = None,
        save_to_db: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """Compatibility wrapper that mirrors the legacy behaviour (no database writes)."""
        result = self.calculate_analysis_scores(parsed_data)
        if not result:
            return None

        scores = result.get("final_scores", {})
        result["confidence_analysis"] = self._generate_confidence_analysis(scores)
        result["saved_to_db"] = False

        if save_to_db and match_id:
            try:
                self._persist_analysis(match_id, result)
                result["saved_to_db"] = True
            except Exception as exc:
                self.logger.error(
                    "Failed to persist fundamental analysis for match %s: %s",
                    match_id,
                    exc,
                    exc_info=True,
                )
        return result

    def calculate_analysis_scores(self, parsed_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Calculate scores using the original legacy logic."""
        try:
            basic_info = parsed_data.get("basic_info", {})
            self.home_team = basic_info.get("home_team", "")
            self.away_team = basic_info.get("away_team", "")
            match_id = parsed_data.get("match_id")

            self.league_name = (basic_info.get("league") or basic_info.get("league_name") or "").strip()
            self.analyzer.set_teams(self.home_team, self.away_team, self.league_name)

            formatted_data = self._prepare_data_for_analysis(parsed_data)
            ratings = self.analyzer.calculate_ratings(formatted_data)
            if not ratings:
                return None

            final_scores = {
                "home_win": ratings.get("home_win_score", 0.0),
                "draw": ratings.get("draw_score", 0.0),
                "away_win": ratings.get("away_win_score", 0.0),
            }

            confidence_levels = {
                "home_win": self._get_confidence_from_score(final_scores["home_win"]),
                "draw": self._get_confidence_from_score(final_scores["draw"]),
                "away_win": self._get_confidence_from_score(final_scores["away_win"]),
            }

            result: Dict[str, Any] = {
                "match_id": match_id,
                "basic_info": basic_info,
                "final_scores": final_scores,
                "confidence_levels": confidence_levels,
                "confidence_level": ratings.get("confidence_level", ""),
                "recommended_outcome": self._get_recommended_outcome(ratings),
                "max_score": max(final_scores.values()) if final_scores else 0.0,
                "weights": {
                    "recent": 0.30,
                    "home_away": 0.40,
                    "h2h": 0.30,
                    "has_h2h_data": bool(formatted_data.get("history")),
                },
            }

            self._generate_odds_patterns(result)
            self.logger.info(
                "Fundamental scores calculated: home %.1f, draw %.1f, away %.1f",
                final_scores["home_win"],
                final_scores["draw"],
                final_scores["away_win"],
            )
            return result
        except Exception as exc:  # pragma: no cover - defensive guard
            self.logger.error("Failed to calculate fundamental analysis scores: %s", exc, exc_info=True)
            return None

    def _persist_analysis(self, match_id: str, result: Dict[str, Any]) -> None:
        """Persist fundamental analysis into the database."""
        final_scores = result.get("final_scores", {})
        confidence_levels = result.get("confidence_levels", {})
        confidence_analysis = result.get("confidence_analysis", {})

        def _serialize(value):
            if isinstance(value, (list, dict)):
                return json.dumps(value, ensure_ascii=False)
            return value

        def _analysis_field(key: str, field: str):
            data = confidence_analysis.get(key, {})
            return _serialize(data.get(field))

        sql = """
            INSERT INTO fundamental_analysis (
                match_id,
                home_team,
                away_team,
                league,
                home_win_score,
                home_confidence_level,
                home_confidence_interval,
                home_odds_suggestions,
                draw_score,
                draw_confidence_level,
                draw_confidence_interval,
                draw_odds_suggestions,
                away_win_score,
                away_confidence_level,
                away_confidence_interval,
                away_odds_suggestions,
                confidence_level,
                recommended_outcome,
                max_score,
                analysis_data,
                data_source_count,
                processing_duration,
                updated_at
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                NOW()
            )
            ON DUPLICATE KEY UPDATE
                home_team = VALUES(home_team),
                away_team = VALUES(away_team),
                league = VALUES(league),
                home_win_score = VALUES(home_win_score),
                home_confidence_level = VALUES(home_confidence_level),
                home_confidence_interval = VALUES(home_confidence_interval),
                home_odds_suggestions = VALUES(home_odds_suggestions),
                draw_score = VALUES(draw_score),
                draw_confidence_level = VALUES(draw_confidence_level),
                draw_confidence_interval = VALUES(draw_confidence_interval),
                draw_odds_suggestions = VALUES(draw_odds_suggestions),
                away_win_score = VALUES(away_win_score),
                away_confidence_level = VALUES(away_confidence_level),
                away_confidence_interval = VALUES(away_confidence_interval),
                away_odds_suggestions = VALUES(away_odds_suggestions),
                confidence_level = VALUES(confidence_level),
                recommended_outcome = VALUES(recommended_outcome),
                max_score = VALUES(max_score),
                analysis_data = VALUES(analysis_data),
                data_source_count = VALUES(data_source_count),
                processing_duration = VALUES(processing_duration),
                updated_at = VALUES(updated_at)
        """

        params = (
            int(match_id),
            self.home_team,
            self.away_team,
            self.league_name,
            final_scores.get("home_win"),
            confidence_levels.get("home_win"),
            _analysis_field("home_win", "interval"),
            _analysis_field("home_win", "odds_suggestions"),
            final_scores.get("draw"),
            confidence_levels.get("draw"),
            _analysis_field("draw", "interval"),
            _analysis_field("draw", "odds_suggestions"),
            final_scores.get("away_win"),
            confidence_levels.get("away_win"),
            _analysis_field("away_win", "interval"),
            _analysis_field("away_win", "odds_suggestions"),
            result.get("confidence_level"),
            result.get("recommended_outcome"),
            result.get("max_score"),
            json.dumps(result, ensure_ascii=False),
            result.get("data_source_count"),
            result.get("processing_duration"),
        )

        execute_update(sql, params)

    def _prepare_data_for_analysis(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Transform parsed data into the structure expected by the legacy analyzer."""
        analysis_data = parsed_data.get("analysis_data", parsed_data)

        formatted_data = {
            "history": [],
            "home_team_history": [],
            "away_team_history": [],
        }

        if "head_to_head" in analysis_data:
            formatted_data["history"] = self._convert_match_records(analysis_data["head_to_head"])
        elif "history" in analysis_data:
            formatted_data["history"] = self._ensure_list_format(analysis_data["history"])

        if "home_recent_league" in analysis_data:
            formatted_data["home_team_history"] = self._convert_match_records(analysis_data["home_recent_league"])
        elif "home_team_history" in analysis_data:
            formatted_data["home_team_history"] = self._ensure_list_format(analysis_data["home_team_history"])

        if "away_recent_league" in analysis_data:
            formatted_data["away_team_history"] = self._convert_match_records(analysis_data["away_recent_league"])
        elif "away_team_history" in analysis_data:
            formatted_data["away_team_history"] = self._ensure_list_format(analysis_data["away_team_history"])

        return formatted_data

    def _convert_match_records(self, records: List[Any]) -> List[List[Any]]:
        """Convert match record objects into the list-of-lists format used by the legacy logic."""
        result: List[List[Any]] = []
        for record in records:
            if hasattr(record, "is_valid") and getattr(record, "is_valid"):
                row = [
                    record.date,
                    "",
                    record.league,
                    "",
                    0,
                    record.home_team,
                    "",
                    record.away_team,
                    record.home_score,
                    record.away_score,
                    record.half_score,
                    record.handicap,
                    record.home_score - record.away_score,
                ]
                result.append(row)
            elif isinstance(record, list):
                result.append(record)
        return result

    def _ensure_list_format(self, data: Any) -> List[List[Any]]:
        """Ensure the given data is in list-of-lists format."""
        if not isinstance(data, list):
            return []
        if data and isinstance(data[0], list):
            return data
        return []

    def _get_confidence_level(self, max_score: float) -> str:
        if max_score >= 9.0:
            return "极致信心"
        if max_score >= 7.9:
            return "信心充足"
        if max_score >= 6.8:
            return "信心中高"
        if max_score >= 5.7:
            return "信心中上"
        if max_score >= 4.4:
            return "信心中庸"
        if max_score >= 3.3:
            return "信心中下"
        if max_score >= 2.2:
            return "信心中低"
        if max_score >= 1.1:
            return "信心不足"
        return "欠缺信心"

    def _get_recommended_outcome(self, ratings: Dict[str, Any]) -> str:
        scores = {
            "home_win": ratings.get("home_win_score", 0.0),
            "draw": ratings.get("draw_score", 0.0),
            "away_win": ratings.get("away_win_score", 0.0),
        }
        return max(scores, key=scores.get)

    def _get_confidence_from_score(self, score: float) -> str:
        if score >= 9.0:
            return "极致信心"
        if score >= 7.9:
            return "信心充足"
        if score >= 6.8:
            return "信心中高"
        if score >= 5.7:
            return "信心中上"
        if score >= 4.4:
            return "信心中庸"
        if score >= 3.3:
            return "信心中下"
        if score >= 2.2:
            return "信心中低"
        if score >= 1.1:
            return "信心不足"
        return "欠缺信心"

    def _generate_odds_patterns(self, result: Dict[str, Any]) -> None:
        confidence = result.get("confidence_level", "")
        recommended = result.get("recommended_outcome", "")
        patterns = self._get_odds_patterns_by_confidence(confidence, recommended)
        result["odds_patterns"] = patterns

    def _get_odds_patterns_by_confidence(self, confidence: str, outcome: str) -> List[str]:
        """根据信心等级获取赔率规律"""
        base_patterns = {
            "欠缺信心": {
                "home_win": ["实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水", "实开盘低水"],
                "draw": ["实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水", "实开盘低水"],
                "away_win": ["实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水", "实开盘低水"],
            },
            "信心不足": {
                "home_win": ["实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水", "实开盘低水"],
                "draw": ["实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水", "实开盘低水"],
                "away_win": ["实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水", "实开盘低水"],
            },
            "信心中低": {
                "home_win": ["韬光盘低水", "韬光盘超低水", "实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水"],
                "draw": ["韬光盘低水", "韬光盘超低水", "实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水"],
                "away_win": ["韬光盘低水", "韬光盘超低水", "实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水", "实开盘中低水"],
            },
            "信心中下": {
                "home_win": ["韬光盘中低水", "韬光盘低水", "韬光盘超低水", "实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水"],
                "draw": ["韬光盘中低水", "韬光盘低水", "韬光盘超低水", "实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水"],
                "away_win": ["韬光盘中低水", "韬光盘低水", "韬光盘超低水", "实开盘超高水", "实开盘高水", "实开盘中高水", "实开盘中水"],
            },
            "信心中庸": {
                "home_win": ["实开盘超高水", "实开盘高水", "实开盘中低水", "实开盘低水", "超实盘高水", "超实盘中高水", "韬光盘中低水", "韬光盘低水"],
                "draw": ["实开盘超高水", "实开盘高水", "实开盘中低水", "实开盘低水", "超实盘高水", "超实盘中高水", "韬光盘中低水", "韬光盘低水"],
                "away_win": ["实开盘超高水", "实开盘高水", "实开盘中低水", "实开盘低水", "超实盘高水", "超实盘中高水", "韬光盘中低水", "韬光盘低水"],
            },
            "信心中上": {
                "home_win": ["实开盘中水", "实开盘中低水", "实开盘低水", "实开盘超低水", "超实盘超高水", "超实盘高水", "超实盘中高水", "超实盘中水"],
                "draw": ["实开盘中水", "实开盘中低水", "实开盘低水", "实开盘超低水", "超实盘超高水", "超实盘高水", "超实盘中高水", "超实盘中水"],
                "away_win": ["实开盘中水", "实开盘中低水", "实开盘低水", "实开盘超低水", "超实盘超高水", "超实盘高水", "超实盘中高水", "超实盘中水"],
            },
            "信心中高": {
                "home_win": ["实开盘低水", "实开盘超低水", "超实盘高水", "超实盘中高水", "超实盘中水", "超实盘中低水", "超实盘低水", "超实盘超低水"],
                "draw": ["实开盘低水", "实开盘超低水", "超实盘高水", "超实盘中高水", "超实盘中水", "超实盘中低水", "超实盘低水", "超实盘超低水"],
                "away_win": ["实开盘低水", "实开盘超低水", "超实盘高水", "超实盘中高水", "超实盘中水", "超实盘中低水", "超实盘低水", "超实盘超低水"],
            },
            "信心充足": {
                "home_win": ["超实盘中低水", "超实盘低水", "超实盘超低水", "超散盘中高水", "超深盘中上水", "超深盘中下水"],
                "draw": ["超实盘中低水", "超实盘低水", "超实盘超低水", "超散盘中高水", "超深盘中上水", "超深盘中下水"],
                "away_win": ["超实盘中低水", "超实盘低水", "超实盘超低水", "超散盘中高水", "超深盘中上水", "超深盘中下水"],
            },
            "极致信心": {
                "home_win": ["超实盘低水", "超实盘超低水", "超散盘中高水", "超深诱盘"],
                "draw": ["超实盘低水", "超实盘超低水", "超散盘中高水", "超深诱盘"],
                "away_win": ["超实盘低水", "超实盘超低水", "超散盘中高水", "超深诱盘"],
            },
        }

        confidence_patterns = base_patterns.get(confidence)
        if confidence_patterns and outcome in confidence_patterns:
            return confidence_patterns[outcome]
        return ["实开盘中水", "实开盘中低水", "实开盘低水"]

    def _generate_confidence_analysis(self, scores: Dict[str, float]) -> Dict[str, Dict[str, Any]]:
        """Generate detailed confidence analysis for each outcome."""

        home_score = scores.get("home_win", 0.0)
        draw_score = scores.get("draw", 0.0)
        away_score = scores.get("away_win", 0.0)

        def get_confidence_level(score: float) -> str:
            if score >= 9.0:
                return "极致信心"
            if score >= 7.9:
                return "信心充足"
            if score >= 6.8:
                return "信心中高"
            if score >= 5.7:
                return "信心中上"
            if score >= 4.4:
                return "信心中庸"
            if score >= 3.3:
                return "信心中下"
            if score >= 2.2:
                return "信心中低"
            if score >= 1.1:
                return "信心不足"
            return "欠缺信心"

        def get_confidence_interval(score: float) -> str:
            if score >= 9.0:
                return "[9.0-10.0]"
            if score >= 7.9:
                return "[7.9-8.9]"
            if score >= 6.8:
                return "[6.8-7.8]"
            if score >= 5.7:
                return "[5.7-6.7]"
            if score >= 4.4:
                return "[4.4-5.6]"
            if score >= 3.3:
                return "[3.3-4.3]"
            if score >= 2.2:
                return "[2.2-3.2]"
            if score >= 1.1:
                return "[1.1-2.1]"
            return "[0.0-1.0]"

        def get_odds_suggestions(confidence_level: str) -> List[str]:
            rules_map = {
                "欠缺信心": [
                    "实开盘高水",
                    "实开盘中高水",
                    "实开盘中水",
                    "实开盘中低水",
                    "实开盘低水"
                ],
                "信心不足": [
                    "实开盘超高水",
                    "实开盘高水",
                    "实开盘中高水",
                    "实开盘中水",
                    "实开盘中低水",
                    "实开盘低水"
                ],
                "信心中低": [
                    "韬光盘低水",
                    "韬光盘超低水",
                    "实开盘超高水",
                    "实开盘高水",
                    "实开盘中高水",
                    "实开盘中水",
                    "实开盘中低水"
                ],
                "信心中下": [
                    "韬光盘中低水",
                    "韬光盘低水",
                    "韬光盘超低水",
                    "实开盘超高水",
                    "实开盘高水",
                    "实开盘中高水",
                    "实开盘中水"
                ],
                "信心中庸": [
                    "实开盘超高水",
                    "实开盘高水",
                    "实开盘中低水",
                    "实开盘低水",
                    "超实盘高水",
                    "超实盘中高水",
                    "韬光盘中低水",
                    "韬光盘低水"
                ],
                "信心中上": [
                    "实开盘中水",
                    "实开盘中低水",
                    "实开盘低水",
                    "实开盘超低水",
                    "超实盘超高水",
                    "超实盘高水",
                    "超实盘中高水",
                    "超实盘中水"
                ],
                "信心中高": [
                    "实开盘低水",
                    "实开盘超低水",
                    "超实盘高水",
                    "超实盘中高水",
                    "超实盘中水",
                    "超实盘中低水",
                    "超实盘低水",
                    "超实盘超低水"
                ],
                "信心充足": [
                    "超实盘中低水",
                    "超实盘低水",
                    "超实盘超低水",
                    "超散盘中高水",
                    "超深盘中上水",
                    "超深盘中下水"
                ],
                "极致信心": [
                    "超实盘低水",
                    "超实盘超低水",
                    "超散盘中高水",
                    "超深诱盘"
                ],
            }
            return rules_map.get(confidence_level, [])

        return {
            "home_win": {
                "level": get_confidence_level(home_score),
                "interval": get_confidence_interval(home_score),
                "odds_suggestions": get_odds_suggestions(get_confidence_level(home_score)),
            },
            "draw": {
                "level": get_confidence_level(draw_score),
                "interval": get_confidence_interval(draw_score),
                "odds_suggestions": get_odds_suggestions(get_confidence_level(draw_score)),
            },
            "away_win": {
                "level": get_confidence_level(away_score),
                "interval": get_confidence_interval(away_score),
                "odds_suggestions": get_odds_suggestions(get_confidence_level(away_score)),
            },
        }


if __name__ == "__main__":
    calculator = FundamentalCalculator()
    print("Legacy fundamental analysis calculator ready")
