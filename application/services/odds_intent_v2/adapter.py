#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
适配器：将现有数据格式转换为v2分析请求
"""

from typing import Dict, Any, Optional
from application.services.odds_intent_v2.schemas import AnalyzeRequest, OddsDict, MetaInfo
from core.logger import get_logger

logger = get_logger(__name__)


def convert_to_v2_request(
    match_id: str,
    analysis_data: Dict[str, Any],
    company_id: int = 115
) -> Optional[AnalyzeRequest]:
    """
    将现有分析数据转换为v2分析请求
    
    Args:
        match_id: 比赛ID
        analysis_data: 来自get_match_analysis_data的数据
        company_id: 公司ID
    
    Returns:
        AnalyzeRequest 或 None（如果数据不完整）
    """
    try:
        company_analyses = analysis_data.get("companyAnalyses", [])
        
        # 查找指定公司
        company_data = None
        for company in company_analyses:
            if company.get("companyId") == company_id:
                company_data = company
                break
        
        if not company_data:
            logger.warning(f"未找到公司ID {company_id} 的数据")
            return None
        
        # 提取骨架
        initial = company_data.get("initial", {})
        skeleton = {
            "type": "range",
            "H": _parse_range(initial.get("homeRange", "")),
            "D": _parse_range(initial.get("drawRange", "")),
            "A": _parse_range(initial.get("awayRange", ""))
        }
        
        # 验证骨架
        if not all(skeleton[k] for k in ["H", "D", "A"]):
            logger.warning(f"公司ID {company_id} 骨架数据不完整")
            return None
        
        # 提取赔率
        initial_odds = initial.get("odds", {})
        current_odds = company_data.get("current", {}).get("odds", {})
        
        odds_open = OddsDict(
            H=initial_odds.get("home"),
            D=initial_odds.get("draw"),
            A=initial_odds.get("away")
        )
        
        odds_live = OddsDict(
            H=current_odds.get("home"),
            D=current_odds.get("draw"),
            A=current_odds.get("away")
        )
        
        # 验证赔率
        if not all([odds_open.H, odds_open.D, odds_open.A, odds_live.H, odds_live.D, odds_live.A]):
            logger.warning(f"公司ID {company_id} 赔率数据不完整")
            return None
        
        # 元信息
        match_info = analysis_data.get("matchInfo", {})
        meta = MetaInfo(
            league=match_info.get("leagueName"),
            zone=initial.get("zone"),
            match_time=str(match_info.get("matchTime", ""))
        )
        
        return AnalyzeRequest(
            match_id=match_id,
            skeleton=skeleton,
            odds_open=odds_open,
            odds_live=odds_live,
            meta=meta
        )
    except Exception as e:
        logger.error(f"转换v2请求失败: {e}", exc_info=True)
        return None


def _parse_range(range_str: str) -> Optional[list]:
    """解析区间字符串，例如 "实开[1.69, 1.88]" -> [1.69, 1.88]"""
    if not range_str:
        return None
    
    import re
    match = re.search(r'\[([\d.]+),\s*([\d.]+)\]', range_str)
    if match:
        return [float(match.group(1)), float(match.group(2))]
    
    return None

