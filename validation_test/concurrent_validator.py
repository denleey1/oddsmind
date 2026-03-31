#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
并发联赛验证器 - 快速验证并输出准确率排名
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import concurrent.futures
from threading import Lock
import time

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class ConcurrentLeagueValidator:
    """并发联赛验证器"""
    
    def __init__(self, max_workers: int = 4):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.max_workers = max_workers
        self.lock = Lock()
        
        # 联赛配置
        self.leagues = {
            8: {'name': '德甲', 'code': 'bundesliga', 'start': 10, 'end': 34},
            11: {'name': '法甲', 'code': 'ligue1', 'start': 10, 'end': 34},
            15: {'name': '韩国K联赛', 'code': 'kleague', 'start': 10, 'end': 28},
            25: {'name': '日职联', 'code': 'jleague', 'start': 10, 'end': 29},
            31: {'name': '西甲', 'code': 'laliga', 'start': 10, 'end': 38},
            34: {'name': '意甲', 'code': 'seriea', 'start': 10, 'end': 38},
            36: {'name': '英超', 'code': 'premier', 'start': 10, 'end': 38}
        }
        
        # 缓存标准欧赔表和规则表
        self._load_analysis_tables()
        
        # 加载推荐映射规则
        self._load_recommendation_mapping()
        
    def _load_analysis_tables(self):
        """加载分析所需的参考表"""
        self.logger.info("加载分析参考表...")
        
        # 加载标准欧赔表
        query = """
            SELECT win_odds, loss_odds, distance, draw_odds
            FROM standard_european_odds
            ORDER BY win_odds, loss_odds
        """
        self.standard_odds = self.db.execute_query(query, fetch='all')
        
        # 按主胜和客胜分别排序以便二分查找
        self.standard_odds_by_win = sorted(
            [{'win_odds': float(row['win_odds']), 'distance': float(row['distance'])} 
             for row in self.standard_odds if row['win_odds'] <= 2.81],
            key=lambda x: x['win_odds']
        )
        
        self.standard_odds_by_loss = sorted(
            [{'odds': float(row['loss_odds']), 'distance': float(row['distance'])} 
             for row in self.standard_odds if row['loss_odds'] >= 2.02],
            key=lambda x: x['odds']
        )
        
        # 加载规则条件表
        query = """
            SELECT team_type, description, rule_value, range_low, range_high
            FROM odds_rule_conditions
            ORDER BY team_type, rule_value
        """
        rule_conditions = self.db.execute_query(query, fetch='all')
        
        self.rule_conditions_home = [r for r in rule_conditions if r['team_type'] == '主队']
        self.rule_conditions_away = [r for r in rule_conditions if r['team_type'] == '客队']
        
        # 加载规则结果表
        query = """
            SELECT rule_value_diff, outcome_if_ge_minus_1_5, outcome_if_lt_minus_1_5
            FROM rule_diff_outcomes
        """
        self.rule_outcomes = self.db.execute_query(query, fetch='all')
        
        self.logger.info(f"已加载 {len(self.standard_odds)} 条标准赔率，"
                        f"{len(self.rule_conditions_home)} 条主队规则，"
                        f"{len(self.rule_conditions_away)} 条客队规则，"
                        f"{len(self.rule_outcomes)} 条结果规则")

    def _load_recommendation_mapping(self):
        """加载推荐映射规则"""
        try:
            mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                self.recommendation_mapping = mapping_data['recommendations']
        except Exception as e:
            self.logger.warning(f"加载推荐映射失败: {e}")
            self.recommendation_mapping = {}

    def validate_league_concurrent(self, league_id: int) -> Dict:
        """并发验证单个联赛"""
        league_info = self.leagues[league_id]
        league_name = league_info['name']
        start_round = league_info['start']
        end_round = league_info['end']
        
        start_time = time.time()
        self.logger.info(f"开始并发验证{league_name}")
        
        # 获取比赛列表
        query = """
            SELECT 
                match_id, round_number, home_team_id, away_team_id,
                home_team_name, away_team_name, home_score, away_score,
                match_time, match_status
            FROM matches
            WHERE league_id = %s 
              AND round_number >= %s 
              AND round_number <= %s
              AND match_status = 'finished'
            ORDER BY round_number, match_time
        """
        
        matches = self.db.execute_query(query, [league_id, start_round, end_round], fetch='all')
        
        # 按轮次分组
        rounds_matches = {}
        for match in matches:
            round_num = match['round_number']
            if round_num not in rounds_matches:
                rounds_matches[round_num] = []
            rounds_matches[round_num].append(match)
        
        all_results = []
        
        # 并发处理各轮次
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_round = {}
            
            for round_num in sorted(rounds_matches.keys()):
                future = executor.submit(self._process_round, league_id, round_num, rounds_matches[round_num])
                future_to_round[future] = round_num
            
            for future in concurrent.futures.as_completed(future_to_round):
                round_num = future_to_round[future]
                try:
                    round_results = future.result()
                    all_results.extend(round_results)
                    self.logger.info(f"{league_name}第{round_num}轮完成，生成{len(round_results)}条结果")
                except Exception as e:
                    self.logger.error(f"{league_name}第{round_num}轮处理失败: {e}")
        
        # 保存结果
        if all_results:
            self._save_results(league_id, all_results)
        
        # 计算准确率并输出排名
        accuracy_stats = self._calculate_accuracy_rankings(league_id)
        
        end_time = time.time()
        duration = end_time - start_time
        
        return {
            'league_info': league_info,
            'total_results': len(all_results),
            'duration': duration,
            'accuracy_stats': accuracy_stats
        }

    def _process_round(self, league_id: int, round_num: int, round_matches: List[Dict]) -> List[Dict]:
        """处理单个轮次的比赛"""
        # 获取上一轮的实力数据
        power_round = round_num - 1
        power_ratings = self._get_power_ratings(league_id, power_round)
        
        if not power_ratings:
            return []
        
        round_results = []
        for match in round_matches:
            match_results = self._analyze_single_match(match, power_ratings, league_id)
            round_results.extend(match_results)
        
        return round_results

    def _get_power_ratings(self, league_id: int, target_round: int) -> Dict:
        """获取指定轮次的球队实力差值"""
        # 为并发创建新的数据库连接
        db = get_connection()
        
        query = """
            SELECT 
                tpr1.team_id as home_team_id,
                tpr2.team_id as away_team_id,
                tpr1.company_id,
                (tpr1.power_level - tpr2.power_level) as power_diff
            FROM team_power_ratings_history tpr1
            JOIN team_power_ratings_history tpr2 ON 
                tpr1.company_id = tpr2.company_id 
                AND tpr1.league_id = tpr2.league_id
                AND tpr1.target_round = tpr2.target_round
            WHERE tpr1.league_id = %s 
              AND tpr1.target_round = %s
        """
        
        power_data = db.execute_query(query, [league_id, target_round], fetch='all')
        
        power_dict = {}
        for row in power_data:
            key = (int(row['home_team_id']), int(row['away_team_id']), int(row['company_id']))
            power_dict[key] = float(row['power_diff'])
        
        return power_dict

    def _analyze_single_match(self, match: Dict, power_ratings: Dict, league_id: int) -> List[Dict]:
        """分析单场比赛的所有公司推荐"""
        match_id = match['match_id']
        home_team_id = match['home_team_id']
        away_team_id = match['away_team_id']
        
        # 为并发创建新的数据库连接
        db = get_connection()
        
        # 获取赔率数据
        odds_query = """
            SELECT 
                company_id,
                initial_home, initial_draw, initial_away, initial_return_rate,
                current_home, current_draw, current_away, current_return_rate
            FROM european_odds
            WHERE match_id = %s AND odds_type = '1x2'
        """
        
        odds_data = db.execute_query(odds_query, [match_id], fetch='all')
        results = []
        
        for odds in odds_data:
            company_id = int(odds['company_id'])
            
            # 检查是否有实力数据
            power_key = (home_team_id, away_team_id, company_id)
            if power_key not in power_ratings:
                continue
            
            power_diff = power_ratings[power_key]
            
            try:
                # 分析赔率并生成推荐
                analysis_result = self._analyze_odds(odds, power_diff)
                
                result = {
                    'match_id': match_id,
                    'company_id': company_id,
                    'round_number': match['round_number'],
                    'home_team_id': home_team_id,
                    'away_team_id': away_team_id,
                    'home_team_name': match['home_team_name'],
                    'away_team_name': match['away_team_name'],
                    'actual_home_score': match['home_score'],
                    'actual_away_score': match['away_score'],
                    'power_diff': power_diff,
                    'initial_recommendation': analysis_result['initial_recommendation'],
                    'current_recommendation': analysis_result['current_recommendation'],
                    'initial_rule_diff': analysis_result['initial_rule_diff'],
                    'current_rule_diff': analysis_result['current_rule_diff'],
                    'analysis_time': datetime.now()
                }
                
                results.append(result)
                
            except Exception as e:
                continue
        
        return results

    def _analyze_odds(self, odds: Dict, power_diff: float) -> Dict:
        """分析赔率并生成推荐"""
        # 计算满水赔率
        initial_return = float(odds['initial_return_rate']) / 100
        current_return = float(odds['current_return_rate']) / 100
        
        initial_home_fullwater = float(odds['initial_home']) / initial_return
        initial_away_fullwater = float(odds['initial_away']) / initial_return
        current_home_fullwater = float(odds['current_home']) / current_return
        current_away_fullwater = float(odds['current_away']) / current_return
        
        # 查找理论distance
        initial_home_distance = self._find_theory_distance(initial_home_fullwater, 'home')
        initial_away_distance = self._find_theory_distance(initial_away_fullwater, 'away')
        current_home_distance = self._find_theory_distance(current_home_fullwater, 'home')
        current_away_distance = self._find_theory_distance(current_away_fullwater, 'away')
        
        # 计算偏移
        initial_home_offset = initial_home_distance - power_diff
        initial_away_offset = initial_away_distance - power_diff
        current_home_offset = current_home_distance - power_diff
        current_away_offset = current_away_distance - power_diff
        
        # 匹配规则
        initial_home_rule = self._match_rule(initial_home_offset, 'home')
        initial_away_rule = self._match_rule(initial_away_offset, 'away')
        current_home_rule = self._match_rule(current_home_offset, 'home')
        current_away_rule = self._match_rule(current_away_offset, 'away')
        
        # 计算规则差并获取推荐
        initial_rule_diff = initial_home_rule['rule_value'] - initial_away_rule['rule_value']
        current_rule_diff = current_home_rule['rule_value'] - current_away_rule['rule_value']
        
        initial_recommendation = self._get_recommendation(initial_rule_diff, power_diff)
        current_recommendation = self._get_recommendation(current_rule_diff, power_diff)
        
        return {
            'initial_recommendation': initial_recommendation,
            'current_recommendation': current_recommendation,
            'initial_rule_diff': initial_rule_diff,
            'current_rule_diff': current_rule_diff
        }

    def _find_theory_distance(self, target_odds: float, odds_type: str) -> float:
        """查找理论distance值"""
        if odds_type == 'home':
            odds_list = self.standard_odds_by_win
            key_field = 'win_odds'
        else:  # away
            odds_list = self.standard_odds_by_loss
            key_field = 'odds'
        
        if not odds_list:
            return 0.0
        
        closest_item = min(odds_list, key=lambda x: abs(x[key_field] - target_odds))
        return closest_item['distance']
    
    def _match_rule(self, offset: float, team_type: str) -> Dict:
        """根据偏移值匹配规则"""
        conditions = self.rule_conditions_home if team_type == 'home' else self.rule_conditions_away
        
        for condition in conditions:
            range_low = condition['range_low'] if condition['range_low'] is not None else -9999
            range_high = condition['range_high'] if condition['range_high'] is not None else 9999
            
            if range_low <= offset <= range_high:
                return {
                    'description': condition['description'],
                    'rule_value': float(condition['rule_value'])
                }
        
        return {'description': 'unknown', 'rule_value': 0}
    
    def _get_recommendation(self, rule_diff: float, power_diff: float) -> str:
        """根据规则差获取推荐"""
        use_ge_minus_1_5 = (power_diff >= -1.5)
        
        closest_rule = min(self.rule_outcomes, 
                          key=lambda x: abs(float(x['rule_value_diff']) - rule_diff))
        
        if use_ge_minus_1_5:
            return closest_rule['outcome_if_ge_minus_1_5']
        else:
            return closest_rule['outcome_if_lt_minus_1_5']

    def _save_results(self, league_id: int, results: List[Dict]):
        """保存验证结果"""
        if not results:
            return
        
        league_info = self.leagues[league_id]
        table_name = f"{league_info['code']}_validation_results"
        
        # 创建表
        create_sql = f"""
        CREATE TABLE IF NOT EXISTS `{table_name}` (
            `id` int AUTO_INCREMENT PRIMARY KEY,
            `match_id` int NOT NULL,
            `company_id` int NOT NULL,
            `round_number` int NOT NULL,
            `home_team_id` int NOT NULL,
            `away_team_id` int NOT NULL,
            `home_team_name` varchar(100),
            `away_team_name` varchar(100),
            `actual_home_score` int,
            `actual_away_score` int,
            `power_diff` decimal(6,2),
            `initial_recommendation` varchar(50),
            `current_recommendation` varchar(50),
            `initial_rule_diff` decimal(5,1),
            `current_rule_diff` decimal(5,1),
            `analysis_time` datetime,
            INDEX `idx_match_company` (`match_id`, `company_id`),
            INDEX `idx_round` (`round_number`),
            INDEX `idx_recommendation` (`initial_recommendation`, `current_recommendation`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{league_info['name']}验证结果表'
        """
        
        self.db.execute_query(create_sql)
        self.db.execute_query(f"TRUNCATE TABLE `{table_name}`")  # 清空重新插入
        
        # 批量插入数据
        insert_sql = f"""
        INSERT INTO `{table_name}` (
            match_id, company_id, round_number, home_team_id, away_team_id,
            home_team_name, away_team_name, actual_home_score, actual_away_score,
            power_diff, initial_recommendation, current_recommendation,
            initial_rule_diff, current_rule_diff, analysis_time
        ) VALUES (
            %(match_id)s, %(company_id)s, %(round_number)s, %(home_team_id)s, %(away_team_id)s,
            %(home_team_name)s, %(away_team_name)s, %(actual_home_score)s, %(actual_away_score)s,
            %(power_diff)s, %(initial_recommendation)s, %(current_recommendation)s,
            %(initial_rule_diff)s, %(current_rule_diff)s, %(analysis_time)s
        )
        """
        
        self.db.execute_many(insert_sql, results)

    def _calculate_accuracy_rankings(self, league_id: int) -> Dict:
        """计算准确率并输出前5名排名"""
        league_info = self.leagues[league_id]
        table_name = f"{league_info['code']}_validation_results"
        
        # 获取验证结果
        query = f"""
        SELECT 
            company_id, actual_home_score, actual_away_score,
            initial_recommendation, current_recommendation, 
            initial_rule_diff, current_rule_diff
        FROM `{table_name}`
        """
        
        results = self.db.execute_query(query, fetch='all')
        if not results:
            return {}
        
        # 计算每个公司的准确率
        company_stats = {}
        
        for row in results:
            company_id = row['company_id']
            
            if company_id not in company_stats:
                company_stats[company_id] = {
                    'total': 0,
                    'initial_correct': 0,
                    'current_correct': 0,
                    'consistent_correct': 0,  # 一致且正确的次数
                    'consistent_total': 0     # 一致的总次数
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
            initial_rule_diff = float(row.get('initial_rule_diff', 0))
            current_rule_diff = float(row.get('current_rule_diff', 0))
            
            initial_correct = self._is_recommendation_correct(
                row['initial_recommendation'], actual_result, initial_rule_diff)
            current_correct = self._is_recommendation_correct(
                row['current_recommendation'], actual_result, current_rule_diff)
            
            stats['initial_correct'] += initial_correct
            stats['current_correct'] += current_correct
            
            # 检查一致性
            if row['initial_recommendation'] == row['current_recommendation']:
                stats['consistent_total'] += 1
                if current_correct:  # 一致且正确
                    stats['consistent_correct'] += 1
        
        # 计算准确率
        company_accuracies = []
        for company_id, stats in company_stats.items():
            if stats['total'] > 0:
                current_accuracy = stats['current_correct'] / stats['total']
                consistent_accuracy = (stats['consistent_correct'] / stats['consistent_total'] 
                                     if stats['consistent_total'] > 0 else 0)
                
                company_accuracies.append({
                    'company_id': company_id,
                    'total': stats['total'],
                    'current_accuracy': current_accuracy,
                    'consistent_accuracy': consistent_accuracy,
                    'consistent_total': stats['consistent_total'],
                    'current_correct': stats['current_correct'],
                    'consistent_correct': stats['consistent_correct']
                })
        
        # 排序并输出前5名
        self._print_top_rankings(league_info['name'], company_accuracies)
        
        return company_accuracies

    def _print_top_rankings(self, league_name: str, company_accuracies: List[Dict]):
        """输出前5名排名"""
        print(f"\n{'='*80}")
        print(f"{league_name} 准确率排名")
        print(f"{'='*80}")
        
        # 1. 即时盘准确率前5名
        top_current = sorted(company_accuracies, 
                           key=lambda x: x['current_accuracy'], reverse=True)[:5]
        
        print(f"\n【即时盘准确率 TOP5】")
        print(f"{'排名':<6} {'公司ID':<10} {'即时准确率':<12} {'预测总数':<10}")
        print("-" * 50)
        
        for i, company in enumerate(top_current, 1):
            print(f"{i:<6} {company['company_id']:<10} "
                  f"{company['current_accuracy']:.2%}{'':6} "
                  f"{company['total']:<10}")
        
        # 2. 一致且正确率前5名
        top_consistent = sorted([c for c in company_accuracies if c['consistent_total'] > 0], 
                               key=lambda x: x['consistent_accuracy'], reverse=True)[:5]
        
        print(f"\n【初盘即时盘一致且正确率 TOP5】")
        print(f"{'排名':<6} {'公司ID':<10} {'一致正确率':<12} {'一致次数':<10}")
        print("-" * 50)
        
        for i, company in enumerate(top_consistent, 1):
            print(f"{i:<6} {company['company_id']:<10} "
                  f"{company['consistent_accuracy']:.2%}{'':6} "
                  f"{company['consistent_total']:<10}")

    def _is_recommendation_correct(self, recommendation: str, actual_result: str, rule_diff: float = 0) -> int:
        """判断推荐是否正确"""
        if recommendation not in self.recommendation_mapping:
            return 0
        
        rule = self.recommendation_mapping[recommendation]
        predicted_result = rule.get('result', 'unknown')
        
        # 特殊处理双平偏让平 - 规则值小的一方获胜
        if recommendation == "双平偏让平":
            if rule_diff < 0:  # 主队规则值小，主队胜
                predicted_result = "home_win"
            elif rule_diff > 0:  # 客队规则值小，客队胜
                predicted_result = "away_win"
            else:  # 规则值相等，平局
                predicted_result = "draw"
        
        # 处理数组形式的结果（多个结果都算正确）
        if isinstance(predicted_result, list):
            return 1 if actual_result in predicted_result else 0
        else:
            return 1 if predicted_result == actual_result else 0

    def validate_all_leagues_concurrent(self):
        """并发验证所有联赛"""
        print("="*80)
        print("开始并发验证所有联赛")
        print("="*80)
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:  # 限制并发数
            future_to_league = {
                executor.submit(self.validate_league_concurrent, league_id): league_id
                for league_id in self.leagues.keys()
            }
            
            results = {}
            for future in concurrent.futures.as_completed(future_to_league):
                league_id = future_to_league[future]
                try:
                    result = future.result()
                    results[league_id] = result
                    
                    league_name = result['league_info']['name']
                    duration = result['duration']
                    total_results = result['total_results']
                    
                    print(f"✅ {league_name} 验证完成! 耗时: {duration:.1f}秒, 生成: {total_results} 条结果")
                    
                except Exception as e:
                    league_name = self.leagues[league_id]['name']
                    print(f"❌ {league_name} 验证失败: {e}")
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        print(f"\n🎉 所有联赛验证完成! 总耗时: {total_duration:.1f}秒")
        return results


def main():
    """主函数"""
    # 使用4个工作线程
    validator = ConcurrentLeagueValidator(max_workers=4)
    validator.validate_all_leagues_concurrent()


if __name__ == "__main__":
    main()