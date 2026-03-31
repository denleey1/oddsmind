#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
L3: 平赔桥梁与分散结构判别引擎
"""

from typing import Dict, Tuple
from core.logger import get_logger
from application.services.odds_intent_v2.config import config

logger = get_logger(__name__)


class DrawEngine:
    """平赔桥梁引擎"""
    
    def __init__(self):
        self.config = config
        thresholds = config.get_thresholds()
        self.draw_spill_pp = thresholds.get("draw_spill_pp", 0.02)
        self.draw_block_pp = thresholds.get("draw_block_pp", -0.02)
        self.valley_edge_pull_threshold = 0.01  # 可配置
    
    def analyze_draw_structure(self, features: Dict) -> Dict:
        """
        分析平赔结构与分散类型
        
        Returns:
            {
                "draw_role": "spill" | "block" | "valley" | "neutral",
                "split_type": "single" | "double" | "none",
                "structure": "PullWinSplitDraw" | "DoubleSplitDraw" | "WinDrawCombineToAway" | ...
            }
        """
        delta_p_live = features.get("delta_p_live", {})
        delta_p_D = delta_p_live.get("D", 0.0)
        delta_p_H = delta_p_live.get("H", 0.0)
        delta_p_A = delta_p_live.get("A", 0.0)
        
        # 6.1 draw_role 判定
        draw_role = self._determine_draw_role(delta_p_D)
        
        # 6.2 单向/双向分散（split_type）
        split_type = self._determine_split_type(draw_role, delta_p_H, delta_p_A)
        
        # 6.3 洼地思维（valley）
        if self._is_valley(draw_role, split_type, delta_p_D, delta_p_H, delta_p_A):
            draw_role = "valley"
        
        # 6.4 结构识别
        structure = self._identify_structure(draw_role, split_type, features)
        
        return {
            "draw_role": draw_role,
            "split_type": split_type,
            "structure": structure
        }
    
    def _determine_draw_role(self, delta_p_D: float) -> str:
        """判定平局角色"""
        if delta_p_D >= self.draw_spill_pp:
            return "spill"
        elif delta_p_D <= self.draw_block_pp:
            return "block"
        else:
            return "neutral"
    
    def _determine_split_type(
        self,
        draw_role: str,
        delta_p_H: float,
        delta_p_A: float
    ) -> str:
        """判定分散类型"""
        if draw_role == "spill":
            # 双向分散：两边都吸筹
            both_edges_up = (delta_p_H > 0) and (delta_p_A > 0)
            if both_edges_up:
                return "double"
            else:
                return "single"
        elif draw_role == "block":
            # 阻平拉边，通常是单向
            return "single"
        else:
            return "none"
    
    def _is_valley(
        self,
        draw_role: str,
        split_type: str,
        delta_p_D: float,
        delta_p_H: float,
        delta_p_A: float
    ) -> bool:
        """判断是否为洼地思维"""
        # 条件1：平分洪 + 双向分散 + 边缘拉力小
        if draw_role == "spill" and split_type == "double":
            edge_pull = abs(delta_p_H - delta_p_A)
            if edge_pull < self.valley_edge_pull_threshold:
                return True
        
        # 条件2：平Δp很大 + 胜负Δp都为正（平更像中转洼地）
        if delta_p_D > 0.03 and delta_p_H > 0 and delta_p_A > 0:
            return True
        
        return False
    
    def _identify_structure(
        self,
        draw_role: str,
        split_type: str,
        features: Dict
    ) -> str:
        """识别综合结构"""
        delta_odds_live = features.get("delta_odds_live", {})
        fav = features.get("fav", "H")
        dog = features.get("dog", "A")
        
        is_fav_real = delta_odds_live.get(fav, 0) <= -0.08
        is_dog_real = delta_odds_live.get(dog, 0) <= -0.08
        
        # PullWinSplitDraw: 阻平 + 热门实
        if draw_role == "block" and is_fav_real:
            return "PullWinSplitDraw"
        
        # DoubleSplitDraw: 双向分散 + 平分洪
        if draw_role == "spill" and split_type == "double":
            return "DoubleSplitDraw"
        
        # WinDrawCombineToAway: 胜平合分到客
        if draw_role == "spill" and split_type == "single":
            if fav == "H" and delta_odds_live.get("A", 0) <= -0.08:
                return "WinDrawCombineToAway"
            elif fav == "A" and delta_odds_live.get("H", 0) <= -0.08:
                return "WinDrawCombineToHome"
        
        # 其他结构可以根据需要扩展
        return "Unknown"

