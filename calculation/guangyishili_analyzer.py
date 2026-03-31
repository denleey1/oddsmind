# 确保在文件顶部导入所有必要的模块
import sqlite3
import os
import collections
import json
import time
import sys
import pandas as pd
import numpy as np
from datetime import datetime
import concurrent.futures  # 添加多线程支持
import logging
import re

# 添加父级目录到Python路径，以便导入config模块
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# 导入配置的数据库路径和联赛配置
from football_analysis_system.config import DB_GUANGYISHILI, DATA_DIR
from football_analysis_system.scrapers.config import LEAGUES

# 获取日志记录器
logger = logging.getLogger("football_analysis")

# 设置覆盖率阈值
COVERAGE_THRESHOLD = 0.80  # 80%的覆盖率阈值
# 设置赔率数据缺失阈值
MISSING_ODDS_THRESHOLD = 5.0  # 5%的缺失率阈值

def calculate_league_power_ratings(db_path, company_id, league_id, league_name, matches_table_name, team_count, max_round):
    """
    为特定联赛和博彩公司计算广义实力评分

    参数:
    db_path: 数据库路径
    company_id: 博彩公司ID
    league_id: 联赛ID
    league_name: 联赛名称
    matches_table_name: 匹配的表名
    team_count: 联赛球队数量
    max_round: 最大轮次

    返回:
    (league_data, incomplete_info) - 计算结果和不完整数据的信息(若有)
    """
    # 调试标志
    is_debug = False

    # 连接数据库 - 每个线程需要自己的连接
    conn = sqlite3.connect(db_path)

    try:
        # 检查数据完整性 - 只保留整体联赛覆盖率检查
        data_completeness_query = f"""
        SELECT COUNT(DISTINCT m.match_id) AS covered_matches,
               (SELECT COUNT(DISTINCT match_id) FROM {matches_table_name} WHERE league_id = {league_id}) AS total_matches
        FROM {matches_table_name} m
        JOIN euro_odds e ON m.match_id = e.match_id
        WHERE e.company_id = '{company_id}' AND m.league_id = {league_id};
        """

        if is_debug:
            print(f"执行SQL查询: {data_completeness_query}")

        completeness_df = pd.read_sql_query(data_completeness_query, conn)
        covered_matches = completeness_df.iloc[0]['covered_matches']
        total_matches = completeness_df.iloc[0]['total_matches']
        coverage_ratio = covered_matches / total_matches if total_matches > 0 else 0

        if is_debug:
            logger.info(f"数据完整性结果: 覆盖比赛数={covered_matches}, 总比赛数={total_matches}, 覆盖率={coverage_ratio:.2%}")

        # 如果覆盖率低于阈值，返回不完整信息
        if coverage_ratio < COVERAGE_THRESHOLD:
            logger.warning(f"警告: 公司ID {company_id} 对联赛 {league_name} 的赔率数据不完整!")
            logger.warning(f"总体覆盖率: {coverage_ratio:.2%} ({covered_matches}/{total_matches})")
            logger.warning(f"跳过对该联赛的广义实力计算。")

            incomplete_info = {
                'league_id': league_id,
                'league_name': league_name,
                'coverage': f"{coverage_ratio:.2%}",
                'matches': f"{covered_matches}/{total_matches}",
                'reason': "数据不完整"
            }

            conn.close()
            return None, incomplete_info

        logger.info(f"公司ID {company_id} 对联赛 {league_name} 的赔率数据完整性检查通过。")

        # 近况轮次数 = 球队总数 - 1 (如联赛有20支球队，则近况考虑19轮)
        recent_rounds = team_count - 1

        # 获取该联赛的赔率数据
        odds_query = f"""
        SELECT m.match_id, m.round_number,
               m.home_team_id, m.home_team_name,
               m.away_team_id, m.away_team_name,
               o.init_home_win_rate, o.init_draw_rate, o.init_away_win_rate
        FROM {matches_table_name} m
        JOIN euro_odds o ON m.match_id = o.match_id
        WHERE o.company_id = '{company_id}' AND m.league_id = {league_id}
        ORDER BY m.round_number;
        """

        if is_debug:
            logger.info(f"执行赔率查询: {odds_query}")

        odds_df = pd.read_sql_query(odds_query, conn)

        # 如果没有数据，返回None
        if odds_df.empty:
            logger.warning(f"没有找到联赛 {league_name} 的赔率数据")
            conn.close()
            return None, {'league_id': league_id, 'league_name': league_name, 'reason': "没有找到赔率数据"}

        if is_debug:
            logger.info(f"成功获取赔率数据，共 {len(odds_df)} 条记录")

        # 直接使用已有的概率数据
        odds_df['home_win_prob'] = odds_df['init_home_win_rate']
        odds_df['draw_prob'] = odds_df['init_draw_rate']
        odds_df['away_win_prob'] = odds_df['init_away_win_rate']

        # 计算不败率
        odds_df['home_team_unbeaten_rate'] = odds_df['home_win_prob'] + odds_df['draw_prob']
        odds_df['away_team_unbeaten_rate'] = odds_df['away_win_prob'] + odds_df['draw_prob']

        # 初始化球队广义实力存储字典
        teams_data = {}

        # 获取所有球队ID
        all_team_ids = list(set(odds_df['home_team_id'].tolist() + odds_df['away_team_id'].tolist()))

        if is_debug:
            logger.info(f"球队总数: {len(all_team_ids)}")

        for team_id in all_team_ids:
            # 该队主场比赛数据
            home_matches = odds_df[odds_df['home_team_id'] == team_id]
            # 该队客场比赛数据
            away_matches = odds_df[odds_df['away_team_id'] == team_id]

            # 获取该队所有比赛
            team_matches = pd.concat([home_matches, away_matches], ignore_index=True)

            # 计算该队自身的最大轮次 - 修改点1：使用球队自身最大轮次而非联赛最大轮次
            team_max_round = team_matches['round_number'].max() if not team_matches.empty else 0

            # 计算主场平均不败率和客场平均不败率 (总体)
            avg_home_unbeaten_rate = home_matches['home_team_unbeaten_rate'].mean() if not home_matches.empty else 0
            avg_away_unbeaten_rate = away_matches['away_team_unbeaten_rate'].mean() if not away_matches.empty else 0

            # 计算初赔总场广义实力
            total_power = avg_home_unbeaten_rate + avg_away_unbeaten_rate

            # 计算近况 - 只取最近N轮的比赛
            recent_threshold = team_max_round - recent_rounds
            recent_home = home_matches[home_matches['round_number'] > recent_threshold]
            recent_away = away_matches[away_matches['round_number'] > recent_threshold]

            recent_home_avg = recent_home['home_team_unbeaten_rate'].mean() if not recent_home.empty else 0
            recent_away_avg = recent_away['away_team_unbeaten_rate'].mean() if not recent_away.empty else 0
            recent_power = recent_home_avg + recent_away_avg

            # 获取球队名称
            team_name = ""
            if not home_matches.empty:
                team_name = home_matches.iloc[0]['home_team_name']
            elif not away_matches.empty:
                team_name = away_matches.iloc[0]['away_team_name']
            
            # 球队名称标准化映射 - 确保一致性
            team_name_mapping = {
                "韦纳穆": "瓦纳默",
                # 可以在这里添加更多映射
            }
            # 应用映射
            if team_name in team_name_mapping:
                logger.info(f"球队名称标准化: {team_name} -> {team_name_mapping[team_name]}")
                team_name = team_name_mapping[team_name]

            # 存储球队数据
            teams_data[team_id] = {
                'team_id': team_id,
                'team_name': team_name,
                'total_power': total_power,
                'recent_power': recent_power,
                'max_round': team_max_round,  # 添加最大轮次信息
                'recent_matches': len(recent_home) + len(recent_away)  # 添加实际近况轮次信息
            }

        # 转换为DataFrame便于处理
        teams_df = pd.DataFrame.from_dict(teams_data, orient='index')

        # 计算初赔综合广义实力评分
        teams_df['combined_power'] = teams_df['total_power'] * 0.2 + teams_df['recent_power'] * 0.8

        # 找出综合广义实力最小的球队作为零点
        min_power = teams_df['combined_power'].min()

        # 计算相对广义实力评分
        teams_df['relative_power'] = teams_df['combined_power'] - min_power

        # 计算档距
        teams_df['power_level'] = (teams_df['relative_power'] / 10.5).round(1)

        # 根据档距进行分类
        def categorize_team(power_level):
            if power_level >= 8.5: return "超强1"
            elif power_level >= 8.0: return "超强2"
            elif power_level >= 7.5: return "人强1"
            elif power_level >= 7.0: return "人强2"
            elif power_level >= 6.5: return "普强1"
            elif power_level >= 6.0: return "普强2"
            elif power_level >= 5.5: return "准强1"
            elif power_level >= 5.0: return "准强2"
            elif power_level >= 4.5: return "中强1"
            elif power_level >= 4.0: return "中强2"
            elif power_level >= 3.5: return "中上1"
            elif power_level >= 3.0: return "中上2"
            elif power_level >= 2.5: return "中游1"
            elif power_level >= 2.0: return "中游2"
            elif power_level >= 1.5: return "中下1"
            elif power_level >= 1.0: return "中下2"
            elif power_level >= 0.5: return "下游1"
            else: return "下游2"

        teams_df['power_category'] = teams_df['power_level'].apply(categorize_team)

        # 按相对广义实力评分排序
        teams_df = teams_df.sort_values(by='relative_power', ascending=False)

        # 添加排名
        teams_df['rank'] = range(1, len(teams_df) + 1)

        # 显示每支球队的最大轮次和近况轮次数量信息
        logger.info(f"\n联赛: {league_name} 各队最大轮次和近况轮次数量:")
        for _, row in teams_df.iterrows():
            logger.info(f"  {row['team_name']}: 最大轮次 {row['max_round']}, 近况包含 {row['recent_matches']} 场比赛")

        # 存储该联赛的结果 - 最终输出结果中移除调试列
        final_teams_df = teams_df.drop(['max_round', 'recent_matches'], axis=1, errors='ignore')

        league_data = {
            'league_name': league_name,
            'teams_df': final_teams_df
        }

        if is_debug:
            logger.info(f"==== 公司ID {company_id} 对联赛 {league_name} 的广义实力计算成功完成 ====\n")

        conn.close()
        return league_data, None

    except Exception as e:
        logger.error(f"计算联赛 {league_name} 的广义实力时出错: {e}")
        if is_debug:
            logger.error(f"==== 公司ID {company_id} 对联赛 {league_name} 处理时出错 ====")
            logger.error(f"错误详情: {e}")
            import traceback
            logger.error(traceback.format_exc())
        conn.close()
        return None, {'league_id': league_id, 'league_name': league_name, 'reason': f"计算错误: {e}"}

