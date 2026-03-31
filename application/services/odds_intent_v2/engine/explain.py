#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
解释生成引擎（模板化）
"""

from typing import Dict, List
from core.logger import get_logger

logger = get_logger(__name__)


class ExplainEngine:
    """解释生成引擎"""
    
    def generate(
        self,
        features: Dict,
        draw_structure: Dict,
        intent_result: Dict,
        rule_result: Dict,
        postprocess_result: Dict
    ) -> List[str]:
        """
        生成解释列表
        
        Returns:
            ["要点1", "要点2", "要点3", ...]
        """
        explain_list = []
        
        delta_odds_live = features.get("delta_odds_live", {})
        delta_p_live = features.get("delta_p_live", {})
        fav = features.get("fav", "H")
        dog = features.get("dog", "A")
        draw_role = draw_structure.get("draw_role", "neutral")
        solutions = intent_result.get("solutions", [])
        final_pick = rule_result.get("final_pick")
        structure = draw_structure.get("structure")
        
        # 1. 实盘/韬盘思维
        if final_pick:
            delta_pick = delta_odds_live.get(final_pick, 0)
            delta_move_pick = features.get("delta_move", {}).get(final_pick, 0) if features.get("delta_move") else None
            
            if delta_pick <= -0.08:
                explain_list.append(f"{self._get_outcome_name(final_pick)} 压赔（实盘思维：降低赔付）")
            elif delta_pick >= 0.08:
                # 韬盘：需要变盘确认
                if delta_move_pick is not None:
                    if delta_move_pick <= -0.03:
                        explain_list.append(f"{self._get_outcome_name(final_pick)} 韬开+后续下压（韬盘确认：阻信心后确认走强）")
                    elif delta_move_pick >= 0.03:
                        explain_list.append(f"{self._get_outcome_name(final_pick)} 韬开+后续上升（韬盘假诱：更可能不出）")
                    else:
                        explain_list.append(f"{self._get_outcome_name(final_pick)} 韬开（阻信心候选，需进一步确认）")
                else:
                    explain_list.append(f"{self._get_outcome_name(final_pick)} 韬开（阻信心候选，需变盘确认）")
        
        # 2. 平局结构
        if draw_role == "spill":
            explain_list.append("平局Δp上调，平为分洪口（欧赔两项可分一项）")
        elif draw_role == "block":
            explain_list.append("平局Δp下调，阻平拉边（结果倾向落在胜负一侧）")
        elif draw_role == "valley":
            explain_list.append("平为资金洼地结构，优先排除平")
        
        # 3. 双向/单向分散
        split_type = draw_structure.get("split_type", "none")
        if split_type == "double":
            explain_list.append("双向分散：胜平负都在吸筹，结构复杂")
        elif split_type == "single":
            explain_list.append("单向分散：偏向一侧吸筹")
        
        # 4. 更优解说明
        if intent_result.get("two_solutions", False):
            explain_list.append("存在双更优解，需结合变盘确认和多公司一致性判断")
        
        for solution in solutions:
            if solution.score > 0.3:
                why_str = "；".join(solution.why[:2])  # 取前两个原因
                if why_str:
                    explain_list.append(f"{solution.name}: {why_str}")
        
        # 5. 变盘确认
        confirm_score = postprocess_result.get("confirm_score", 0.5)
        if confirm_score > 0.6:
            explain_list.append("变盘确认：推荐方向持续下压，确认走强")
        elif confirm_score < 0.4:
            explain_list.append("变盘警告：推荐方向上升，可能存在反做")
        
        # 6. 结构标签
        if structure:
            explain_list.append(f"结构识别：{structure}")
        
        return explain_list[:5]  # 最多返回5条
    
    def _get_outcome_name(self, outcome: str) -> str:
        """获取赛果名称"""
        names = {
            "H": "主胜",
            "D": "平局",
            "A": "客胜"
        }
        return names.get(outcome, outcome)

