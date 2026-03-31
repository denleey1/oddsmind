#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pagination payload operations for public match-detail endpoints."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional, Set, Tuple


def _build_base_payload(
    data: Dict[str, Any],
    company_analyses: Any,
    top_company: Any,
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "matchId": data.get("matchId"),
        "leagueName": data.get("leagueName"),
        "roundNumber": data.get("roundNumber"),
        "totalRounds": data.get("totalRounds"),
        "matchTime": data.get("matchTime"),
        "homeTeam": data.get("homeTeam"),
        "awayTeam": data.get("awayTeam"),
        "homeTeamLogo": data.get("homeTeamLogo"),
        "awayTeamLogo": data.get("awayTeamLogo"),
        "matchStatus": data.get("matchStatus"),
        "homeScore": data.get("homeScore"),
        "awayScore": data.get("awayScore"),
        "standings": data.get("standings"),
        "fundamentalAnalysis": data.get("fundamentalAnalysis"),
        "company_analyses": company_analyses,
        "companyAnalyses": company_analyses,
        "topCompany": top_company,
        "companySummary": summary,
        "poissonPrediction": data.get("poissonPrediction"),
        "asianHandicap": data.get("asianHandicap"),
        "drawSystemAnalysis": data.get("drawSystemAnalysis"),
    }


