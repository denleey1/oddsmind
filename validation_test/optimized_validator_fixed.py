#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复版的优化多联赛验证器
解决连接池耗尽和轮次处理失败问题
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import json
import concurrent.futures
from threading import Lock
import time
import traceback

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger


class OptimizedValidatorFixed:
    """修复版的多联赛综合验证器"""
    
    def __init__(self, max_workers: int = 2, min_odds: float = 1.4):
        """
        初始化验证器
        
        Args:
            max_workers: 最大并发数（降低以避免连接池耗尽）
            min_odds: 最小赔率阈值
        """
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.max_workers = max_workers  # 降低并发数
        self.min_odds = min_odds
        self.lock = Lock()
        
        # 验证结果存储
        self.validation_results = {}
        self.company_info = {}
        
        # 自动发现联赛数据
        self.leagues = self._discover_leagues()
        
        # 缓存分析表和映射规则
        self._load_analysis_tables()
        self._load_recommendation_mapping()
        self._load_company_info()
        
        print(f"初始化完成，赔率过滤条件：初始主胜或客胜赔率 >= {min_odds}")
    
    def _discover_leagues(self) -> Dict:
        """自动发现数据库中的联赛数据"""
        print("正在自动发现联赛数据...")
        
        query = """
        SELECT 
            l.league_id,
            l.name_cn,
            l.name_en,
            l.country,
            COUNT(DISTINCT m.match_id) as total_matches,
            SUM(CASE WHEN m.match_status = 'finished' THEN 1 ELSE 0 END) as finished_matches,
            MIN(m.round_number) as min_round,
            MAX(m.round_number) as max_round
        FROM leagues l
        JOIN matches m ON l.league_id = m.league_id
        WHERE m.round_number IS NOT NULL AND m.round_number > 0
        GROUP BY l.league_id, l.name_cn, l.name_en, l.country
        HAVING finished_matches > 50
        ORDER BY finished_matches DESC
        """
        
        try:
            league_data = self.db.execute_query(query, fetch='all')
            
            leagues = {}
            for league in league_data:
                league_id = league['league_id']
                
                # 生成联赛代码
                name_cn = league['name_cn'] or ''
                if 'K联赛' in name_cn or '南韩' in name_cn:
                    code = 'kleague'
                elif 'J1' in name_cn or '日职' in name_cn:
                    code = 'jleague'
                elif '德甲' in name_cn:
                    code = 'bundesliga'
                elif '英超' in name_cn:
                    code = 'premier'
                elif '西甲' in name_cn:
                    code = 'laliga'
                elif '意甲' in name_cn:
                    code = 'seriea'
                elif '法甲' in name_cn:
                    code = 'ligue1'
                else:
                    code = f'league_{league_id}'
                
                # 确定验证轮次范围
                min_round = league['min_round'] if league['min_round'] else 1
                max_round = league['max_round'] if league['max_round'] else 38
                start_round = max(10, min_round)
                end_round = min(max_round, 38)  # 限制最大轮次
                
                leagues[league_id] = {
                    'name': name_cn,
                    'name_en': league['name_en'] or name_cn,
                    'code': code,
                    'country': league['country'],
                    'total_matches': league['total_matches'],
                    'finished_matches': league['finished_matches'],
                    'start': start_round,
                    'end': end_round
                }
            
            print(f"发现 {len(leagues)} 个有效联赛")
            return leagues
            
        except Exception as e:
            self.logger.error(f"发现联赛数据失败: {e}")
            return {}
    
    def _load_analysis_tables(self):
        """加载分析所需的参考表"""
        print("加载分析参考表...")
        
        try:
            # 加载标准欧赔表
            query = """
                SELECT win_odds, loss_odds, distance, draw_odds
                FROM standard_european_odds
                ORDER BY win_odds, loss_odds
            """
            self.standard_odds = self.db.execute_query(query, fetch='all')
            
            if self.standard_odds:
                # 按主胜和客胜分别排序
                self.standard_odds_by_win = sorted(
                    [{'win_odds': float(row['win_odds']), 'distance': float(row['distance'])} 
                     for row in self.standard_odds if row['win_odds'] and float(row['win_odds']) <= 2.81],
                    key=lambda x: x['win_odds']
                )
                
                self.standard_odds_by_loss = sorted(
                    [{'odds': float(row['loss_odds']), 'distance': float(row['distance'])} 
                     for row in self.standard_odds if row['loss_odds'] and float(row['loss_odds']) >= 2.02],
                    key=lambda x: x['odds']
                )
            else:
                self.standard_odds_by_win = []
                self.standard_odds_by_loss = []
            
            # 加载规则条件表
            query = """
                SELECT team_type, description, rule_value, range_low, range_high
                FROM odds_rule_conditions
                ORDER BY team_type, rule_value
            """
            rule_conditions = self.db.execute_query(query, fetch='all')
            
            if rule_conditions:
                self.rule_conditions_home = [r for r in rule_conditions if r['team_type'] == '主队']
                self.rule_conditions_away = [r for r in rule_conditions if r['team_type'] == '客队']
            else:
                self.rule_conditions_home = []
                self.rule_conditions_away = []
            
            # 加载规则结果表
            query = """
                SELECT rule_value_diff, outcome_if_ge_minus_1_5, outcome_if_lt_minus_1_5
                FROM rule_diff_outcomes
            """
            self.rule_outcomes = self.db.execute_query(query, fetch='all')
            if not self.rule_outcomes:
                self.rule_outcomes = []
            
            print(f"已加载分析参考表")
            
        except Exception as e:
            self.logger.error(f"加载分析表失败: {e}")
            self.standard_odds_by_win = []
            self.standard_odds_by_loss = []
            self.rule_conditions_home = []
            self.rule_conditions_away = []
            self.rule_outcomes = []

    def _load_recommendation_mapping(self):
        """加载推荐映射规则"""
        try:
            mapping_file = Path(__file__).parent / 'recommendation_mapping.json'
            if mapping_file.exists():
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
                    self.recommendation_mapping = mapping_data['recommendations']
            else:
                self.logger.warning(f"推荐映射文件不存在: {mapping_file}")
                self.recommendation_mapping = {}
        except Exception as e:
            self.logger.warning(f"加载推荐映射失败: {e}")
            self.recommendation_mapping = {}

    def _load_company_info(self):
        """加载公司信息"""
        try:
            company_query = "SELECT company_id, name, country FROM companies"
            companies = self.db.execute_query(company_query, fetch='all')
            
            if companies:
                for company in companies:
                    company_id = company['company_id']
                    self.company_info[company_id] = {
                        'name': company['name'],
                        'country': company.get('country', '未知')
                    }
                print(f"加载了 {len(self.company_info)} 家公司信息")
            else:
                print("未找到公司信息")
                
        except Exception as e:
            print(f"加载公司信息失败: {e}")
            self.company_info = {}

    def get_company_display_name(self, company_id: int) -> str:
        """获取公司显示名称"""
        if company_id in self.company_info:
            info = self.company_info[company_id]
            name = info['name']
            country = info['country']
            return f"{name}({country})"
        else:
            return f"公司{company_id}"

    def validate_single_league(self, league_id: int) -> Dict:
        """验证单个联赛"""
        if league_id not in self.leagues:
            return {'error': f'联赛ID {league_id} 不存在'}
            
        league_info = self.leagues[league_id]
        league_name = league_info['name']
        start_round = league_info['start']
        end_round = league_info['end']
        
        start_time = time.time()
        self.logger.info(f"开始验证{league_name}（赔率过滤：>={self.min_odds}）")
        
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
              AND home_score IS NOT NULL
              AND away_score IS NOT NULL
            ORDER BY round_number, match_time
        """
        
        try:
            matches = self.db.execute_query(query, [league_id, start_round, end_round], fetch='all')
            
            if not matches:
                return {'error': f'{league_name}没有找到符合条件的比赛'}
            
            # 统计
            filtered_matches = 0
            processed_matches = 0
            
            # 按轮次分组
            rounds_matches = {}
            for match in matches:
                round_num = match['round_number']
                if round_num not in rounds_matches:
                    rounds_matches[round_num] = []
                rounds_matches[round_num].append(match)
            
            all_results = []
            
            # 串行处理各轮次（避免连接池耗尽）
            for round_num in sorted(rounds_matches.keys()):
                try:
                    round_result = self._process_round_with_filter(
                        league_id, 
                        round_num, 
                        rounds_matches[round_num]
                    )
                    
                    if round_result:
                        all_results.extend(round_result.get('results', []))
                        filtered_matches += round_result.get('filtered', 0)
                        processed_matches += round_result.get('processed', 0)
                        
                        if round_result.get('results'):
                            print(f"{league_name}第{round_num}轮完成，"
                                  f"处理{round_result['processed']}场，"
                                  f"过滤{round_result['filtered']}场，"
                                  f"生成{len(round_result['results'])}条结果")
                except Exception as e:
                    self.logger.error(f"{league_name}第{round_num}轮处理失败: {e}")
                    continue
            
            # 保存结果
            if all_results:
                self._save_results(league_id, all_results)
            
            # 计算准确率
            accuracy_stats = self._calculate_accuracy_rankings(league_id)
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"\n{league_name}验证完成:")
            print(f"  总比赛数: {len(matches)}")
            print(f"  被过滤数: {filtered_matches} (赔率<{self.min_odds})")
            print(f"  实际处理: {processed_matches}")
            if len(matches) > 0:
                print(f"  过滤比例: {filtered_matches/len(matches)*100:.1f}%")
            
            return {
                'league_info': league_info,
                'total_matches': len(matches),
                'filtered_matches': filtered_matches,
                'processed_matches': processed_matches,
                'total_results': len(all_results),
                'duration': duration,
                'accuracy_stats': accuracy_stats
            }
            
        except Exception as e:
            self.logger.error(f"验证联赛{league_name}失败: {e}")
            return {'error': str(e)}

    def _process_round_with_filter(self, league_id: int, round_num: int, round_matches: List[Dict]) -> Dict:
        """处理单个轮次的比赛（带赔率过滤）"""
        try:
            # 获取上一轮的实力数据
            power_round = round_num - 1
            power_ratings = self._get_power_ratings(league_id, power_round)
            
            # 如果没有实力数据，尝试使用当前轮次
            if not power_ratings and round_num > 0:
                power_ratings = self._get_power_ratings(league_id, round_num)
            
            if not power_ratings:
                self.logger.warning(f"联赛{league_id}第{round_num}轮缺少实力数据")
                return {'results': [], 'filtered': 0, 'processed': 0}
            
            round_results = []
            filtered_count = 0
            processed_count = 0
            
            for match in round_matches:
                try:
                    # 检查是否需要过滤
                    if self._should_filter_match(match['match_id']):
                        filtered_count += 1
                        continue
                    
                    processed_count += 1
                    match_results = self._analyze_single_match(match, power_ratings)
                    if match_results:
                        round_results.extend(match_results)
                except Exception as e:
                    self.logger.debug(f"处理比赛{match['match_id']}失败: {e}")
                    continue
            
            return {
                'results': round_results,
                'filtered': filtered_count,
                'processed': processed_count
            }
            
        except Exception as e:
            self.logger.error(f"处理轮次{round_num}失败: {e}")
            return {'results': [], 'filtered': 0, 'processed': 0}

    def _should_filter_match(self, match_id: int) -> bool:
        """检查比赛是否应该被过滤"""
        try:
            # 查询该比赛的最小赔率
            query = """
                SELECT 
                    MIN(initial_home) as min_home,
                    MIN(initial_away) as min_away
                FROM european_odds
                WHERE match_id = %s 
                  AND odds_type = '1x2'
                  AND initial_home IS NOT NULL
                  AND initial_away IS NOT NULL
            """
            
            result = self.db.execute_query(query, [match_id], fetch='one')
            
            if result and result['min_home'] and result['min_away']:
                min_home = float(result['min_home'])
                min_away = float(result['min_away'])
                
                # 如果任何公司的主胜或客胜赔率小于阈值，则过滤
                if min_home < self.min_odds or min_away < self.min_odds:
                    return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"检查比赛{match_id}赔率时出错: {e}")
            return False

    def _get_power_ratings(self, league_id: int, target_round: int) -> Dict:
        """获取指定轮次的球队实力差值"""
        try:
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
                  AND tpr1.power_level IS NOT NULL
                  AND tpr2.power_level IS NOT NULL
            """
            
            power_data = self.db.execute_query(query, [league_id, target_round], fetch='all')
            
            power_dict = {}
            if power_data:
                for row in power_data:
                    if row['home_team_id'] and row['away_team_id'] and row['power_diff'] is not None:
                        key = (int(row['home_team_id']), int(row['away_team_id']), int(row['company_id']))
                        power_dict[key] = float(row['power_diff'])
            
            return power_dict
            
        except Exception as e:
            self.logger.error(f"获取实力数据失败: {e}")
            return {}

    def _analyze_single_match(self, match: Dict, power_ratings: Dict) -> List[Dict]:
        """分析单场比赛的所有公司推荐"""
        try:
            match_id = match['match_id']
            home_team_id = match['home_team_id']
            away_team_id = match['away_team_id']
            
            # 获取赔率数据
            odds_query = """
                SELECT 
                    company_id,
                    initial_home, initial_draw, initial_away, initial_return_rate,
                    current_home, current_draw, current_away, current_return_rate
                FROM european_odds
                WHERE match_id = %s 
                  AND odds_type = '1x2'
                  AND initial_home >= %s 
                  AND initial_away >= %s
                  AND initial_home IS NOT NULL
                  AND initial_away IS NOT NULL
                  AND initial_return_rate IS NOT NULL
                  AND current_return_rate IS NOT NULL
            """
            
            odds_data = self.db.execute_query(odds_query, [match_id, self.min_odds, self.min_odds], fetch='all')
            results = []
            
            if not odds_data:
                return results
            
            for odds in odds_data:
                try:
                    company_id = int(odds['company_id'])
                    
                    # 检查是否有实力数据
                    power_key = (home_team_id, away_team_id, company_id)
                    if power_key not in power_ratings:
                        continue
                    
                    power_diff = power_ratings[power_key]
                    
                    # 分析赔率并生成推荐
                    analysis_result = self._analyze_odds(odds, power_diff)
                    
                    if analysis_result:
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
                            'initial_recommendation': analysis_result.get('initial_recommendation', ''),
                            'current_recommendation': analysis_result.get('current_recommendation', ''),
                            'initial_rule_diff': analysis_result.get('initial_rule_diff', 0),
                            'current_rule_diff': analysis_result.get('current_rule_diff', 0),
                            'initial_home_odds': float(odds['initial_home']),
                            'initial_away_odds': float(odds['initial_away']),
                            'analysis_time': datetime.now()
                        }
                        
                        results.append(result)
                        
                except Exception as e:
                    self.logger.debug(f"分析公司{odds.get('company_id')}失败: {e}")
                    continue
            
            return results
            
        except Exception as e:
            self.logger.error(f"分析比赛{match.get('match_id')}失败: {e}")
            return []

    def _analyze_odds(self, odds: Dict, power_diff: float) -> Dict:
        """分析赔率并生成推荐"""
        try:
            # 计算满水赔率
            initial_return = float(odds['initial_return_rate']) / 100 if odds['initial_return_rate'] else 1
            current_return = float(odds['current_return_rate']) / 100 if odds['current_return_rate'] else 1
            
            if initial_return <= 0 or current_return <= 0:
                return {}
            
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
            
            # 计算规则差
            initial_rule_diff = initial_home_rule['rule_value'] - initial_away_rule['rule_value']
            current_rule_diff = current_home_rule['rule_value'] - current_away_rule['rule_value']
            
            # 获取推荐
            initial_recommendation = self._get_recommendation(initial_rule_diff, power_diff)
            current_recommendation = self._get_recommendation(current_rule_diff, power_diff)
            
            return {
                'initial_recommendation': initial_recommendation,
                'current_recommendation': current_recommendation,
                'initial_rule_diff': initial_rule_diff,
                'current_rule_diff': current_rule_diff
            }
            
        except Exception as e:
            self.logger.debug(f"分析赔率失败: {e}")
            return {}

    def _find_theory_distance(self, target_odds: float, odds_type: str) -> float:
        """查找理论distance值"""
        try:
            if odds_type == 'home':
                odds_list = self.standard_odds_by_win
                key_field = 'win_odds'
            else:
                odds_list = self.standard_odds_by_loss
                key_field = 'odds'
            
            if not odds_list:
                return 0.0
            
            closest_item = min(odds_list, key=lambda x: abs(x.get(key_field, 0) - target_odds))
            return closest_item.get('distance', 0.0)
        except:
            return 0.0
    
    def _match_rule(self, offset: float, team_type: str) -> Dict:
        """根据偏移值匹配规则"""
        try:
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
        except:
            return {'description': 'unknown', 'rule_value': 0}
    
    def _get_recommendation(self, rule_diff: float, power_diff: float) -> str:
        """根据规则差获取推荐"""
        try:
            if not self.rule_outcomes:
                return '未知'
                
            use_ge_minus_1_5 = (power_diff >= -1.5)
            
            closest_rule = min(self.rule_outcomes, 
                              key=lambda x: abs(float(x.get('rule_value_diff', 0)) - rule_diff))
            
            if use_ge_minus_1_5:
                return closest_rule.get('outcome_if_ge_minus_1_5', '未知')
            else:
                return closest_rule.get('outcome_if_lt_minus_1_5', '未知')
        except:
            return '未知'

    def _save_results(self, league_id: int, results: List[Dict]):
        """保存验证结果"""
        if not results:
            return
        
        try:
            league_info = self.leagues[league_id]
            table_name = f"{league_info['code']}_validation_filtered"
            
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
                `initial_home_odds` decimal(5,2),
                `initial_away_odds` decimal(5,2),
                `analysis_time` datetime,
                INDEX `idx_match_company` (`match_id`, `company_id`),
                INDEX `idx_round` (`round_number`),
                INDEX `idx_recommendation` (`initial_recommendation`, `current_recommendation`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='{league_info['name']}验证结果(过滤赔率<{self.min_odds})'
            """
            
            self.db.execute_query(create_sql)
            self.db.execute_query(f"TRUNCATE TABLE `{table_name}`")
            
            # 批量插入数据
            insert_sql = f"""
            INSERT INTO `{table_name}` (
                match_id, company_id, round_number, home_team_id, away_team_id,
                home_team_name, away_team_name, actual_home_score, actual_away_score,
                power_diff, initial_recommendation, current_recommendation,
                initial_rule_diff, current_rule_diff, initial_home_odds, initial_away_odds,
                analysis_time
            ) VALUES (
                %(match_id)s, %(company_id)s, %(round_number)s, %(home_team_id)s, %(away_team_id)s,
                %(home_team_name)s, %(away_team_name)s, %(actual_home_score)s, %(actual_away_score)s,
                %(power_diff)s, %(initial_recommendation)s, %(current_recommendation)s,
                %(initial_rule_diff)s, %(current_rule_diff)s, %(initial_home_odds)s, %(initial_away_odds)s,
                %(analysis_time)s
            )
            """
            
            self.db.execute_many(insert_sql, results)
            print(f"已保存 {len(results)} 条验证结果到表 {table_name}")
            
        except Exception as e:
            self.logger.error(f"保存结果失败: {e}")

    def _calculate_accuracy_rankings(self, league_id: int) -> Dict:
        """计算准确率并输出排名"""
        try:
            league_info = self.leagues[league_id]
            table_name = f"{league_info['code']}_validation_filtered"
            
            # 检查表是否存在
            check_table = f"SHOW TABLES LIKE '{table_name}'"
            table_exists = self.db.execute_query(check_table, fetch='all')
            
            if not table_exists:
                return {}
            
            # 获取验证结果
            query = f"""
            SELECT 
                company_id, actual_home_score, actual_away_score,
                current_recommendation, current_rule_diff,
                initial_recommendation, initial_rule_diff
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
                        'consistent': 0,
                        'consistent_correct': 0
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
                    stats['consistent'] += 1
                    if current_correct:
                        stats['consistent_correct'] += 1
            
            # 计算准确率并排序
            company_accuracies = []
            for company_id, stats in company_stats.items():
                if stats['total'] > 0:
                    company_accuracies.append({
                        'company_id': company_id,
                        'company_name': self.get_company_display_name(company_id),
                        'total': stats['total'],
                        'initial_accuracy': stats['initial_correct'] / stats['total'],
                        'current_accuracy': stats['current_correct'] / stats['total'],
                        'consistency_rate': stats['consistent'] / stats['total'],
                        'consistent_accuracy': (stats['consistent_correct'] / stats['consistent'] 
                                              if stats['consistent'] > 0 else 0),
                        'initial_correct': stats['initial_correct'],
                        'current_correct': stats['current_correct'],
                        'consistent_total': stats['consistent'],
                        'consistent_correct': stats['consistent_correct']
                    })
            
            # 按即时盘准确率排序
            company_accuracies.sort(key=lambda x: x['current_accuracy'], reverse=True)
            
            # 输出前10名排名
            self._print_league_rankings(league_info['name'], company_accuracies)
            
            return {
                'league_name': league_info['name'],
                'league_code': league_info['code'],
                'total_predictions': len(results),
                'total_companies': len(company_accuracies),
                'companies': company_accuracies
            }
            
        except Exception as e:
            self.logger.error(f"计算准确率失败: {e}")
            return {}

    def _print_league_rankings(self, league_name: str, company_accuracies: List[Dict]):
        """输出单个联赛的排名"""
        print(f"\n【{league_name} 准确率排名 TOP10】（过滤赔率<{self.min_odds}）")
        print(f"{'排名':<6} {'公司名称(国家)':<30} {'即时准确率':<12} {'初盘准确率':<12} "
              f"{'一致性':<10} {'预测总数':<10}")
        print("-" * 90)
        
        top_10 = company_accuracies[:10]
        for i, company in enumerate(top_10, 1):
            consistency_str = f"{company['consistency_rate']:.1%}"
            
            print(f"{i:<6} {company['company_name']:<30} "
                  f"{company['current_accuracy']:.2%}{'':6} "
                  f"{company['initial_accuracy']:.2%}{'':6} "
                  f"{consistency_str:<10} "
                  f"{company['total']:<10}")

    def _is_recommendation_correct(self, recommendation: str, actual_result: str, rule_diff: float = 0) -> int:
        """判断推荐是否正确"""
        if not recommendation or recommendation not in self.recommendation_mapping:
            return 0
        
        try:
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
                return 1 if actual_result in predicted_result else 0
            else:
                return 1 if predicted_result == actual_result else 0
        except:
            return 0

    def validate_all_leagues(self):
        """验证所有联赛并生成综合报告"""
        print("="*100)
        print(f"多联赛全轮次全公司综合验证开始（赔率过滤：>={self.min_odds}）")
        print("="*100)
        
        if not self.leagues:
            print("❌ 没有发现有效的联赛数据")
            return
        
        start_time = time.time()
        all_results = {}
        
        # 串行处理避免连接池问题
        for league_id in self.leagues.keys():
            try:
                print(f"\n开始验证联赛ID: {league_id}")
                result = self.validate_single_league(league_id)
                
                if 'error' not in result:
                    all_results[league_id] = result
                    
                    league_name = result['league_info']['name']
                    duration = result['duration']
                    total_results = result['total_results']
                    filtered = result.get('filtered_matches', 0)
                    
                    print(f"✅ {league_name} 验证完成! "
                          f"耗时: {duration:.1f}秒, "
                          f"过滤: {filtered}场, "
                          f"生成: {total_results}条结果")
                else:
                    print(f"❌ {self.leagues[league_id]['name']}: {result['error']}")
                    
            except Exception as e:
                league_name = self.leagues[league_id]['name']
                print(f"❌ {league_name} 验证失败: {e}")
                self.logger.error(f"验证联赛{league_id}异常: {traceback.format_exc()}")
        
        # 生成综合报告
        self._generate_comprehensive_report(all_results)
        
        end_time = time.time()
        total_duration = end_time - start_time
        
        print(f"\n🎉 所有联赛验证完成! 总耗时: {total_duration:.1f}秒")
        
        return all_results

    def _generate_comprehensive_report(self, all_results: Dict):
        """生成综合报告"""
        print(f"\n{'='*120}")
        print(f"多联赛验证综合报告（赔率过滤：>={self.min_odds}）")
        print(f"{'='*120}")
        
        if not all_results:
            print("没有成功验证的联赛数据")
            return
        
        # 统计总体过滤情况
        total_original = sum(r.get('total_matches', 0) for r in all_results.values())
        total_filtered = sum(r.get('filtered_matches', 0) for r in all_results.values())
        total_processed = sum(r.get('processed_matches', 0) for r in all_results.values())
        
        print(f"\n数据过滤统计:")
        print(f"  原始比赛总数: {total_original}")
        print(f"  被过滤比赛数: {total_filtered}")
        print(f"  实际处理比赛: {total_processed}")
        if total_original > 0:
            print(f"  总体过滤比例: {total_filtered/total_original*100:.1f}%")
        
        # 各联赛概览
        print(f"\n{'联赛':<15} {'原始比赛':<10} {'过滤数':<10} {'过滤率':<10} {'最高准确率':<12} {'最佳公司':<30}")
        print("-" * 100)
        
        for league_id, result in all_results.items():
            stats = result.get('accuracy_stats', {})
            if stats and stats.get('companies'):
                best = stats['companies'][0]
                total_matches = result.get('total_matches', 1)
                filter_rate = result.get('filtered_matches', 0) / total_matches * 100 if total_matches > 0 else 0
                
                print(f"{stats['league_name']:<15} "
                      f"{result.get('total_matches', 0):<10} "
                      f"{result.get('filtered_matches', 0):<10} "
                      f"{filter_rate:.1f}%{'':6} "
                      f"{best['current_accuracy']:.2%}{'':6} "
                      f"{best['company_name']:<30}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="修复版优化验证器")
    parser.add_argument('--min-odds', type=float, default=1.4,
                       help='最小赔率阈值（默认1.4）')
    parser.add_argument('--league-id', type=int,
                       help='指定联赛ID')
    parser.add_argument('--max-workers', type=int, default=2,
                       help='最大并发数（默认2）')
    
    args = parser.parse_args()
    
    validator = OptimizedValidatorFixed(
        max_workers=args.max_workers,
        min_odds=args.min_odds
    )
    
    if args.league_id:
        # 验证单个联赛
        result = validator.validate_single_league(args.league_id)
        if 'error' not in result:
            print(f"\n✅ 验证完成!")
    else:
        # 验证所有联赛
        validator.validate_all_leagues()


if __name__ == "__main__":
    main()