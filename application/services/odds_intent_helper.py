#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
欧赔意图分析辅助函数
从现有数据中提取骨架和赔率
"""

from typing import Dict, Any, Optional, List
from core.logger import get_logger

logger = get_logger(__name__)


def extract_skeleton_from_company_data(company_data: Dict[str, Any], company_id: int = None) -> Optional[Dict]:
    """
    （旧逻辑/兼容）从公司分析数据中提取骨架区间。

    注意：真实业务里的“骨架/合理区间”应来自“理论区间”模块（数值赔率区间）。
    这里仅保留历史逻辑（解析形如 "实开[1.69, 1.88]" 的数字区间字符串），
    当数据源确实提供数值区间字符串时才会成功。
    
    Args:
        company_data: 公司分析数据（来自match_analysis_service）
        company_id: 公司ID（用于日志）
    
    Returns:
        骨架字典 {"type": "range", "H": [1.69, 1.88], ...} 或 None
    """
    try:
        initial = company_data.get("initial", {})
        company_name = company_data.get("companyName", f"公司ID{company_id}")
        
        # 尝试从区间字符串中提取数值
        # 例如: "实开[1.69, 1.88]" -> [1.69, 1.88]
        def parse_range(range_str: str) -> Optional[List[float]]:
            if not range_str:
                return None
            
            # 尝试提取 [low, high] 格式
            import re
            match = re.search(r'\[([\d.]+),\s*([\d.]+)\]', range_str)
            if match:
                return [float(match.group(1)), float(match.group(2))]
            
            # 如果没有找到，返回None
            return None
        
        home_range_str = initial.get("homeRange", "")
        draw_range_str = initial.get("drawRange", "")
        away_range_str = initial.get("awayRange", "")
        
        home_range = parse_range(home_range_str)
        draw_range = parse_range(draw_range_str)
        away_range = parse_range(away_range_str)
        
        # 记录缺失的数据
        missing_ranges = []
        if not home_range:
            missing_ranges.append(f"homeRange: {home_range_str}")
        if not draw_range:
            missing_ranges.append(f"drawRange: {draw_range_str}")
        if not away_range:
            missing_ranges.append(f"awayRange: {away_range_str}")
        
        if missing_ranges:
            logger.warning(f"公司 {company_name} (ID: {company_id}) 缺少骨架区间数据: {', '.join(missing_ranges)}")
            return None
        
        return {
            "type": "range",
            "H": home_range,
            "D": draw_range,
            "A": away_range
        }
    except Exception as e:
        logger.warning(f"提取骨架区间失败 (公司ID: {company_id}): {e}", exc_info=True)
        return None


def extract_odds_from_company_data(company_data: Dict[str, Any], company_id: int = None) -> Optional[Dict[str, Dict[str, float]]]:
    """
    从公司分析数据中提取初赔和即时赔
    
    Args:
        company_data: 公司分析数据
        company_id: 公司ID（用于日志）
    
    Returns:
        {"open": {"H": 2.10, "D": 3.10, "A": 3.40}, "live": {...}} 或 None
    """
    try:
        initial_odds = company_data.get("initial", {}).get("odds", {})
        current_odds = company_data.get("current", {}).get("odds", {})
        company_name = company_data.get("companyName", f"公司ID{company_id}")
        
        odds_open = {
            "H": initial_odds.get("home"),
            "D": initial_odds.get("draw"),
            "A": initial_odds.get("away")
        }
        
        odds_live = {
            "H": current_odds.get("home"),
            "D": current_odds.get("draw"),
            "A": current_odds.get("away")
        }
        
        # 检查是否有缺失值（None或0）
        # 注意：赔率不应该为0，但None表示缺失
        missing_open = [k for k, v in odds_open.items() if v is None or v <= 0]
        missing_live = [k for k, v in odds_live.items() if v is None or v <= 0]
        
        if missing_open or missing_live:
            missing_info = []
            if missing_open:
                missing_info.append(f"初赔缺失: {', '.join(missing_open)}")
            if missing_live:
                missing_info.append(f"即时赔缺失: {', '.join(missing_live)}")
            logger.warning(f"公司 {company_name} (ID: {company_id}) 赔率数据不完整: {'; '.join(missing_info)}")
            logger.debug(f"初赔数据: {odds_open}, 即时赔数据: {odds_live}")
            return None
        
        return {
            "open": odds_open,
            "live": odds_live
        }
    except Exception as e:
        logger.warning(f"提取赔率失败 (公司ID: {company_id}): {e}", exc_info=True)
        return None


def prepare_odds_intent_input(
    match_analysis_data: Dict[str, Any],
    company_id: int = 115,
    fallback_company_ids: List[int] = None
) -> Optional[Dict[str, Any]]:
    """
    从match_analysis_data中准备欧赔意图分析的输入
    
    Args:
        match_analysis_data: 来自get_match_analysis_data的结果
        company_id: 首选公司ID（115=威廉, 80=澳门, 432=马会, 281=平博, 190=Interwetten），默认115（威廉）
        fallback_company_ids: 备用公司ID列表，如果首选公司数据不完整，按顺序尝试这些公司
    
    Returns:
        {
            "skeleton": {...},
            "odds_open": {...},
            "odds_live": {...},
            "company_id": ...,
            "company_name": ...
        } 或 None
    """
    try:
        if fallback_company_ids is None:
            # 默认备用顺序：威廉(115) -> 澳门(80) -> 马会(432) -> Interwetten(190)
            # 注意：平博(281)通常没有骨架区间，所以不放在备用列表中
            fallback_company_ids = [115, 80, 432, 190]
        
        # 确保首选公司ID在尝试列表中
        company_ids_to_try = [company_id]
        for cid in fallback_company_ids:
            if cid != company_id:
                company_ids_to_try.append(cid)
        
        # 兼容两种调用方式：
        # 1. 传入整个 get_match_analysis_data 的结果（包含 success 和 data）
        # 2. 传入 analysis_result['data']（只有 data 部分）
        if "data" in match_analysis_data and "companyAnalyses" in match_analysis_data.get("data", {}):
            # 方式1：传入整个结果
            company_analyses = match_analysis_data.get("data", {}).get("companyAnalyses", [])
        elif "companyAnalyses" in match_analysis_data:
            # 方式2：直接传入 data 部分
            company_analyses = match_analysis_data.get("companyAnalyses", [])
        else:
            company_analyses = []
        
        if not company_analyses:
            logger.error("比赛分析数据中没有公司数据")
            return None
        
        # 尝试每个公司ID
        for try_company_id in company_ids_to_try:
            # 查找指定公司ID的公司数据
            target_company = None
            for company in company_analyses:
                try:
                    # companyId可能是字符串或整数，统一转换为整数比较
                    company_id_from_data = company.get("companyId")
                    if company_id_from_data is None:
                        continue
                    company_id_int = int(company_id_from_data)
                    if company_id_int == try_company_id:
                        target_company = company
                        break
                except (ValueError, TypeError):
                    # 如果转换失败，跳过这条记录
                    continue
            
            # 如果没找到指定公司，尝试下一个
            if not target_company:
                logger.debug(f"未找到公司数据: company_id={try_company_id}，尝试下一个")
                continue
            
            company_name = target_company.get("companyName", f"公司ID{try_company_id}")
            logger.info(f"尝试使用公司 {company_name} (ID: {try_company_id}) 的数据")
            
            # 提取赔率
            odds_data = extract_odds_from_company_data(target_company, company_id=try_company_id)
            if not odds_data:
                logger.warning(f"公司 {company_name} (ID: {try_company_id}) 无法提取赔率，尝试下一个公司")
                continue

            # 提取骨架（优先：理论区间数值骨架；兜底：旧字符串数值区间解析）
            skeleton = None
            try:
                from application.services.odds_intent.theoretical_lookup import choose_best_skeleton_range

                home_strength = target_company.get("homeTierLevel")
                away_strength = target_company.get("awayTierLevel")
                if not home_strength or not away_strength:
                    raise ValueError(f"缺少广义实力档位: homeTierLevel={home_strength}, awayTierLevel={away_strength}")

                skeleton = choose_best_skeleton_range(
                    home_strength=str(home_strength),
                    away_strength=str(away_strength),
                    odds_open={
                        "H": odds_data["open"]["H"],
                        "D": odds_data["open"]["D"],
                        "A": odds_data["open"]["A"],
                    },
                )
            except Exception as e:
                logger.warning(
                    f"理论区间骨架提取失败 (公司 {company_name} ID:{try_company_id})，尝试旧骨架解析。原因: {e}"
                )
                skeleton = extract_skeleton_from_company_data(target_company, company_id=try_company_id)

            if not skeleton:
                logger.warning(f"公司 {company_name} (ID: {try_company_id}) 无法提取骨架区间（理论区间/兜底均失败），尝试下一个公司")
                continue
            
            # 成功提取所有数据
            logger.info(f"成功使用公司 {company_name} (ID: {try_company_id}) 的数据")
            return {
                "skeleton": skeleton,
                "odds_open": odds_data["open"],
                "odds_live": odds_data["live"],
                "company_id": try_company_id,
                "company_name": company_name
            }
        
        # 所有公司都尝试过了，都没有完整数据
        logger.error(f"无法从任何公司提取完整的骨架区间和赔率数据。已尝试的公司ID: {company_ids_to_try}")
        return None
        
    except Exception as e:
        logger.error(f"准备欧赔意图分析输入失败: {e}", exc_info=True)
        return None

