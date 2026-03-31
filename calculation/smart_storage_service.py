#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
智能存储服务 - 优化重复计算问题
支持增量存储，避免重复计算已存在的数据
"""
import sys
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from database.models import TeamPowerRatingHistoryModel
from core.logger import get_logger

logger = get_logger(__name__)


class SmartStorageService:
    """
    智能存储服务
    特点:
    1. 存储前检查是否已存在，避免重复计算
    2. 支持增量更新
    3. 智能去重和数据完整性检查
    """

    def __init__(self, db_connection=None):
        """初始化智能存储服务"""
        self.db = db_connection or get_connection()
        self._existing_cache = {}  # 缓存已存在的记录，提高查询效率

    def save_round_history_smart(
        self,
        team_powers: Dict,
        league_info: Dict,
        company_id: int,
        company_name: str,
        season: Optional[str],
        round_number: int,
        matches_df: Optional[pd.DataFrame] = None,
        start_round: int = 1,
        force_update: bool = False
    ) -> Dict:
        """
        智能保存轮次历史数据 - 避免重复计算
        
        Args:
            team_powers: 球队实力字典
            league_info: 联赛信息
            company_id: 公司ID
            company_name: 公司名称
            season: 赛季
            round_number: 轮次
            matches_df: 比赛数据
            start_round: 起始轮次
            force_update: 是否强制更新已存在的数据
            
        Returns:
            保存结果统计
        """
        if not team_powers:
            logger.warning(f"第{round_number}轮公司{company_id}无实力数据可保存")
            return {
                'success': False,
                'reason': 'No team powers data',
                'saved_count': 0,
                'skipped_count': 0,
                'updated_count': 0
            }

        league_id = league_info.get('league_id', 0)
        
        # 1. 检查已存在的记录
        existing_teams = self._check_existing_records(
            league_id=league_id,
            company_id=company_id,
            season=season,
            round_number=round_number
        )
        
        # 2. 确定需要处理的球队
        teams_to_insert = []
        teams_to_update = []
        teams_to_skip = []
        
        calculation_time = datetime.now()
        
        for team_id, team_data in team_powers.items():
            team_id_int = int(team_id)
            
            if team_id_int in existing_teams and not force_update:
                teams_to_skip.append(team_id_int)
                continue
                
            record = TeamPowerRatingHistoryModel(
                team_id=team_id_int,
                league_id=league_id,
                company_id=company_id,
                season=season,
                round_number=round_number,
                calculation_date=calculation_time,
                start_round=start_round,
                target_round=round_number,
                total_power=team_data.get('total_power', 0.0),
                recent_power=team_data.get('recent_power', 0.0),
                relative_power=team_data.get('relative_power', 0.0),
                power_level=team_data.get('power_level', 0.0),
                tier_distance=team_data.get('tier_distance', 0.0),
                tier_level=team_data.get('tier_level', ''),
                team_name=team_data.get('team_name', ''),
                company_name=company_name
            )
            
            if team_id_int in existing_teams:
                teams_to_update.append(record)
            else:
                teams_to_insert.append(record)
        
        # 3. 执行数据库操作
        result = {
            'success': True,
            'saved_count': 0,
            'skipped_count': len(teams_to_skip),
            'updated_count': 0,
            'insert_count': 0
        }
        
        # 批量插入新记录
        if teams_to_insert:
            insert_count = self._batch_insert_new_records(teams_to_insert)
            result['saved_count'] += insert_count
            result['insert_count'] = insert_count
        
        # 批量更新已存在记录
        if teams_to_update:
            update_count = self._batch_update_existing_records(teams_to_update)
            result['updated_count'] = update_count
            result['saved_count'] += update_count
        
        # 4. 更新缓存
        self._update_existing_cache(league_id, company_id, season, round_number, team_powers.keys())
        
        # 5. 记录日志
        if result['skipped_count'] > 0:
            logger.info(f"第{round_number}轮公司{company_id}: 新增{result['insert_count']}, "
                       f"更新{result['updated_count']}, 跳过{result['skipped_count']}")
        else:
            logger.info(f"第{round_number}轮公司{company_id}: 保存{result['saved_count']}条记录")
        
        return result

    def _check_existing_records(
        self,
        league_id: int,
        company_id: int,
        season: Optional[str],
        round_number: int
    ) -> Set[int]:
        """
        检查已存在的记录
        
        Returns:
            已存在的team_id集合
        """
        cache_key = (league_id, company_id, season, round_number)
        
        # 检查缓存
        if cache_key in self._existing_cache:
            return self._existing_cache[cache_key]
        
        try:
            query = """
            SELECT team_id
            FROM team_power_ratings
            WHERE league_id = %s 
            AND company_id = %s 
            AND round_number = %s
            AND (season = %s OR (%s IS NULL AND season IS NULL))
            """
            
            existing_data = self.db.execute_query(
                query, 
                (league_id, company_id, round_number, season, season), 
                fetch='all'
            )
            
            existing_teams = {row['team_id'] for row in existing_data} if existing_data else set()
            
            # 缓存结果
            self._existing_cache[cache_key] = existing_teams
            
            return existing_teams
            
        except Exception as e:
            logger.warning(f"检查已存在记录时出错: {e}")
            return set()

    def _batch_insert_new_records(self, records: List[TeamPowerRatingHistoryModel]) -> int:
        """批量插入新记录"""
        if not records:
            return 0

        sql = """
        INSERT INTO team_power_ratings (
            team_id, league_id, company_id, season, round_number, calculation_date,
            start_round, target_round,
            total_power, recent_power, relative_power, 
            power_level, tier_level, tier_distance,
            team_name, company_name
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s,
            %s, %s
        )
        """
        
        try:
            successful_count = 0
            for record in records:
                try:
                    self.db.execute_query(sql, (
                        record.team_id, record.league_id, record.company_id, 
                        record.season, record.round_number, record.calculation_date,
                        record.start_round, record.target_round,
                        record.total_power, record.recent_power, record.relative_power, 
                        record.power_level, record.tier_level, record.tier_distance,
                        record.team_name, record.company_name
                    ))
                    successful_count += 1
                except Exception as record_error:
                    logger.warning(f"插入记录失败 (team_id={record.team_id}): {record_error}")
                    continue
            
            return successful_count
            
        except Exception as e:
            logger.error(f"批量插入新记录失败: {e}")
            return 0

    def _batch_update_existing_records(self, records: List[TeamPowerRatingHistoryModel]) -> int:
        """批量更新已存在的记录"""
        if not records:
            return 0

        sql = """
        UPDATE team_power_ratings SET
            calculation_date = %s,
            start_round = %s,
            target_round = %s,
            total_power = %s,
            recent_power = %s,
            relative_power = %s,
            power_level = %s,
            tier_level = %s,
            tier_distance = %s,
            team_name = %s,
            company_name = %s
        WHERE team_id = %s 
        AND league_id = %s 
        AND company_id = %s 
        AND round_number = %s
        AND (season = %s OR (%s IS NULL AND season IS NULL))
        """
        
        try:
            successful_count = 0
            for record in records:
                try:
                    affected_rows = self.db.execute_query(sql, (
                        record.calculation_date,
                        record.start_round, record.target_round,
                        record.total_power, record.recent_power, record.relative_power,
                        record.power_level, record.tier_level, record.tier_distance,
                        record.team_name, record.company_name,
                        record.team_id, record.league_id, record.company_id, record.round_number,
                        record.season, record.season
                    ))
                    if affected_rows and affected_rows > 0:
                        successful_count += 1
                except Exception as record_error:
                    logger.warning(f"更新记录失败 (team_id={record.team_id}): {record_error}")
                    continue
            
            return successful_count
            
        except Exception as e:
            logger.error(f"批量更新记录失败: {e}")
            return 0

    def _update_existing_cache(
        self,
        league_id: int,
        company_id: int,
        season: Optional[str],
        round_number: int,
        team_ids: List[str]
    ):
        """更新缓存中的已存在记录"""
        cache_key = (league_id, company_id, season, round_number)
        
        if cache_key not in self._existing_cache:
            self._existing_cache[cache_key] = set()
        
        # 将新保存的team_id添加到缓存
        for team_id in team_ids:
            self._existing_cache[cache_key].add(int(team_id))

    def check_round_completeness(
        self,
        league_id: int,
        round_number: int,
        season: Optional[str] = None,
        expected_companies: Optional[List[int]] = None
    ) -> Dict:
        """
        检查轮次数据完整性
        
        Args:
            league_id: 联赛ID
            round_number: 轮次
            season: 赛季
            expected_companies: 预期的公司ID列表
            
        Returns:
            完整性检查结果
        """
        try:
            # 查询该轮次已存在的公司和球队数据
            query = """
            SELECT 
                company_id,
                COUNT(DISTINCT team_id) as team_count,
                COUNT(*) as total_records,
                MAX(calculation_date) as latest_calculation
            FROM team_power_ratings
            WHERE league_id = %s 
            AND round_number = %s
            AND (season = %s OR %s IS NULL)
            GROUP BY company_id
            ORDER BY company_id
            """
            
            results = self.db.execute_query(
                query,
                (league_id, round_number, season, season),
                fetch='all'
            )
            
            if not results:
                return {
                    'complete': False,
                    'existing_companies': [],
                    'missing_companies': expected_companies or [],
                    'total_records': 0
                }
            
            existing_companies = [row['company_id'] for row in results]
            total_records = sum(row['total_records'] for row in results)
            
            # 计算缺失的公司
            missing_companies = []
            if expected_companies:
                missing_companies = [cid for cid in expected_companies if cid not in existing_companies]
            
            return {
                'complete': len(missing_companies) == 0 if expected_companies else len(existing_companies) > 0,
                'existing_companies': existing_companies,
                'missing_companies': missing_companies,
                'total_records': total_records,
                'company_details': {
                    row['company_id']: {
                        'team_count': row['team_count'],
                        'total_records': row['total_records'],
                        'latest_calculation': row['latest_calculation']
                    }
                    for row in results
                }
            }
            
        except Exception as e:
            logger.error(f"检查轮次完整性时出错: {e}")
            return {'complete': False, 'error': str(e)}

    def get_calculation_gaps(
        self,
        league_id: int,
        season: Optional[str] = None,
        start_round: int = 9,
        end_round: Optional[int] = None
    ) -> Dict:
        """
        获取计算缺口 - 找出缺少数据的轮次
        
        Returns:
            缺口分析结果
        """
        try:
            # 获取可用轮次范围
            available_query = """
            SELECT DISTINCT round_number 
            FROM matches 
            WHERE league_id = %s 
            AND (season = %s OR %s IS NULL)
            AND round_number >= %s
            ORDER BY round_number
            """
            
            params = [league_id, season, season, start_round]
            if end_round:
                available_query += " AND round_number <= %s"
                params.append(end_round)
            
            available_rounds = self.db.execute_query(available_query, params, fetch='all')
            available_round_numbers = [row['round_number'] for row in available_rounds]
            
            # 获取已计算的轮次
            calculated_query = """
            SELECT DISTINCT round_number,
                   COUNT(DISTINCT company_id) as company_count,
                   COUNT(DISTINCT team_id) as team_count
            FROM team_power_ratings
            WHERE league_id = %s
            AND (season = %s OR %s IS NULL)
            AND round_number >= %s
            GROUP BY round_number
            ORDER BY round_number
            """
            
            calc_params = [league_id, season, season, start_round]
            if end_round:
                calculated_query += " HAVING round_number <= %s"
                calc_params.append(end_round)
            
            calculated_rounds = self.db.execute_query(calculated_query, calc_params, fetch='all')
            calculated_round_numbers = [row['round_number'] for row in calculated_rounds]
            
            # 找出缺口
            missing_rounds = [r for r in available_round_numbers if r not in calculated_round_numbers]
            
            return {
                'league_id': league_id,
                'season': season,
                'available_rounds': available_round_numbers,
                'calculated_rounds': calculated_round_numbers,
                'missing_rounds': missing_rounds,
                'total_available': len(available_round_numbers),
                'total_calculated': len(calculated_round_numbers),
                'total_missing': len(missing_rounds),
                'completion_rate': len(calculated_round_numbers) / len(available_round_numbers) * 100 if available_round_numbers else 0,
                'calculated_details': {
                    row['round_number']: {
                        'company_count': row['company_count'],
                        'team_count': row['team_count']
                    }
                    for row in calculated_rounds
                }
            }
            
        except Exception as e:
            logger.error(f"获取计算缺口时出错: {e}")
            return {'error': str(e)}

    def clear_cache(self):
        """清空缓存"""
        self._existing_cache.clear()
        logger.info("已清空存储服务缓存")

    def get_cache_stats(self) -> Dict:
        """获取缓存统计信息"""
        return {
            'cache_size': len(self._existing_cache),
            'cache_keys': list(self._existing_cache.keys())
        }


def main():
    """测试和演示智能存储服务"""
    import argparse
    
    parser = argparse.ArgumentParser(description="智能存储服务工具")
    parser.add_argument('--check-gaps', action='store_true', help='检查计算缺口')
    parser.add_argument('--league-id', type=int, help='联赛ID')
    parser.add_argument('--season', type=str, help='赛季')
    parser.add_argument('--start-round', type=int, default=9, help='起始轮次')
    parser.add_argument('--end-round', type=int, help='结束轮次')
    
    args = parser.parse_args()
    
    if args.check_gaps and args.league_id:
        service = SmartStorageService()
        gaps = service.get_calculation_gaps(
            league_id=args.league_id,
            season=args.season,
            start_round=args.start_round,
            end_round=args.end_round
        )
        
        print(f"联赛ID {args.league_id} 计算缺口分析:")
        print(f"可用轮次: {gaps['total_available']}")
        print(f"已计算轮次: {gaps['total_calculated']}")
        print(f"缺失轮次: {gaps['total_missing']}")
        print(f"完成率: {gaps['completion_rate']:.1f}%")
        
        if gaps['missing_rounds']:
            print(f"缺失轮次详情: {gaps['missing_rounds']}")
        else:
            print("✅ 所有轮次计算完整")


if __name__ == "__main__":
    main()
