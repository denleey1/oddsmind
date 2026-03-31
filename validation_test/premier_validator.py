#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
英超历史数据验证器
使用已完成的英超比赛数据验证模型准确率
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import pandas as pd

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class PremierLeagueValidator:
    """英超历史数据验证器"""
    
    def __init__(self):
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.league_id = 36  # 英超联赛ID
        
        # 缓存标准欧赔表和规则表
        self._load_analysis_tables()
        
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
    
    def get_validation_matches(self, start_round: int = 10, end_round: int = 38) -> List[Dict]:
        """获取验证用的比赛列表"""
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
        
        matches = self.db.execute_query(query, [self.league_id, start_round, end_round], fetch='all')
        self.logger.info(f"找到 {len(matches)} 场待验证比赛 (第{start_round}-{end_round}轮)")
        
        return matches
    
    def get_power_ratings(self, target_round: int) -> Dict[Tuple[int, int], float]:
        """获取指定轮次的球队实力差值"""
        query = """
            SELECT 
                tpr1.team_id as home_team_id,
                tpr2.team_id as away_team_id,
                tpr1.company_id,
                tpr1.power_level as home_power,
                tpr2.power_level as away_power,
                (tpr1.power_level - tpr2.power_level) as power_diff
            FROM team_power_ratings_history tpr1
            JOIN team_power_ratings_history tpr2 ON 
                tpr1.company_id = tpr2.company_id 
                AND tpr1.league_id = tpr2.league_id
                AND tpr1.target_round = tpr2.target_round
            WHERE tpr1.league_id = %s 
              AND tpr1.target_round = %s
        """
        
        power_data = self.db.execute_query(query, [self.league_id, target_round], fetch='all')
        
        # 转换为方便查询的格式 {(home_team_id, away_team_id, company_id): power_diff}
        power_dict = {}
        for row in power_data:
            key = (int(row['home_team_id']), int(row['away_team_id']), int(row['company_id']))
            power_dict[key] = float(row['power_diff'])
        
        self.logger.info(f"加载第{target_round}轮实力数据: {len(power_data)} 条记录")
        return power_dict
    
    def get_match_odds(self, match_id: int) -> List[Dict]:
        """获取比赛的赔率数据"""
        query = """
            SELECT 
                company_id,
                initial_home, initial_draw, initial_away, initial_return_rate,
                current_home, current_draw, current_away, current_return_rate
            FROM european_odds
            WHERE match_id = %s AND odds_type = '1x2'
        """
        
        odds_data = self.db.execute_query(query, [match_id], fetch='all')
        return odds_data or []
    
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
        
        # 简单的最近匹配
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
        
        # 查找最接近的规则差
        closest_rule = min(self.rule_outcomes, 
                          key=lambda x: abs(float(x['rule_value_diff']) - rule_diff))
        
        if use_ge_minus_1_5:
            return closest_rule['outcome_if_ge_minus_1_5']
        else:
            return closest_rule['outcome_if_lt_minus_1_5']
    
    def analyze_single_match(self, match: Dict, power_ratings: Dict) -> List[Dict]:
        """分析单场比赛的所有公司推荐"""
        match_id = match['match_id']
        home_team_id = match['home_team_id']
        away_team_id = match['away_team_id']
        
        # 获取赔率数据
        odds_data = self.get_match_odds(match_id)
        
        results = []
        
        for odds in odds_data:
            company_id = int(odds['company_id'])
            
            # 检查是否有实力数据
            power_key = (home_team_id, away_team_id, company_id)
            if power_key not in power_ratings:
                continue
            
            power_diff = power_ratings[power_key]
            
            try:
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
                    'initial_recommendation': initial_recommendation,
                    'current_recommendation': current_recommendation,
                    'initial_rule_diff': initial_rule_diff,
                    'current_rule_diff': current_rule_diff,
                    'analysis_time': datetime.now()
                }
                
                results.append(result)
                
            except Exception as e:
                self.logger.warning(f"分析比赛{match_id}公司{company_id}失败: {e}")
                continue
        
        return results
    
    def validate_premier(self, start_round: int = 10, end_round: int = 38) -> List[Dict]:
        """验证英超比赛数据"""
        self.logger.info(f"开始验证英超第{start_round}-{end_round}轮比赛")
        
        # 获取比赛列表
        matches = self.get_validation_matches(start_round, end_round)
        
        all_results = []
        
        # 按轮次分组处理
        rounds = {}
        for match in matches:
            round_num = match['round_number']
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append(match)
        
        for round_num in sorted(rounds.keys()):
            round_matches = rounds[round_num]
            
            # 获取上一轮的实力数据
            power_round = round_num - 1
            power_ratings = self.get_power_ratings(power_round)
            
            if not power_ratings:
                self.logger.warning(f"第{power_round}轮没有实力数据，跳过第{round_num}轮")
                continue
            
            self.logger.info(f"分析第{round_num}轮 ({len(round_matches)}场比赛)，使用第{power_round}轮实力数据")
            
            round_results = []
            for match in round_matches:
                match_results = self.analyze_single_match(match, power_ratings)
                round_results.extend(match_results)
            
            self.logger.info(f"第{round_num}轮完成，生成 {len(round_results)} 条推荐结果")
            all_results.extend(round_results)
        
        self.logger.info(f"验证完成，总计生成 {len(all_results)} 条推荐结果")
        return all_results
    
    def save_validation_results(self, results: List[Dict], table_name: str = 'premier_validation_results'):
        """保存验证结果到数据库"""
        if not results:
            self.logger.warning("没有结果需要保存")
            return
        
        # 创建结果表
        create_table_sql = f"""
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
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='英超验证结果表'
        """
        
        self.db.execute_query(create_table_sql)
        
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
        self.logger.info(f"成功保存 {len(results)} 条验证结果到表 {table_name}")


def main():
    """主函数"""
    validator = PremierLeagueValidator()
    
    # 验证第10-38轮比赛
    results = validator.validate_premier(start_round=10, end_round=38)
    
    # 保存结果
    validator.save_validation_results(results)
    
    print(f"\n验证完成！")
    print(f"总计分析: {len(results)} 条推荐结果")
    
    # 简单统计
    if results:
        rounds = set(r['round_number'] for r in results)
        companies = set(r['company_id'] for r in results)
        matches = set(r['match_id'] for r in results)
        
        print(f"涉及轮次: 第{min(rounds)}-{max(rounds)}轮")
        print(f"涉及比赛: {len(matches)} 场")
        print(f"涉及公司: {len(companies)} 家")
        
        # 推荐结果分布
        initial_recs = {}
        current_recs = {}
        for r in results:
            initial_recs[r['initial_recommendation']] = initial_recs.get(r['initial_recommendation'], 0) + 1
            current_recs[r['current_recommendation']] = current_recs.get(r['current_recommendation'], 0) + 1
        
        print(f"\n初盘推荐分布:")
        for rec, count in sorted(initial_recs.items()):
            print(f"  {rec}: {count} 次")
        
        print(f"\n即时推荐分布:")
        for rec, count in sorted(current_recs.items()):
            print(f"  {rec}: {count} 次")


if __name__ == "__main__":
    main()