def _apply_full_branch_requested_fields(
    response_data: Dict[str, Any],
    data: Dict[str, Any],
    requested_fields: Optional[Set[str]],
    top_analyses_list: Any,
    top_analysis: Any,
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    if not requested_fields:
        return response_data

    filtered_data = {"matchId": data.get("matchId"), "pagination": response_data["pagination"]}
    if "matchTime" in requested_fields:
        filtered_data["matchTime"] = data.get("matchTime")
    if "leagueName" in requested_fields:
        filtered_data["leagueName"] = data.get("leagueName")
    if "homeTeam" in requested_fields:
        filtered_data["homeTeam"] = data.get("homeTeam")
    if "awayTeam" in requested_fields:
        filtered_data["awayTeam"] = data.get("awayTeam")
    if "company_analyses" in requested_fields or "companyAnalyses" in requested_fields:
        filtered_data["company_analyses"] = top_analyses_list
        filtered_data["companyAnalyses"] = top_analyses_list
    if "oddsAnalysis" in requested_fields:
        filtered_data["oddsAnalysis"] = top_analysis
    if "topCompany" in requested_fields:
        filtered_data["topCompany"] = top_analysis
    if "companySummary" in requested_fields:
        filtered_data["companySummary"] = summary
    return filtered_data


def _apply_paginated_branch_requested_fields(
    response_data: Dict[str, Any],
    data: Dict[str, Any],
    requested_fields: Optional[Set[str]],
    current_page_analyses: Any,
    top_analysis_page: Any,
    summary: Dict[str, Any],
) -> Dict[str, Any]:
    if not requested_fields:
        return response_data

    filtered_data = {"matchId": data.get("matchId"), "pagination": response_data["pagination"]}
    if "matchTime" in requested_fields:
        filtered_data["matchTime"] = data.get("matchTime")
    if "leagueName" in requested_fields:
        filtered_data["leagueName"] = data.get("leagueName")
    if "homeTeam" in requested_fields:
        filtered_data["homeTeam"] = data.get("homeTeam")
    if "awayTeam" in requested_fields:
        filtered_data["awayTeam"] = data.get("awayTeam")
    if "company_analyses" in requested_fields or "companyAnalyses" in requested_fields:
        filtered_data["company_analyses"] = current_page_analyses
        filtered_data["companyAnalyses"] = current_page_analyses
    if "topCompany" in requested_fields:
        filtered_data["topCompany"] = top_analysis_page
    if "companySummary" in requested_fields:
        filtered_data["companySummary"] = summary
    return filtered_data


def _load_match_with_analyses(
    match_id: int,
    match_detail_service: Any,
    get_match_detail_fn: Callable[[str], Dict[str, Any]],
) -> Tuple[Dict[str, Any], Any, Any, Any]:
    result = get_match_detail_fn(str(match_id))
    data = result["data"]

    all_analyses_raw = match_detail_service.get_odds_analyses(str(match_id)) or []
    all_analyses_raw = match_detail_service.sort_analyses_by_priority(all_analyses_raw, limit=None)

    all_analyses_list = []
    for analysis in all_analyses_raw:
        formatted_analysis = match_detail_service.format_analysis_data(analysis)
        all_analyses_list.append(formatted_analysis)

    top_analyses_list = match_detail_service.get_top_analyses(all_analyses_list)
    summary = (
        match_detail_service.summary_calculator.calculate_company_summary(all_analyses_raw)
        if all_analyses_raw
        else {}
    )

    return data, all_analyses_list, top_analyses_list, summary


def build_public_match_detail_pagination_payload_ops(
    match_id: int,
    load_type: str,
    page: int,
    page_size: int,
    requested_fields: Optional[Set[str]],
    match_detail_service: Any,
    get_match_detail_fn: Callable[[str], Dict[str, Any]],
    error_handler: Any,
) -> Tuple[Dict[str, Any], int]:
    if load_type == "basic" or load_type == "full":
        result = get_match_detail_fn(str(match_id))
        if not result or not result.get("success"):
            return error_handler.handle_not_found_error("比赛"), 404

        data, all_analyses_list, top_analyses_list, summary = _load_match_with_analyses(
            match_id=match_id,
            match_detail_service=match_detail_service,
            get_match_detail_fn=get_match_detail_fn,
        )

        total_companies = len(all_analyses_list)
        total_pages = (total_companies + page_size - 1) // page_size if total_companies > 0 else 1

        top_analysis = top_analyses_list[0] if top_analyses_list else None

        response_data = _build_base_payload(
            data=data,
            company_analyses=all_analyses_list,
            top_company=top_analysis,
            summary=summary,
        )
        response_data["oddsAnalysis"] = top_analysis
        response_data["pagination"] = {
            "page": 1,
            "page_size": total_companies,
            "total_companies": total_companies,
            "total_pages": total_pages,
            "has_more": page < total_pages,
            "has_prev": page > 1,
        }
        response_data = _apply_full_branch_requested_fields(
            response_data=response_data,
            data=data,
            requested_fields=requested_fields,
            top_analyses_list=top_analyses_list,
            top_analysis=top_analysis,
            summary=summary,
        )
        return {"success": True, "data": response_data}, 200

    result = get_match_detail_fn(str(match_id))
    if not result["success"]:
        return error_handler.handle_not_found_error("比赛"), 404

    data, all_analyses_list, top_analyses_list, summary = _load_match_with_analyses(
        match_id=match_id,
        match_detail_service=match_detail_service,
        get_match_detail_fn=get_match_detail_fn,
    )

    total_companies = len(all_analyses_list)
    total_pages = (total_companies + page_size - 1) // page_size

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    current_page_analyses = all_analyses_list[start_idx:end_idx]

    top_analysis_page = None
    if top_analyses_list:
        for analysis in current_page_analyses:
            if analysis.get("company_id") == top_analyses_list[0].get("company_id"):
                top_analysis_page = analysis
                break

    response_data = _build_base_payload(
        data=data,
        company_analyses=current_page_analyses,
        top_company=top_analysis_page,
        summary=summary,
    )
    response_data["pagination"] = {
        "page": page,
        "page_size": page_size,
        "total_companies": total_companies,
        "total_pages": total_pages,
        "has_more": end_idx < total_companies,
        "has_prev": page > 1,
    }
    response_data = _apply_paginated_branch_requested_fields(
        response_data=response_data,
        data=data,
        requested_fields=requested_fields,
        current_page_analyses=current_page_analyses,
        top_analysis_page=top_analysis_page,
        summary=summary,
    )
    return {"success": True, "data": response_data}, 200


__all__ = ["build_public_match_detail_pagination_payload_ops"]

