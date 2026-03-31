#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
按公司维度分析预测准确率
分别统计每个公司在不同联赛的表现
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple
from datetime import datetime
import json

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class CompanyDimensionValidator:
    """按公司维度分析验证器"""
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        
        # 联赛映射
        self.leagues = {
            15: ("韩K联赛", "kleague_validation_results"),
            25: ("日职联", "jleague_validation_results"),
        }
        
        # 主要公司列表
        self.main_companies = [791, 16, 680, 649, 104]
        
        # 加载推荐映射
        self._load_recommendation_mapping()
    
    def _load_recommendation_mapping(self):
        """加载推荐映射"""
        try:
            mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                self.recommendation_mapping = mapping_data['recommendations']
        except Exception as e:
            self.logger.error(f"无法加载推荐映射: {e}")
            self.recommendation_mapping = {}
    
    def analyze_by_company(self, company_id: int):
        """分析单个公司在所有联赛的表现"""
        
        print(f"\n分析公司 {company_id} 的预测表现")
        print("="*80)
        
        company_stats = {}
        
        for league_id, (league_name, table_name) in self.leagues.items():
            # 检查表是否存在
            check_query = """
            SELECT COUNT(*) as count
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
              AND table_name = %s
            """
            
            table_exists = self.db.execute_query(check_query, [table_name], fetch='one')
            
            if not table_exists or table_exists['count'] == 0:
                print(f"{league_name}: 验证表不存在")
                continue
            
            # 获取该公司在该联赛的所有预测
            query = f"""
            SELECT 
                match_id,
                actual_home_score,
                actual_away_score,
                current_recommendation,
                current_rule_diff,
                initial_recommendation,
                initial_rule_diff
            FROM {table_name}
            WHERE company_id = %s
            """
            
            results = self.db.execute_query(query, [company_id], fetch='all')
            
            if not results:
                print(f"{league_name}: 没有预测数据")
                continue
            
            # 统计准确率
            stats = self._calculate_accuracy(results)
            company_stats[league_name] = stats
            
            # 显示结果
            print(f"\n{league_name}:")
            print(f"  总预测数: {stats['total']}")
            print(f"  正确预测: {stats['correct']}")
            print(f"  准确率: {stats['accuracy']:.1f}%")
            print(f"  胜预测: {stats['win_predictions']} (正确: {stats['win_correct']}, 准确率: {stats['win_accuracy']:.1f}%)")
            print(f"  平预测: {stats['draw_predictions']} (正确: {stats['draw_correct']}, 准确率: {stats['draw_accuracy']:.1f}%)")
            print(f"  负预测: {stats['loss_predictions']} (正确: {stats['loss_correct']}, 准确率: {stats['loss_accuracy']:.1f}%)")
        
        return company_stats
    
    def _calculate_accuracy(self, results: List[Dict]) -> Dict:
        """计算准确率统计"""
        
        stats = {
            'total': 0,
            'correct': 0,
            'win_predictions': 0,
            'win_correct': 0,
            'draw_predictions': 0,
            'draw_correct': 0,
            'loss_predictions': 0,
            'loss_correct': 0
        }
        
        for row in results:
            stats['total'] += 1
            
            # 判断实际结果
            if row['actual_home_score'] > row['actual_away_score']:
                actual_result = 'home_win'
            elif row['actual_home_score'] < row['actual_away_score']:
                actual_result = 'away_win'
            else:
                actual_result = 'draw'
            
            # 判断预测结果
            recommendation = row['current_recommendation']
            rule_diff = float(row.get('current_rule_diff', 0))
            
            if recommendation in self.recommendation_mapping:
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
                
                # 统计预测类型
                if isinstance(predicted_result, list):
                    # 如果预测多个结果，简化处理
                    if 'home_win' in predicted_result:
                        stats['win_predictions'] += 1
                        if actual_result == 'home_win':
                            stats['win_correct'] += 1
                            stats['correct'] += 1
                    elif 'draw' in predicted_result:
                        stats['draw_predictions'] += 1
                        if actual_result == 'draw':
                            stats['draw_correct'] += 1
                            stats['correct'] += 1
                    elif 'away_win' in predicted_result:
                        stats['loss_predictions'] += 1
                        if actual_result == 'away_win':
                            stats['loss_correct'] += 1
                            stats['correct'] += 1
                else:
                    if predicted_result == 'home_win':
                        stats['win_predictions'] += 1
                        if actual_result == 'home_win':
                            stats['win_correct'] += 1
                            stats['correct'] += 1
                    elif predicted_result == 'draw':
                        stats['draw_predictions'] += 1
                        if actual_result == 'draw':
                            stats['draw_correct'] += 1
                            stats['correct'] += 1
                    elif predicted_result == 'away_win':
                        stats['loss_predictions'] += 1
                        if actual_result == 'away_win':
                            stats['loss_correct'] += 1
                            stats['correct'] += 1
        
        # 计算准确率
        stats['accuracy'] = stats['correct'] / stats['total'] * 100 if stats['total'] > 0 else 0
        stats['win_accuracy'] = stats['win_correct'] / stats['win_predictions'] * 100 if stats['win_predictions'] > 0 else 0
        stats['draw_accuracy'] = stats['draw_correct'] / stats['draw_predictions'] * 100 if stats['draw_predictions'] > 0 else 0
        stats['loss_accuracy'] = stats['loss_correct'] / stats['loss_predictions'] * 100 if stats['loss_predictions'] > 0 else 0
        
        return stats
    
    def compare_all_companies(self):
        """对比所有主要公司的表现"""
        
        print("\n主要公司预测表现对比")
        print("="*80)
        
        all_company_stats = {}
        
        # 分析每个主要公司
        for company_id in self.main_companies:
            print(f"\n分析公司 {company_id}...")
            stats = self.analyze_by_company(company_id)
            all_company_stats[company_id] = stats
        
        # 生成对比表格
        print("\n" + "="*80)
        print("综合对比表")
        print("-"*80)
        
        # 按联赛显示
        for league_id, (league_name, table_name) in self.leagues.items():
            print(f"\n{league_name}:")
            print(f"{'公司ID':<10} {'总预测':<10} {'准确率':<10} {'胜准确率':<12} {'平准确率':<12} {'负准确率':<12}")
            print("-"*70)
            
            league_data = []
            for company_id in self.main_companies:
                if company_id in all_company_stats and league_name in all_company_stats[company_id]:
                    stats = all_company_stats[company_id][league_name]
                    league_data.append((
                        company_id,
                        stats['total'],
                        stats['accuracy'],
                        stats['win_accuracy'],
                        stats['draw_accuracy'],
                        stats['loss_accuracy']
                    ))
            
            # 按总体准确率排序
            league_data.sort(key=lambda x: x[2], reverse=True)
            
            for company_id, total, accuracy, win_acc, draw_acc, loss_acc in league_data:
                print(f"{company_id:<10} {total:<10} {accuracy:<10.1f} {win_acc:<12.1f} {draw_acc:<12.1f} {loss_acc:<12.1f}")
        
        # 找出最佳公司
        self._find_best_companies(all_company_stats)
    
    def _find_best_companies(self, all_stats: Dict):
        """找出各方面表现最佳的公司"""
        
        print("\n" + "="*80)
        print("最佳公司推荐")
        print("-"*40)
        
        # 按联赛找最佳
        for league_id, (league_name, table_name) in self.leagues.items():
            print(f"\n{league_name}:")
            
            best_overall = None
            best_win = None
            best_draw = None
            best_loss = None
            
            for company_id, stats_dict in all_stats.items():
                if league_name in stats_dict:
                    stats = stats_dict[league_name]
                    
                    # 最佳总体准确率
                    if not best_overall or stats['accuracy'] > best_overall[1]:
                        best_overall = (company_id, stats['accuracy'])
                    
                    # 最佳胜预测
                    if stats['win_predictions'] > 20:  # 至少20个预测
                        if not best_win or stats['win_accuracy'] > best_win[1]:
                            best_win = (company_id, stats['win_accuracy'])
                    
                    # 最佳平预测
                    if stats['draw_predictions'] > 10:  # 至少10个预测
                        if not best_draw or stats['draw_accuracy'] > best_draw[1]:
                            best_draw = (company_id, stats['draw_accuracy'])
                    
                    # 最佳负预测
                    if stats['loss_predictions'] > 20:  # 至少20个预测
                        if not best_loss or stats['loss_accuracy'] > best_loss[1]:
                            best_loss = (company_id, stats['loss_accuracy'])
            
            if best_overall:
                print(f"  最佳总体: 公司{best_overall[0]} ({best_overall[1]:.1f}%)")
            if best_win:
                print(f"  最佳胜预测: 公司{best_win[0]} ({best_win[1]:.1f}%)")
            if best_draw:
                print(f"  最佳平预测: 公司{best_draw[0]} ({best_draw[1]:.1f}%)")
            if best_loss:
                print(f"  最佳负预测: 公司{best_loss[0]} ({best_loss[1]:.1f}%)")
    
    def analyze_all_companies_in_league(self, league_id: int):
        """分析所有公司在指定联赛的表现"""
        
        if league_id not in self.leagues:
            print(f"联赛{league_id}不在分析范围内")
            return
        
        league_name, table_name = self.leagues[league_id]
        
        print(f"\n分析所有公司在{league_name}的表现")
        print("="*80)
        
        # 获取所有公司的预测
        query = f"""
        SELECT 
            company_id,
            COUNT(*) as total,
            SUM(CASE WHEN 
                (actual_home_score > actual_away_score AND current_recommendation IN ('主让1胜', '主让1平', '主让2胜', '主让2平')) OR
                (actual_home_score < actual_away_score AND current_recommendation IN ('客让1胜', '客让1平', '客让2胜', '客让2平')) OR
                (actual_home_score = actual_away_score AND current_recommendation IN ('平', '双平偏平'))
            THEN 1 ELSE 0 END) as correct
        FROM {table_name}
        GROUP BY company_id
        HAVING COUNT(*) >= 50  -- 至少50个预测
        ORDER BY (correct * 1.0 / total) DESC
        LIMIT 20
        """
        
        results = self.db.execute_query(query, fetch='all')
        
        if results:
            print(f"{'排名':<6} {'公司ID':<10} {'总预测':<10} {'正确数':<10} {'准确率':<10}")
            print("-"*56)
            
            for idx, row in enumerate(results, 1):
                accuracy = row['correct'] / row['total'] * 100
                print(f"{idx:<6} {row['company_id']:<10} {row['total']:<10} {row['correct']:<10} {accuracy:.1f}%")


def main():
    """主函数"""
    validator = CompanyDimensionValidator()
    
    # 1. 对比主要公司
    print("\n=== 主要公司（791, 16, 680, 649, 104）分析 ===")
    validator.compare_all_companies()
    
    # 2. 分析所有公司在韩K联赛的表现
    print("\n\n=== 韩K联赛所有公司排名 ===")
    validator.analyze_all_companies_in_league(15)
    
    # 3. 分析所有公司在日职联的表现
    print("\n\n=== 日职联所有公司排名 ===")
    validator.analyze_all_companies_in_league(25)


if __name__ == "__main__":
    main()