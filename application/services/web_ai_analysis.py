#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Business orchestration for web AI analysis routes."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from application.services.web_ai_formatting import format_analysis_text


def _parse_company_id(payload: Optional[Dict[str, Any]], default: int = 115) -> int:
    company_id = payload.get("company_id", default) if payload else default
    try:
        return int(company_id)
    except (ValueError, TypeError):
        return default


def _build_available_companies(analysis_data: Dict[str, Any]) -> List[str]:
    companies = []
    for company in analysis_data.get("companyAnalyses", []):
        cid = company.get("companyId")
        cname = company.get("companyName", "Unknown")
        if cid:
            companies.append(f"{cname}(ID:{cid})")
    return companies


def build_ai_analysis_payload(
    match_id: int,
    request_json: Optional[Dict[str, Any]],
    logger: Any,
) -> Tuple[Dict[str, Any], int]:
    """Build payload for ``/api/matches/<id>/ai-analysis``."""
    from application.services.match_analysis_service import get_match_analysis_data
    from application.services.odds_intent_helper import prepare_odds_intent_input
    from application.services.odds_intent_service import analyze_odds_intent

    analysis_result = get_match_analysis_data(str(match_id))
    if not analysis_result.get("success"):
        return analysis_result, 404

    company_id = _parse_company_id(request_json, default=115)
    intent_input = prepare_odds_intent_input(analysis_result["data"], company_id=company_id)
    if not intent_input:
        available_companies = _build_available_companies(analysis_result.get("data", {}))
        available_info = (
            f"可用公司: {', '.join(available_companies)}"
            if available_companies
            else "无可用公司数据"
        )
        return {
            "success": False,
            "error": (
                f"无法从公司ID {company_id} 及其备用公司提取完整的骨架区间和赔率数据。"
                f"请确保比赛有完整的分析数据。{available_info}"
            ),
            "available_companies": available_companies,
        }, 400

    exclude_mode = request_json.get("exclude_mode", False) if request_json else False
    try:
        result = analyze_odds_intent(
            match_id=str(match_id),
            skeleton=intent_input["skeleton"],
            odds_open=intent_input["odds_open"],
            odds_live=intent_input["odds_live"],
            context={
                "company_id": intent_input.get("company_id"),
                "company_name": intent_input.get("company_name"),
                "exclude_mode": exclude_mode,
            },
        )
    except Exception as exc:
        logger.error("欧赔意图分析失败: %s", exc, exc_info=True)
        return {"success": False, "error": f"分析失败: {str(exc)}"}, 500

    analysis_text = format_analysis_text(result, analysis_result["data"])
    pick = result.get("pick", "N/A")
    pick_name = {"H": "主胜", "D": "平局", "A": "客胜"}.get(pick, pick)
    exclude_info = ""
    if result.get("exclude"):
        exclude = result.get("exclude")
        exclude_name = {"H": "主胜", "D": "平局", "A": "客胜"}.get(exclude, exclude)
        exclude_info = f" | 排除: {exclude_name}"
    final_judgment = (
        f"{pick_name} | {result.get('intent_summary', '')}{exclude_info} | "
        f"置信度: {result.get('confidence', 0)}%"
    )

    return {
        "success": True,
        "data": {
            "analysis": analysis_text,
            "finalJudgment": final_judgment,
            "oddsIntent": result,
            "matchInfo": analysis_result["data"].get("matchInfo", {}),
        },
    }, 200


def build_ai_analysis_v2_payload(
    match_id: int,
    request_json: Optional[Dict[str, Any]],
) -> Tuple[Dict[str, Any], int]:
    """Build payload for ``/api/v2/matches/<id>/analyze``."""
    from application.services.match_analysis_service import get_match_analysis_data
    from application.services.odds_intent_v2 import OddsIntentAnalyzer
    from application.services.odds_intent_v2.adapter import convert_to_v2_request

    analysis_result = get_match_analysis_data(str(match_id))
    if not analysis_result.get("success"):
        return analysis_result, 404

    company_id = _parse_company_id(request_json, default=115)
    v2_request = convert_to_v2_request(str(match_id), analysis_result["data"], company_id=company_id)
    if not v2_request:
        available_companies = _build_available_companies(analysis_result.get("data", {}))
        available_info = (
            f"可用公司: {', '.join(available_companies)}"
            if available_companies
            else "无可用公司数据"
        )
        return {
            "success": False,
            "error": f"无法从公司ID {company_id} 提取完整的骨架区间和赔率数据。{available_info}",
            "available_companies": available_companies,
        }, 400

    analyzer = OddsIntentAnalyzer()
    response = analyzer.analyze(v2_request)
    return {"success": True, "data": response.dict()}, 200


__all__ = ["build_ai_analysis_payload", "build_ai_analysis_v2_payload"]
