#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
赔率分析数据仓库
负责从数据库中为赔率分析模块提取所有需要的数据
"""
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import bisect

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import DatabaseConnection
from core.logger import get_logger


class AnalysisRepository:
    """
    数据仓库，提供赔率分析所需的所有数据查询
    """
    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.logger = get_logger(self.__class__.__name__)

    def get_match_info(self, match_id: int) -> Optional[Dict]:
        """获取比赛基本信息，包括比赛状态"""
        query = "SELECT league_id, division, home_team_id, away_team_id, round_number, match_status, match_time FROM matches WHERE match_id = %s"
        return self.db.execute_query(query, [match_id], fetch='one')

    def get_latest_odds_for_match(self, match_id: int) -> List[Dict]:
        """获取一场比赛所有公司的最新赔率数据（初盘和即时盘）"""
        # 使用LEFT JOIN确保即使公司不在companies表中也能返回数据
        query = """
            SELECT 
                oc.company_id,
                COALESCE(c.name_cn, CONCAT('公司_', oc.company_id)) AS company_name,
                oc.initial_home, 
                oc.initial_draw, 
                oc.initial_away, 
                oc.initial_return_rate,
                oc.current_home, 
                oc.current_draw, 
                oc.current_away, 
                oc.current_return_rate
            FROM odds_changes oc
            LEFT JOIN companies c ON oc.company_id = c.company_id
            WHERE oc.match_id = %s
        """
        results = self.db.execute_query(query, [match_id], fetch='all')
        self.logger.info(f"为比赛 {match_id} 获取了 {len(results)} 家公司的赔率数据")
        return results or []

    def get_latest_odds_from_european(self, match_id: int) -> List[Dict]:
        """从 european_odds 获取该比赛的最新赔率（用于验证/兜底）。"""
        # 使用LEFT JOIN确保即使公司不在companies表中也能返回数据
        query = """
            SELECT 
                eo.company_id,
                COALESCE(c.name_cn, CONCAT('公司_', eo.company_id)) AS company_name,
                eo.initial_home, 
                eo.initial_draw, 
                eo.initial_away, 
                eo.initial_return_rate,
                eo.current_home, 
                eo.current_draw, 
                eo.current_away, 
                eo.current_return_rate
            FROM european_odds eo
            LEFT JOIN companies c ON eo.company_id = c.company_id
            WHERE eo.match_id = %s
        """
        results = self.db.execute_query(query, [match_id], fetch='all')
        self.logger.info(f"(european_odds) 为比赛 {match_id} 获取了 {len(results)} 家公司的赔率数据")
        return results or []

    def get_team_powers_for_companies(self, company_ids: List[int], home_team_id: int, away_team_id: int,
                                      league_id: int = None, division: str = None) -> Dict[int, Dict]:
        """
        为指定的公司列表，批量获取主客队的广义实力。
        对分区赛制联赛，优先使用分区内排名；如果没有则退回全局排名。
        """
        if not company_ids:
            return {}

        placeholders = ','.join(['%s'] * len(company_ids))
        # 优先使用分区特定数据，fallback 到全局数据（division=''）
        target_division = division if division else ''
        query = f"""
            SELECT 
                tpr.company_id,
                tpr.team_id,
                tpr.power_level,
                tpr.division
            FROM team_power_ratings tpr
            WHERE tpr.company_id IN ({placeholders})
              AND tpr.team_id IN (%s, %s)
              AND tpr.division = %s
        """
        params = company_ids + [home_team_id, away_team_id, target_division]
        if league_id:
            query = query.rstrip() + " AND tpr.league_id = %s"
            params.append(league_id)
        results = self.db.execute_query(query, params, fetch='all')

        # 组织数据
        team_powers = {}
        for r in results:
            company_id = r['company_id']
            if company_id not in team_powers:
                team_powers[company_id] = {}
            
            if r['team_id'] == home_team_id:
                team_powers[company_id]['home_power'] = float(r['power_level'])
            elif r['team_id'] == away_team_id:
                team_powers[company_id]['away_power'] = float(r['power_level'])

        # 计算档距差并过滤不完整的数据
        final_powers = {}
        for cid, powers in team_powers.items():
            if 'home_power' in powers and 'away_power' in powers:
                final_powers[cid] = {
                    'home_power': powers['home_power'],
                    'away_power': powers['away_power'],
                    'power_diff': powers['home_power'] - powers['away_power']
                }
        
        self.logger.info(f"为 {len(final_powers)} 家公司找到了匹配的广义实力数据")
        return final_powers

    def get_standard_odds(self) -> Tuple[List[Dict], List[Dict]]:
        """获取标准欧赔参照表，并按主胜和客胜分别排序"""
        query = "SELECT win_odds, draw_odds, loss_odds, distance FROM standard_european_odds ORDER BY win_odds, loss_odds"
        results = self.db.execute_query(query, fetch='all')
        if not results:
            return [], []

        standard_odds_by_win = []
        loss_odds_map = {}
        
        for row in results:
            entry = {
                'win_odds': float(row['win_odds']),
                'draw_odds': float(row['draw_odds']),
                'loss_odds': float(row['loss_odds']),
                'distance': float(row['distance'])
            }
            standard_odds_by_win.append(entry)
            
            loss_val = entry['loss_odds']
            if loss_val not in loss_odds_map:
                loss_odds_map[loss_val] = {
                    'odds': loss_val,
                    'distance': entry['distance'],
                    'draw_odds': entry['draw_odds']
                }
        
        standard_odds_by_loss = sorted(loss_odds_map.values(), key=lambda x: x['odds'])
        self.logger.info(f"加载了 {len(standard_odds_by_win)} 条主胜标准赔率 和 {len(standard_odds_by_loss)} 条客胜标准赔率")
        return standard_odds_by_win, standard_odds_by_loss

    def get_rule_conditions(self) -> Tuple[List[Dict], List[Dict]]:
        """获取赔率规则条件"""
        query = "SELECT team_type, description, rule_value, range_low, range_high FROM odds_rule_conditions ORDER BY rule_value"
        results = self.db.execute_query(query, fetch='all')
        
        rule_conditions_home = []
        rule_conditions_away = []
        
        for row in results:
            condition = {
                'description': row['description'],
                'rule_value': float(row['rule_value']),
                'range_low': float(row['range_low']) if row['range_low'] is not None else float('-inf'),
                'range_high': float(row['range_high']) if row['range_high'] is not None else float('inf')
            }
            if row['team_type'] == '主队':
                rule_conditions_home.append(condition)
            elif row['team_type'] == '客队':
                rule_conditions_away.append(condition)

        self.logger.info(f"加载了 {len(rule_conditions_home)} 条主队规则 和 {len(rule_conditions_away)} 条客队规则")
        return rule_conditions_home, rule_conditions_away

    def get_rule_outcomes(self) -> List[Dict]:
        """获取规则差异对应的赛果"""
        query = "SELECT rule_value_diff, outcome_if_ge_minus_1_5, outcome_if_lt_minus_1_5 FROM rule_diff_outcomes ORDER BY rule_value_diff"
        results = self.db.execute_query(query, fetch='all')
        self.logger.info(f"加载了 {len(results)} 条规则赛果")
        return results or []

    def find_rule(self, team_type: str, home_odds: float, away_odds: float, power_diff: float) -> Optional[Dict]:
        """
        根据赔率和实力差查找对应的规则
        
        Args:
            team_type: 'home' 或 'away'
            home_odds: 主队赔率
            away_odds: 客队赔率  
            power_diff: 实力差（主队实力 - 客队实力）
            
        Returns:
            规则字典，包含 description 和 rule_value，如果找不到则返回 None
        """
        try:
            # 1. 计算满水赔率（假设返还率为90%，这里简化处理）
            return_rate = 0.90
            if team_type == 'home':
                fullwater_odds = float(home_odds) / return_rate
            else:
                fullwater_odds = float(away_odds) / return_rate
            
            # 2. 查找理论距离
            theory_distance = self._find_theory_distance(fullwater_odds, team_type)
            
            # 3. 计算偏移值
            offset = theory_distance - power_diff
            
            # 4. 匹配规则
            rule = self._match_rule(offset, team_type)
            
            if rule['description'] != 'unknown':
                return {
                    'rule_id': f"{team_type}_{rule['rule_value']}",
                    'description': rule['description'],
                    'rule_value': rule['rule_value']
                }
            
            return None
            
        except Exception as e:
            self.logger.error(f"查找规则失败: {e}")
            return None

    def find_outcome_by_rules(self, home_rule_id: str, away_rule_id: str) -> Optional[Dict]:
        """
        根据主客规则查找赛果
        
        Args:
            home_rule_id: 主队规则ID
            away_rule_id: 客队规则ID
            
        Returns:
            赛果规则字典
        """
        try:
            # 从规则ID中提取规则值
            home_rule_value = float(home_rule_id.split('_')[-1])
            away_rule_value = float(away_rule_id.split('_')[-1])
            
            # 计算规则差
            rule_diff = home_rule_value - away_rule_value
            
            # 查找最接近的规则结果
            rule_outcomes = self.get_rule_outcomes()
            if not rule_outcomes:
                return None
            
            closest = min(rule_outcomes, key=lambda x: abs(float(x['rule_value_diff']) - rule_diff))
            
            return {
                'rule_value_diff': rule_diff,
                'outcome_if_ge_minus_1_5': closest['outcome_if_ge_minus_1_5'],
                'outcome_if_lt_minus_1_5': closest['outcome_if_lt_minus_1_5']
            }
            
        except Exception as e:
            self.logger.error(f"查找赛果规则失败: {e}")
            return None

    def _find_theory_distance(self, target_odds: float, odds_type: str) -> float:
        """
        找到最接近的理论distance值
        
        Args:
            target_odds: 目标满水赔率
            odds_type: 'home'（主胜） 或 'away'（客胜）
            
        Returns:
            理论distance值
        """
        try:
            standard_odds_win, standard_odds_loss = self.get_standard_odds()
            
            if odds_type == 'home':
                odds_list = standard_odds_win
                key_field = 'win_odds'
            else:
                odds_list = standard_odds_loss
                key_field = 'odds'
            
            if not odds_list:
                return 0.0
            
            # 使用二分查找找到最接近的值
            import bisect
            keys = [item[key_field] for item in odds_list]
            idx = bisect.bisect_left(keys, target_odds)
            
            if idx == 0:
                return odds_list[0]['distance']
            if idx == len(odds_list):
                return odds_list[-1]['distance']
            
            before = odds_list[idx - 1]
            after = odds_list[idx]
            if abs(before[key_field] - target_odds) < abs(after[key_field] - target_odds):
                return before['distance']
            else:
                return after['distance']
                
        except Exception as e:
            self.logger.error(f"查找理论距离失败: {e}")
            return 0.0

    def _match_rule(self, offset: float, team_type: str) -> Dict:
        """
        根据偏移值匹配规则
        
        Args:
            offset: 偏移值
            team_type: 'home' 或 'away'
            
        Returns:
            匹配的规则信息
        """
        try:
            rule_conditions_home, rule_conditions_away = self.get_rule_conditions()
            conditions = rule_conditions_home if team_type == 'home' else rule_conditions_away
            
            for condition in conditions:
                if condition['range_low'] <= offset <= condition['range_high']:
                    return {
                        'description': condition['description'],
                        'rule_value': condition['rule_value']
                    }
            
            # 如果没有匹配的，返回默认值
            return {
                'description': 'unknown',
                'rule_value': 0
            }
            
        except Exception as e:
            self.logger.error(f"匹配规则失败: {e}")
            return {
                'description': 'unknown',
                'rule_value': 0
            }

    # ------------------------------------------------------------------
    # 三大公司（澳门=80 / 马会=432 / 威廉=115）初盘&即时盘区间 + 基本面信心
    # ------------------------------------------------------------------

    # 固定的三家公司 ID
    KEY_COMPANY_IDS = {
        'macau':   '80',   # 澳门
        'hkjc':    '432',  # 马会（香港马会）
        'william': '115',  # 威廉希尔
    }

    def get_three_company_odds_with_fundamental(
        self,
        match_ids: Optional[List[int]] = None
    ) -> List[Dict]:
        """
        查询同时拥有澳门(80)、马会(432)、威廉(115)三家公司赔率的比赛，
        返回每场比赛的：
          - 三家公司各自的 初盘/即时盘 主平客开盘区间
          - fundamental_analysis 中的基本面信心数值
            (home_win_score / draw_score / away_win_score / confidence_level / recommended_outcome)

        Args:
            match_ids: 可选，传入则只查询指定 match_id 列表；不传则查全部。

        Returns:
            List[Dict]，每条记录代表一场满足条件的比赛，字段说明：
              match_id
              # 澳门
              macau_init_home_range / macau_init_draw_range / macau_init_away_range
              macau_cur_home_range  / macau_cur_draw_range  / macau_cur_away_range
              # 马会
              hkjc_init_home_range  / hkjc_init_draw_range  / hkjc_init_away_range
              hkjc_cur_home_range   / hkjc_cur_draw_range   / hkjc_cur_away_range
              # 威廉
              william_init_home_range / william_init_draw_range / william_init_away_range
              william_cur_home_range  / william_cur_draw_range  / william_cur_away_range
              # 基本面
              home_win_score / draw_score / away_win_score
              confidence_level / recommended_outcome
        """
        company_ids = list(self.KEY_COMPANY_IDS.values())   # ['80','432','115']
        placeholders = ','.join(['%s'] * len(company_ids))

        # 可选的 match_id 过滤条件
        match_filter_sql = ""
        params: List = company_ids[:]
        if match_ids:
            mid_placeholders = ','.join(['%s'] * len(match_ids))
            match_filter_sql = f"AND oar.match_id IN ({mid_placeholders})"
            params += match_ids

        query = f"""
            SELECT
                oar.match_id,

                -- 澳门 (company_id = 80)
                MAX(CASE WHEN oar.company_id = '80' THEN oar.initial_home_range END) AS macau_init_home_range,
                MAX(CASE WHEN oar.company_id = '80' THEN oar.initial_draw_range  END) AS macau_init_draw_range,
                MAX(CASE WHEN oar.company_id = '80' THEN oar.initial_away_range  END) AS macau_init_away_range,
                MAX(CASE WHEN oar.company_id = '80' THEN oar.current_home_range  END) AS macau_cur_home_range,
                MAX(CASE WHEN oar.company_id = '80' THEN oar.current_draw_range  END) AS macau_cur_draw_range,
                MAX(CASE WHEN oar.company_id = '80' THEN oar.current_away_range  END) AS macau_cur_away_range,

                -- 马会 (company_id = 432)
                MAX(CASE WHEN oar.company_id = '432' THEN oar.initial_home_range END) AS hkjc_init_home_range,
                MAX(CASE WHEN oar.company_id = '432' THEN oar.initial_draw_range  END) AS hkjc_init_draw_range,
                MAX(CASE WHEN oar.company_id = '432' THEN oar.initial_away_range  END) AS hkjc_init_away_range,
                MAX(CASE WHEN oar.company_id = '432' THEN oar.current_home_range  END) AS hkjc_cur_home_range,
                MAX(CASE WHEN oar.company_id = '432' THEN oar.current_draw_range  END) AS hkjc_cur_draw_range,
                MAX(CASE WHEN oar.company_id = '432' THEN oar.current_away_range  END) AS hkjc_cur_away_range,

                -- 威廉 (company_id = 115)
                MAX(CASE WHEN oar.company_id = '115' THEN oar.initial_home_range END) AS william_init_home_range,
                MAX(CASE WHEN oar.company_id = '115' THEN oar.initial_draw_range  END) AS william_init_draw_range,
                MAX(CASE WHEN oar.company_id = '115' THEN oar.initial_away_range  END) AS william_init_away_range,
                MAX(CASE WHEN oar.company_id = '115' THEN oar.current_home_range  END) AS william_cur_home_range,
                MAX(CASE WHEN oar.company_id = '115' THEN oar.current_draw_range  END) AS william_cur_draw_range,
                MAX(CASE WHEN oar.company_id = '115' THEN oar.current_away_range  END) AS william_cur_away_range,

                -- 基本面信心数值
                fa.home_win_score,
                fa.draw_score,
                fa.away_win_score,
                fa.confidence_level,
                fa.recommended_outcome

            FROM odds_analysis_results oar
            INNER JOIN fundamental_analysis fa ON oar.match_id = fa.match_id
            WHERE oar.company_id IN ({placeholders})
              AND fa.is_active = 1
              {match_filter_sql}
            GROUP BY
                oar.match_id,
                fa.home_win_score,
                fa.draw_score,
                fa.away_win_score,
                fa.confidence_level,
                fa.recommended_outcome
            HAVING COUNT(DISTINCT oar.company_id) = 3
            ORDER BY oar.match_id DESC
        """

        results = self.db.execute_query(query, params, fetch='all')
        self.logger.info(
            f"三大公司赔率区间+基本面查询完成，共 {len(results)} 场比赛"
            + (f"（限定 {len(match_ids)} 场）" if match_ids else "")
        )
        return results or []

    def close(self):
        """关闭数据库连接"""
        pass
 