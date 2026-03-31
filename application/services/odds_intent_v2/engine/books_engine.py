#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多公司一致性引擎
"""

from typing import Dict, List, Optional
from core.logger import get_logger

logger = get_logger(__name__)


class BooksEngine:
    """多公司一致性引擎"""
    
    def analyze_consensus(
        self,
        book_results: List[Dict]
    ) -> Dict:
        """
        分析多公司一致性
        
        Args:
            book_results: 每个公司的分析结果列表
                [{"book": "williamhill", "pick": "H", "pattern": "...", "confidence": 72}, ...]
        
        Returns:
            {
                "consensus_score": float,
                "divergence_score": float,
                "per_book": List[Dict]
            }
        """
        if not book_results:
            return {
                "consensus_score": 0.0,
                "divergence_score": 1.0,
                "per_book": []
            }
        
        # 统计pick分布
        pick_counts = {}
        pattern_counts = {}
        
        for result in book_results:
            pick = result.get("pick")
            pattern = result.get("pattern")
            
            if pick:
                pick_counts[pick] = pick_counts.get(pick, 0) + 1
            if pattern:
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        # 计算共识分数
        total_books = len(book_results)
        if total_books == 0:
            consensus_score = 0.0
        else:
            # 基础共识：同一pick的公司数占比
            max_pick_count = max(pick_counts.values()) if pick_counts else 0
            consensus_score = max_pick_count / total_books
            
            # 高级版：殊途同归加分
            if len(pattern_counts) > 1 and max_pick_count < total_books:
                # 如果picks不同但patterns相似，可能是殊途同归
                # 简化处理：如果patterns都指向同一类（如都包含"Real"或"Tao"）
                pattern_similarity = self._check_pattern_similarity(pattern_counts)
                if pattern_similarity:
                    consensus_score = min(1.0, consensus_score + 0.15)
        
        divergence_score = 1.0 - consensus_score
        
        return {
            "consensus_score": consensus_score,
            "divergence_score": divergence_score,
            "per_book": book_results
        }
    
    def _check_pattern_similarity(self, pattern_counts: Dict[str, int]) -> bool:
        """检查pattern相似性（简化版）"""
        patterns = list(pattern_counts.keys())
        if len(patterns) < 2:
            return False
        
        # 检查是否都包含相同的关键词
        keywords = ["Real", "Tao", "Spill", "Block", "Split"]
        for keyword in keywords:
            if all(keyword in p for p in patterns):
                return True
        
        return False

