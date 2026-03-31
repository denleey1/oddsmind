#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
初盘准确率分析
统计和分析各公司的初盘推荐准确率
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection


class InitialOddsAnalyzer:
    """初盘准确率分析器"""
    
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
    
    def get_league_initial_accuracy(self, league_id: int) -> Dict:
        """获取联赛初盘准确率数据"""
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
            initial_recommendation, initial_rule_diff,
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
            
            # 判断初盘推荐是否正确
            initial_recommendation = row['initial_recommendation']
            initial_rule_diff = row['initial_rule_diff'] or 0
            
            initial_correct = self._is_recommendation_correct(
                initial_recommendation, actual_result, initial_rule_diff, recommendation_mapping
            )
            
            # 判断即时盘推荐是否正确
            current_recommendation = row['current_recommendation']
            current_rule_diff = row['current_rule_diff'] or 0
            
            current_correct = self._is_recommendation_correct(
                current_recommendation, actual_result, current_rule_diff, recommendation_mapping
            )
            
            if company_id not in company_stats:
                company_stats[company_id] = {
                    'total': 0,
                    'initial_correct': 0,
                    'current_correct': 0,
                    'both_correct': 0,
                    'consistent_matches': 0,  # 初盘即时盘推荐一致的场次
                    'consistent_correct': 0   # 一致且都正确的场次
                }
            
            company_stats[company_id]['total'] += 1
            company_stats[company_id]['initial_correct'] += initial_correct
            company_stats[company_id]['current_correct'] += current_correct
            
            # 统计一致性
            if initial_recommendation == current_recommendation:
                company_stats[company_id]['consistent_matches'] += 1
                if initial_correct and current_correct:
                    company_stats[company_id]['consistent_correct'] += 1
            
            # 统计双重正确
            if initial_correct and current_correct:
                company_stats[company_id]['both_correct'] += 1
        
        # 转换为准确率列表
        accuracy_list = []
        for company_id, stats in company_stats.items():
            if stats['total'] >= 50:  # 至少50个样本
                initial_accuracy = (stats['initial_correct'] * 100.0) / stats['total']
                current_accuracy = (stats['current_correct'] * 100.0) / stats['total']
                consistency_rate = (stats['consistent_matches'] * 100.0) / stats['total']
                consistent_accuracy = (stats['consistent_correct'] * 100.0) / stats['consistent_matches'] if stats['consistent_matches'] > 0 else 0
                
                accuracy_list.append({
                    'company_id': company_id,
                    'total_predictions': stats['total'],
                    'initial_correct': stats['initial_correct'],
                    'current_correct': stats['current_correct'],
                    'initial_accuracy': initial_accuracy,
                    'current_accuracy': current_accuracy,
                    'consistency_rate': consistency_rate,
                    'consistent_matches': stats['consistent_matches'],
                    'consistent_accuracy': consistent_accuracy
                })
        
        # 按初盘准确率排序
        accuracy_list.sort(key=lambda x: x['initial_accuracy'], reverse=True)
        
        if not accuracy_list:
            return {}
        
        return {
            'league_name': self.leagues[league_id]['name'],
            'total_companies': len(accuracy_list),
            'companies': accuracy_list
        }
    
    def generate_initial_odds_report(self) -> None:
        """生成初盘准确率报告"""
        print("=" * 100)
        print("初盘准确率分析报告")
        print("=" * 100)
        
        all_league_data = []
        
        # 分析每个联赛
        for league_id in self.leagues.keys():
            print(f"\n正在分析{self.leagues[league_id]['name']}初盘准确率...")
            
            try:
                league_data = self.get_league_initial_accuracy(league_id)
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
        
        # 生成详细报告
        print("\n" + "=" * 120)
        print("各联赛初盘vs即时盘准确率对比")
        print("=" * 120)
        
        global_top_companies = []
        
        for league_data in all_league_data:
            print(f"\n【{league_data['league_name']}】TOP5 初盘准确率公司")
            print("-" * 80)
            print("排名 | 公司ID | 初盘准确率 | 即时盘准确率 | 差值 | 一致性 | 一致时准确率")
            print("-" * 80)
            
            top5 = league_data['companies'][:5]
            for i, company in enumerate(top5, 1):
                diff = company['initial_accuracy'] - company['current_accuracy']
                print(f"{i:2d}   | {company['company_id']:6d} | "
                      f"{company['initial_accuracy']:8.1f}% | "
                      f"{company['current_accuracy']:9.1f}% | "
                      f"{diff:+5.1f}% | "
                      f"{company['consistency_rate']:5.1f}% | "
                      f"{company['consistent_accuracy']:8.1f}%")
                
                # 收集全球TOP公司
                company['league'] = league_data['league_name']
                global_top_companies.append(company)
        
        # 全球初盘准确率排名
        global_top_companies.sort(key=lambda x: x['initial_accuracy'], reverse=True)
        
        print("\n" + "=" * 120)
        print("全球初盘准确率TOP20公司")
        print("=" * 120)
        print("排名 | 公司ID | 联赛 | 初盘准确率 | 即时盘准确率 | 样本数 | 一致性")
        print("-" * 120)
        
        for i, company in enumerate(global_top_companies[:20], 1):
            print(f"{i:2d}   | {company['company_id']:6d} | "
                  f"{company['league']:8s} | "
                  f"{company['initial_accuracy']:8.1f}% | "
                  f"{company['current_accuracy']:9.1f}% | "
                  f"{company['total_predictions']:6d} | "
                  f"{company['consistency_rate']:5.1f}%")
        
        # 统计分析
        print(f"\n" + "=" * 100)
        print("初盘vs即时盘统计分析")
        print("=" * 100)
        
        initial_better = sum(1 for c in global_top_companies if c['initial_accuracy'] > c['current_accuracy'])
        current_better = sum(1 for c in global_top_companies if c['current_accuracy'] > c['initial_accuracy'])
        equal = len(global_top_companies) - initial_better - current_better
        
        print(f"初盘准确率更高的公司: {initial_better} 家 ({initial_better/len(global_top_companies)*100:.1f}%)")
        print(f"即时盘准确率更高的公司: {current_better} 家 ({current_better/len(global_top_companies)*100:.1f}%)")
        print(f"准确率相等的公司: {equal} 家 ({equal/len(global_top_companies)*100:.1f}%)")
        
        avg_initial = sum(c['initial_accuracy'] for c in global_top_companies) / len(global_top_companies)
        avg_current = sum(c['current_accuracy'] for c in global_top_companies) / len(global_top_companies)
        avg_consistency = sum(c['consistency_rate'] for c in global_top_companies) / len(global_top_companies)
        
        print(f"\n平均初盘准确率: {avg_initial:.2f}%")
        print(f"平均即时盘准确率: {avg_current:.2f}%")
        print(f"平均一致性: {avg_consistency:.2f}%")
        print(f"准确率差值: {avg_initial - avg_current:+.2f}%")
        
        # 保存报告到文件
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = Path(__file__).parent / f"initial_odds_report_{timestamp}.md"
        
        self._save_report_to_file(all_league_data, global_top_companies, filename)
        print(f"\n📄 报告已保存至: {filename}")
    
    def _save_report_to_file(self, all_league_data: List[Dict], 
                           global_companies: List[Dict], filename: Path) -> None:
        """保存报告到Markdown文件"""
        content = f"""# 初盘准确率分析报告

**报告生成时间:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 📊 核心发现

### 初盘 vs 即时盘对比统计

"""
        
        initial_better = sum(1 for c in global_companies if c['initial_accuracy'] > c['current_accuracy'])
        current_better = sum(1 for c in global_companies if c['current_accuracy'] > c['initial_accuracy'])
        equal = len(global_companies) - initial_better - current_better
        
        avg_initial = sum(c['initial_accuracy'] for c in global_companies) / len(global_companies)
        avg_current = sum(c['current_accuracy'] for c in global_companies) / len(global_companies)
        avg_consistency = sum(c['consistency_rate'] for c in global_companies) / len(global_companies)
        
        content += f"""
| 指标 | 初盘 | 即时盘 | 差值 |
|------|------|--------|------|
| 平均准确率 | {avg_initial:.2f}% | {avg_current:.2f}% | {avg_initial - avg_current:+.2f}% |
| 表现更好的公司数 | {initial_better} | {current_better} | - |
| 占比 | {initial_better/len(global_companies)*100:.1f}% | {current_better/len(global_companies)*100:.1f}% | - |

**平均一致性:** {avg_consistency:.2f}%

---

## 🏆 全球初盘准确率TOP20公司

| 排名 | 公司ID | 联赛 | 初盘准确率 | 即时盘准确率 | 样本数 | 一致性 |
|------|--------|------|------------|--------------|--------|--------|
"""
        
        for i, company in enumerate(global_companies[:20], 1):
            content += f"| {i} | {company['company_id']} | {company['league']} | {company['initial_accuracy']:.1f}% | {company['current_accuracy']:.1f}% | {company['total_predictions']} | {company['consistency_rate']:.1f}% |\n"
        
        content += "\n---\n\n## 📈 各联赛详细分析\n\n"
        
        for league_data in all_league_data:
            content += f"### {league_data['league_name']} TOP5公司\n\n"
            content += "| 排名 | 公司ID | 初盘准确率 | 即时盘准确率 | 差值 | 一致性 | 一致时准确率 |\n"
            content += "|------|--------|------------|--------------|------|--------|--------------|\n"
            
            for i, company in enumerate(league_data['companies'][:5], 1):
                diff = company['initial_accuracy'] - company['current_accuracy']
                content += f"| {i} | {company['company_id']} | {company['initial_accuracy']:.1f}% | {company['current_accuracy']:.1f}% | {diff:+.1f}% | {company['consistency_rate']:.1f}% | {company['consistent_accuracy']:.1f}% |\n"
            
            content += "\n"
        
        content += """
---

## 🎯 关键结论

1. **初盘vs即时盘准确率对比**: 整体而言初盘和即时盘准确率相近
2. **市场效率**: 数据反映了博彩市场的相对效率
3. **公司差异**: 不同公司在初盘和即时盘上存在明显差异
4. **一致性分析**: 高一致性公司更值得关注

---

*本报告基于历史数据分析生成，仅供参考。*
"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)


def main():
    """主函数"""
    analyzer = InitialOddsAnalyzer()
    analyzer.generate_initial_odds_report()


if __name__ == "__main__":
    main()