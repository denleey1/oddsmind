#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
胜平负专项分析器
深度分析各公司在预测主胜、平局、客胜方面的准确率
找出每种结果的专家公司
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import pandas as pd
from collections import defaultdict
import numpy as np

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger

logger = get_logger(__name__)


class WinDrawLoseAnalyzer:
    """
    胜平负专项分析器
    深度分析每种结果的预测准确率
    """
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.recommendation_mapping = self._load_recommendation_mapping()
        self.company_info = self._load_company_info()
        
    def _load_recommendation_mapping(self) -> Dict:
        """加载推荐映射规则"""
        try:
            mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                return mapping_data['recommendations']
        except Exception as e:
            self.logger.warning(f"加载推荐映射失败: {e}")
            return {}
    
    def _load_company_info(self) -> Dict:
        """加载公司信息"""
        try:
            query = "SELECT company_id, name, country FROM companies"
            companies = self.db.execute_query(query, fetch='all')
            
            company_dict = {}
            for company in companies:
                company_dict[company['company_id']] = {
                    'name': company['name'],
                    'country': company.get('country', '未知')
                }
            return company_dict
        except Exception as e:
            self.logger.warning(f"加载公司信息失败: {e}")
            return {}
    
    def analyze_win_draw_lose_detailed(self) -> Dict:
        """
        详细分析胜平负预测情况
        统计每种结果的预测准确率、预测频率等
        """
        self.logger.info("="*100)
        self.logger.info("开始胜平负详细分析")
        self.logger.info("="*100)
        
        # 获取所有验证表
        tables = self._get_all_validation_tables()
        
        # 初始化统计结构
        company_stats = defaultdict(lambda: {
            # 总体统计
            'total_predictions': 0,
            'total_correct': 0,
            
            # 按实际结果统计（当实际是主胜/平/负时，预测对了多少）
            'actual_home_win': {'total': 0, 'correct': 0, 'predictions': defaultdict(int)},
            'actual_draw': {'total': 0, 'correct': 0, 'predictions': defaultdict(int)},
            'actual_away_win': {'total': 0, 'correct': 0, 'predictions': defaultdict(int)},
            
            # 按预测结果统计（当预测主胜/平/负时，实际对了多少）
            'predict_home_win': {'total': 0, 'correct': 0},
            'predict_draw': {'total': 0, 'correct': 0},
            'predict_away_win': {'total': 0, 'correct': 0},
            
            # 特殊统计
            'confidence_levels': defaultdict(lambda: {'total': 0, 'correct': 0}),
            'league_performance': defaultdict(lambda: {'total': 0, 'correct': 0})
        })
        
        # 遍历所有表进行统计
        for table_info in tables:
            table_name = table_info['table_name']
            league_name = table_info['league_name']
            
            query = f"""
            SELECT 
                company_id,
                actual_home_score,
                actual_away_score,
                current_recommendation,
                current_rule_diff,
                initial_recommendation,
                power_diff
            FROM {table_name}
            """
            
            results = self.db.execute_query(query, fetch='all')
            
            if not results:
                continue
            
            for row in results:
                company_id = row['company_id']
                stats = company_stats[company_id]
                
                # 判断实际结果
                if row['actual_home_score'] > row['actual_away_score']:
                    actual_result = 'home_win'
                    actual_key = 'actual_home_win'
                elif row['actual_home_score'] < row['actual_away_score']:
                    actual_result = 'away_win'
                    actual_key = 'actual_away_win'
                else:
                    actual_result = 'draw'
                    actual_key = 'actual_draw'
                
                # 获取预测结果
                predicted_result = self._get_predicted_result(
                    row['current_recommendation'],
                    row['current_rule_diff']
                )
                
                # 总体统计
                stats['total_predictions'] += 1
                
                # 按实际结果统计
                stats[actual_key]['total'] += 1
                stats[actual_key]['predictions'][predicted_result] += 1
                
                # 判断是否预测正确
                is_correct = self._check_prediction_correct(
                    predicted_result, 
                    actual_result
                )
                
                if is_correct:
                    stats['total_correct'] += 1
                    stats[actual_key]['correct'] += 1
                
                # 按预测结果统计
                if predicted_result == 'home_win':
                    stats['predict_home_win']['total'] += 1
                    if actual_result == 'home_win':
                        stats['predict_home_win']['correct'] += 1
                elif predicted_result == 'draw':
                    stats['predict_draw']['total'] += 1
                    if actual_result == 'draw':
                        stats['predict_draw']['correct'] += 1
                elif predicted_result == 'away_win':
                    stats['predict_away_win']['total'] += 1
                    if actual_result == 'away_win':
                        stats['predict_away_win']['correct'] += 1
                
                # 联赛表现
                stats['league_performance'][league_name]['total'] += 1
                if is_correct:
                    stats['league_performance'][league_name]['correct'] += 1
                
                # 信心等级分析（基于power_diff）
                if row['power_diff'] is not None:
                    power_diff = abs(float(row['power_diff']))
                    if power_diff < 1.5:
                        confidence = 'low'
                    elif power_diff < 3.0:
                        confidence = 'medium'
                    else:
                        confidence = 'high'
                    
                    stats['confidence_levels'][confidence]['total'] += 1
                    if is_correct:
                        stats['confidence_levels'][confidence]['correct'] += 1
        
        # 计算各项准确率并生成报告
        analysis_results = self._calculate_accuracies(company_stats)
        
        # 输出分析结果
        self._print_detailed_analysis(analysis_results)
        
        return analysis_results
    
    def find_specialist_companies(self) -> Dict:
        """
        找出各领域的专家公司
        - 主胜专家：预测主胜准确率最高
        - 平局专家：预测平局准确率最高
        - 客胜专家：预测客胜准确率最高
        - 冷门专家：预测冷门结果准确率高
        - 稳健专家：整体准确率高且稳定
        """
        self.logger.info("寻找专家公司...")
        
        analysis_results = self.analyze_win_draw_lose_detailed()
        
        specialists = {
            'home_win_experts': [],
            'draw_experts': [],
            'away_win_experts': [],
            'upset_experts': [],
            'stable_experts': [],
            'high_confidence_experts': []
        }
        
        for company_id, stats in analysis_results.items():
            # 至少需要100场预测才能入选
            if stats['total_predictions'] < 100:
                continue
            
            # 主胜专家
            if stats['predict_home_win']['accuracy'] > 0.65 and stats['predict_home_win']['total'] > 50:
                specialists['home_win_experts'].append({
                    'company_id': company_id,
                    'company_name': self._get_company_name(company_id),
                    'accuracy': stats['predict_home_win']['accuracy'],
                    'total': stats['predict_home_win']['total'],
                    'correct': stats['predict_home_win']['correct']
                })
            
            # 平局专家
            if stats['predict_draw']['accuracy'] > 0.35 and stats['predict_draw']['total'] > 30:
                specialists['draw_experts'].append({
                    'company_id': company_id,
                    'company_name': self._get_company_name(company_id),
                    'accuracy': stats['predict_draw']['accuracy'],
                    'total': stats['predict_draw']['total'],
                    'correct': stats['predict_draw']['correct']
                })
            
            # 客胜专家
            if stats['predict_away_win']['accuracy'] > 0.60 and stats['predict_away_win']['total'] > 50:
                specialists['away_win_experts'].append({
                    'company_id': company_id,
                    'company_name': self._get_company_name(company_id),
                    'accuracy': stats['predict_away_win']['accuracy'],
                    'total': stats['predict_away_win']['total'],
                    'correct': stats['predict_away_win']['correct']
                })
            
            # 稳健专家（整体准确率高）
            if stats['overall_accuracy'] > 0.60:
                specialists['stable_experts'].append({
                    'company_id': company_id,
                    'company_name': self._get_company_name(company_id),
                    'accuracy': stats['overall_accuracy'],
                    'total': stats['total_predictions'],
                    'correct': stats['total_correct']
                })
            
            # 高信心专家
            if 'high' in stats['confidence_levels'] and stats['confidence_levels']['high']['accuracy'] > 0.70:
                specialists['high_confidence_experts'].append({
                    'company_id': company_id,
                    'company_name': self._get_company_name(company_id),
                    'accuracy': stats['confidence_levels']['high']['accuracy'],
                    'total': stats['confidence_levels']['high']['total'],
                    'correct': stats['confidence_levels']['high']['correct']
                })
        
        # 排序
        for key in specialists:
            specialists[key].sort(key=lambda x: x['accuracy'], reverse=True)
        
        # 输出专家公司
        self._print_specialist_companies(specialists)
        
        return specialists
    
    def analyze_prediction_patterns(self) -> Dict:
        """
        分析预测模式
        - 哪些公司倾向于预测主胜
        - 哪些公司倾向于预测平局
        - 哪些公司预测比较均衡
        """
        self.logger.info("分析预测模式...")
        
        # 获取所有验证表
        tables = self._get_all_validation_tables()
        
        prediction_patterns = defaultdict(lambda: {
            'home_win_count': 0,
            'draw_count': 0,
            'away_win_count': 0,
            'total': 0
        })
        
        for table_info in tables:
            table_name = table_info['table_name']
            
            query = f"""
            SELECT 
                company_id,
                current_recommendation,
                current_rule_diff
            FROM {table_name}
            """
            
            results = self.db.execute_query(query, fetch='all')
            
            if not results:
                continue
            
            for row in results:
                company_id = row['company_id']
                predicted_result = self._get_predicted_result(
                    row['current_recommendation'],
                    row['current_rule_diff']
                )
                
                prediction_patterns[company_id]['total'] += 1
                
                if predicted_result == 'home_win':
                    prediction_patterns[company_id]['home_win_count'] += 1
                elif predicted_result == 'draw':
                    prediction_patterns[company_id]['draw_count'] += 1
                elif predicted_result == 'away_win':
                    prediction_patterns[company_id]['away_win_count'] += 1
        
        # 分类公司
        conservative_companies = []  # 保守型（倾向主队）
        aggressive_companies = []    # 激进型（倾向客队）
        balanced_companies = []      # 均衡型
        draw_specialists = []        # 平局专家
        
        for company_id, pattern in prediction_patterns.items():
            if pattern['total'] < 100:
                continue
            
            home_rate = pattern['home_win_count'] / pattern['total']
            draw_rate = pattern['draw_count'] / pattern['total']
            away_rate = pattern['away_win_count'] / pattern['total']
            
            company_data = {
                'company_id': company_id,
                'company_name': self._get_company_name(company_id),
                'home_rate': home_rate,
                'draw_rate': draw_rate,
                'away_rate': away_rate,
                'total': pattern['total']
            }
            
            # 分类
            if home_rate > 0.5:
                conservative_companies.append(company_data)
            elif away_rate > 0.35:
                aggressive_companies.append(company_data)
            elif draw_rate > 0.25:
                draw_specialists.append(company_data)
            else:
                balanced_companies.append(company_data)
        
        # 排序
        conservative_companies.sort(key=lambda x: x['home_rate'], reverse=True)
        aggressive_companies.sort(key=lambda x: x['away_rate'], reverse=True)
        draw_specialists.sort(key=lambda x: x['draw_rate'], reverse=True)
        
        patterns_result = {
            'conservative': conservative_companies[:10],
            'aggressive': aggressive_companies[:10],
            'balanced': balanced_companies[:10],
            'draw_specialists': draw_specialists[:10]
        }
        
        # 输出分析结果
        self._print_prediction_patterns(patterns_result)
        
        return patterns_result
    
    def _get_all_validation_tables(self) -> List[Dict]:
        """获取所有验证结果表"""
        return [
            {'table_name': 'premier_league_validation_results', 'league_name': '英超'},
            {'table_name': 'laliga_validation_results', 'league_name': '西甲'},
            {'table_name': 'bundesliga_validation_results', 'league_name': '德甲'},
            {'table_name': 'seriea_validation_results', 'league_name': '意甲'},
            {'table_name': 'ligue1_validation_results', 'league_name': '法甲'},
            {'table_name': 'jleague_validation_results', 'league_name': '日职联'},
            {'table_name': 'kleague_validation_results', 'league_name': '韩K联'}
        ]
    
    def _get_predicted_result(self, recommendation: str, rule_diff: float) -> str:
        """获取预测结果"""
        if recommendation not in self.recommendation_mapping:
            return 'unknown'
        
        rule = self.recommendation_mapping[recommendation]
        predicted_result = rule.get('result', 'unknown')
        
        # 特殊处理双平偏让平
        if recommendation == "双平偏让平":
            if rule_diff and rule_diff < 0:
                return "home_win"
            elif rule_diff and rule_diff > 0:
                return "away_win"
            else:
                return "draw"
        
        # 处理数组形式的结果（取第一个作为主要预测）
        if isinstance(predicted_result, list):
            if 'home_win' in predicted_result:
                return 'home_win'
            elif 'away_win' in predicted_result:
                return 'away_win'
            elif 'draw' in predicted_result:
                return 'draw'
        
        return predicted_result
    
    def _check_prediction_correct(self, predicted: str, actual: str) -> bool:
        """检查预测是否正确"""
        return predicted == actual
    
    def _calculate_accuracies(self, company_stats: Dict) -> Dict:
        """计算各项准确率"""
        results = {}
        
        for company_id, stats in company_stats.items():
            if stats['total_predictions'] == 0:
                continue
            
            # 整体准确率
            overall_accuracy = stats['total_correct'] / stats['total_predictions']
            
            # 实际结果准确率
            actual_accuracies = {}
            for result_type in ['actual_home_win', 'actual_draw', 'actual_away_win']:
                if stats[result_type]['total'] > 0:
                    actual_accuracies[result_type] = {
                        'accuracy': stats[result_type]['correct'] / stats[result_type]['total'],
                        'total': stats[result_type]['total'],
                        'correct': stats[result_type]['correct']
                    }
            
            # 预测结果准确率
            predict_accuracies = {}
            for result_type in ['predict_home_win', 'predict_draw', 'predict_away_win']:
                if stats[result_type]['total'] > 0:
                    predict_accuracies[result_type] = {
                        'accuracy': stats[result_type]['correct'] / stats[result_type]['total'],
                        'total': stats[result_type]['total'],
                        'correct': stats[result_type]['correct']
                    }
            
            # 信心等级准确率
            confidence_accuracies = {}
            for level, level_stats in stats['confidence_levels'].items():
                if level_stats['total'] > 0:
                    confidence_accuracies[level] = {
                        'accuracy': level_stats['correct'] / level_stats['total'],
                        'total': level_stats['total'],
                        'correct': level_stats['correct']
                    }
            
            results[company_id] = {
                'total_predictions': stats['total_predictions'],
                'total_correct': stats['total_correct'],
                'overall_accuracy': overall_accuracy,
                **actual_accuracies,
                **predict_accuracies,
                'confidence_levels': confidence_accuracies
            }
        
        return results
    
    def _get_company_name(self, company_id: int) -> str:
        """获取公司名称"""
        if company_id in self.company_info:
            info = self.company_info[company_id]
            return f"{info['name']}({info['country']})"
        return f"公司{company_id}"
    
    def _print_detailed_analysis(self, analysis_results: Dict):
        """输出详细分析结果"""
        print("\n" + "="*120)
        print("胜平负详细分析报告")
        print("="*120)
        
        # 找出各项最佳
        best_overall = max(analysis_results.items(), 
                          key=lambda x: x[1]['overall_accuracy'] if x[1]['total_predictions'] > 100 else 0)
        
        best_home_predictor = max(analysis_results.items(),
                                 key=lambda x: x[1].get('predict_home_win', {}).get('accuracy', 0) 
                                 if x[1].get('predict_home_win', {}).get('total', 0) > 50 else 0)
        
        best_draw_predictor = max(analysis_results.items(),
                                 key=lambda x: x[1].get('predict_draw', {}).get('accuracy', 0)
                                 if x[1].get('predict_draw', {}).get('total', 0) > 20 else 0)
        
        best_away_predictor = max(analysis_results.items(),
                                 key=lambda x: x[1].get('predict_away_win', {}).get('accuracy', 0)
                                 if x[1].get('predict_away_win', {}).get('total', 0) > 50 else 0)
        
        print(f"\n🏆 总体最佳: {self._get_company_name(best_overall[0])}")
        print(f"   准确率: {best_overall[1]['overall_accuracy']:.2%}")
        print(f"   预测数: {best_overall[1]['total_predictions']}")
        
        print(f"\n🥇 主胜预测最佳: {self._get_company_name(best_home_predictor[0])}")
        if 'predict_home_win' in best_home_predictor[1]:
            print(f"   准确率: {best_home_predictor[1]['predict_home_win']['accuracy']:.2%}")
            print(f"   预测数: {best_home_predictor[1]['predict_home_win']['total']}")
        
        print(f"\n🥈 平局预测最佳: {self._get_company_name(best_draw_predictor[0])}")
        if 'predict_draw' in best_draw_predictor[1]:
            print(f"   准确率: {best_draw_predictor[1]['predict_draw']['accuracy']:.2%}")
            print(f"   预测数: {best_draw_predictor[1]['predict_draw']['total']}")
        
        print(f"\n🥉 客胜预测最佳: {self._get_company_name(best_away_predictor[0])}")
        if 'predict_away_win' in best_away_predictor[1]:
            print(f"   准确率: {best_away_predictor[1]['predict_away_win']['accuracy']:.2%}")
            print(f"   预测数: {best_away_predictor[1]['predict_away_win']['total']}")
    
    def _print_specialist_companies(self, specialists: Dict):
        """输出专家公司"""
        print("\n" + "="*120)
        print("专家公司分析")
        print("="*120)
        
        # 主胜专家
        if specialists['home_win_experts']:
            print("\n【主胜专家 TOP5】")
            print(f"{'排名':<6} {'公司':<30} {'准确率':<12} {'正确/总数':<15}")
            print("-" * 70)
            for i, company in enumerate(specialists['home_win_experts'][:5], 1):
                print(f"{i:<6} {company['company_name']:<30} "
                      f"{company['accuracy']:.2%}{'':6} "
                      f"{company['correct']}/{company['total']}")
        
        # 平局专家
        if specialists['draw_experts']:
            print("\n【平局专家 TOP5】")
            print(f"{'排名':<6} {'公司':<30} {'准确率':<12} {'正确/总数':<15}")
            print("-" * 70)
            for i, company in enumerate(specialists['draw_experts'][:5], 1):
                print(f"{i:<6} {company['company_name']:<30} "
                      f"{company['accuracy']:.2%}{'':6} "
                      f"{company['correct']}/{company['total']}")
        
        # 客胜专家
        if specialists['away_win_experts']:
            print("\n【客胜专家 TOP5】")
            print(f"{'排名':<6} {'公司':<30} {'准确率':<12} {'正确/总数':<15}")
            print("-" * 70)
            for i, company in enumerate(specialists['away_win_experts'][:5], 1):
                print(f"{i:<6} {company['company_name']:<30} "
                      f"{company['accuracy']:.2%}{'':6} "
                      f"{company['correct']}/{company['total']}")
        
        # 稳健专家
        if specialists['stable_experts']:
            print("\n【稳健专家 TOP5】")
            print(f"{'排名':<6} {'公司':<30} {'准确率':<12} {'正确/总数':<15}")
            print("-" * 70)
            for i, company in enumerate(specialists['stable_experts'][:5], 1):
                print(f"{i:<6} {company['company_name']:<30} "
                      f"{company['accuracy']:.2%}{'':6} "
                      f"{company['correct']}/{company['total']}")
    
    def _print_prediction_patterns(self, patterns: Dict):
        """输出预测模式分析"""
        print("\n" + "="*120)
        print("预测模式分析")
        print("="*120)
        
        # 保守型公司
        if patterns['conservative']:
            print("\n【保守型公司】（倾向预测主胜）")
            print(f"{'排名':<6} {'公司':<30} {'主胜率':<10} {'平率':<10} {'客胜率':<10}")
            print("-" * 70)
            for i, company in enumerate(patterns['conservative'][:5], 1):
                print(f"{i:<6} {company['company_name']:<30} "
                      f"{company['home_rate']:.1%}{'':4} "
                      f"{company['draw_rate']:.1%}{'':4} "
                      f"{company['away_rate']:.1%}")
        
        # 激进型公司
        if patterns['aggressive']:
            print("\n【激进型公司】（倾向预测客胜）")
            print(f"{'排名':<6} {'公司':<30} {'客胜率':<10} {'主胜率':<10} {'平率':<10}")
            print("-" * 70)
            for i, company in enumerate(patterns['aggressive'][:5], 1):
                print(f"{i:<6} {company['company_name']:<30} "
                      f"{company['away_rate']:.1%}{'':4} "
                      f"{company['home_rate']:.1%}{'':4} "
                      f"{company['draw_rate']:.1%}")
        
        # 平局专家
        if patterns['draw_specialists']:
            print("\n【平局专注公司】（经常预测平局）")
            print(f"{'排名':<6} {'公司':<30} {'平率':<10} {'主胜率':<10} {'客胜率':<10}")
            print("-" * 70)
            for i, company in enumerate(patterns['draw_specialists'][:5], 1):
                print(f"{i:<6} {company['company_name']:<30} "
                      f"{company['draw_rate']:.1%}{'':4} "
                      f"{company['home_rate']:.1%}{'':4} "
                      f"{company['away_rate']:.1%}")


def main():
    """主函数"""
    analyzer = WinDrawLoseAnalyzer()
    
    print("胜平负专项分析系统")
    print("="*120)
    
    # 1. 详细分析
    print("\n1. 执行胜平负详细分析...")
    detailed_results = analyzer.analyze_win_draw_lose_detailed()
    
    # 2. 寻找专家公司
    print("\n2. 寻找各领域专家公司...")
    specialists = analyzer.find_specialist_companies()
    
    # 3. 分析预测模式
    print("\n3. 分析公司预测模式...")
    patterns = analyzer.analyze_prediction_patterns()
    
    print("\n✅ 分析完成！")
    print("="*120)
    
    # 输出总结
    print("\n【分析总结】")
    print("1. 已找出主胜、平局、客胜各领域的专家公司")
    print("2. 已识别保守型、激进型、均衡型等不同风格的公司")
    print("3. 建议根据比赛特点选择对应的专家公司进行参考")


if __name__ == "__main__":
    main()