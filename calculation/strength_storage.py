#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
存储服务：负责将计算结果保存到数据库
"""
import sys
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import DatabaseConnection
from core.logger import get_logger

logger = get_logger(__name__)

class StrengthStorageService:
    """
    负责将计算结果存储到数据库
    """
    def __init__(self, db: DatabaseConnection, league_id: int):
        self.db = db
        self.league_id = league_id

    def save_results(self, team_powers: Dict, league_info: Dict, company_id: int, company_name: str, 
                     season: Optional[str], start_round: Optional[int], target_round: Optional[int],
                     division: str = ''):
        """
        保存计算结果到 team_power_ratings 表。
        使用 INSERT ... ON DUPLICATE KEY UPDATE 实现覆盖更新。

        Args:
            division: 分区标识 ('east', 'west' 等)，空字符串表示全局/无分区。
        """
        if not team_powers:
            logger.warning("没有实力数据可保存")
            return

        try:
            insert_query = """
                INSERT INTO team_power_ratings (
                    team_id, league_id, company_id, season, division, round_number, calculation_date,
                    total_power, recent_power, relative_power, power_level, tier_distance,
                    tier_level, team_name, company_name
                )
                VALUES (
                    %(team_id)s, %(league_id)s, %(company_id)s, %(season)s, %(division)s, %(round_number)s, %(calculation_date)s,
                    %(total_power)s, %(recent_power)s, %(relative_power)s, %(power_level)s, %(tier_distance)s,
                    %(tier_level)s, %(team_name)s, %(company_name)s
                )
                ON DUPLICATE KEY UPDATE
                    season = VALUES(season),
                    division = VALUES(division),
                    round_number = VALUES(round_number),
                    calculation_date = VALUES(calculation_date),
                    total_power = VALUES(total_power),
                    recent_power = VALUES(recent_power),
                    relative_power = VALUES(relative_power),
                    power_level = VALUES(power_level),
                    tier_distance = VALUES(tier_distance),
                    tier_level = VALUES(tier_level),
                    team_name = VALUES(team_name),
                    company_name = VALUES(company_name),
                    updated_at = NOW();
            """
            
            data_to_save = self._prepare_data_for_save(
                team_powers=team_powers, 
                league_id=self.league_id, 
                company_id=company_id, 
                company_name=company_name,
                season=season, 
                target_round=target_round,
                division=division
            )
            
            if not data_to_save:
                logger.info("没有准备好用于保存的数据")
                return

            affected_rows = self.db.execute_many(insert_query, data_to_save)
            logger.info(f"为公司 {company_name} (ID: {company_id}) 成功保存/更新 {affected_rows} 条广义实力数据到 `team_power_ratings` 表")

        except Exception as e:
            logger.error(f"为公司ID {company_id} 保存数据到 `team_power_ratings` 表失败: {e}", exc_info=True)
            raise

    def _prepare_data_for_save(self, team_powers: Dict, league_id: int, company_id: int, company_name: str,
                               season: Optional[str], target_round: Optional[int],
                               division: str = '') -> list:
        """准备用于批量插入/更新的数据，格式为字典列表"""
        calculation_date = datetime.now()
        
        data_list = []
        for team_id, team_data in team_powers.items():
            data_list.append({
                "team_id": team_id,
                "league_id": league_id,
                "company_id": company_id,
                "season": season,
                "division": division,
                "round_number": target_round,
                "calculation_date": calculation_date,
                "total_power": team_data.get('total_power'),
                "recent_power": team_data.get('recent_power'),
                "relative_power": team_data.get('relative_power'),
                "power_level": team_data.get('power_level'),
                "tier_distance": team_data.get('tier_distance'),
                "tier_level": team_data.get('tier_level') or team_data.get('level_class'),
                "team_name": team_data.get('team_name'),
                "company_name": company_name
            })
        return data_list