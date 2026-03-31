#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
三串投注盈利性分析
基于验证结果分析三串投注的数学期望
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


class TripleBetAnalyzer:
    """三串投注分析器"""
    
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
        
        # 加载推荐映射规则
        self._load_recommendation_mapping()
    
    def _load_recommendation_mapping(self):
        """加载推荐映射规则"""
        try:
            mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                self.recommendation_mapping = mapping_data['recommendations']
        except Exception as e:
            print(f"❌ 加载推荐映射失败: {e}")
            self.recommendation_mapping = {}
    
    def _is_recommendation_correct(self, recommendation: str, actual_result: str, rule_diff: float = 0) -> int:
        """判断推荐是否正确"""
        if recommendation not in self.recommendation_mapping:
            return 0
        
        rule = self.recommendation_mapping[recommendation]
        predicted_result = rule.get('result', 'unknown')
        
        if recommendation == "双平偏让平":
            if rule_diff < 0:
                predicted_result = "home_win"
            elif rule_diff > 0:
                predicted_result = "away_win"
            else:
                predicted_result = "draw"
        
        if isinstance(predicted_result, list):
            return 1 if actual_result in predicted_result else 0
        else:
            return 1 if predicted_result == actual_result else 0
    
    def get_company_accuracy(self, league_id: int) -> List[Dict]:
        """获取联赛中各公司的准确率"""
        league_info = self.leagues[league_id]
        table_name = f"{league_info['code']}_validation_results"
        
        # 检查表是否存在
        check_query = f"""
        SELECT COUNT(*) as cnt 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = '{table_name}'
        """
        result = self.db.execute_query(check_query, fetch='one')
        
        if result['cnt'] == 0:
            return []
        
        # 获取验证结果
        query = f"""
        SELECT 
            company_id, actual_home_score, actual_away_score,
            current_recommendation, current_rule_diff
        FROM `{table_name}`
        """
        
        results = self.db.execute_query(query, fetch='all')
        if not results:
            return []
        
        # 计算每个公司的准确率
        company_stats = {}
        
        for row in results:
            company_id = row['company_id']
            
            if company_id not in company_stats:
                company_stats[company_id] = {
                    'total': 0,
                    'correct': 0
                }
            
            stats = company_stats[company_id]
            stats['total'] += 1
            
            # 判断比赛结果
            if row['actual_home_score'] > row['actual_away_score']:
                actual_result = 'home_win'
            elif row['actual_home_score'] < row['actual_away_score']:
                actual_result = 'away_win'
            else:
                actual_result = 'draw'
            
            # 判断推荐是否正确
            current_rule_diff = float(row.get('current_rule_diff', 0))
            correct = self._is_recommendation_correct(
                row['current_recommendation'], actual_result, current_rule_diff)
            
            stats['correct'] += correct
        
        # 计算准确率并过滤样本数量太少的公司
        company_accuracies = []
        for company_id, stats in company_stats.items():
            if stats['total'] >= 50:  # 至少50个样本才有统计意义
                accuracy = stats['correct'] / stats['total']
                company_accuracies.append({
                    'company_id': company_id,
                    'total': stats['total'],
                    'correct': stats['correct'],
                    'accuracy': accuracy
                })
        
        # 按准确率排序
        company_accuracies.sort(key=lambda x: x['accuracy'], reverse=True)
        
        return company_accuracies
    
    def calculate_triple_bet_expectation(self, accuracy: float, typical_odds: float = 2.0) -> Dict:
        """计算三串投注的数学期望
        
        Args:
            accuracy: 单场预测准确率
            typical_odds: 典型单场赔率（假设）
        
        Returns:
            包含各种分析结果的字典
        """
        # 三串全中的概率
        triple_success_prob = accuracy ** 3
        
        # 理论三串赔率（不考虑抽水）
        theoretical_triple_odds = typical_odds ** 3
        
        # 考虑博彩公司抽水，实际赔率通常是理论赔率的85-95%
        water_rates = [0.85, 0.90, 0.95]  # 不同的抽水率
        
        results = []
        
        for water_rate in water_rates:
            actual_triple_odds = theoretical_triple_odds * water_rate
            
            # 数学期望 = 中奖概率 × 赔率 - 1
            expected_value = triple_success_prob * actual_triple_odds - 1
            
            # 盈利率
            profit_rate = expected_value * 100
            
            results.append({
                'water_rate': water_rate,
                'actual_odds': actual_triple_odds,
                'expected_value': expected_value,
                'profit_rate': profit_rate
            })
        
        return {
            'single_accuracy': accuracy,
            'triple_success_prob': triple_success_prob,
            'theoretical_odds': theoretical_triple_odds,
            'scenarios': results
        }
    
    def analyze_all_leagues(self):
        """分析所有联赛的三串投注盈利性"""
        print("="*100)
        print("三串投注盈利性分析")
        print("="*100)
        
        all_results = []
        
        for league_id, league_info in self.leagues.items():
            print(f"\n正在分析{league_info['name']}...")
            
            company_accuracies = self.get_company_accuracy(league_id)
            
            if not company_accuracies:
                print(f"❌ {league_info['name']} 数据不足")
                continue
            
            # 分析不同准确率等级的公司
            accuracy_levels = []
            
            # TOP1公司
            if len(company_accuracies) >= 1:
                top1 = company_accuracies[0]
                accuracy_levels.append(('TOP1', top1['accuracy'], top1['total']))
            
            # TOP3平均
            if len(company_accuracies) >= 3:
                top3_avg = sum(c['accuracy'] for c in company_accuracies[:3]) / 3
                accuracy_levels.append(('TOP3平均', top3_avg, sum(c['total'] for c in company_accuracies[:3])))
            
            # TOP5平均
            if len(company_accuracies) >= 5:
                top5_avg = sum(c['accuracy'] for c in company_accuracies[:5]) / 5
                accuracy_levels.append(('TOP5平均', top5_avg, sum(c['total'] for c in company_accuracies[:5])))
            
            # 整体平均
            overall_avg = sum(c['accuracy'] for c in company_accuracies) / len(company_accuracies)
            accuracy_levels.append(('整体平均', overall_avg, sum(c['total'] for c in company_accuracies)))
            
            league_results = {
                'league_name': league_info['name'],
                'company_count': len(company_accuracies),
                'accuracy_levels': accuracy_levels
            }
            
            all_results.append(league_results)
        
        # 生成详细报告
        self._print_detailed_analysis(all_results)
        
        # 生成投资建议
        self._print_investment_advice(all_results)
    
    def _print_detailed_analysis(self, all_results: List[Dict]):
        """打印详细分析"""
        print(f"\n{'='*120}")
        print("各联赛三串投注分析详情")
        print(f"{'='*120}")
        
        # 假设不同的典型赔率场景
        odds_scenarios = [1.8, 2.0, 2.2]  # 低、中、高赔率
        
        for result in all_results:
            print(f"\n【{result['league_name']}】(参与公司: {result['company_count']}家)")
            print("-" * 80)
            
            for level_name, accuracy, sample_size in result['accuracy_levels']:
                print(f"\n{level_name}: 准确率 {accuracy:.1%} (样本: {sample_size})")
                
                for odds in odds_scenarios:
                    analysis = self.calculate_triple_bet_expectation(accuracy, odds)
                    
                    print(f"  单场赔率{odds}: 三串概率{analysis['triple_success_prob']:.2%}, "
                          f"理论赔率{analysis['theoretical_odds']:.2f}")
                    
                    for scenario in analysis['scenarios']:
                        water_desc = f"{(1-scenario['water_rate'])*100:.0f}%抽水"
                        profit_color = "🟢" if scenario['profit_rate'] > 0 else "🔴"
                        
                        print(f"    {water_desc}: 实际赔率{scenario['actual_odds']:.2f}, "
                              f"期望{scenario['expected_value']:+.1%} {profit_color}")
    
    def _print_investment_advice(self, all_results: List[Dict]):
        """打印投资建议"""
        print(f"\n{'='*100}")
        print("三串投注投资建议")
        print(f"{'='*100}")
        
        # 收集最佳准确率
        best_accuracies = []
        for result in all_results:
            for level_name, accuracy, sample_size in result['accuracy_levels']:
                if 'TOP1' in level_name and sample_size >= 100:  # 只考虑样本充足的TOP1公司
                    best_accuracies.append({
                        'league': result['league_name'],
                        'accuracy': accuracy,
                        'sample_size': sample_size
                    })
        
        if not best_accuracies:
            print("❌ 数据不足，无法给出投资建议")
            return
        
        # 找出最佳准确率
        best_accuracies.sort(key=lambda x: x['accuracy'], reverse=True)
        
        print("\n📊 最具投资价值的联赛与准确率:")
        print(f"{'排名':<6} {'联赛':<15} {'TOP1准确率':<12} {'样本数':<10} {'三串成功率':<12}")
        print("-" * 70)
        
        for i, item in enumerate(best_accuracies[:5], 1):
            triple_prob = item['accuracy'] ** 3
            print(f"{i:<6} {item['league']:<15} {item['accuracy']:.1%}{'':6} "
                  f"{item['sample_size']:<10} {triple_prob:.2%}")
        
        # 具体投资建议
        if best_accuracies:
            best = best_accuracies[0]
            best_accuracy = best['accuracy']
            
            print(f"\n🎯 基于最佳准确率 {best_accuracy:.1%} 的投资建议:")
            print("-" * 50)
            
            # 在不同抽水率下的盈利性分析
            odds_range = [1.8, 2.0, 2.2, 2.5]
            
            profitable_scenarios = []
            
            for odds in odds_range:
                analysis = self.calculate_triple_bet_expectation(best_accuracy, odds)
                
                for scenario in analysis['scenarios']:
                    if scenario['expected_value'] > 0:
                        profitable_scenarios.append({
                            'odds': odds,
                            'water_rate': scenario['water_rate'],
                            'profit_rate': scenario['profit_rate'],
                            'triple_odds': scenario['actual_odds']
                        })
            
            if profitable_scenarios:
                print("\n✅ 有盈利潜力的场景:")
                profitable_scenarios.sort(key=lambda x: x['profit_rate'], reverse=True)
                
                for scenario in profitable_scenarios[:5]:
                    water_desc = f"{(1-scenario['water_rate'])*100:.0f}%抽水"
                    print(f"  单场赔率{scenario['odds']}, {water_desc}: "
                          f"期望收益率 +{scenario['profit_rate']:.1f}%, "
                          f"三串赔率 {scenario['triple_odds']:.2f}")
                
                print(f"\n💡 投资策略建议:")
                print(f"1. 重点关注准确率>{best_accuracy:.0%}的顶级公司")
                print(f"2. 选择单场赔率1.8-2.2的比赛组合")
                print(f"3. 寻找抽水率较低的投注平台(抽水<10%)")
                print(f"4. 严格资金管理，单次投注不超过资金的2-3%")
                print(f"5. 长期投注才能体现数学期望优势")
                
            else:
                print("\n❌ 当前准确率下，三串投注无正期望值")
                print("💡 建议:")
                print("1. 继续优化模型，提升单场准确率至65%+")
                print("2. 考虑二串投注降低风险")
                print("3. 或专注单场高概率投注")
        
        # 风险提醒
        print(f"\n⚠️ 风险提醒:")
        print("1. 以上分析基于历史数据，实际表现可能有差异")
        print("2. 三串投注风险较高，需要严格的资金管理")
        print("3. 博彩市场存在不确定性，投资需谨慎")
        print("4. 本分析仅供参考，不构成投资建议")
    
    def generate_monte_carlo_simulation(self, accuracy: float, num_bets: int = 1000, bet_amount: float = 100):
        """蒙特卡洛模拟三串投注"""
        import random
        
        print(f"\n{'='*80}")
        print(f"蒙特卡洛模拟 - 准确率{accuracy:.1%}, {num_bets}次投注")
        print(f"{'='*80}")
        
        # 假设单场赔率2.0，三串赔率8.0，抽水率10%
        single_odds = 2.0
        triple_odds = single_odds ** 3 * 0.9  # 考虑10%抽水
        
        results = []
        
        for _ in range(num_bets):
            # 模拟三场比赛
            wins = 0
            for _ in range(3):
                if random.random() < accuracy:
                    wins += 1
            
            # 三场全中才有奖金
            if wins == 3:
                profit = bet_amount * triple_odds - bet_amount
            else:
                profit = -bet_amount
            
            results.append(profit)
        
        # 统计结果
        total_profit = sum(results)
        win_count = len([r for r in results if r > 0])
        win_rate = win_count / num_bets
        
        print(f"投注结果:")
        print(f"  总投注额: {num_bets * bet_amount:,.0f}")
        print(f"  总盈亏: {total_profit:+,.0f}")
        print(f"  收益率: {total_profit/(num_bets * bet_amount)*100:+.1f}%")
        print(f"  中奖次数: {win_count}/{num_bets}")
        print(f"  中奖率: {win_rate:.1%}")
        print(f"  理论中奖率: {accuracy**3:.1%}")
        print(f"  平均单次盈亏: {total_profit/num_bets:+.1f}")


def main():
    """主函数"""
    analyzer = TripleBetAnalyzer()
    
    # 分析所有联赛
    analyzer.analyze_all_leagues()
    
    # 选择最佳准确率进行蒙特卡洛模拟
    print(f"\n{'='*100}")
    print("请输入要模拟的准确率 (0.5-0.8之间，按回车使用0.58):")
    
    try:
        user_input = input().strip()
        if user_input:
            accuracy = float(user_input)
        else:
            accuracy = 0.58  # 默认使用58%准确率
        
        if 0.5 <= accuracy <= 0.8:
            analyzer.generate_monte_carlo_simulation(accuracy)
        else:
            print("准确率应在50%-80%之间")
    
    except (ValueError, KeyboardInterrupt):
        print("使用默认58%准确率进行模拟")
        analyzer.generate_monte_carlo_simulation(0.58)


if __name__ == "__main__":
    main()