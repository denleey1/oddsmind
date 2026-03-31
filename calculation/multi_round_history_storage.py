#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多轮次历史广义实力存储服务
负责将广义实力计算结果存储到历史表并提供查询功能
"""
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
import pandas as pd
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from database.models import TeamPowerRatingHistoryModel
from core.logger import get_logger

logger = get_logger(__name__)


class MultiRoundHistoryStorageService:
    """
    多轮次历史广义实力存储服务
    """

    def __init__(self, db_connection=None):
        """
        初始化存储服务
        
        Args:
            db_connection: 数据库连接（可选，如果不提供会自动获取）
        """
        self.db = db_connection or get_connection()

    def save_round_history(
        self,
        team_powers: Dict,
        league_info: Dict,
        company_id: int,
        company_name: str,
        season: Optional[str],
        round_number: int,
        matches_df: Optional[pd.DataFrame] = None,
        start_round: int = 1
    ) -> int:
        """
        保存单轮次的广义实力历史数据
        
        Args:
            team_powers: 球队实力字典
            league_info: 联赛信息
            company_id: 公司ID
            company_name: 公司名称
            season: 赛季
            round_number: 轮次
            matches_df: 比赛数据（用于计算统计信息）
            
        Returns:
            成功保存的记录数
        """
        if not team_powers:
            logger.warning(f"第{round_number}轮公司{company_id}无实力数据可保存")
            return 0

        # 计算数据覆盖率
        data_coverage_rate = self._calculate_coverage_rate(matches_df) if matches_df is not None else None
        
        # 准备批量插入的数据
        history_records = []
        calculation_time = datetime.now()
        
        for team_id, team_data in team_powers.items():
            record = TeamPowerRatingHistoryModel(
                team_id=int(team_id),
                league_id=league_info.get('league_id', 0),
                company_id=company_id,
                season=season,
                round_number=round_number,
                calculation_date=calculation_time,
                
                # 轮次信息
                start_round=start_round,  # 实际的起始轮次
                target_round=round_number,  # 目标轮次就是当前轮次
                
                # 广义实力指标
                total_power=team_data.get('total_power', 0.0),
                recent_power=team_data.get('recent_power', 0.0),
                relative_power=team_data.get('relative_power', 0.0),
                power_level=team_data.get('power_level', 0.0),
                tier_distance=team_data.get('tier_distance', 0.0),
                tier_level=team_data.get('tier_level', ''),
                
                # 名称
                team_name=team_data.get('team_name', ''),
                company_name=company_name
            )
            history_records.append(record)

        # 批量插入数据库
        return self._batch_insert_history(history_records)

    def _calculate_coverage_rate(self, matches_df: pd.DataFrame) -> Optional[float]:
        """计算数据覆盖率"""
        if matches_df.empty:
            return None
        
        try:
            total_matches = len(matches_df)
            # 计算有完整赔率数据的比赛数量
            complete_matches = len(matches_df.dropna(subset=[
                'initial_home_prob', 'initial_draw_prob', 'initial_away_prob'
            ]))
            
            if total_matches > 0:
                coverage_rate = (complete_matches / total_matches) * 100
                return round(coverage_rate, 2)
        except Exception as e:
            logger.warning(f"计算数据覆盖率时出错: {e}")
        
        return None

    def _batch_insert_history(self, history_records: List[TeamPowerRatingHistoryModel]) -> int:
        """批量插入历史记录"""
        if not history_records:
            return 0

        # 使用REPLACE INTO实现upsert功能（覆盖已存在的记录）
        sql = """
        REPLACE INTO team_power_ratings (
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
            # 逐条插入数据（使用数据库连接对象的execute_query方法）
            successful_count = 0
            for record in history_records:
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
                    logger.warning(f"插入单条记录失败 (team_id={record.team_id}): {record_error}")
                    continue
            
            logger.info(f"成功保存 {successful_count}/{len(history_records)} 条广义实力历史记录")
            return successful_count
            
        except Exception as e:
            logger.error(f"批量插入历史记录失败: {e}")
            raise

    def get_team_power_history(
        self,
        team_id: int,
        league_id: int,
        company_id: Optional[int] = None,
        season: Optional[str] = None,
        start_round: Optional[int] = None,
        end_round: Optional[int] = None
    ) -> List[Dict]:
        """
        查询球队的广义实力历史数据
        
        Args:
            team_id: 球队ID
            league_id: 联赛ID
            company_id: 公司ID（可选）
            season: 赛季（可选）
            start_round: 起始轮次（可选）
            end_round: 结束轮次（可选）
            
        Returns:
            历史数据列表
        """
        conditions = ["team_id = %s", "league_id = %s"]
        params = [team_id, league_id]
        
        if company_id:
            conditions.append("company_id = %s")
            params.append(company_id)
        
        if season:
            conditions.append("season = %s")
            params.append(season)
        
        if start_round:
            conditions.append("round_number >= %s")
            params.append(start_round)
        
        if end_round:
            conditions.append("round_number <= %s")
            params.append(end_round)
        
        sql = f"""
        SELECT * FROM team_power_ratings
        WHERE {' AND '.join(conditions)}
        ORDER BY round_number, company_id
        """
        
        try:
            results = self.db.execute_query(sql, params, fetch='all')
            return results or []
        except Exception as e:
            logger.error(f"查询球队广义实力历史失败: {e}")
            return []

    def get_round_power_rankings(
        self,
        league_id: int,
        round_number: int,
        company_id: Optional[int] = None,
        season: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict]:
        """
        查询特定轮次的实力排名
        
        Args:
            league_id: 联赛ID
            round_number: 轮次
            company_id: 公司ID（可选）
            season: 赛季（可选）
            limit: 返回记录数限制
            
        Returns:
            排名数据列表
        """
        conditions = ["league_id = %s", "round_number = %s"]
        params = [league_id, round_number]
        
        if company_id:
            conditions.append("company_id = %s")
            params.append(company_id)
        
        if season:
            conditions.append("season = %s")
            params.append(season)
        
        sql = f"""
        SELECT team_id, team_name, company_id, company_name,
               total_power, relative_power, power_level, tier_level,
               target_round, calculation_date,
               ROW_NUMBER() OVER (ORDER BY total_power DESC) as ranking
        FROM team_power_ratings
        WHERE {' AND '.join(conditions)}
        ORDER BY total_power DESC
        LIMIT %s
        """
        
        params.append(limit)
        
        try:
            results = self.db.execute_query(sql, params, fetch='all')
            return results or []
        except Exception as e:
            logger.error(f"查询轮次实力排名失败: {e}")
            return []

    def get_league_calculation_summary(
        self,
        league_id: int,
        season: Optional[str] = None
    ) -> Dict:
        """
        获取联赛的计算摘要统计信息
        
        Args:
            league_id: 联赛ID
            season: 赛季（可选）
            
        Returns:
            摘要统计信息
        """
        conditions = ["league_id = %s"]
        params = [league_id]
        
        if season:
            conditions.append("season = %s")
            params.append(season)
        
        sql = f"""
        SELECT 
            COUNT(DISTINCT round_number) as total_rounds,
            COUNT(DISTINCT company_id) as total_companies,
            COUNT(DISTINCT team_id) as total_teams,
            COUNT(*) as total_records,
            MIN(round_number) as min_round,
            MAX(round_number) as max_round,
            MIN(calculation_date) as first_calculation,
            MAX(calculation_date) as last_calculation,
            AVG(data_coverage_rate) as avg_coverage_rate
        FROM team_power_ratings
        WHERE {' AND '.join(conditions)}
        """
        
        try:
            result = self.db.execute_query(sql, params, fetch='one')
            
            return {
                'league_id': league_id,
                'season': season,
                'summary': result or {}
            }
        except Exception as e:
            logger.error(f"获取联赛计算摘要失败: {e}")
            return {'league_id': league_id, 'season': season, 'summary': {}}

    def get_companies_by_round(
        self,
        league_id: int,
        round_number: int,
        season: Optional[str] = None
    ) -> List[Dict]:
        """
        获取特定轮次计算过的所有公司信息
        
        Args:
            league_id: 联赛ID
            round_number: 轮次
            season: 赛季（可选）
            
        Returns:
            公司信息列表
        """
        conditions = ["league_id = %s", "round_number = %s"]
        params = [league_id, round_number]
        
        if season:
            conditions.append("season = %s")
            params.append(season)
        
        sql = f"""
        SELECT DISTINCT 
            company_id, company_name,
            COUNT(DISTINCT team_id) as teams_count,
            AVG(data_coverage_rate) as avg_coverage_rate,
            MAX(calculation_date) as calculation_date
        FROM team_power_ratings
        WHERE {' AND '.join(conditions)}
        GROUP BY company_id, company_name
        ORDER BY company_id
        """
        
        try:
            results = self.db.execute_query(sql, params, fetch='all')
            return results or []
        except Exception as e:
            logger.error(f"查询轮次公司信息失败: {e}")
            return []

    def delete_round_data(
        self,
        league_id: int,
        round_number: int,
        season: Optional[str] = None,
        company_id: Optional[int] = None
    ) -> int:
        """
        删除指定轮次的历史数据
        
        Args:
            league_id: 联赛ID
            round_number: 轮次
            season: 赛季（可选）
            company_id: 公司ID（可选，不指定则删除该轮次所有公司数据）
            
        Returns:
            删除的记录数
        """
        conditions = ["league_id = %s", "round_number = %s"]
        params = [league_id, round_number]
        
        if season:
            conditions.append("season = %s")
            params.append(season)
        
        if company_id:
            conditions.append("company_id = %s")
            params.append(company_id)
        
        sql = f"""
        DELETE FROM team_power_ratings
        WHERE {' AND '.join(conditions)}
        """
        
        try:
            affected_rows = self.db.execute_query(sql, params)
            
            logger.info(f"删除了 {affected_rows} 条历史记录")
            return affected_rows
            
        except Exception as e:
            logger.error(f"删除历史数据失败: {e}")
            raise

    def export_history_data(
        self,
        league_id: int,
        output_file: str,
        season: Optional[str] = None,
        company_id: Optional[int] = None,
        start_round: Optional[int] = None,
        end_round: Optional[int] = None
    ) -> bool:
        """
        导出历史数据到CSV文件
        
        Args:
            league_id: 联赛ID
            output_file: 输出文件路径
            season: 赛季（可选）
            company_id: 公司ID（可选）
            start_round: 起始轮次（可选）
            end_round: 结束轮次（可选）
            
        Returns:
            是否成功导出
        """
        conditions = ["league_id = %s"]
        params = [league_id]
        
        if season:
            conditions.append("season = %s")
            params.append(season)
        
        if company_id:
            conditions.append("company_id = %s")
            params.append(company_id)
        
        if start_round:
            conditions.append("round_number >= %s")
            params.append(start_round)
        
        if end_round:
            conditions.append("round_number <= %s")
            params.append(end_round)
        
        sql = f"""
        SELECT * FROM team_power_ratings
        WHERE {' AND '.join(conditions)}
        ORDER BY round_number, company_id, combined_power DESC
        """
        
        try:
            # 获取数据
            results = self.db.execute_query(sql, params, fetch='all')
            
            if not results:
                logger.warning("没有数据可导出")
                return False
            
            # 转换为DataFrame并导出
            df = pd.DataFrame(results)
            df.to_csv(output_file, index=False, encoding='utf-8')
            
            logger.info(f"成功导出 {len(df)} 条记录到文件: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"导出历史数据失败: {e}")
            return False
