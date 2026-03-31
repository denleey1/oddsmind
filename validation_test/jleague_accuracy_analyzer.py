#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日职联准确率分析器
分析已保存的验证结果，显示详细的准确率统计
"""

import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class JLeagueAccuracyAnalyzer:
    """日职联准确率分析器"""
    
    def __init__(self, table_name='jleague_validation_results'):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.table_name = table_name
        
    def load_validation_results(self):
        """加载验证结果"""
        query = f"""
        SELECT 
            match_id, company_id, round_number,
            home_team_name, away_team_name,
            actual_home_score, actual_away_score,
            initial_recommendation, current_recommendation,
            power_diff, initial_rule_diff, current_rule_diff
        FROM {self.table_name}
        ORDER BY round_number, match_id, company_id
        """
        
        results = self.db.execute_query(query, fetch='all')
        self.logger.info(f"加载了 {len(results)} 条验证结果")
        
        return results
    
    def map_recommendation_to_result(self, recommendation):
        """将推荐结果映射为比赛结果"""
        if not recommendation:
            return 'unknown'
            
        rec = str(recommendation).lower()
        
        # 主胜相关
        if any(keyword in rec for keyword in ['主胜', '主让', '主队', 'home']):
            return 'home_win'
        
        # 客胜相关  
        if any(keyword in rec for keyword in ['客胜', '客让', '客队', 'away']):
            return 'away_win'
            
        # 平局相关
        if any(keyword in rec for keyword in ['平局', '平', 'draw', '双平']):
            return 'draw'
            
        return 'unknown'
    
    def analyze_accuracy(self):
        """分析准确率"""
        results = self.load_validation_results()
        
        if not results:
            print("没有数据可供分析")
            return
            
        print("\n" + "="*80)
        print("📊 日职联预测准确率分析报告")
        print("="*80)
        
        # 计算实际比赛结果
        for result in results:
            home_score = result['actual_home_score'] or 0
            away_score = result['actual_away_score'] or 0
            
            if home_score > away_score:
                result['actual_result'] = 'home_win'
            elif home_score < away_score:
                result['actual_result'] = 'away_win'  
            else:
                result['actual_result'] = 'draw'
                
            # 映射推荐结果
            result['initial_prediction'] = self.map_recommendation_to_result(result['initial_recommendation'])
            result['current_prediction'] = self.map_recommendation_to_result(result['current_recommendation'])
        
        # 1. 整体统计
        total_predictions = len(results)
        companies = set(r['company_id'] for r in results)
        matches = set(r['match_id'] for r in results)
        rounds = set(r['round_number'] for r in results)
        
        print(f"📋 基本信息:")
        print(f"   总预测数: {total_predictions:,} 次")
        print(f"   涉及比赛: {len(matches)} 场")
        print(f"   涉及公司: {len(companies)} 家") 
        print(f"   涉及轮次: 第{min(rounds)}-{max(rounds)}轮")
        
        # 2. 各公司准确率分析
        print(f"\n🏆 各公司预测准确率排名 (TOP 20):")
        print("-"*70)
        
        company_stats = {}
        for company_id in companies:
            company_results = [r for r in results if r['company_id'] == company_id]
            
            # 计算准确率
            initial_correct = 0
            current_correct = 0
            
            for r in company_results:
                if r['initial_prediction'] == r['actual_result']:
                    initial_correct += 1
                if r['current_prediction'] == r['actual_result']:
                    current_correct += 1
            
            total = len(company_results)
            initial_accuracy = (initial_correct / total) * 100 if total > 0 else 0
            current_accuracy = (current_correct / total) * 100 if total > 0 else 0
            
            company_stats[company_id] = {
                'total': total,
                'initial_correct': initial_correct,
                'current_correct': current_correct,
                'initial_accuracy': initial_accuracy,
                'current_accuracy': current_accuracy
            }
        
        # 按初盘准确率排序，显示TOP 20
        sorted_companies = sorted(company_stats.items(), key=lambda x: x[1]['initial_accuracy'], reverse=True)[:20]
        
        print(f"{'公司ID':<8} {'总预测':<8} {'初盘正确':<10} {'初盘准确率':<12} {'即时正确':<10} {'即时准确率':<12}")
        print("-"*70)
        
        for company_id, stats in sorted_companies:
            print(f"{company_id:<8} {stats['total']:<8} {stats['initial_correct']:<10} "
                  f"{stats['initial_accuracy']:.1f}%{'':<7} {stats['current_correct']:<10} "
                  f"{stats['current_accuracy']:.1f}%")
        
        # 3. 最佳公司
        if sorted_companies:
            best_company = sorted_companies[0]
            print(f"\n🥇 最佳预测公司:")
            print(f"   公司ID: {best_company[0]}")
            print(f"   预测场次: {best_company[1]['total']} 次")
            print(f"   初盘准确率: {best_company[1]['initial_accuracy']:.1f}%")
            print(f"   即时准确率: {best_company[1]['current_accuracy']:.1f}%")
        
        # 4. 胜平负准确率分析
        print(f"\n⚽ 胜平负预测准确率分析:")
        print("-"*55)
        
        result_types = ['home_win', 'draw', 'away_win'] 
        result_names = {'home_win': '主胜', 'draw': '平局', 'away_win': '客胜'}
        
        for result_type in result_types:
            # 实际该结果的比赛
            actual_results = [r for r in results if r['actual_result'] == result_type]
            if not actual_results:
                continue
                
            # 预测该结果且正确的
            initial_predicted_correct = 0
            current_predicted_correct = 0
            
            for r in actual_results:
                if r['initial_prediction'] == result_type:
                    initial_predicted_correct += 1
                if r['current_prediction'] == result_type:
                    current_predicted_correct += 1
            
            total_actual = len(actual_results)
            initial_accuracy = (initial_predicted_correct / total_actual) * 100 if total_actual > 0 else 0
            current_accuracy = (current_predicted_correct / total_actual) * 100 if total_actual > 0 else 0
            
            print(f"{result_names[result_type]:<6} 实际{total_actual:>4}次 "
                  f"初盘识别{initial_predicted_correct:>4}次({initial_accuracy:>5.1f}%) "
                  f"即时识别{current_predicted_correct:>4}次({current_accuracy:>5.1f}%)")
        
        # 5. 整体准确率对比
        total_initial_correct = sum(s['initial_correct'] for s in company_stats.values())
        total_current_correct = sum(s['current_correct'] for s in company_stats.values()) 
        
        overall_initial_accuracy = (total_initial_correct / total_predictions) * 100
        overall_current_accuracy = (total_current_correct / total_predictions) * 100
        
        print(f"\n📈 整体准确率:")
        print(f"   初盘整体准确率: {overall_initial_accuracy:.1f}% ({total_initial_correct:,}/{total_predictions:,})")
        print(f"   即时整体准确率: {overall_current_accuracy:.1f}% ({total_current_correct:,}/{total_predictions:,})")
        
        accuracy_diff = overall_current_accuracy - overall_initial_accuracy
        trend = "↗️" if accuracy_diff > 0 else "↘️" if accuracy_diff < 0 else "➡️"
        print(f"   准确率变化: {trend} {accuracy_diff:+.1f}%")
        
        # 6. 主要公司(Tier 1)分析
        print(f"\n🎯 主要公司 (Tier 1) 准确率分析:")
        print("-"*50)
        tier1_companies = [791, 16, 680, 649, 104]
        tier1_names = {
            791: "Sisa(意大利)", 
            16: "10Bet(英国)", 
            680: "Stanley(马尔他)",
            649: "IBC(哥斯达黎加)", 
            104: "Interwet(塞浦路斯)"
        }
        
        tier1_results = []
        for company_id in tier1_companies:
            if company_id in company_stats:
                stats = company_stats[company_id]
                tier1_results.append((company_id, stats))
                
                print(f"{tier1_names[company_id]:<20} "
                      f"初盘: {stats['initial_accuracy']:>5.1f}% "
                      f"即时: {stats['current_accuracy']:>5.1f}% "
                      f"({stats['total']} 次预测)")
        
        if tier1_results:
            best_tier1 = max(tier1_results, key=lambda x: x[1]['initial_accuracy'])
            print(f"\n   Tier 1最佳: {tier1_names[best_tier1[0]]} (初盘{best_tier1[1]['initial_accuracy']:.1f}%)")
        
        print("="*80)


def main():
    """主函数"""
    analyzer = JLeagueAccuracyAnalyzer()
    analyzer.analyze_accuracy()


if __name__ == "__main__":
    main()