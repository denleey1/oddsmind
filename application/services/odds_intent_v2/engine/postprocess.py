#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
后处理：变盘确认、尾巴阻尼、NoBet判断
"""

from typing import Dict, Optional, List
from core.logger import get_logger
from application.services.odds_intent_v2.config import config

logger = get_logger(__name__)


class PostProcessor:
    """后处理器"""
    
    def __init__(self):
        self.config = config
        thresholds = config.get_thresholds()
        self.move_confirm = thresholds.get("move_confirm", -0.03)
        self.move_reverse = thresholds.get("move_reverse", 0.03)
        weights = config.get_weights()
        self.w_tail_penalty = weights.get("w_tail_penalty", -0.2)
        
        # 净水位列表（常见净位）
        self.clean_levels = {0.00, 0.10, 0.20, 0.25, 0.30, 0.50, 0.70, 0.75}
        # 尾巴水位（需要阻尼的）
        self.tail_levels = {0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09}
    
    def process(
        self,
        features: Dict,
        intent_result: Dict,
        pick: Optional[str],
        confidence_base: int,
        solution_name: Optional[str] = None
    ) -> Dict:
        """
        后处理：变盘确认、尾巴阻尼、最终置信度
        
        Args:
            solution_name: 使用的solution名称（"REAL_solution"或"TAO_solution"）
        
        Returns:
            {
                "confirm_score": float,
                "tail_penalty": Dict[str, float],
                "confidence": int,
                "status": "ok" | "nobet" | "low_confidence"
            }
        """
        # 9.1 变盘确认（对TAO_solution需要特殊处理）
        confirm_score = self._calculate_confirm_score(features, pick, solution_name)
        
        # 9.2 尾巴阻尼
        tail_penalty = self._calculate_tail_penalty(features.get("odds_live", {}))
        
        # 计算最终置信度
        confidence = self._calculate_final_confidence(
            confidence_base,
            confirm_score,
            tail_penalty,
            pick
        )
        
        # 判断状态
        status = self._determine_status(confidence, intent_result)
        
        return {
            "confirm_score": confirm_score,
            "tail_penalty": tail_penalty,
            "confidence": confidence,
            "status": status
        }
    
    def _calculate_confirm_score(
        self,
        features: Dict,
        pick: Optional[str],
        solution_name: Optional[str] = None
    ) -> float:
        """
        计算变盘确认分数
        
        对于TAO_solution（韬盘候选）：
        - 韬开 + 后续下压 = 韬真确认（更可能打出）
        - 韬开 + 后续上升 = 韬假诱（更可能不出）
        """
        if not pick:
            return 0.5  # 默认中等确认
        
        delta_move = features.get("delta_move")
        if not delta_move:
            return 0.5  # 没有初赔，无法确认
        
        delta_odds_live = features.get("delta_odds_live", {})
        move_pick = delta_move.get(pick, 0.0)
        odds_pick = delta_odds_live.get(pick, 0.0)
        
        # 如果是TAO_solution（韬盘候选），需要特殊处理
        if solution_name == "TAO_solution":
            # 韬开确认：该方向是韬开（Δodds >= tao）且后续下压（Δmove <= move_confirm）
            if odds_pick >= self.config.get_thresholds().get("tao", 0.08):
                if move_pick <= self.move_confirm:
                    # 韬开 + 后续下压 = 韬真确认（更可能打出）
                    return 0.75  # 高确认
                elif move_pick >= self.move_reverse:
                    # 韬开 + 后续上升 = 韬假诱（更可能不出）
                    return 0.25  # 低确认
                else:
                    return 0.5  # 中等确认（韬开但变盘不明显）
            else:
                # 不是韬开，按普通逻辑处理
                if move_pick <= self.move_confirm:
                    return 0.8
                elif move_pick >= self.move_reverse:
                    return 0.3
                else:
                    return 0.5
        else:
            # REAL_solution或其他：pick方向若下压（确认走强）→ confirm +
            if move_pick <= self.move_confirm:
                return 0.8  # 高确认
            # pick方向若上升（反做/诱导）→ confirm -
            elif move_pick >= self.move_reverse:
                return 0.3  # 低确认
            else:
                return 0.5  # 中等确认
    
    def _calculate_tail_penalty(
        self,
        odds_live: Dict[str, float]
    ) -> Dict[str, float]:
        """计算尾巴阻尼"""
        penalty = {}
        
        for key, odd in odds_live.items():
            # 取小数部分
            frac = round(odd - int(odd), 2)
            
            # 如果是尾巴水位且不是净位
            if frac in self.tail_levels and frac not in self.clean_levels:
                penalty[key] = 1.0  # 阻尼
            else:
                penalty[key] = 0.0  # 无阻尼
        
        return penalty
    
    def _calculate_final_confidence(
        self,
        confidence_base: int,
        confirm_score: float,
        tail_penalty: Dict[str, float],
        pick: Optional[str]
    ) -> int:
        """计算最终置信度"""
        confidence = float(confidence_base)
        
        # 变盘确认调整
        if confirm_score > 0.6:
            confidence += 5
        elif confirm_score < 0.4:
            confidence -= 5
        
        # 尾巴阻尼调整
        if pick and tail_penalty.get(pick, 0) > 0:
            confidence += int(self.w_tail_penalty * 10)  # 转换为整数调整
        
        return max(0, min(100, int(confidence)))
    
    def _determine_status(
        self,
        confidence: int,
        intent_result: Dict
    ) -> str:
        """判断最终状态"""
        two_solutions = intent_result.get("two_solutions", False)
        
        # NoBet条件
        if two_solutions and confidence < 50:
            return "nobet"
        
        if confidence < 40:
            return "low_confidence"
        
        return "ok"
    
    def check_nobet_conditions(
        self,
        features: Dict,
        intent_result: Dict,
        draw_structure: Dict,
        consensus_score: Optional[float] = None
    ) -> Optional[str]:
        """
        检查NoBet条件
        
        Returns:
            None 或 NoBet原因字符串
        """
        two_solutions = intent_result.get("two_solutions", False)
        solutions = intent_result.get("solutions", [])
        
        # 条件1：双更优解且分数接近且确认不足
        if two_solutions and len(solutions) >= 2:
            score_diff = abs(solutions[0].score - solutions[1].score)
            if score_diff < 0.15:
                return "双更优解冲突且确认不足"
        
        # 条件2：平结构无法判 + 主客均不显著
        draw_role = draw_structure.get("draw_role", "neutral")
        delta_odds_live = features.get("delta_odds_live", {})
        
        if draw_role == "neutral":
            is_any_real = any(v <= -0.08 for v in delta_odds_live.values())
            is_any_tao = any(v >= 0.08 for v in delta_odds_live.values())
            if not is_any_real and not is_any_tao:
                if consensus_score and consensus_score < 0.6:
                    return "全中庸盘口且公司分歧大"
        
        # 条件3：多公司共识低
        if consensus_score is not None and consensus_score < 0.5:
            if two_solutions:
                return "多公司不一致且双更优解"
        
        return None

