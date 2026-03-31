#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据仓库：负责加载和验证广义实力计算所需的数据
"""
import sys
from pathlib import Path
import pandas as pd
from typing import Optional, Dict, Tuple

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import DatabaseConnection
from core.logger import get_logger

logger = get_logger(__name__)

# 数据完整性阈值
COVERAGE_THRESHOLD = 0.80  # 80% coverage threshold

class StrengthDataRepository:
    """
    广义实力计算的数据仓库
    """
    def __init__(self, db: DatabaseConnection):
        self.db = db

    def load_all_companies_data(self, league_id: int, season: Optional[str],
                                division: Optional[str] = None) -> Dict[int, pd.DataFrame]:
        """
        加载联赛中所有公司的比赛和赔率数据，并按公司进行分组和筛选。

        Args:
            league_id: 联赛ID
            season: 赛季
            division: 分区标识 (如 'east', 'west')。为 None 表示加载全部比赛。
        """
        div_label = f" [分区={division}]" if division else ""
        logger.info(f"开始为联赛 {league_id}{div_label} 加载所有公司的赔率数据...")

        # 1. 一次性查询出所有相关数据
        query = """
        SELECT 
            m.match_id, m.league_id, m.season, m.division, m.round_number,
            m.home_team_id, m.away_team_id,
            COALESCE(ht.name_cn, m.home_team_name, CONCAT('Team_', m.home_team_id)) as home_team,
            COALESCE(at.name_cn, m.away_team_name, CONCAT('Team_', m.away_team_id)) as away_team,
            m.home_score, m.away_score, m.match_time, m.match_status,
            eo.company_id,
            COALESCE(c.name_cn, c.name_en, CONCAT('Company_', eo.company_id)) as company_name,
            eo.initial_home_prob, eo.initial_draw_prob, eo.initial_away_prob
        FROM matches m
        INNER JOIN european_odds eo ON m.match_id = eo.match_id
        LEFT JOIN teams ht ON m.home_team_id = ht.team_id
        LEFT JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN companies c ON eo.company_id = c.company_id
        WHERE m.league_id = %s
          AND eo.initial_home_prob IS NOT NULL 
          AND eo.initial_draw_prob IS NOT NULL 
          AND eo.initial_away_prob IS NOT NULL
          AND m.match_status = 'finished'
          {season_filter}
          {division_filter}
        ORDER BY eo.company_id, m.match_time
        """
        
        params = [league_id]
        season_filter = ""
        division_filter = ""
        if season:
            season_filter = "AND m.season = %s"
            params.append(season)
        if division:
            division_filter = "AND m.division = %s"
            params.append(division)
        query = query.format(season_filter=season_filter, division_filter=division_filter)

        try:
            raw_data = self.db.execute_query(query, params, fetch='all')
            if not raw_data:
                logger.warning("没有找到符合条件的任何公司赔率数据")
                return {}
            
            full_df = pd.DataFrame(raw_data)
            
            # 2. 获取总比赛场数用于计算覆盖率
            total_matches_query = "SELECT COUNT(DISTINCT match_id) as total FROM matches WHERE league_id = %s AND match_status = 'finished'"
            total_params = [league_id]
            if season:
                total_matches_query += " AND season = %s"
                total_params.append(season)
            if division:
                total_matches_query += " AND division = %s"
                total_params.append(division)
            
            total_matches_result = self.db.execute_query(total_matches_query, total_params, fetch='one')
            total_finished_matches = total_matches_result['total'] if total_matches_result else 0

            if total_finished_matches == 0:
                logger.warning(f"联赛 {league_id} 没有已完成的比赛，无法计算覆盖率。")
                return {}

            # 3. 按公司分组，并筛选出符合覆盖率的公司
            valid_companies_data = {}
            grouped_by_company = full_df.groupby('company_id')

            logger.info(f"发现 {len(grouped_by_company)} 家公司的数据，正在逐一校验覆盖率...")

            for company_id, company_df in grouped_by_company:
                covered_matches = company_df['match_id'].nunique()
                coverage_ratio = covered_matches / total_finished_matches if total_finished_matches > 0 else 0
                company_name = company_df['company_name'].iloc[0]

                if coverage_ratio >= COVERAGE_THRESHOLD:
                    logger.info(f"  [通过] 公司: {company_name} (ID: {company_id}) | 覆盖率: {coverage_ratio:.2%} ({covered_matches}/{total_finished_matches})")
                    
                    # 预处理数据
                    company_df['home_team_unbeaten_rate'] = company_df['initial_home_prob'] + company_df['initial_draw_prob']
                    company_df['away_team_unbeaten_rate'] = company_df['initial_away_prob'] + company_df['initial_draw_prob']
                    valid_companies_data[company_id] = company_df
                else:
                    logger.info(f"  [跳过] 公司: {company_name} (ID: {company_id}) | 覆盖率: {coverage_ratio:.2%} ({covered_matches}/{total_finished_matches}) - 未达到 {COVERAGE_THRESHOLD:.0%} 阈值")

            if not valid_companies_data:
                logger.warning("没有公司的赔率数据满足覆盖率要求，无法进行计算。")

            return valid_companies_data

        except Exception as e:
            logger.error(f"加载所有公司数据失败: {e}", exc_info=True)
            return {}

    def get_league_info(self, league_id: int) -> Optional[Dict]:
        """加载联赛信息"""
        try:
            league_info = self.db.execute_query(
                "SELECT league_id, name_cn, name_en, country FROM leagues WHERE league_id = %s",
                (league_id,),
                fetch='one'
            )
            if league_info:
                logger.info(f"加载联赛信息: {league_info['name_cn']} ({league_info['name_en']})")
                return league_info
            else:
                logger.error(f"未找到联赛ID {league_id} 的信息")
                return None
        except Exception as e:
            logger.error(f"加载联赛信息失败: {e}")
            return None

    def get_matches_data(self, league_id: int, season: Optional[str], company_id: Optional[int], 
                           start_round: Optional[int], target_round: Optional[int]) -> Tuple[pd.DataFrame, int]:
        """
        加载比赛数据和赔率概率
        """
        log_msg = f"开始加载联赛 {league_id}"
        if start_round or target_round:
            round_parts = []
            if start_round:
                round_parts.append(f"从第{start_round}轮开始")
            if target_round:
                round_parts.append(f"截至第{target_round}轮")
            log_msg += f" {' '.join(round_parts)}的比赛和赔率数据..."
        else:
            log_msg += " 的比赛和赔率数据..."
        logger.info(log_msg)
        
        query = """
        SELECT DISTINCT
            m.match_id, m.league_id, m.season, m.round_number,
            m.home_team_id, m.away_team_id,
            COALESCE(ht.name_cn, m.home_team_name, CONCAT('Team_', m.home_team_id)) as home_team,
            COALESCE(at.name_cn, m.away_team_name, CONCAT('Team_', m.away_team_id)) as away_team,
            m.home_score, m.away_score, m.match_time, m.match_status,
            eo.company_id,
            COALESCE(c.name_cn, 'Unknown') as company_name,
            eo.initial_home_prob, eo.initial_draw_prob, eo.initial_away_prob
        FROM matches m
        INNER JOIN european_odds eo ON m.match_id = eo.match_id
        LEFT JOIN teams ht ON m.home_team_id = ht.team_id
        LEFT JOIN teams at ON m.away_team_id = at.team_id
        LEFT JOIN companies c ON eo.company_id = c.company_id
        WHERE m.league_id = %s
          AND eo.initial_home_prob IS NOT NULL 
          AND eo.initial_draw_prob IS NOT NULL 
          AND eo.initial_away_prob IS NOT NULL
          AND m.match_status = 'finished'
        """
        
        params = [league_id]
        if season:
            query += " AND m.season = %s"
            params.append(season)
        if company_id:
            query += " AND eo.company_id = %s"
            params.append(company_id)
        if start_round:
            query += " AND m.round_number >= %s"
            params.append(start_round)
        if target_round:
            query += " AND m.round_number <= %s"
            params.append(target_round)
        
        query += " ORDER BY m.match_time, m.match_id, eo.company_id"
        
        try:
            raw_data = self.db.execute_query(query, params, fetch='all')
            if not raw_data:
                logger.warning("没有找到符合条件的比赛数据")
                return pd.DataFrame(), company_id
            
            matches_df = pd.DataFrame(raw_data)
            
            # 如果没有指定公司，自动选择数据最多的公司
            if not company_id:
                company_counts = matches_df['company_id'].value_counts()
                if not company_counts.empty:
                    company_id = company_counts.index[0]
                    company_name = matches_df[matches_df['company_id'] == company_id]['company_name'].iloc[0]
                    matches_df = matches_df[matches_df['company_id'] == company_id].copy()
                    logger.info(f"自动选择数据最多的博彩公司: {company_name} (ID: {company_id}, 数据量: {company_counts.iloc[0]})")
                else:
                    logger.warning("未找到任何公司的数据")
                    return pd.DataFrame(), None

            if matches_df.empty:
                 return pd.DataFrame(), company_id

            matches_df['home_team_unbeaten_rate'] = matches_df['initial_home_prob'] + matches_df['initial_draw_prob']
            matches_df['away_team_unbeaten_rate'] = matches_df['initial_away_prob'] + matches_df['initial_draw_prob']
            
            self._show_data_summary(matches_df)
            
            return matches_df, company_id
            
        except Exception as e:
            logger.error(f"加载比赛数据失败: {e}")
            return pd.DataFrame(), company_id
            
    def _show_data_summary(self, df: pd.DataFrame):
        """显示数据摘要信息"""
        if df.empty: return
        unique_teams = pd.concat([df['home_team'], df['away_team']]).nunique()
        try:
            min_date = pd.to_datetime(df['match_time']).min().date()
            max_date = pd.to_datetime(df['match_time']).max().date()
            date_range = f"{min_date} 到 {max_date}"
        except Exception:
            date_range = "日期格式异常"
        seasons = df['season'].dropna().unique()
        company_name = df['company_name'].iloc[0]
        
        logger.info(f"数据摘要:")
        logger.info(f"  - 比赛数量: {len(df)}")
        logger.info(f"  - 队伍数量: {unique_teams}")
        logger.info(f"  - 时间范围: {date_range}")
        logger.info(f"  - 赛季: {list(seasons) if len(seasons) > 0 else '未指定'}")
        logger.info(f"  - 博彩公司: {company_name}")

    def validate_data_coverage(self, league_id: int, company_id: int, season: Optional[str]) -> Tuple[bool, Dict]:
        """
        验证数据覆盖率
        """
        query_base = """
        SELECT COUNT(DISTINCT m.match_id) AS covered_matches,
               (SELECT COUNT(DISTINCT match_id) FROM matches WHERE league_id = %s {season_cond_total} AND match_status = 'finished') AS total_matches
        FROM matches m
        JOIN european_odds e ON m.match_id = e.match_id
        WHERE e.company_id = %s AND m.league_id = %s {season_cond_main} AND m.match_status = 'finished'
        """
        
        params = [league_id]
        if season:
            query = query_base.format(season_cond_total="AND season = %s", season_cond_main="AND m.season = %s")
            params.extend([season, company_id, league_id, season])
        else:
            query = query_base.format(season_cond_total="", season_cond_main="")
            params.extend([company_id, league_id])

        try:
            result = self.db.execute_query(query, params, fetch='one')
            if not result or result['total_matches'] is None:
                return False, {"error": "查询覆盖率数据失败"}

            covered = result['covered_matches']
            total = result['total_matches']
            ratio = covered / total if total > 0 else 0
            
            info = {
                'total_matches': total,
                'covered_matches': covered,
                'coverage_ratio': ratio,
                'company_id': company_id,
                'league_id': league_id
            }
            
            is_valid = ratio >= COVERAGE_THRESHOLD
            logger.info(f"数据完整性: 覆盖比赛数={covered}, 总比赛数={total}, 覆盖率={ratio:.2%}")
            
            if not is_valid:
                logger.warning(f"警告: 公司ID {company_id} 对联赛 {league_id} 的赔率数据不完整!")
            
            return is_valid, info
            
        except Exception as e:
            logger.error(f"验证数据覆盖率时出错: {e}")
            return False, {"error": str(e)}