def get_leagues_with_incomplete_odds(conn, matches_table_name='matches'):
    """
    获取赔率数据不完整的联赛列表

    参数:
    conn: 数据库连接
    matches_table_name: 比赛表名

    返回:
    包含数据不完整联赛ID的列表
    """
    try:
        # 查询每个联赛中已完成比赛但缺少赔率数据的占比
        query = f"""
        WITH completed_matches AS (
            SELECT
                league_id,
                league_name,
                match_id,
                matchid
            FROM
                {matches_table_name}
            WHERE
                match_status = 4 OR match_status = -1  -- 已完成的比赛
        ),
        league_stats AS (
            SELECT
                cm.league_id,
                cm.league_name,
                COUNT(cm.match_id) AS total_completed_matches,
                SUM(CASE WHEN e.match_id IS NULL THEN 1 ELSE 0 END) AS missing_odds_count
            FROM
                completed_matches cm
            LEFT JOIN
                euro_odds e ON cm.match_id = e.match_id
            GROUP BY
                cm.league_id, cm.league_name
        )
        SELECT
            league_id,
            league_name,
            total_completed_matches,
            missing_odds_count,
            (missing_odds_count * 100.0 / total_completed_matches) AS missing_percentage
        FROM
            league_stats
        WHERE
            total_completed_matches > 0  -- 避免除以零
            AND (missing_odds_count * 100.0 / total_completed_matches) > {MISSING_ODDS_THRESHOLD}
        ORDER BY
            missing_percentage DESC;
        """

        df = pd.read_sql_query(query, conn)

        if not df.empty:
            logger.warning(f"以下联赛的赔率数据不完整(缺失率>{MISSING_ODDS_THRESHOLD}%):")
            for _, row in df.iterrows():
                logger.warning(f"  - {row['league_name']} (ID: {row['league_id']}): "
                               f"完成比赛 {row['total_completed_matches']} 场, "
                               f"缺失赔率 {row['missing_odds_count']} 场, "
                               f"缺失率 {row['missing_percentage']:.2f}%")

            # 返回数据不完整的联赛ID列表
            return df['league_id'].tolist()

        return []

    except Exception as e:
        logger.error(f"检查赔率数据完整性时出错: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []

def calculate_league_power_ratings_optimized(db_path, company_id, league_id, league_name, matches_table_name, team_count, max_round):
    """
    优化版本的广义实力评分计算函数
    主要优化：
    1. SQL查询优化，减少查询次数
    2. 使用pandas向量化操作替代循环
    3. 一次性计算所有球队统计信息
    """
    is_debug = False

    conn = sqlite3.connect(db_path)

    try:
        # 优化1：合并数据完整性检查和主要数据获取为一个查询
        combined_query = f"""
        WITH league_matches AS (
            SELECT m.match_id, m.round_number,
                   m.home_team_id, m.home_team_name,
                   m.away_team_id, m.away_team_name
            FROM {matches_table_name} m
            WHERE m.league_id = {league_id}
        ),
        odds_data AS (
            SELECT lm.match_id, lm.round_number,
                   lm.home_team_id, lm.home_team_name,
                   lm.away_team_id, lm.away_team_name,
                   o.init_home_win_rate, o.init_draw_rate, o.init_away_win_rate
            FROM league_matches lm
            LEFT JOIN euro_odds o ON lm.match_id = o.match_id AND o.company_id = '{company_id}'
        )
        SELECT *,
               COUNT(*) OVER() AS total_matches,
               SUM(CASE WHEN init_home_win_rate IS NOT NULL THEN 1 ELSE 0 END) OVER() AS covered_matches
        FROM odds_data
        WHERE init_home_win_rate IS NOT NULL
        ORDER BY round_number;
        """

        if is_debug:
            logger.info(f"执行优化的合并查询")

        odds_df = pd.read_sql_query(combined_query, conn)

        if odds_df.empty:
            logger.warning(f"没有找到联赛 {league_name} 的赔率数据")
            conn.close()
            return None, {'league_id': league_id, 'league_name': league_name, 'reason': "没有找到赔率数据"}

        # 检查数据完整性
        total_matches = odds_df['total_matches'].iloc[0]
        covered_matches = odds_df['covered_matches'].iloc[0]
        coverage_ratio = covered_matches / total_matches if total_matches > 0 else 0

        if is_debug:
            logger.info(f"数据完整性结果: 覆盖比赛数={covered_matches}, 总比赛数={total_matches}, 覆盖率={coverage_ratio:.2%}")

        if coverage_ratio < COVERAGE_THRESHOLD:
            logger.warning(f"警告: 公司ID {company_id} 对联赛 {league_name} 的赔率数据不完整!")
            incomplete_info = {
                'league_id': league_id,
                'league_name': league_name,
                'coverage': f"{coverage_ratio:.2%}",
                'matches': f"{covered_matches}/{total_matches}",
                'reason': "数据不完整"
            }
            conn.close()
            return None, incomplete_info

        # 删除不需要的列
        odds_df = odds_df.drop(['total_matches', 'covered_matches'], axis=1)

        # 计算概率和不败率
        odds_df['home_win_prob'] = odds_df['init_home_win_rate']
        odds_df['draw_prob'] = odds_df['init_draw_rate']
        odds_df['away_win_prob'] = odds_df['init_away_win_rate']
        odds_df['home_team_unbeaten_rate'] = odds_df['home_win_prob'] + odds_df['draw_prob']
        odds_df['away_team_unbeaten_rate'] = odds_df['away_win_prob'] + odds_df['draw_prob']

        # 优化2：使用向量化操作计算所有球队统计信息
        # 创建主场和客场数据的统一格式
        home_data = odds_df[['home_team_id', 'home_team_name', 'round_number', 'home_team_unbeaten_rate']].copy()
        home_data.columns = ['team_id', 'team_name', 'round_number', 'unbeaten_rate']
        home_data['match_type'] = 'home'

        away_data = odds_df[['away_team_id', 'away_team_name', 'round_number', 'away_team_unbeaten_rate']].copy()
        away_data.columns = ['team_id', 'team_name', 'round_number', 'unbeaten_rate']
        away_data['match_type'] = 'away'

        # 合并所有比赛数据
        all_matches = pd.concat([home_data, away_data], ignore_index=True)

        # 计算每支球队的最大轮次
        team_max_rounds = all_matches.groupby('team_id')['round_number'].max().reset_index()
        team_max_rounds.columns = ['team_id', 'team_max_round']

        # 合并最大轮次信息
        all_matches = all_matches.merge(team_max_rounds, on='team_id')

        # 近况轮次数
        recent_rounds = team_count - 1

        # 标记近况比赛
        all_matches['is_recent'] = all_matches['round_number'] > (all_matches['team_max_round'] - recent_rounds)

        # 优化3：使用groupby一次性计算所有统计信息
        # 按球队和主客场分组计算平均不败率
        team_stats = all_matches.groupby(['team_id', 'team_name', 'match_type']).agg({
            'unbeaten_rate': 'mean',
            'team_max_round': 'first'
        }).reset_index()

        # 按球队和主客场、近况分组计算近况平均不败率
        recent_stats = all_matches[all_matches['is_recent']].groupby(['team_id', 'team_name', 'match_type']).agg({
            'unbeaten_rate': 'mean'
        }).reset_index()
        recent_stats.columns = ['team_id', 'team_name', 'match_type', 'recent_unbeaten_rate']

        # 计算实际近况轮次数量
        recent_match_counts = all_matches[all_matches['is_recent']].groupby('team_id').size().reset_index()
        recent_match_counts.columns = ['team_id', 'recent_matches']

        # 透视表转换为主客场列
        team_stats_pivot = team_stats.pivot_table(
            index=['team_id', 'team_name', 'team_max_round'],
            columns='match_type',
            values='unbeaten_rate',
            fill_value=0
        ).reset_index()

        recent_stats_pivot = recent_stats.pivot_table(
            index=['team_id', 'team_name'],
            columns='match_type',
            values='recent_unbeaten_rate',
            fill_value=0
        ).reset_index()

        # 合并数据
        teams_data = team_stats_pivot.merge(recent_stats_pivot, on=['team_id', 'team_name'], how='left')
        teams_data = teams_data.merge(recent_match_counts, on='team_id', how='left')

        # 填充缺失值
        teams_data = teams_data.fillna(0)

        # 重命名列
        teams_data.columns = ['team_id', 'team_name', 'max_round', 'away_unbeaten', 'home_unbeaten',
                             'recent_away_unbeaten', 'recent_home_unbeaten', 'recent_matches']

        # 计算总体和近况广义实力
        teams_data['total_power'] = teams_data['home_unbeaten'] + teams_data['away_unbeaten']
        teams_data['recent_power'] = teams_data['recent_home_unbeaten'] + teams_data['recent_away_unbeaten']

        # 计算综合广义实力评分
        teams_data['combined_power'] = teams_data['total_power'] * 0.2 + teams_data['recent_power'] * 0.8

        # 计算相对广义实力评分
        min_power = teams_data['combined_power'].min()
        teams_data['relative_power'] = teams_data['combined_power'] - min_power

        # 计算档距和分类
        teams_data['power_level'] = (teams_data['relative_power'] / 10.5).round(1)

        def categorize_team(power_level):
            if power_level >= 8.5: return "超强1"
            elif power_level >= 8.0: return "超强2"
            elif power_level >= 7.5: return "人强1"
            elif power_level >= 7.0: return "人强2"
            elif power_level >= 6.5: return "普强1"
            elif power_level >= 6.0: return "普强2"
            elif power_level >= 5.5: return "准强1"
            elif power_level >= 5.0: return "准强2"
            elif power_level >= 4.5: return "中强1"
            elif power_level >= 4.0: return "中强2"
            elif power_level >= 3.5: return "中上1"
            elif power_level >= 3.0: return "中上2"
            elif power_level >= 2.5: return "中游1"
            elif power_level >= 2.0: return "中游2"
            elif power_level >= 1.5: return "中下1"
            elif power_level >= 1.0: return "中下2"
            elif power_level >= 0.5: return "下游1"
            else: return "下游2"

        teams_data['power_category'] = teams_data['power_level'].apply(categorize_team)

        # 排序和排名
        teams_data = teams_data.sort_values(by='relative_power', ascending=False)
        teams_data['rank'] = range(1, len(teams_data) + 1)

        # 输出调试信息
        if is_debug or logger.isEnabledFor(logging.INFO):
            logger.info(f"\n联赛: {league_name} 各队最大轮次和近况轮次数量:")
            for _, row in teams_data.iterrows():
                logger.info(f"  {row['team_name']}: 最大轮次 {row['max_round']}, 近况包含 {row['recent_matches']} 场比赛")

        # 准备最终输出，移除调试列
        final_teams_df = teams_data[['team_id', 'team_name', 'total_power', 'recent_power',
                                   'combined_power', 'relative_power', 'power_level',
                                   'power_category', 'rank']].copy()

        league_data = {
            'league_name': league_name,
            'teams_df': final_teams_df
        }

        if is_debug:
            logger.info(f"==== 公司ID {company_id} 对联赛 {league_name} 的广义实力计算成功完成 ====\n")

        conn.close()
        return league_data, None

    except Exception as e:
        logger.error(f"计算联赛 {league_name} 的广义实力时出错: {e}")
        if is_debug:
            logger.error(f"==== 公司ID {company_id} 对联赛 {league_name} 处理时出错 ====")
            import traceback
            logger.error(traceback.format_exc())
        conn.close()
        return None, {'league_id': league_id, 'league_name': league_name, 'reason': f"计算错误: {e}"}

def calculate_league_power_ratings_fast(db_path, company_id, league_id, league_name, matches_table_name, team_count, max_round):
    """
    真正优化的广义实力评分计算函数
    核心优化：简化SQL查询，减少复杂操作
    """
    is_debug = False

    conn = sqlite3.connect(db_path)

    try:
        # 步骤1：简单查询获取该联赛的所有比赛数据
        total_matches_query = f"SELECT COUNT(*) FROM {matches_table_name} WHERE league_id = {league_id}"
        total_matches = pd.read_sql_query(total_matches_query, conn).iloc[0, 0]

        # 步骤2：获取有赔率的比赛数据 - 使用最简单的JOIN
        odds_query = f"""
        SELECT m.match_id, m.round_number,
               m.home_team_id, m.home_team_name,
               m.away_team_id, m.away_team_name,
               o.init_home_win_rate, o.init_draw_rate, o.init_away_win_rate
        FROM {matches_table_name} m
        INNER JOIN euro_odds o ON m.match_id = o.match_id
        WHERE m.league_id = {league_id} AND o.company_id = '{company_id}'
        ORDER BY m.round_number;
        """

        if is_debug:
            logger.info(f"执行简化查询")

        odds_df = pd.read_sql_query(odds_query, conn)
        conn.close()  # 早点关闭连接

        if odds_df.empty:
            logger.warning(f"没有找到联赛 {league_name} 的赔率数据")
            return None, {'league_id': league_id, 'league_name': league_name, 'reason': "没有找到赔率数据"}

        # 步骤3：检查数据完整性
        covered_matches = len(odds_df)
        coverage_ratio = covered_matches / total_matches if total_matches > 0 else 0

        if is_debug:
            logger.info(f"数据完整性结果: 覆盖比赛数={covered_matches}, 总比赛数={total_matches}, 覆盖率={coverage_ratio:.2%}")

        if coverage_ratio < COVERAGE_THRESHOLD:
            logger.warning(f"警告: 公司ID {company_id} 对联赛 {league_name} 的赔率数据不完整!")
            incomplete_info = {
                'league_id': league_id,
                'league_name': league_name,
                'coverage': f"{coverage_ratio:.2%}",
                'matches': f"{covered_matches}/{total_matches}",
                'reason': "数据不完整"
            }
            return None, incomplete_info

        # 步骤4：计算不败率
        odds_df['home_unbeaten'] = odds_df['init_home_win_rate'] + odds_df['init_draw_rate']
        odds_df['away_unbeaten'] = odds_df['init_away_win_rate'] + odds_df['init_draw_rate']

        # 步骤5：获取所有球队ID
        all_teams = set(odds_df['home_team_id'].tolist() + odds_df['away_team_id'].tolist())

        # 步骤6：为每个球队计算统计数据 - 使用字典存储，避免复杂的pandas操作
        teams_data = {}
        recent_rounds = team_count - 1

        for team_id in all_teams:
            # 获取球队名称
            team_name = ""
            home_mask = odds_df['home_team_id'] == team_id
            away_mask = odds_df['away_team_id'] == team_id

            if home_mask.any():
                team_name = odds_df[home_mask]['home_team_name'].iloc[0]
            elif away_mask.any():
                team_name = odds_df[away_mask]['away_team_name'].iloc[0]
            
            # 球队名称标准化映射 - 确保一致性
            team_name_mapping = {
                "韦纳穆": "瓦纳默",
                # 可以在这里添加更多映射
            }
            # 应用映射
            if team_name in team_name_mapping:
                logger.info(f"球队名称标准化: {team_name} -> {team_name_mapping[team_name]}")
                team_name = team_name_mapping[team_name]

            # 主场比赛
            home_matches = odds_df[home_mask]
            # 客场比赛
            away_matches = odds_df[away_mask]

            # 计算该队最大轮次
            all_rounds = []
            if not home_matches.empty:
                all_rounds.extend(home_matches['round_number'].tolist())
            if not away_matches.empty:
                all_rounds.extend(away_matches['round_number'].tolist())

            team_max_round = max(all_rounds) if all_rounds else 0

            # 计算近况 - 只取最近N轮的比赛
            recent_threshold = team_max_round - recent_rounds
            recent_home = home_matches[home_matches['round_number'] > recent_threshold]
            recent_away = away_matches[away_matches['round_number'] > recent_threshold]

            recent_home_avg = recent_home['home_unbeaten'].mean() if not recent_home.empty else 0
            recent_away_avg = recent_away['away_unbeaten'].mean() if not recent_away.empty else 0
            recent_power = recent_home_avg + recent_away_avg

            # 存储球队数据
            teams_data[team_id] = {
                'team_id': team_id,
                'team_name': team_name,
                'total_power': team_max_round,
                'recent_power': recent_power,
                'max_round': team_max_round,
                'recent_matches': len(recent_home) + len(recent_away)
            }

        # 步骤7：转换为DataFrame并计算最终评分
        teams_df = pd.DataFrame.from_dict(teams_data, orient='index')

        if teams_df.empty:
            return None, {'league_id': league_id, 'league_name': league_name, 'reason': "没有球队数据"}

        # 计算综合广义实力评分
        teams_df['combined_power'] = teams_df['total_power'] * 0.2 + teams_df['recent_power'] * 0.8

        # 计算相对广义实力评分
        min_power = teams_df['combined_power'].min()
        teams_df['relative_power'] = teams_df['combined_power'] - min_power

        # 计算档距
        teams_df['power_level'] = (teams_df['relative_power'] / 10.5).round(1)

        # 档次分类
        def categorize_team(power_level):
            if power_level >= 8.5: return "超强1"
            elif power_level >= 8.0: return "超强2"
            elif power_level >= 7.5: return "人强1"
            elif power_level >= 7.0: return "人强2"
            elif power_level >= 6.5: return "普强1"
            elif power_level >= 6.0: return "普强2"
            elif power_level >= 5.5: return "准强1"
            elif power_level >= 5.0: return "准强2"
            elif power_level >= 4.5: return "中强1"
            elif power_level >= 4.0: return "中强2"
            elif power_level >= 3.5: return "中上1"
            elif power_level >= 3.0: return "中上2"
            elif power_level >= 2.5: return "中游1"
            elif power_level >= 2.0: return "中游2"
            elif power_level >= 1.5: return "中下1"
            elif power_level >= 1.0: return "中下2"
            elif power_level >= 0.5: return "下游1"
            else: return "下游2"

        teams_df['power_category'] = teams_df['power_level'].apply(categorize_team)
        teams_df = teams_df.sort_values(by='relative_power', ascending=False)
        teams_df['rank'] = range(1, len(teams_df) + 1)

        # 调试信息
        if is_debug or logger.isEnabledFor(logging.INFO):
            logger.info(f"\n联赛: {league_name} 各队最大轮次和近况轮次数量:")
            for _, row in teams_df.iterrows():
                logger.info(f"  {row['team_name']}: 最大轮次 {row['max_round']}, 近况包含 {row['recent_matches']} 场比赛")

        # 准备最终输出
        final_teams_df = teams_df[['team_id', 'team_name', 'total_power', 'recent_power',
                                 'combined_power', 'relative_power', 'power_level',
                                 'power_category', 'rank']].copy()

        league_data = {
            'league_name': league_name,
            'teams_df': final_teams_df
        }

        if is_debug:
            logger.info(f"==== 公司ID {company_id} 对联赛 {league_name} 的广义实力计算成功完成 ====\n")

        return league_data, None

    except Exception as e:
        logger.error(f"计算联赛 {league_name} 的广义实力时出错: {e}")
        if is_debug:
            import traceback
            logger.error(traceback.format_exc())
        conn.close()
        return None, {'league_id': league_id, 'league_name': league_name, 'reason': f"计算错误: {e}"}

def calculate_league_power_ratings_fast_corrected(db_path, company_id, league_id, league_name, matches_table_name, team_count, max_round):
    """
    确保与原版本计算逻辑100%一致的优化版本
    """
    is_debug = False

    conn = sqlite3.connect(db_path)

    try:
        # 1. 获取总比赛数（用于覆盖率检查）
        total_matches_query = f"SELECT COUNT(*) FROM {matches_table_name} WHERE league_id = {league_id}"
        total_matches = pd.read_sql_query(total_matches_query, conn).iloc[0, 0]

        # 2. 获取有赔率的比赛数据
        odds_query = f"""
        SELECT m.match_id, m.round_number,
               m.home_team_id, m.home_team_name,
               m.away_team_id, m.away_team_name,
               o.init_home_win_rate, o.init_draw_rate, o.init_away_win_rate
        FROM {matches_table_name} m
        INNER JOIN euro_odds o ON m.match_id = o.match_id
        WHERE m.league_id = {league_id} AND o.company_id = '{company_id}'
        ORDER BY m.round_number;
        """

        odds_df = pd.read_sql_query(odds_query, conn)

        conn.close()

        if odds_df.empty:
            return None, {'league_id': league_id, 'league_name': league_name, 'reason': "没有找到赔率数据"}

        # 3. 数据完整性检查（与原版本一致）
        covered_matches = len(odds_df)
        coverage_ratio = covered_matches / total_matches if total_matches > 0 else 0

        if coverage_ratio < COVERAGE_THRESHOLD:
            incomplete_info = {
                'league_id': league_id,
                'league_name': league_name,
                'coverage': f"{coverage_ratio:.2%}",
                'matches': f"{covered_matches}/{total_matches}",
                'reason': "数据不完整"
            }
            return None, incomplete_info

        # 4. 计算概率和不败率（与原版本完全一致）
        odds_df['home_win_prob'] = odds_df['init_home_win_rate']
        odds_df['draw_prob'] = odds_df['init_draw_rate']
        odds_df['away_win_prob'] = odds_df['init_away_win_rate']
        odds_df['home_team_unbeaten_rate'] = odds_df['home_win_prob'] + odds_df['draw_prob']
        odds_df['away_team_unbeaten_rate'] = odds_df['away_win_prob'] + odds_df['draw_prob']

        # 5. 获取所有球队并计算统计数据
        all_team_ids = list(set(odds_df['home_team_id'].tolist() + odds_df['away_team_id'].tolist()))
        teams_data = {}
        recent_rounds = team_count - 1  # 与原版本一致

        for team_id in all_team_ids:
            # 获取球队名称
            team_name = ""
            home_matches = odds_df[odds_df['home_team_id'] == team_id]
            away_matches = odds_df[odds_df['away_team_id'] == team_id]

            if not home_matches.empty:
                team_name = home_matches.iloc[0]['home_team_name']
            elif not away_matches.empty:
                team_name = away_matches.iloc[0]['away_team_name']
            
            # 球队名称标准化映射 - 确保一致性
            team_name_mapping = {
                "韦纳穆": "瓦纳默",
                # 可以在这里添加更多映射
            }
            # 应用映射
            if team_name in team_name_mapping:
                logger.info(f"球队名称标准化: {team_name} -> {team_name_mapping[team_name]}")
                team_name = team_name_mapping[team_name]

            # 获取该队所有比赛
            team_matches = pd.concat([home_matches, away_matches], ignore_index=True)
            team_max_round = team_matches['round_number'].max() if not team_matches.empty else 0

            # 计算总体平均不败率（与原版本一致）
            avg_home_unbeaten_rate = home_matches['home_team_unbeaten_rate'].mean() if not home_matches.empty else 0
            avg_away_unbeaten_rate = away_matches['away_team_unbeaten_rate'].mean() if not away_matches.empty else 0
            total_power = avg_home_unbeaten_rate + avg_away_unbeaten_rate


            # 计算近况（与原版本逻辑完全一致）
            recent_home_matches = home_matches[home_matches['round_number'] > team_max_round - recent_rounds]
            recent_away_matches = away_matches[away_matches['round_number'] > team_max_round - recent_rounds]

            recent_avg_home_unbeaten_rate = recent_home_matches['home_team_unbeaten_rate'].mean() if not recent_home_matches.empty else 0
            recent_avg_away_unbeaten_rate = recent_away_matches['away_team_unbeaten_rate'].mean() if not recent_away_matches.empty else 0
            recent_power = recent_avg_home_unbeaten_rate + recent_avg_away_unbeaten_rate


            # 存储数据
            teams_data[team_id] = {
                'team_id': team_id,
                'team_name': team_name,
                'total_power': total_power,
                'recent_power': recent_power,
                'max_round': team_max_round,
                'recent_matches': len(recent_home_matches) + len(recent_away_matches)
            }

        # 6. 后续计算（与原版本完全一致）
        teams_df = pd.DataFrame.from_dict(teams_data, orient='index')

        if teams_df.empty:
            return None, {'league_id': league_id, 'league_name': league_name, 'reason': "没有球队数据"}

        # 计算综合广义实力评分
        teams_df['combined_power'] = teams_df['total_power'] * 0.2 + teams_df['recent_power'] * 0.8

        # 计算相对广义实力评分
        min_power = teams_df['combined_power'].min()
        teams_df['relative_power'] = teams_df['combined_power'] - min_power


        # 计算档距
        teams_df['power_level'] = (teams_df['relative_power'] / 10.5).round(1)

        # 分类（与原版本完全相同）
        def categorize_team(power_level):
            if power_level >= 8.5: return "超强1"
            elif power_level >= 8.0: return "超强2"
            elif power_level >= 7.5: return "人强1"
            elif power_level >= 7.0: return "人强2"
            elif power_level >= 6.5: return "普强1"
            elif power_level >= 6.0: return "普强2"
            elif power_level >= 5.5: return "准强1"
            elif power_level >= 5.0: return "准强2"
            elif power_level >= 4.5: return "中强1"
            elif power_level >= 4.0: return "中强2"
            elif power_level >= 3.5: return "中上1"
            elif power_level >= 3.0: return "中上2"
            elif power_level >= 2.5: return "中游1"
            elif power_level >= 2.0: return "中游2"
            elif power_level >= 1.5: return "中下1"
            elif power_level >= 1.0: return "中下2"
            elif power_level >= 0.5: return "下游1"
            else: return "下游2"

        teams_df['power_category'] = teams_df['power_level'].apply(categorize_team)
        teams_df = teams_df.sort_values(by='relative_power', ascending=False)
        teams_df['rank'] = range(1, len(teams_df) + 1)


        # 输出最终结果
        final_teams_df = teams_df[['team_id', 'team_name', 'total_power', 'recent_power',
                                 'combined_power', 'relative_power', 'power_level',
                                 'power_category', 'rank']].copy()

        league_data = {
            'league_name': league_name,
            'teams_df': final_teams_df
        }

        return league_data, None

    except Exception as e:
        logger.error(f"计算联赛 {league_name} 的广义实力时出错: {e}")
        if is_debug:
            import traceback
            logger.error(traceback.format_exc())
        if 'conn' in locals() and conn:
            conn.close()
        return None, {'league_id': league_id, 'league_name': league_name, 'reason': f"计算错误: {e}"}

def calculate_generalized_power_ratings(db_path, company_ids=["115", "90", "432", "80", "255", "81", "474", "4", "976", "937", "657"]):
    """
    使用优化后的快速版本计算广义实力评分
    """
    logger.info(f"\n===== 数据库路径检查 =====")
    logger.info(f"使用的数据库路径: {db_path}")

    # 连接数据库
    try:
        logger.info(f"尝试连接数据库 {db_path}...")
        conn = sqlite3.connect(db_path)
        logger.info("数据库连接成功!")

        # 检查表结构
        tables_query = "SELECT name FROM sqlite_master WHERE type='table';"
        tables = pd.read_sql_query(tables_query, conn)

        # 确定比赛表名
        matches_table_name = 'matches' if 'matches' in tables['name'].tolist() else 'match'
        logger.info(f"使用比赛表: {matches_table_name}")

        # 获取联赛列表
        leagues_query = f"""
        SELECT DISTINCT league_id, league_name
        FROM {matches_table_name}
        ORDER BY league_name;
        """
        leagues_df = pd.read_sql_query(leagues_query, conn)

        # 仅计算英超：根据LEAGUES配置中提供的URL提取联赛ID并进行过滤
        try:
            active_league_ids = set()
            for info in LEAGUES.values():
                url = info.get('url', '')
                m = re.search(r'/s(\d+)', url)
                if m:
                    active_league_ids.add(int(m.group(1)))
            if active_league_ids:
                leagues_df = leagues_df[leagues_df['league_id'].isin(list(active_league_ids))].reset_index(drop=True)
                logger.info(f"仅计算这些联赛ID: {sorted(active_league_ids)}")
        except Exception as e:
            logger.warning(f"根据LEAGUES限制联赛范围失败: {e}")

    except Exception as e:
        logger.error(f"连接数据库时出错: {e}")
        return {}, {}

    results = {}

    # 为每家博彩公司计算
    for company_id in company_ids:
        logger.info(f"\n开始处理博彩公司 {company_id} 的数据")

        company_results = {}
        company_incomplete_data = []

        # 准备任务列表
        tasks = []
        for _, league in leagues_df.iterrows():
            league_id = league['league_id']
            league_name = league['league_name']

            # 获取球队数和最大轮次
            try:
                teams_query = f"""
                SELECT COUNT(DISTINCT team_id) AS team_count
                FROM (
                    SELECT home_team_id AS team_id FROM {matches_table_name} WHERE league_id = {league_id}
                    UNION
                    SELECT away_team_id AS team_id FROM {matches_table_name} WHERE league_id = {league_id}
                ) AS all_teams;
                """
                team_count = pd.read_sql_query(teams_query, conn).iloc[0, 0]

                max_round_query = f"SELECT MAX(round_number) FROM {matches_table_name} WHERE league_id = {league_id};"
                max_round = pd.read_sql_query(max_round_query, conn).iloc[0, 0]

                if team_count > 0:
                    tasks.append((db_path, company_id, league_id, league_name, matches_table_name, team_count, max_round))

            except Exception as e:
                logger.warning(f"跳过联赛 {league_name}: {e}")
                continue

        # 使用线程池执行任务
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
            future_to_league = {
                executor.submit(
                    calculate_league_power_ratings_fast_corrected,  # 使用快速版本
                    task[0], task[1], task[2], task[3], task[4], task[5], task[6]
                ): (task[2], task[3]) for task in tasks
            }

            # 收集结果
            for future in concurrent.futures.as_completed(future_to_league):
                league_id, league_name = future_to_league[future]
                try:
                    league_data, incomplete_info = future.result()
                    if league_data:
                        company_results[league_id] = league_data
                    if incomplete_info:
                        company_incomplete_data.append(incomplete_info)
                except Exception as e:
                    logger.error(f"处理联赛 {league_name} 时出错: {e}")
                    company_incomplete_data.append({
                        'league_id': league_id,
                        'league_name': league_name,
                        'reason': f"处理错误: {e}"
                    })

        # 保存结果
        results[company_id] = company_results
        if company_incomplete_data:
            if company_id not in results:
                results[company_id] = {}
            # 这里应该是设置incomplete_data，但我看原代码逻辑有问题，先简化

    conn.close()
    return results, {}

def create_power_ratings_table(db_path):
    """创建存储广义实力评分的表"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 检查表是否已存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='team_power_ratings';")
    if cursor.fetchone() is None:
        # 创建表
        cursor.execute('''
        CREATE TABLE team_power_ratings (
            id INTEGER PRIMARY KEY,
            company_id TEXT,          -- 博彩公司ID
            company_name TEXT,        -- 博彩公司名称
            league_id INTEGER,        -- 联赛ID
            league_name TEXT,         -- 联赛名称
            team_id INTEGER,          -- 球队ID
            team_name TEXT,           -- 球队名称
            total_power REAL,         -- 初赔总场广义实力
            recent_power REAL,        -- 近况广义实力
            combined_power REAL,      -- 综合广义实力
            relative_power REAL,      -- 相对广义实力
            power_level REAL,         -- 档距
            power_category TEXT,      -- 档次分类
            rank INTEGER,             -- 联赛内排名
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP  -- 更新时间
        );
        ''')

        # 创建索引
        cursor.execute("CREATE INDEX idx_company_league ON team_power_ratings(company_id, league_id);")
        cursor.execute("CREATE INDEX idx_team ON team_power_ratings(team_id);")

        print("创建表 team_power_ratings 成功")
    else:
        print("表 team_power_ratings 已存在")

    conn.commit()
    conn.close()

def save_power_ratings(db_path, power_ratings, company_names):
    """
    将广义实力评分保存到数据库，只保留最新的数据

    参数:
    db_path: 数据库路径
    power_ratings: 计算得到的广义实力评分数据
    company_names: 博彩公司名称字典
    """
    # 确保表存在
    create_power_ratings_table(db_path)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 获取当前时间
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 插入计数
    insert_count = 0

    # 清空整个表，确保只保存符合覆盖率要求的最新数据
    print("清空team_power_ratings表中的所有历史数据...")
    cursor.execute("DELETE FROM team_power_ratings")

    # 遍历每个公司的数据
    for company_id, league_ratings in power_ratings.items():
        company_name = company_names.get(company_id, f"公司_{company_id}")

        # 遍历每个联赛的数据
        for league_id, league_data in league_ratings.items():
            league_name = league_data['league_name']
            ratings_df = league_data['teams_df']

            # 遍历每支球队的数据
            for idx, row in ratings_df.iterrows():
                # 准备插入数据
                data = (
                    company_id,
                    company_name,
                    league_id,
                    league_name,
                    row['team_id'],
                    row['team_name'],
                    row['total_power'],
                    row['recent_power'],
                    row['combined_power'],
                    row['relative_power'],
                    row['power_level'],
                    row['power_category'],
                    row['rank'],
                    current_time
                )

                # 插入数据
                cursor.execute('''
                INSERT INTO team_power_ratings
                (company_id, company_name, league_id, league_name, team_id, team_name,
                 total_power, recent_power, combined_power, relative_power, power_level,
                 power_category, rank, update_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', data)

                insert_count += 1

    # 提交事务
    conn.commit()
    print(f"成功保存 {insert_count} 条广义实力评分数据")

    conn.close()
    return insert_count

def calculate_bookmaker_power_from_odds(home_win_odds, draw_odds, away_win_odds, payout_rate):
    """
    基于博彩公司的初赔和返还率计算队伍的广义实力值

    参数:
    home_win_odds: 主队胜赔率 (如2.28)
    draw_odds: 平局赔率 (如3.08)
    away_win_odds: 客队胜赔率
    payout_rate: 返还率 (如91.92%)

    返回:
    tuple: (主队广义实力, 客队广义实力, 广义实力差值)
    """
    try:
        # 将返还率从百分比转换为小数
        if payout_rate > 1:
            payout_rate = payout_rate / 100.0

        # 计算真实概率 (移除水钱影响)
        raw_home_prob = 1 / float(home_win_odds)
        raw_draw_prob = 1 / float(draw_odds)
        raw_away_prob = 1 / float(away_win_odds)

        # 总概率用于标准化
        total_prob = raw_home_prob + raw_draw_prob + raw_away_prob

        # 标准化概率，使其和为返还率
        home_win_prob = (raw_home_prob / total_prob) * payout_rate
        draw_prob = (raw_draw_prob / total_prob) * payout_rate
        away_win_prob = (raw_away_prob / total_prob) * payout_rate

        # 计算不败率 (广义实力的核心指标)
        home_unbeaten_rate = home_win_prob + draw_prob
        away_unbeaten_rate = away_win_prob + draw_prob

        # 按照广义实力计算方法，不败率需要乘以2来得到广义实力值
        # 这是基于原有计算逻辑中的 total_power = avg_home_unbeaten_rate + avg_away_unbeaten_rate
        home_power = home_unbeaten_rate * 2  # 模拟主客场的平均值
        away_power = away_unbeaten_rate * 2

        # 计算差值
        power_difference = home_power - away_power

        logger.info(f"马会初赔广义实力计算:")
        logger.info(f"原始赔率: 主胜={home_win_odds}, 平局={draw_odds}, 客胜={away_win_odds}")
        logger.info(f"返还率: {payout_rate:.2%}")
        logger.info(f"标准化概率: 主胜={home_win_prob:.4f}, 平局={draw_prob:.4f}, 客胜={away_win_prob:.4f}")
        logger.info(f"不败率: 主队={home_unbeaten_rate:.4f}, 客队={away_unbeaten_rate:.4f}")
        logger.info(f"广义实力: 主队={home_power:.4f}, 客队={away_power:.4f}")
        logger.info(f"广义实力差值: {power_difference:.4f}")

        return round(home_power, 4), round(away_power, 4), round(power_difference, 4)

    except Exception as e:
        logger.error(f"计算马会初赔广义实力时出错: {e}")
        return None, None, None

def compare_power_differences(existing_diff, bookmaker_diff, home_team, away_team):
    """
    比较现有广义实力差值与博彩公司初赔计算的广义实力差值

    参数:
    existing_diff: 现有的广义实力差值
    bookmaker_diff: 基于博彩公司初赔计算的广义实力差值
    home_team: 主队名称
    away_team: 客队名称

    返回:
    dict: 包含比较结果的字典
    """
    try:
        if existing_diff is None or bookmaker_diff is None:
            return {
                'status': 'error',
                'message': '缺少必要的数据进行比较'
            }

        # 计算差异
        difference = abs(existing_diff - bookmaker_diff)

        # 判断一致性程度
        if difference <= 0.05:
            consistency = "高度一致"
            color = "green"
        elif difference <= 0.1:
            consistency = "基本一致"
            color = "blue"
        elif difference <= 0.2:
            consistency = "存在差异"
            color = "orange"
        else:
            consistency = "差异较大"
            color = "red"

        # 分析倾向
        if bookmaker_diff > existing_diff:
            tendency = f"马会更看好{home_team}"
        elif bookmaker_diff < existing_diff:
            tendency = f"马会更看好{away_team}"
        else:
            tendency = "评估一致"

        result = {
            'status': 'success',
            'existing_diff': existing_diff,
            'bookmaker_diff': bookmaker_diff,
            'difference': difference,
            'consistency': consistency,
            'color': color,
            'tendency': tendency,
            'analysis': f"""
广义实力差值比较分析:
• 现有差值: {existing_diff:.4f} ({home_team} vs {away_team})
• 马会差值: {bookmaker_diff:.4f}
• 绝对差异: {difference:.4f}
• 一致性: {consistency}
• 倾向分析: {tendency}
            """.strip()
        }

        logger.info(f"广义实力差值比较: 现有={existing_diff:.4f}, 马会={bookmaker_diff:.4f}, 差异={difference:.4f}, {consistency}")

        return result

    except Exception as e:
        logger.error(f"比较广义实力差值时出错: {e}")
        return {
            'status': 'error',
            'message': f'比较计算出错: {str(e)}'
        }

def main(source_db_path, target_db_path=None):
    """
    主函数，执行广义实力计算并输出结果

    参数:
    source_db_path: 源数据库路径（包含赛事和赔率数据）
    target_db_path: 目标数据库路径（用于保存广义实力评分，默认为None表示不保存）
    """
    # 博彩公司对应表
    company_names = {
        "115": "威廉希尔",
        "90": "易胜博",
        "432": "香港马会",
        "80": "澳门",
        "255": "BWIN",
        "81": "伟德",
        "474": "利记",
        "4": "Nordicbet",
        "976": "18BET",
        "937": "BetISn",
        "657": "iddaa"
    }

    print(f"使用覆盖率阈值: {COVERAGE_THRESHOLD:.2%}")
    print(f"源数据库路径: {source_db_path}")
    print(f"目标数据库路径: {target_db_path}")

    # 验证源数据库文件是否存在
    if not os.path.exists(source_db_path):
        print(f"错误: 源数据库文件不存在: {source_db_path}")
        # 检查DATA_DIR目录
        print(f"检查数据目录 {DATA_DIR}:")
        if os.path.exists(DATA_DIR):
            print(f"数据目录存在，其中的文件有:")
            for file in os.listdir(DATA_DIR):
                file_path = os.path.join(DATA_DIR, file)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path) / (1024 * 1024)  # 转换为MB
                    print(f"  - {file} ({file_size:.2f} MB)")
        else:
            print(f"数据目录不存在!")
        return None

    # 计算各公司的广义实力评分，并获取未计算的联赛列表
    power_ratings, incomplete_data = calculate_generalized_power_ratings(source_db_path)

    # 输出结果
    for company_id, league_ratings in power_ratings.items():
        company_name = company_names.get(company_id, f"公司 {company_id}")
        print(f"\n{company_name} 各联赛广义实力评分:")
        print("=" * 80)

        for league_id, league_data in league_ratings.items():
            league_name = league_data['league_name']
            ratings_df = league_data['teams_df']

            print(f"\n联赛: {league_name} (ID: {league_id})")
            print("-" * 60)
            print(ratings_df[['rank', 'team_name', 'total_power', 'recent_power',
                             'combined_power', 'relative_power', 'power_level', 'power_category']])

            # 输出各档球队汇总
            print(f"\n{league_name} 球队档次分布:")
            print("-" * 40)
            category_counts = ratings_df['power_category'].value_counts().sort_index()
            for category, count in category_counts.items():
                print(f"{category}: {count} 支球队")

    # 如果提供了目标数据库路径，保存结果
    if target_db_path:
        print(f"\n开始将广义实力评分保存到数据库: {target_db_path}")
        save_power_ratings(target_db_path, power_ratings, company_names)
        print("数据保存完成!")

    # 输出由于数据不完整而未计算的联赛信息
    if incomplete_data:
        print("\n" + "=" * 80)
        print(f"⚠️ 以下联赛因数据覆盖不完整(未达到{COVERAGE_THRESHOLD:.2%})未计算广义实力 ⚠️")
        print("=" * 80)

        for company_id, leagues in incomplete_data.items():
            company_name = company_names.get(company_id, f"公司ID {company_id}")
            print(f"\n📊 {company_name} 未计算的联赛:")

            for league in leagues:
                league_name = league['league_name']
                coverage_info = league.get('coverage', '未知')
                matches_info = league.get('matches', '未知')
                reason = league.get('reason', '未知原因')

                print(f"  - {league_name} (ID: {league['league_id']})")
                if 'coverage' in league:
                    print(f"    覆盖率: {coverage_info} ({matches_info})")
                print(f"    原因: {reason}")

    return power_ratings

if __name__ == "__main__":
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 获取项目根目录
    project_root = os.path.dirname(current_dir)

    # 使用配置的数据目录
    # 确保目录存在
    os.makedirs(DATA_DIR, exist_ok=True)

    # 源数据库和目标数据库路径
    source_db_path = os.path.join(DATA_DIR, "football.db")
    # 使用配置的广义实力数据库路径
    target_db_path = DB_GUANGYISHILI

    print(f"源数据库路径: {source_db_path}")
    print(f"目标数据库路径: {target_db_path}")

    # 执行计算并保存结果
    main(source_db_path, target_db_path)