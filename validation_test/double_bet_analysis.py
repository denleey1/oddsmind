#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
二串投注盈利性分析
基于验证结果分析二串投注的数学期望
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import math

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection


class DoubleBetAnalyzer:
    """二串投注分析器"""
    
    def __init__(self):
        self.db = get_connection()
        
        # 联赛配置
        self.leagues = {
            8: {'name': '德甲', 'code': 'bundesliga'},
            11: {'name': '法甲', 'code': 'ligue1'},
            15: {'name': '韩国K联赛', 'code': 'kleague'},
            25: {'name': '日职联', 'code': 'jleague'},
            31: {'name': '西甲', 'code': 'laliga'},
            34: {'name': '意甲', 'code': 'seriea'},
            36: {'name': '英超', 'code': 'premier'}
        }
    
    def _is_recommendation_correct(self, recommendation: str, actual_result: str, 
                                 rule_diff: float, recommendation_mapping: Dict) -> int:
        """判断推荐是否正确"""
        if recommendation not in recommendation_mapping:
            return 0
        
        rule = recommendation_mapping[recommendation]
        predicted_result = rule.get('result', 'unknown')
        
        # 处理双平偏让平的特殊逻辑
        if recommendation == "双平偏让平":
            if rule_diff < 0:
                predicted_result = "home_win"
            elif rule_diff > 0:
                predicted_result = "away_win"
            else:
                predicted_result = "draw"
        
        # 处理数组结果
        if isinstance(predicted_result, list):
            return 1 if actual_result in predicted_result else 0
        
        return 1 if predicted_result == actual_result else 0
    
    def get_league_accuracy(self, league_id: int) -> Dict:
        """获取联赛准确率数据"""
        table_name = f"{self.leagues[league_id]['code']}_validation_results"
        
        # 检查表是否存在
        check_query = f"""
        SELECT COUNT(*) as cnt 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = '{table_name}'
        """
        result = self.db.execute_query(check_query, fetch='one')
        
        if result['cnt'] == 0:
            return {}
        
        # 获取验证结果并计算准确率
        query = f"""
        SELECT 
            company_id, actual_home_score, actual_away_score,
            current_recommendation, current_rule_diff
        FROM `{table_name}`
        """
        
        results = self.db.execute_query(query, fetch='all')
        if not results:
            return {}
        
        # 加载推荐映射规则
        try:
            mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                recommendation_mapping = mapping_data.get('recommendation_mapping', {})
        except Exception as e:
            print(f"❌ 加载推荐映射失败: {e}")
            recommendation_mapping = {}
        
        # 计算每个公司的准确率
        company_stats = {}
        
        for row in results:
            company_id = row['company_id']
            
            # 确定实际比赛结果
            home_score = row['actual_home_score'] or 0
            away_score = row['actual_away_score'] or 0
            
            if home_score > away_score:
                actual_result = 'home_win'
            elif home_score < away_score:
                actual_result = 'away_win'
            else:
                actual_result = 'draw'
            
            # 判断推荐是否正确
            recommendation = row['current_recommendation']
            rule_diff = row['current_rule_diff'] or 0
            
            is_correct = self._is_recommendation_correct(
                recommendation, actual_result, rule_diff, recommendation_mapping
            )
            
            if company_id not in company_stats:
                company_stats[company_id] = {
                    'total': 0,
                    'correct': 0
                }
            
            company_stats[company_id]['total'] += 1
            company_stats[company_id]['correct'] += is_correct
        
        # 转换为准确率列表
        accuracy_list = []
        for company_id, stats in company_stats.items():
            if stats['total'] >= 50:  # 至少50个样本
                accuracy_rate = (stats['correct'] * 100.0) / stats['total']
                accuracy_list.append({
                    'company_id': company_id,
                    'total_predictions': stats['total'],
                    'correct_predictions': stats['correct'],
                    'accuracy_rate': accuracy_rate
                })
        
        # 按准确率排序
        accuracy_list.sort(key=lambda x: x['accuracy_rate'], reverse=True)
        
        if not accuracy_list:
            return {}
        
        # 计算统计数据
        top1 = accuracy_list[0]
        top3_avg = self._calculate_average_accuracy(accuracy_list[:3])
        top5_avg = self._calculate_average_accuracy(accuracy_list[:5])
        overall_avg = self._calculate_average_accuracy(accuracy_list)
        
        return {
            'league_name': self.leagues[league_id]['name'],
            'total_companies': len(accuracy_list),
            'top1': {
                'accuracy': top1['accuracy_rate'],
                'samples': top1['total_predictions']
            },
            'top3_avg': top3_avg,
            'top5_avg': top5_avg,
            'overall_avg': overall_avg
        }
    
    def _calculate_average_accuracy(self, results: List[Dict]) -> Dict:
        """计算平均准确率"""
        if not results:
            return {'accuracy': 0, 'samples': 0}
        
        total_correct = sum(r['correct_predictions'] for r in results)
        total_samples = sum(r['total_predictions'] for r in results)
        
        return {
            'accuracy': round(total_correct * 100.0 / total_samples, 1) if total_samples > 0 else 0,
            'samples': total_samples
        }
    
    def calculate_double_bet_expectation(self, accuracy: float, single_odds: float = 2.0, water_rate: float = 0.10) -> Dict:
        """计算二串投注的数学期望
        
        Args:
            accuracy: 单场准确率 (0-1之间)
            single_odds: 单场赔率
            water_rate: 抽水率
        
        Returns:
            包含盈利分析的字典
        """
        # 二串成功概率 = 单场准确率的平方
        double_success_prob = accuracy ** 2
        
        # 理论赔率 = 单场赔率的平方
        theoretical_double_odds = single_odds ** 2
        
        # 实际赔率 = 理论赔率 × (1 - 抽水率)
        actual_double_odds = theoretical_double_odds * (1 - water_rate)
        
        # 数学期望 = 成功概率 × 实际赔率 - 1
        expected_value = double_success_prob * actual_double_odds - 1
        
        # 盈亏平衡需要的准确率
        breakeven_accuracy = math.sqrt(1 / actual_double_odds)
        
        return {
            'single_accuracy': accuracy,
            'double_success_prob': double_success_prob,
            'single_odds': single_odds,
            'theoretical_double_odds': theoretical_double_odds,
            'actual_double_odds': actual_double_odds,
            'expected_value': expected_value,
            'expected_return_pct': expected_value * 100,
            'breakeven_accuracy': breakeven_accuracy,
            'water_rate': water_rate,
            'is_profitable': expected_value > 0
        }
    
    def analyze_double_betting_scenarios(self, accuracy_rate: float, samples: int) -> None:
        """分析不同场景下的二串投注"""
        accuracy = accuracy_rate / 100.0
        
        print(f"  单场赔率1.8: 二串概率{accuracy**2*100:.2f}%, 理论赔率{1.8**2:.2f}")
        for water in [0.15, 0.10, 0.05]:
            result = self.calculate_double_bet_expectation(accuracy, 1.8, water)
            status = "🟢" if result['is_profitable'] else "🔴"
            print(f"    {int(water*100)}%抽水: 实际赔率{result['actual_double_odds']:.2f}, "
                  f"期望{result['expected_return_pct']:+.1f}% {status}")
        
        print(f"  单场赔率2.0: 二串概率{accuracy**2*100:.2f}%, 理论赔率{2.0**2:.2f}")
        for water in [0.15, 0.10, 0.05]:
            result = self.calculate_double_bet_expectation(accuracy, 2.0, water)
            status = "🟢" if result['is_profitable'] else "🔴"
            print(f"    {int(water*100)}%抽水: 实际赔率{result['actual_double_odds']:.2f}, "
                  f"期望{result['expected_return_pct']:+.1f}% {status}")
        
        print(f"  单场赔率2.2: 二串概率{accuracy**2*100:.2f}%, 理论赔率{2.2**2:.2f}")
        for water in [0.15, 0.10, 0.05]:
            result = self.calculate_double_bet_expectation(accuracy, 2.2, water)
            status = "🟢" if result['is_profitable'] else "🔴"
            print(f"    {int(water*100)}%抽水: 实际赔率{result['actual_double_odds']:.2f}, "
                  f"期望{result['expected_return_pct']:+.1f}% {status}")
        
        print()
    
    def generate_investment_advice(self, all_league_data: List[Dict]) -> None:
        """生成投资建议"""
        print("=" * 100)
        print("二串投注投资建议")
        print("=" * 100)
        
        # 排序获取最佳准确率
        top_leagues = sorted(all_league_data, key=lambda x: x['top1']['accuracy'], reverse=True)
        
        print("\n📊 最具投资价值的联赛与准确率:")
        print("排名     联赛              TOP1准确率      样本数        二串成功率       ")
        print("-" * 70)
        for i, league in enumerate(top_leagues[:5], 1):
            double_success_rate = (league['top1']['accuracy'] / 100) ** 2 * 100
            print(f"{i:<6} {league['league_name']:<14} {league['top1']['accuracy']:.1f}%       "
                  f"{league['top1']['samples']:<8} {double_success_rate:.2f}%")
        
        best_accuracy = top_leagues[0]['top1']['accuracy'] / 100.0
        
        print(f"\n🎯 基于最佳准确率 {top_leagues[0]['top1']['accuracy']:.1f}% 的投资建议:")
        print("-" * 50)
        
        print("\n✅ 有盈利潜力的场景:")
        profitable_scenarios = []
        
        for single_odds in [1.8, 2.0, 2.2, 2.5]:
            for water_rate in [0.05, 0.10, 0.15]:
                result = self.calculate_double_bet_expectation(best_accuracy, single_odds, water_rate)
                if result['is_profitable']:
                    profitable_scenarios.append((single_odds, water_rate, result))
        
        # 按期望收益率降序排列
        profitable_scenarios.sort(key=lambda x: x[2]['expected_return_pct'], reverse=True)
        
        if profitable_scenarios:
            for single_odds, water_rate, result in profitable_scenarios[:10]:  # 显示前10个最佳场景
                print(f"  单场赔率{single_odds}, {int(water_rate*100)}%抽水: "
                      f"期望收益率 {result['expected_return_pct']:+.1f}%, "
                      f"二串赔率 {result['actual_double_odds']:.2f}")
        else:
            print("  ⚠️ 在当前准确率下，所有常见场景都无法盈利")
        
        print(f"\n💡 投资策略建议:")
        print("1. 重点关注准确率>50%的顶级公司")
        print("2. 选择单场赔率2.0-2.5的比赛组合") 
        print("3. 寻找抽水率较低的投注平台(抽水<10%)")
        print("4. 二串投注风险相对三串更低，但仍需严格资金管理")
        print("5. 单次投注不超过资金的3-5%")
        
        # 计算盈亏平衡点
        breakeven_2_0_10 = self.calculate_double_bet_expectation(0.5, 2.0, 0.10)
        print(f"\n📈 盈亏平衡分析:")
        print(f"单场赔率2.0, 10%抽水下需要准确率: {breakeven_2_0_10['breakeven_accuracy']*100:.1f}%")
        
        breakeven_1_8_05 = self.calculate_double_bet_expectation(0.5, 1.8, 0.05)
        print(f"单场赔率1.8, 5%抽水下需要准确率: {breakeven_1_8_05['breakeven_accuracy']*100:.1f}%")
        
        print(f"\n⚠️ 风险提醒:")
        print("1. 以上分析基于历史数据，实际表现可能有差异")
        print("2. 二串投注风险低于三串，但仍需谨慎管理资金")
        print("3. 博彩市场存在不确定性，投资需谨慎")
        print("4. 本分析仅供参考，不构成投资建议")
        
        print("=" * 100)
    
    def run_analysis(self) -> None:
        """运行完整的二串投注分析"""
        print("=" * 100)
        print("二串投注盈利性分析")
        print("=" * 100)
        
        all_league_data = []
        
        # 分析每个联赛
        for league_id in self.leagues.keys():
            print(f"\n正在分析{self.leagues[league_id]['name']}...")
            
            try:
                league_data = self.get_league_accuracy(league_id)
                if not league_data:
                    print(f"⚠️ {self.leagues[league_id]['name']} 暂无数据")
                    continue
                
                all_league_data.append(league_data)
                
            except Exception as e:
                print(f"❌ 分析{self.leagues[league_id]['name']}时出错: {e}")
                continue
        
        if not all_league_data:
            print("❌ 没有找到任何验证数据")
            return
        
        # 详细分析结果
        print("\n" + "=" * 120)
        print("各联赛二串投注分析详情")
        print("=" * 120)
        
        for league_data in all_league_data:
            print(f"\n【{league_data['league_name']}】(参与公司: {league_data['total_companies']}家)")
            print("-" * 80)
            
            print(f"\nTOP1: 准确率 {league_data['top1']['accuracy']:.1f}% (样本: {league_data['top1']['samples']})")
            self.analyze_double_betting_scenarios(league_data['top1']['accuracy'], league_data['top1']['samples'])
            
            print(f"TOP3平均: 准确率 {league_data['top3_avg']['accuracy']:.1f}% (样本: {league_data['top3_avg']['samples']})")
            self.analyze_double_betting_scenarios(league_data['top3_avg']['accuracy'], league_data['top3_avg']['samples'])
            
            print(f"TOP5平均: 准确率 {league_data['top5_avg']['accuracy']:.1f}% (样本: {league_data['top5_avg']['samples']})")
            self.analyze_double_betting_scenarios(league_data['top5_avg']['accuracy'], league_data['top5_avg']['samples'])
            
            print(f"整体平均: 准确率 {league_data['overall_avg']['accuracy']:.1f}% (样本: {league_data['overall_avg']['samples']})")
            self.analyze_double_betting_scenarios(league_data['overall_avg']['accuracy'], league_data['overall_avg']['samples'])
        
        # 生成投资建议
        self.generate_investment_advice(all_league_data)


def main():
    """主函数"""
    analyzer = DoubleBetAnalyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()