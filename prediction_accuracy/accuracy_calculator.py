#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
预测准确率计算服务
根据推荐结果和实际比分计算预测准确率
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.logger import get_logger


class AccuracyCalculator:
    """
    预测准确率计算器
    根据推荐结果和实际比赛结果计算准确率
    """
    
    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)
    
    def get_match_result(self, home_score: int, away_score: int) -> str:
        """
        根据比分确定比赛结果
        
        Args:
            home_score: 主队得分
            away_score: 客队得分
            
        Returns:
            'home_win' | 'draw' | 'away_win'
        """
        if home_score > away_score:
            return 'home_win'
        elif home_score == away_score:
            return 'draw'
        else:
            return 'away_win'
    
    def parse_recommendation(self, recommendation: str) -> Optional[str]:
        """
        解析推荐结果，提取预测的胜平负结果
        
        Args:
            recommendation: 推荐结果，如"主让1胜"、"双平"、"客让1胜"等
            
        Returns:
            'home_win' | 'draw' | 'away_win' | None
        """
        if not recommendation:
            return None
        
        # 判断是否预测主胜
        if '主' in recommendation and '胜' in recommendation:
            return 'home_win'
        
        # 判断是否预测客胜
        if '客' in recommendation and '胜' in recommendation:
            return 'away_win'
        
        # 判断是否预测平局
        if '平' in recommendation:
            return 'draw'
        
        # 判断是否预测主负（即客胜）
        if '主' in recommendation and '负' in recommendation:
            return 'away_win'
        
        # 判断是否预测客负（即主胜）
        if '客' in recommendation and '负' in recommendation:
            return 'home_win'
        
        # 无法识别
        self.logger.warning(f"无法识别的推荐结果: {recommendation}")
        return None
    
    def is_prediction_correct(self, recommendation: str, home_score: int, away_score: int) -> Optional[bool]:
        """
        判断预测是否准确
        
        Args:
            recommendation: 推荐结果
            home_score: 主队得分
            away_score: 客队得分
            
        Returns:
            True(准确) | False(不准确) | None(无法判断)
        """
        predicted = self.parse_recommendation(recommendation)
        if predicted is None:
            return None
        
        actual = self.get_match_result(home_score, away_score)
        
        return predicted == actual
    
    def calculate_accuracy_stats(self, predictions: List[Dict]) -> Dict:
        """
        计算准确率统计数据
        
        Args:
            predictions: 预测数据列表，每项包含：
                - recommendation: 推荐结果
                - home_score: 主队得分
                - away_score: 客队得分
                - confidence: 置信度（可选）
                - company_name: 公司名称（可选）
                
        Returns:
            统计数据字典
        """
        total = 0
        correct = 0
        incorrect = 0
        unknown = 0
        
        # 按预测结果分类统计
        result_stats = {
            'home_win': {'total': 0, 'correct': 0},
            'draw': {'total': 0, 'correct': 0},
            'away_win': {'total': 0, 'correct': 0}
        }
        
        # 按置信度分类统计
        confidence_stats = {
            'high': {'total': 0, 'correct': 0},
            'medium': {'total': 0, 'correct': 0},
            'low': {'total': 0, 'correct': 0}
        }
        
        for pred in predictions:
            recommendation = pred.get('recommendation')
            home_score = pred.get('home_score')
            away_score = pred.get('away_score')
            confidence = pred.get('confidence', 'unknown')
            
            if home_score is None or away_score is None:
                continue
            
            is_correct = self.is_prediction_correct(recommendation, home_score, away_score)
            
            if is_correct is None:
                unknown += 1
                continue
            
            total += 1
            
            if is_correct:
                correct += 1
            else:
                incorrect += 1
            
            # 按预测结果统计
            predicted = self.parse_recommendation(recommendation)
            if predicted:
                result_stats[predicted]['total'] += 1
                if is_correct:
                    result_stats[predicted]['correct'] += 1
            
            # 按置信度统计
            if confidence in confidence_stats:
                confidence_stats[confidence]['total'] += 1
                if is_correct:
                    confidence_stats[confidence]['correct'] += 1
        
        # 计算准确率
        overall_accuracy = (correct / total * 100) if total > 0 else 0
        
        # 计算各预测结果的准确率
        for result_type in result_stats:
            stats = result_stats[result_type]
            if stats['total'] > 0:
                stats['accuracy'] = stats['correct'] / stats['total'] * 100
            else:
                stats['accuracy'] = 0
        
        # 计算各置信度的准确率
        for conf_level in confidence_stats:
            stats = confidence_stats[conf_level]
            if stats['total'] > 0:
                stats['accuracy'] = stats['correct'] / stats['total'] * 100
            else:
                stats['accuracy'] = 0
        
        return {
            'total_predictions': total,
            'correct_predictions': correct,
            'incorrect_predictions': incorrect,
            'unknown_predictions': unknown,
            'overall_accuracy': round(overall_accuracy, 2),
            'by_result_type': result_stats,
            'by_confidence': confidence_stats
        }

