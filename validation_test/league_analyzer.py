#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
联赛验证分析器 - 支持参数化分析不同联赛
"""

import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
import pandas as pd

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class LeagueAnalyzer:
    """联赛分析器 - 支持多联赛参数化分析"""
    
    # 联赛配置 (基于实际数据库中的联赛)
    LEAGUE_CONFIG = {
        'premier': {'id': 36, 'name': '英超', 'full_name': 'English Premier League', 'country': 'England', 'status': 'completed'},
        'laliga': {'id': 31, 'name': '西甲', 'full_name': 'Spanish La Liga', 'country': 'Spain', 'status': 'pending'}, 
        'bundesliga': {'id': 8, 'name': '德甲', 'full_name': 'German Bundesliga', 'country': 'Germany', 'status': 'pending'},
        'seriea': {'id': 34, 'name': '意甲', 'full_name': 'Italian Serie A', 'country': 'Italy', 'status': 'pending'},
        'ligue1': {'id': 11, 'name': '法甲', 'full_name': 'France Ligue 1', 'country': 'France', 'status': 'pending'},
        'kleague': {'id': 15, 'name': '韩国K联赛', 'full_name': 'K League 1', 'country': 'South Korea', 'status': 'pending'},
        'jleague': {'id': 25, 'name': '日职联', 'full_name': 'J1 League', 'country': 'Japan', 'status': 'pending'}
    }
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        
        # 加载映射规则
        mapping_file = Path(__file__).parent / "recommendation_mapping.json"
        with open(mapping_file, 'r', encoding='utf-8') as f:
            self.mapping_config = json.load(f)
        
        self.mapping_rules = self.mapping_config['mapping_rules']['rules']
        
    def get_available_leagues(self) -> Dict[str, Dict]:
        """获取可用的联赛列表"""
        return self.LEAGUE_CONFIG
    
    def check_league_readiness(self, league_ids: List[int]) -> Dict[int, bool]:
        """检查联赛是否准备好进行验证"""
        readiness = {}
        
        for league_id in league_ids:
            # 检查广义实力数据
            power_stats = self.db.execute_query('''
                SELECT 
                    COUNT(DISTINCT target_round) as round_count,
                    MIN(target_round) as min_round, 
                    MAX(target_round) as max_round
                FROM team_power_ratings_history 
                WHERE league_id = %s
            ''', [league_id], fetch='one')
            
            # 需要有多轮广义实力数据才能进行验证
            if power_stats and power_stats['round_count'] and power_stats['round_count'] > 0:
                min_round = power_stats['min_round'] or 0
                max_round = power_stats['max_round'] or 0
                readiness[league_id] = max_round > min_round
            else:
                readiness[league_id] = False
        
        return readiness
    
    def get_league_matches(self, league_ids: List[int], start_round: int = 1, 
                          end_round: int = 38, table_suffix: str = None) -> Dict[int, List[Dict]]:
        """获取联赛比赛数据"""
        if table_suffix:
            table_name = f"{table_suffix}_validation_results"
        else:
            # 根据联赛ID生成表名
            if len(league_ids) == 1:
                league_key = next((k for k, v in self.LEAGUE_CONFIG.items() if v['id'] == league_ids[0]), 'unknown')
                table_name = f"{league_key}_validation_results"
            else:
                table_name = "multi_league_validation_results"
        
        # 检查表是否存在
        check_query = f"SHOW TABLES LIKE '{table_name}'"
        if not self.db.execute_query(check_query, fetch='one'):
            self.logger.error(f"表 {table_name} 不存在")
            return {}
        
        # 构建WHERE条件
        if len(league_ids) == 1:
            league_condition = ""  # 单联赛表不需要联赛ID条件
            params = [start_round, end_round]
        else:
            league_condition = f"AND league_id IN ({','.join(['%s'] * len(league_ids))})"
            params = [start_round, end_round] + league_ids
        
        query = f"""
            SELECT 
                match_id, company_id, round_number,
                home_team_id, away_team_id, home_team_name, away_team_name,
                actual_home_score, actual_away_score,
                initial_recommendation, current_recommendation,
                initial_rule_diff, current_rule_diff,
                power_diff
            FROM {table_name}
            WHERE round_number >= %s AND round_number <= %s
            {league_condition}
            ORDER BY round_number, match_id, company_id
        """
        
        results = self.db.execute_query(query, params, fetch='all')
        
        # 按联赛分组
        league_data = defaultdict(list)
        for result in results:
            # 如果是多联赛表，需要获取联赛ID
            if len(league_ids) > 1:
                league_id = result.get('league_id', league_ids[0])
            else:
                league_id = league_ids[0]
            
            league_data[league_id].append(result)
        
        self.logger.info(f"加载了 {len(results)} 条验证数据，涵盖 {len(league_data)} 个联赛")
        return dict(league_data)
    
    def get_match_results(self, validation_data: List[Dict]) -> Dict[int, str]:
        """从验证数据中提取比赛结果"""
        match_results = {}
        
        for row in validation_data:
            match_id = row['match_id']
            if match_id in match_results:
                continue
                
            home_score = row['actual_home_score']
            away_score = row['actual_away_score']
            
            if home_score > away_score:
                match_results[match_id] = '主胜'
            elif home_score == away_score:
                match_results[match_id] = '平'
            else:
                match_results[match_id] = '负'
        
        return match_results
    
    def check_prediction_accuracy(self, recommendation: str, actual_result: str, 
                                  rule_diff: float = None) -> bool:
        """检查推荐是否准确"""
        if recommendation not in self.mapping_rules:
            return False
        
        rule = self.mapping_rules[recommendation]
        expected_results = rule['result']
        
        # 处理动态判断的双平偏让平
        if expected_results == "dynamic":
            if rule_diff is None:
                return False
            
            # 根据规则差判断
            if rule_diff > 0:
                expected_results = "主胜"  # 主队规则值大
            elif rule_diff < 0:
                expected_results = "负"   # 客队规则值大
            else:
                expected_results = "平"   # 相等
        
        # 处理数组形式的结果
        if isinstance(expected_results, list):
            return actual_result in expected_results
        else:
            return actual_result == expected_results
    
    def analyze_league_accuracy(self, league_data: Dict[int, List[Dict]]) -> Dict[int, Dict]:
        """分析各联赛的准确率"""
        league_results = {}
        
        for league_id, validation_data in league_data.items():
            self.logger.info(f"分析联赛 {league_id} 的准确率...")
            
            # 获取比赛结果
            match_results = self.get_match_results(validation_data)
            
            # 按公司统计
            company_stats = defaultdict(lambda: {
                'initial_total': 0, 'initial_correct': 0,
                'current_total': 0, 'current_correct': 0,
                'consistency_total': 0, 'consistency_match': 0
            })
            
            for row in validation_data:
                company_id = row['company_id']
                match_id = row['match_id']
                
                if match_id not in match_results:
                    continue
                
                actual_result = match_results[match_id]
                stats = company_stats[company_id]
                
                # 初盘准确率
                initial_rec = row['initial_recommendation']
                initial_rule_diff = float(row['initial_rule_diff'])
                if self.check_prediction_accuracy(initial_rec, actual_result, initial_rule_diff):
                    stats['initial_correct'] += 1
                stats['initial_total'] += 1
                
                # 即时盘准确率
                current_rec = row['current_recommendation']
                current_rule_diff = float(row['current_rule_diff'])
                if self.check_prediction_accuracy(current_rec, actual_result, current_rule_diff):
                    stats['current_correct'] += 1
                stats['current_total'] += 1
                
                # 一致性统计
                if initial_rec == current_rec:
                    stats['consistency_match'] += 1
                stats['consistency_total'] += 1
            
            # 计算最终结果
            company_results = []
            for company_id, stats in company_stats.items():
                if stats['current_total'] == 0:
                    continue
                
                initial_accuracy = stats['initial_correct'] / stats['initial_total'] if stats['initial_total'] > 0 else 0
                current_accuracy = stats['current_correct'] / stats['current_total'] if stats['current_total'] > 0 else 0
                consistency = stats['consistency_match'] / stats['consistency_total'] if stats['consistency_total'] > 0 else 0
                
                company_results.append({
                    'company_id': company_id,
                    'initial_accuracy': initial_accuracy,
                    'current_accuracy': current_accuracy,
                    'consistency': consistency,
                    'total_predictions': stats['current_total'],
                    'initial_correct': stats['initial_correct'],
                    'current_correct': stats['current_correct']
                })
            
            league_results[league_id] = {
                'companies': company_results,
                'total_companies': len(company_results),
                'total_predictions': sum(c['total_predictions'] for c in company_results)
            }
            
            self.logger.info(f"联赛 {league_id} 完成：{len(company_results)} 家公司")
        
        return league_results
    
    def generate_reports(self, league_results: Dict[int, Dict], 
                        top_accuracy: int = 15, top_consistency: int = 10) -> Dict[int, Dict]:
        """生成报告"""
        reports = {}
        
        for league_id, data in league_results.items():
            companies = data['companies']
            
            # 即时盘准确率前N名
            top_current = sorted(companies, key=lambda x: x['current_accuracy'], reverse=True)[:top_accuracy]
            
            # 在准确率前N名中找一致性前M名
            top_company_ids = {c['company_id'] for c in top_current}
            consistency_candidates = [c for c in companies if c['company_id'] in top_company_ids]
            top_consist = sorted(consistency_candidates, key=lambda x: x['consistency'], reverse=True)[:top_consistency]
            
            reports[league_id] = {
                'league_info': data,
                'top_accuracy': top_current,
                'top_consistency': top_consist
            }
        
        return reports
    
    def generate_report_content(self, reports: Dict[int, Dict]) -> str:
        """生成报告内容"""
        content = []
        
        for league_id, report in reports.items():
            league_name = next((v['name'] for k, v in self.LEAGUE_CONFIG.items() if v['id'] == league_id), f'联赛{league_id}')
            
            content.append("="*80)
            content.append(f"{league_name} 验证结果分析报告")
            content.append("="*80)
            content.append(f"总公司数: {report['league_info']['total_companies']}")
            content.append(f"总预测数: {report['league_info']['total_predictions']}")
            content.append("")
            
            # 准确率排名
            content.append(f"[即时盘推荐准确率排名] (前{len(report['top_accuracy'])}名)")
            content.append("-" * 80)
            content.append(f"{'排名':<4} {'公司ID':<8} {'即时准确率':<12} {'初盘准确率':<12} {'预测总数':<8} {'一致性':<8}")
            content.append("-" * 80)
            
            for i, result in enumerate(report['top_accuracy'], 1):
                content.append(f"{i:<4} {result['company_id']:<8} "
                              f"{result['current_accuracy']:<12.3f} {result['initial_accuracy']:<12.3f} "
                              f"{result['total_predictions']:<8} {result['consistency']:<8.3f}")
            
            content.append("")
            
            # 一致性排名
            content.append(f"[初盘即时盘一致性排名] (准确率前{len(report['top_accuracy'])}名中的前{len(report['top_consistency'])}名)")
            content.append("-" * 80)
            content.append(f"{'排名':<4} {'公司ID':<8} {'一致性':<10} {'即时准确率':<12} {'初盘准确率':<12} {'预测总数':<8}")
            content.append("-" * 80)
            
            for i, result in enumerate(report['top_consistency'], 1):
                content.append(f"{i:<4} {result['company_id']:<8} "
                              f"{result['consistency']:<10.3f} {result['current_accuracy']:<12.3f} "
                              f"{result['initial_accuracy']:<12.3f} {result['total_predictions']:<8}")
            
            content.append("")
            
            if report['top_accuracy']:
                content.append(f"{league_name} 总结:")
                content.append(f"- 即时盘准确率最高: 公司{report['top_accuracy'][0]['company_id']} ({report['top_accuracy'][0]['current_accuracy']:.3f})")
                if report['top_consistency']:
                    content.append(f"- 一致性最高: 公司{report['top_consistency'][0]['company_id']} ({report['top_consistency'][0]['consistency']:.3f})")
            
            content.append("")
            content.append("")
        
        return "\n".join(content)
    
    def print_reports(self, reports: Dict[int, Dict]):
        """打印报告"""
        content = self.generate_report_content(reports)
        print(content)
    
    def save_reports(self, reports: Dict[int, Dict], output_file: str = None):
        """保存报告到文件"""
        if output_file is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"league_analysis_report_{timestamp}.txt"
        
        content = self.generate_report_content(reports)
        
        # 确保输出目录存在
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        self.logger.info(f"报告已保存到: {output_path.absolute()}")
        return output_path


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='联赛验证结果分析器')
    parser.add_argument('--leagues', '-l', nargs='+', 
                       choices=['premier', 'laliga', 'bundesliga', 'seriea', 'ligue1', 'kleague', 'jleague', 'all'],
                       default=['premier'], help='要分析的联赛 (premier=英超, laliga=西甲, bundesliga=德甲, seriea=意甲, ligue1=法甲, kleague=韩国K联赛, jleague=日本J1联赛, all=全部)')
    parser.add_argument('--start-round', '-s', type=int, default=10, 
                       help='起始轮次 (默认: 10)')
    parser.add_argument('--end-round', '-e', type=int, default=38,
                       help='结束轮次 (默认: 38)')
    parser.add_argument('--top-accuracy', '-ta', type=int, default=15,
                       help='准确率排名显示数量 (默认: 15)')
    parser.add_argument('--top-consistency', '-tc', type=int, default=10,
                       help='一致性排名显示数量 (默认: 10)')
    parser.add_argument('--table-suffix', '-t', type=str,
                       help='自定义表名后缀 (如: premier_league)')
    parser.add_argument('--output', '-o', type=str,
                       help='输出报告文件路径 (默认: 自动生成时间戳文件名)')
    parser.add_argument('--no-save', action='store_true',
                       help='不保存报告文件，仅在控制台显示')
    
    args = parser.parse_args()
    
    analyzer = LeagueAnalyzer()
    
    # 处理联赛选择
    if 'all' in args.leagues:
        selected_leagues = list(analyzer.LEAGUE_CONFIG.keys())
    else:
        selected_leagues = args.leagues
    
    # 获取联赛ID和中文名
    league_ids = [analyzer.LEAGUE_CONFIG[league]['id'] for league in selected_leagues]
    league_names = [analyzer.LEAGUE_CONFIG[league]['name'] for league in selected_leagues]
    
    print(f"分析联赛: {', '.join(league_names)} ({', '.join(selected_leagues)})")
    print(f"轮次范围: {args.start_round}-{args.end_round}")
    print(f"准确率排名: 前{args.top_accuracy}名")
    print(f"一致性排名: 前{args.top_consistency}名")
    if args.table_suffix:
        print(f"使用表: {args.table_suffix}_validation_results")
    
    # 检查联赛验证就绪状态
    if not args.table_suffix:  # 只在没有指定表名时检查
        readiness = analyzer.check_league_readiness(league_ids)
        not_ready = [lid for lid, ready in readiness.items() if not ready]
        
        if not_ready:
            not_ready_names = []
            for lid in not_ready:
                if lid in league_ids:
                    idx = league_ids.index(lid)
                    not_ready_names.append(league_names[idx])
            
            print(f"[警告] 以下联赛缺少广义实力数据，无法验证: {', '.join(not_ready_names)}")
            ready_leagues = [lid for lid in league_ids if readiness.get(lid, False)]
            if not ready_leagues:
                print("[错误] 所选联赛均无法验证，请检查广义实力数据")
                return
            league_ids = ready_leagues  # 只保留可验证的联赛
            # 更新联赛名称列表
            league_names = [analyzer.LEAGUE_CONFIG[league]['name'] for league in selected_leagues if analyzer.LEAGUE_CONFIG[league]['id'] in league_ids]
    
    print("-" * 50)
    
    # 获取数据
    league_data = analyzer.get_league_matches(
        league_ids, args.start_round, args.end_round, args.table_suffix
    )
    
    if not league_data:
        print("未找到验证数据")
        return
    
    # 分析准确率
    league_results = analyzer.analyze_league_accuracy(league_data)
    
    # 生成报告
    reports = analyzer.generate_reports(league_results, args.top_accuracy, args.top_consistency)
    
    # 打印报告
    analyzer.print_reports(reports)
    
    # 保存报告文件
    if not args.no_save:
        output_file = analyzer.save_reports(reports, args.output)
        print(f"\n[报告文件已保存]: {output_file}")
    else:
        print("\n[仅控制台显示，未保存报告文件]")


if __name__ == "__main__":
    main()