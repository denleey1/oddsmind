#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多维度预测准确率分析器
全方位分析各公司在不同维度下的预测准确率，找出最适合的公司
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import pandas as pd
from collections import defaultdict

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger

logger = get_logger(__name__)


class MultiDimensionAnalyzer:
    """
    多维度预测准确率分析器
    分析维度包括:
    1. 结果类型维度 (胜/平/负)
    2. 赔率区间维度
    3. 主客场维度
    4. 强弱对比维度
    5. 时间段维度 (初盘/即时盘)
    6. 公司特征维度
    7. 联赛特征维度
    """
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.recommendation_mapping = self._load_recommendation_mapping()
        
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
    
    def analyze_by_result_type(self, league_id: Optional[int] = None) -> Dict:
        """
        按结果类型（胜/平/负）分析各公司准确率
        找出每种结果预测最准确的公司
        """
        self.logger.info("="*80)
        self.logger.info("开始胜平负分类准确率分析")
        self.logger.info("="*80)
        
        # 构建查询
        base_query = """
        SELECT 
            company_id,
            actual_home_score,
            actual_away_score,
            initial_recommendation,
            current_recommendation,
            initial_rule_diff,
            current_rule_diff
        FROM {table_name}
        WHERE 1=1
        """
        
        # 获取所有联赛的验证结果表
        tables = self._get_validation_tables(league_id)
        
        all_results = {
            'home_win': defaultdict(lambda: {'total': 0, 'initial_correct': 0, 'current_correct': 0}),
            'draw': defaultdict(lambda: {'total': 0, 'initial_correct': 0, 'current_correct': 0}),
            'away_win': defaultdict(lambda: {'total': 0, 'initial_correct': 0, 'current_correct': 0})
        }
        
        for table_name in tables:
            query = base_query.format(table_name=table_name)
            results = self.db.execute_query(query, fetch='all')
            
            if not results:
                continue
                
            for row in results:
                # 判断实际结果
                if row['actual_home_score'] > row['actual_away_score']:
                    actual_result = 'home_win'
                elif row['actual_home_score'] < row['actual_away_score']:
                    actual_result = 'away_win'
                else:
                    actual_result = 'draw'
                
                company_id = row['company_id']
                
                # 统计该结果类型
                all_results[actual_result][company_id]['total'] += 1
                
                # 判断预测是否正确
                initial_correct = self._is_prediction_correct_for_result(
                    row['initial_recommendation'], 
                    actual_result, 
                    row['initial_rule_diff']
                )
                current_correct = self._is_prediction_correct_for_result(
                    row['current_recommendation'], 
                    actual_result, 
                    row['current_rule_diff']
                )
                
                if initial_correct:
                    all_results[actual_result][company_id]['initial_correct'] += 1
                if current_correct:
                    all_results[actual_result][company_id]['current_correct'] += 1
        
        # 计算准确率并排序
        result_rankings = {}
        
        for result_type, company_stats in all_results.items():
            rankings = []
            for company_id, stats in company_stats.items():
                if stats['total'] >= 50:  # 至少预测50场
                    initial_acc = stats['initial_correct'] / stats['total'] if stats['total'] > 0 else 0
                    current_acc = stats['current_correct'] / stats['total'] if stats['total'] > 0 else 0
                    
                    rankings.append({
                        'company_id': company_id,
                        'total_predictions': stats['total'],
                        'initial_accuracy': initial_acc,
                        'current_accuracy': current_acc,
                        'initial_correct': stats['initial_correct'],
                        'current_correct': stats['current_correct']
                    })
            
            # 按即时盘准确率排序
            rankings.sort(key=lambda x: x['current_accuracy'], reverse=True)
            result_rankings[result_type] = rankings[:10]  # 保留前10名
        
        # 输出分析结果
        self._print_result_type_analysis(result_rankings)
        
        return result_rankings
    
    def analyze_by_odds_range(self, league_id: Optional[int] = None) -> Dict:
        """
        按赔率区间分析准确率
        区间：
        - 强势主胜 (主胜赔率 < 1.5)
        - 一般主胜 (1.5 <= 主胜赔率 < 2.0)
        - 均势 (2.0 <= 主胜赔率 < 2.5)
        - 冷门 (主胜赔率 >= 2.5)
        """
        self.logger.info("开始赔率区间准确率分析")
        
        odds_ranges = {
            'strong_home': '主胜赔率 < 1.5',
            'normal_home': '1.5 <= 主胜赔率 < 2.0',
            'balanced': '2.0 <= 主胜赔率 < 3.0',
            'upset': '主胜赔率 >= 3.0'
        }
        
        # 获取赔率数据并分析
        query = """
        SELECT 
            vr.company_id,
            vr.match_id,
            vr.actual_home_score,
            vr.actual_away_score,
            vr.current_recommendation,
            vr.current_rule_diff,
            eo.initial_home,
            eo.current_home
        FROM {table_name} vr
        JOIN european_odds eo ON vr.match_id = eo.match_id AND vr.company_id = eo.company_id
        WHERE eo.odds_type = '1x2'
        """
        
        tables = self._get_validation_tables(league_id)
        range_results = {range_key: defaultdict(lambda: {'total': 0, 'correct': 0}) 
                        for range_key in odds_ranges.keys()}
        
        for table_name in tables:
            results = self.db.execute_query(query.format(table_name=table_name), fetch='all')
            
            if not results:
                continue
                
            for row in results:
                # 判断赔率区间
                current_home_odds = float(row['current_home'])
                
                if current_home_odds < 1.5:
                    range_key = 'strong_home'
                elif current_home_odds < 2.0:
                    range_key = 'normal_home'
                elif current_home_odds < 3.0:
                    range_key = 'balanced'
                else:
                    range_key = 'upset'
                
                # 判断实际结果
                if row['actual_home_score'] > row['actual_away_score']:
                    actual_result = 'home_win'
                elif row['actual_home_score'] < row['actual_away_score']:
                    actual_result = 'away_win'
                else:
                    actual_result = 'draw'
                
                company_id = row['company_id']
                range_results[range_key][company_id]['total'] += 1
                
                # 判断预测是否正确
                if self._is_prediction_correct_for_result(
                    row['current_recommendation'], 
                    actual_result, 
                    row['current_rule_diff']
                ):
                    range_results[range_key][company_id]['correct'] += 1
        
        # 计算准确率并排序
        range_rankings = {}
        for range_key, company_stats in range_results.items():
            rankings = []
            for company_id, stats in company_stats.items():
                if stats['total'] >= 20:  # 至少预测20场
                    accuracy = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
                    rankings.append({
                        'company_id': company_id,
                        'total': stats['total'],
                        'correct': stats['correct'],
                        'accuracy': accuracy
                    })
            
            rankings.sort(key=lambda x: x['accuracy'], reverse=True)
            range_rankings[range_key] = rankings[:5]
        
        # 输出分析结果
        self._print_odds_range_analysis(range_rankings, odds_ranges)
        
        return range_rankings
    
    def analyze_by_consistency(self, league_id: Optional[int] = None) -> Dict:
        """
        分析初盘即时盘一致性
        找出初盘即时盘保持一致且准确率高的公司（稳定型公司）
        以及变盘后准确率提升的公司（灵活型公司）
        """
        self.logger.info("开始一致性分析")
        
        query = """
        SELECT 
            company_id,
            actual_home_score,
            actual_away_score,
            initial_recommendation,
            current_recommendation,
            initial_rule_diff,
            current_rule_diff
        FROM {table_name}
        """
        
        tables = self._get_validation_tables(league_id)
        
        consistency_stats = defaultdict(lambda: {
            'total': 0,
            'consistent': 0,
            'consistent_correct': 0,
            'changed': 0,
            'changed_to_correct': 0,
            'initial_correct': 0,
            'current_correct': 0
        })
        
        for table_name in tables:
            results = self.db.execute_query(query.format(table_name=table_name), fetch='all')
            
            if not results:
                continue
                
            for row in results:
                # 判断实际结果
                if row['actual_home_score'] > row['actual_away_score']:
                    actual_result = 'home_win'
                elif row['actual_home_score'] < row['actual_away_score']:
                    actual_result = 'away_win'
                else:
                    actual_result = 'draw'
                
                company_id = row['company_id']
                stats = consistency_stats[company_id]
                stats['total'] += 1
                
                # 判断初盘和即时盘是否正确
                initial_correct = self._is_prediction_correct_for_result(
                    row['initial_recommendation'], 
                    actual_result, 
                    row['initial_rule_diff']
                )
                current_correct = self._is_prediction_correct_for_result(
                    row['current_recommendation'], 
                    actual_result, 
                    row['current_rule_diff']
                )
                
                if initial_correct:
                    stats['initial_correct'] += 1
                if current_correct:
                    stats['current_correct'] += 1
                
                # 判断一致性
                if row['initial_recommendation'] == row['current_recommendation']:
                    stats['consistent'] += 1
                    if current_correct:
                        stats['consistent_correct'] += 1
                else:
                    stats['changed'] += 1
                    if not initial_correct and current_correct:
                        stats['changed_to_correct'] += 1
        
        # 分类公司类型
        stable_companies = []  # 稳定型公司
        flexible_companies = []  # 灵活型公司
        
        for company_id, stats in consistency_stats.items():
            if stats['total'] < 100:  # 至少100场预测
                continue
                
            consistency_rate = stats['consistent'] / stats['total']
            consistent_accuracy = stats['consistent_correct'] / stats['consistent'] if stats['consistent'] > 0 else 0
            change_improvement = stats['changed_to_correct'] / stats['changed'] if stats['changed'] > 0 else 0
            
            # 稳定型：一致性高且准确率高
            if consistency_rate > 0.7 and consistent_accuracy > 0.6:
                stable_companies.append({
                    'company_id': company_id,
                    'consistency_rate': consistency_rate,
                    'consistent_accuracy': consistent_accuracy,
                    'total': stats['total']
                })
            
            # 灵活型：变盘后准确率提升明显
            if stats['changed'] > 20 and change_improvement > 0.3:
                flexible_companies.append({
                    'company_id': company_id,
                    'change_rate': stats['changed'] / stats['total'],
                    'change_improvement': change_improvement,
                    'total': stats['total']
                })
        
        # 排序
        stable_companies.sort(key=lambda x: x['consistent_accuracy'], reverse=True)
        flexible_companies.sort(key=lambda x: x['change_improvement'], reverse=True)
        
        # 输出分析结果
        self._print_consistency_analysis(stable_companies[:10], flexible_companies[:10])
        
        return {
            'stable_companies': stable_companies[:10],
            'flexible_companies': flexible_companies[:10]
        }
    
    def analyze_company_specialties(self, league_id: Optional[int] = None) -> Dict:
        """
        分析各公司的专长领域
        找出每个公司最擅长预测的场景
        """
        self.logger.info("开始公司专长分析")
        
        # 定义分析维度
        specialties = {}
        
        # 1. 分析每个公司在不同结果类型的表现
        result_analysis = self.analyze_by_result_type(league_id)
        
        # 2. 分析每个公司在不同赔率区间的表现
        odds_analysis = self.analyze_by_odds_range(league_id)
        
        # 3. 综合分析，找出每个公司的专长
        company_profiles = defaultdict(lambda: {
            'best_result_type': None,
            'best_result_accuracy': 0,
            'best_odds_range': None,
            'best_range_accuracy': 0,
            'overall_score': 0
        })
        
        # 处理结果类型专长
        for result_type, rankings in result_analysis.items():
            for company in rankings[:5]:  # 只看前5名
                company_id = company['company_id']
                accuracy = company['current_accuracy']
                
                if accuracy > company_profiles[company_id]['best_result_accuracy']:
                    company_profiles[company_id]['best_result_type'] = result_type
                    company_profiles[company_id]['best_result_accuracy'] = accuracy
        
        # 处理赔率区间专长
        for range_key, rankings in odds_analysis.items():
            for company in rankings[:3]:  # 只看前3名
                company_id = company['company_id']
                accuracy = company['accuracy']
                
                if accuracy > company_profiles[company_id]['best_range_accuracy']:
                    company_profiles[company_id]['best_odds_range'] = range_key
                    company_profiles[company_id]['best_range_accuracy'] = accuracy
        
        # 计算综合得分
        for company_id, profile in company_profiles.items():
            profile['overall_score'] = (
                profile['best_result_accuracy'] * 0.6 + 
                profile['best_range_accuracy'] * 0.4
            )
        
        # 转换为列表并排序
        company_list = [
            {'company_id': cid, **profile} 
            for cid, profile in company_profiles.items()
        ]
        company_list.sort(key=lambda x: x['overall_score'], reverse=True)
        
        # 输出分析结果
        self._print_company_specialties(company_list[:20])
        
        return company_list[:20]
    
    def find_best_companies_for_scenario(
        self, 
        result_type: Optional[str] = None,
        odds_range: Optional[str] = None,
        league_id: Optional[int] = None
    ) -> List[Dict]:
        """
        根据特定场景找出最佳公司
        
        Args:
            result_type: 结果类型 (home_win/draw/away_win)
            odds_range: 赔率区间 (strong_home/normal_home/balanced/upset)
            league_id: 联赛ID
            
        Returns:
            最适合该场景的公司列表
        """
        conditions = []
        params = []
        
        # 构建查询条件
        base_query = """
        SELECT 
            vr.company_id,
            COUNT(*) as total,
            SUM(CASE WHEN {correct_condition} THEN 1 ELSE 0 END) as correct
        FROM {table_name} vr
        """
        
        # 如果指定了赔率区间，需要关联赔率表
        if odds_range:
            base_query += """
            JOIN european_odds eo ON vr.match_id = eo.match_id AND vr.company_id = eo.company_id
            WHERE eo.odds_type = '1x2'
            """
            
            # 添加赔率区间条件
            if odds_range == 'strong_home':
                conditions.append("eo.current_home < 1.5")
            elif odds_range == 'normal_home':
                conditions.append("eo.current_home >= 1.5 AND eo.current_home < 2.0")
            elif odds_range == 'balanced':
                conditions.append("eo.current_home >= 2.0 AND eo.current_home < 3.0")
            elif odds_range == 'upset':
                conditions.append("eo.current_home >= 3.0")
        else:
            base_query += " WHERE 1=1"
        
        # 添加结果类型条件
        if result_type:
            if result_type == 'home_win':
                conditions.append("vr.actual_home_score > vr.actual_away_score")
            elif result_type == 'draw':
                conditions.append("vr.actual_home_score = vr.actual_away_score")
            elif result_type == 'away_win':
                conditions.append("vr.actual_home_score < vr.actual_away_score")
        
        # 定义正确预测的条件（这里简化处理）
        correct_condition = "1=1"  # 需要根据实际推荐判断
        
        if conditions:
            base_query += " AND " + " AND ".join(conditions)
        
        base_query += " GROUP BY vr.company_id"
        
        # 获取表并执行查询
        tables = self._get_validation_tables(league_id)
        all_companies = defaultdict(lambda: {'total': 0, 'correct': 0})
        
        # 实际执行查询会比较复杂，这里简化展示逻辑
        # ...
        
        return []
    
    def _get_validation_tables(self, league_id: Optional[int] = None) -> List[str]:
        """获取验证结果表列表"""
        if league_id:
            # 根据联赛ID获取对应的表名
            league_mapping = {
                36: 'premier_league_validation_results',
                31: 'laliga_validation_results',
                8: 'bundesliga_validation_results',
                11: 'seriea_validation_results',
                23: 'ligue1_validation_results',
                25: 'jleague_validation_results',
                15: 'kleague_validation_results'
            }
            table_name = league_mapping.get(league_id)
            return [table_name] if table_name else []
        else:
            # 返回所有验证表
            return [
                'premier_league_validation_results',
                'laliga_validation_results',
                'bundesliga_validation_results',
                'seriea_validation_results',
                'ligue1_validation_results',
                'jleague_validation_results',
                'kleague_validation_results'
            ]
    
    def _is_prediction_correct_for_result(
        self, 
        recommendation: str, 
        actual_result: str, 
        rule_diff: float = 0
    ) -> bool:
        """判断预测是否正确"""
        if recommendation not in self.recommendation_mapping:
            return False
        
        rule = self.recommendation_mapping[recommendation]
        predicted_result = rule.get('result', 'unknown')
        
        # 特殊处理双平偏让平
        if recommendation == "双平偏让平":
            if rule_diff < 0:
                predicted_result = "home_win"
            elif rule_diff > 0:
                predicted_result = "away_win"
            else:
                predicted_result = "draw"
        
        # 处理数组形式的结果
        if isinstance(predicted_result, list):
            return actual_result in predicted_result
        else:
            return predicted_result == actual_result
    
    def _print_result_type_analysis(self, result_rankings: Dict):
        """输出结果类型分析"""
        print("\n" + "="*100)
        print("胜平负分类准确率分析")
        print("="*100)
        
        result_names = {
            'home_win': '主胜',
            'draw': '平局',
            'away_win': '客胜'
        }
        
        for result_type, rankings in result_rankings.items():
            print(f"\n【{result_names[result_type]}预测最佳公司 TOP10】")
            print(f"{'排名':<6} {'公司ID':<10} {'即时准确率':<12} {'初盘准确率':<12} "
                  f"{'正确数':<10} {'总预测数':<10}")
            print("-" * 80)
            
            for i, company in enumerate(rankings[:10], 1):
                print(f"{i:<6} {company['company_id']:<10} "
                      f"{company['current_accuracy']:.2%}{'':6} "
                      f"{company['initial_accuracy']:.2%}{'':6} "
                      f"{company['current_correct']:<10} "
                      f"{company['total_predictions']:<10}")
            
            if rankings:
                best = rankings[0]
                print(f"\n🏆 {result_names[result_type]}预测冠军: "
                      f"公司{best['company_id']} (准确率: {best['current_accuracy']:.2%})")
    
    def _print_odds_range_analysis(self, range_rankings: Dict, odds_ranges: Dict):
        """输出赔率区间分析"""
        print("\n" + "="*100)
        print("赔率区间准确率分析")
        print("="*100)
        
        for range_key, description in odds_ranges.items():
            rankings = range_rankings.get(range_key, [])
            
            print(f"\n【{description} - TOP5】")
            print(f"{'排名':<6} {'公司ID':<10} {'准确率':<12} {'正确数':<10} {'总数':<10}")
            print("-" * 60)
            
            for i, company in enumerate(rankings[:5], 1):
                print(f"{i:<6} {company['company_id']:<10} "
                      f"{company['accuracy']:.2%}{'':6} "
                      f"{company['correct']:<10} "
                      f"{company['total']:<10}")
    
    def _print_consistency_analysis(self, stable_companies: List, flexible_companies: List):
        """输出一致性分析"""
        print("\n" + "="*100)
        print("公司类型分析")
        print("="*100)
        
        print("\n【稳定型公司 TOP10】")
        print("特点: 初盘即时盘保持一致，且准确率高")
        print(f"{'排名':<6} {'公司ID':<10} {'一致性':<10} {'一致准确率':<12} {'总预测数':<10}")
        print("-" * 60)
        
        for i, company in enumerate(stable_companies[:10], 1):
            print(f"{i:<6} {company['company_id']:<10} "
                  f"{company['consistency_rate']:.1%}{'':4} "
                  f"{company['consistent_accuracy']:.2%}{'':6} "
                  f"{company['total']:<10}")
        
        print("\n【灵活型公司 TOP10】")
        print("特点: 根据临场信息调整预测，变盘后准确率提升")
        print(f"{'排名':<6} {'公司ID':<10} {'变盘率':<10} {'改进率':<12} {'总预测数':<10}")
        print("-" * 60)
        
        for i, company in enumerate(flexible_companies[:10], 1):
            print(f"{i:<6} {company['company_id']:<10} "
                  f"{company['change_rate']:.1%}{'':4} "
                  f"{company['change_improvement']:.2%}{'':6} "
                  f"{company['total']:<10}")
    
    def _print_company_specialties(self, companies: List):
        """输出公司专长分析"""
        print("\n" + "="*100)
        print("公司专长分析")
        print("="*100)
        
        result_names = {
            'home_win': '主胜',
            'draw': '平局',
            'away_win': '客胜'
        }
        
        range_names = {
            'strong_home': '强势主队',
            'normal_home': '一般主队',
            'balanced': '均势',
            'upset': '冷门'
        }
        
        print(f"\n{'排名':<6} {'公司ID':<10} {'最擅长结果':<15} {'准确率':<10} "
              f"{'最擅长赔率':<15} {'准确率':<10} {'综合得分':<10}")
        print("-" * 100)
        
        for i, company in enumerate(companies[:20], 1):
            best_result = result_names.get(company['best_result_type'], '无')
            best_range = range_names.get(company['best_odds_range'], '无')
            
            print(f"{i:<6} {company['company_id']:<10} "
                  f"{best_result:<15} {company['best_result_accuracy']:.2%}{'':4} "
                  f"{best_range:<15} {company['best_range_accuracy']:.2%}{'':4} "
                  f"{company['overall_score']:.3f}")
    
    def generate_comprehensive_report(self, output_file: str = "company_analysis_report.md"):
        """生成综合分析报告"""
        self.logger.info("开始生成综合分析报告")
        
        report_lines = []
        report_lines.append("# 多维度公司预测准确率综合分析报告")
        report_lines.append(f"\n生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # 1. 胜平负分析
        report_lines.append("## 1. 胜平负分类准确率分析\n")
        result_rankings = self.analyze_by_result_type()
        
        for result_type, rankings in result_rankings.items():
            if rankings:
                best = rankings[0]
                report_lines.append(f"- **{result_type}最佳**: 公司{best['company_id']} "
                                  f"(准确率: {best['current_accuracy']:.2%})")
        
        # 2. 赔率区间分析
        report_lines.append("\n## 2. 赔率区间准确率分析\n")
        odds_rankings = self.analyze_by_odds_range()
        
        for range_key, rankings in odds_rankings.items():
            if rankings:
                best = rankings[0]
                report_lines.append(f"- **{range_key}最佳**: 公司{best['company_id']} "
                                  f"(准确率: {best['accuracy']:.2%})")
        
        # 3. 公司类型分析
        report_lines.append("\n## 3. 公司类型分析\n")
        consistency_result = self.analyze_by_consistency()
        
        if consistency_result['stable_companies']:
            report_lines.append("### 稳定型公司\n")
            for company in consistency_result['stable_companies'][:5]:
                report_lines.append(f"- 公司{company['company_id']}: "
                                  f"一致性{company['consistency_rate']:.1%}, "
                                  f"准确率{company['consistent_accuracy']:.2%}")
        
        if consistency_result['flexible_companies']:
            report_lines.append("\n### 灵活型公司\n")
            for company in consistency_result['flexible_companies'][:5]:
                report_lines.append(f"- 公司{company['company_id']}: "
                                  f"变盘改进率{company['change_improvement']:.2%}")
        
        # 4. 公司专长分析
        report_lines.append("\n## 4. 公司专长分析\n")
        specialties = self.analyze_company_specialties()
        
        for company in specialties[:10]:
            report_lines.append(f"- 公司{company['company_id']}: "
                              f"擅长{company['best_result_type']}预测"
                              f"({company['best_result_accuracy']:.2%}), "
                              f"擅长{company['best_odds_range']}场景"
                              f"({company['best_range_accuracy']:.2%})")
        
        # 保存报告
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(report_lines))
        
        self.logger.info(f"报告已生成: {output_file}")
        
        return report_lines


def main():
    """主函数"""
    analyzer = MultiDimensionAnalyzer()
    
    print("多维度预测准确率分析系统")
    print("="*100)
    
    # 1. 胜平负分析
    print("\n1. 分析胜平负预测准确率...")
    result_rankings = analyzer.analyze_by_result_type()
    
    # 2. 赔率区间分析
    print("\n2. 分析赔率区间准确率...")
    odds_rankings = analyzer.analyze_by_odds_range()
    
    # 3. 一致性分析
    print("\n3. 分析公司类型...")
    consistency_result = analyzer.analyze_by_consistency()
    
    # 4. 公司专长分析
    print("\n4. 分析公司专长...")
    specialties = analyzer.analyze_company_specialties()
    
    # 5. 生成报告
    print("\n5. 生成综合报告...")
    analyzer.generate_comprehensive_report()
    
    print("\n✅ 分析完成！")
    print("="*100)


if __name__ == "__main__":
    main()