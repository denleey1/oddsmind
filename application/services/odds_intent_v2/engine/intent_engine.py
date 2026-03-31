#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L4: 更优解与庄家意图推断引擎
"""

from typing import Dict, List, Optional
from core.logger import get_logger
from application.services.odds_intent_v2.config import config
from application.services.odds_intent_v2.schemas import Solution

logger = get_logger(__name__)


class IntentEngine:
    """意图推断引擎"""
    
    def __init__(self):
        self.config = config
        thresholds = config.get_thresholds()
        self.real_threshold = thresholds.get("real", -0.08)
        self.tao_threshold = thresholds.get("tao", 0.08)
        weights = config.get_weights()
        self.w_real = weights.get("w_real", 1.0)
        self.w_tao = weights.get("w_tao", 0.8)
        self.w_draw_spill = weights.get("w_draw_spill", 0.4)
        self.two_solutions_threshold = 0.15  # 双更优解判断阈值
    
    def analyze_intent(
        self,
        features: Dict,
        draw_structure: Dict
    ) -> Dict:
        """
        分析庄家意图，构造更优解
        
        Returns:
            {
                "solutions": [...],
                "two_solutions": bool,
                "exclude": List[str]
            }
        """
        delta_odds_live = features.get("delta_odds_live", {})
        delta_p_live = features.get("delta_p_live", {})
        fav = features.get("fav", "H")
        dog = features.get("dog", "A")
        draw_role = draw_structure.get("draw_role", "neutral")
        
        # 7.1 定义实/韬标签
        is_real_H = delta_odds_live.get("H", 0) <= self.real_threshold
        is_tao_H = delta_odds_live.get("H", 0) >= self.tao_threshold
        is_real_A = delta_odds_live.get("A", 0) <= self.real_threshold
        is_tao_A = delta_odds_live.get("A", 0) >= self.tao_threshold
        
        # 7.2 构造两个更优解候选
        real_solution = self._construct_real_solution(
            features, draw_structure, fav, dog, is_real_H, is_real_A
        )
        
        tao_solution = self._construct_tao_solution(
            features, draw_structure, fav, dog, is_tao_H, is_tao_A
        )
        
        # 7.3 判断two_solutions
        two_solutions = self._is_two_solutions(real_solution, tao_solution)
        
        # 排除项
        exclude = []
        if draw_structure.get("draw_role") == "valley":
            exclude.append("D")
        
        return {
            "solutions": [real_solution, tao_solution],
            "two_solutions": two_solutions,
            "exclude": exclude
        }
    
    def _construct_real_solution(
        self,
        features: Dict,
        draw_structure: Dict,
        fav: str,
        dog: str,
        is_real_H: bool,
        is_real_A: bool
    ) -> Solution:
        """构造REAL_solution（降低赔付主导）"""
        score = 0.0
        why = []
        delta_odds_live = features.get("delta_odds_live", {})
        draw_role = draw_structure.get("draw_role", "neutral")
        
        # 热门方向实
        if is_real_H and fav == "H":
            score += self.w_real
            why.append(f"热门方向({fav})压赔=降低赔付风险")
        elif is_real_A and fav == "A":
            score += self.w_real
            why.append(f"热门方向({fav})压赔=降低赔付风险")
        
        # 冷门方向实
        if is_real_H and dog == "H":
            score += self.w_real
            why.append(f"冷门方向({dog})压赔=降赔付保护")
        elif is_real_A and dog == "A":
            score += self.w_real
            why.append(f"冷门方向({dog})压赔=降赔付保护")
        
        # 平分洪加分（因为平可做分洪降低目标方向赔付压力）
        if draw_role == "spill":
            score += self.w_draw_spill
            why.append("平局分洪=降低目标方向赔付压力")
        
        # 目标选择：被压得更狠的一端
        if is_real_H and is_real_A:
            # 两边都实，选压得更狠的
            target = "H" if delta_odds_live.get("H", 0) < delta_odds_live.get("A", 0) else "A"
        elif is_real_H:
            target = "H"
        elif is_real_A:
            target = "A"
        else:
            # 没有明确的实，选热门方向
            target = fav
        
        return Solution(
            name="REAL_solution",
            target=target,
            score=min(score, 1.0),
            why=why
        )
    
    def _construct_tao_solution(
        self,
        features: Dict,
        draw_structure: Dict,
        fav: str,
        dog: str,
        is_tao_H: bool,
        is_tao_A: bool
    ) -> Solution:
        """
        构造TAO_solution（阻信心主导）
        
        韬盘思维：韬不是"否认"，而是"候选方向之一"
        韬开用于先阻信心/控受注，让冷门结果更容易出且不被大量跟投
        需要变盘确认和平赔结构配合来裁决
        """
        score = 0.0
        why = []
        delta_odds_live = features.get("delta_odds_live", {})
        draw_role = draw_structure.get("draw_role", "neutral")
        
        # 热门方向韬（阻信心候选信号）
        if is_tao_H and fav == "H":
            score += self.w_tao
            why.append(f"热门方向({fav})韬开=阻信心候选（需变盘确认）")
        elif is_tao_A and fav == "A":
            score += self.w_tao
            why.append(f"热门方向({fav})韬开=阻信心候选（需变盘确认）")
        
        # 冷门方向韬（阻信心候选信号）
        if is_tao_H and dog == "H":
            score += self.w_tao
            why.append(f"冷门方向({dog})韬开=阻信心候选（需变盘确认）")
        elif is_tao_A and dog == "A":
            score += self.w_tao
            why.append(f"冷门方向({dog})韬开=阻信心候选（需变盘确认）")
        
        # 阻平拉边加分
        if draw_role == "block":
            score += 0.3
            why.append("阻平拉边=倾向落在胜负一侧")
        
        # 目标选择：被抬得更狠的一端（韬开方向）
        if is_tao_H and is_tao_A:
            # 两边都韬，选抬得更狠的
            target = "H" if delta_odds_live.get("H", 0) > delta_odds_live.get("A", 0) else "A"
        elif is_tao_H:
            target = "H"
        elif is_tao_A:
            target = "A"
        else:
            # 没有明确的韬，选冷门方向
            target = dog
        
        return Solution(
            name="TAO_solution",
            target=target,
            score=min(score, 1.0),
            why=why
        )
    
    def _is_two_solutions(
        self,
        real_solution: Solution,
        tao_solution: Solution
    ) -> bool:
        """判断是否存在双更优解"""
        if real_solution.score < 0.3 or tao_solution.score < 0.3:
            return False
        
        score_diff = abs(real_solution.score - tao_solution.score)
        return score_diff < self.two_solutions_threshold

