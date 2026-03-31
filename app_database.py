#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
应用数据库操作模块
从app.py中提取的数据库查询和操作函数，提高代码组织性
"""
from typing import List, Dict, Any, Optional, Tuple
from database.connection import get_connection as get_database_connection
from core.logger import get_logger

logger = get_logger(__name__)


def execute_query(sql: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
    """
    执行查询并返回结果 - [性能优化] 使用连接池
    
    Args:
        sql: SQL查询语句
        params: 查询参数
        
    Returns:
        List[Dict[str, Any]]: 查询结果列表
        
    Note:
        [性能优化] 时区和超时设置已移至连接池初始化 (database/pool.py)，
        避免每次查询都执行额外的 SET 语句。
    """
    # 性能监控：记录数据库查询时间
    db_start = None
    try:
        from flask import g
        if hasattr(g, 'performance_monitor'):
            import time
            db_start = time.time()
    except Exception:
        db_start = None
    
    try:
        db = get_database_connection()
        # [架构收敛] 统一通过 database.connection 访问数据库，保持调用方签名不变
        results = db.execute_query(
            sql,
            params if params is not None else (),
            fetch='all',
        ) or []
        
        # 性能监控：记录数据库查询时间
        if db_start is not None:
            try:
                from flask import g
                if hasattr(g, 'performance_monitor'):
                    import time
                    db_time = time.time() - db_start
                    if 't_db' in g.performance_monitor.timings:
                        g.performance_monitor.timings['t_db'] += db_time
                    else:
                        g.performance_monitor.timings['t_db'] = db_time
            except Exception:
                pass
        
        return results
    except Exception as exc:
        logger.error("执行查询失败: %s", exc, exc_info=True)
        raise


def execute_update(sql: str, params: Optional[tuple] = None) -> None:
    """
    执行更新操作 - [性能优化] 使用连接池
    
    Args:
        sql: SQL更新语句
        params: 更新参数
        
    Note:
        [性能优化] 时区设置已移至连接池初始化 (database/pool.py)
    """
    db = get_database_connection()
    db.execute_query(sql, params if params is not None else ())


def get_matches_to_monitor() -> List[Dict[str, Any]]:
    """
    获取需要监控的比赛（根据配置筛选联赛和时间范围）
    
    Returns:
        List[Dict[str, Any]]: 需要监控的比赛列表
    """
    try:
        # 导入监控配置
        from config.monitoring_config import (
            MONITORED_LEAGUES, MONITORING_DAYS, 
            MAX_MATCHES_TO_MONITOR, MONITOR_ALL_LEAGUES
        )
        
        from datetime import timedelta
        from utils.timezone_utils import now as get_now
        
        now = get_now()
        # [关键修复] 只监控未开始和进行中的比赛，不再包含已结束的比赛
        # 已结束的比赛由 _sync_final_odds 专门处理，不需要在常规监控中重复抓取
        # 原逻辑：包括过去24小时内完成的比赛 → 导致已结束比赛仍被抓取和分析
        start_time = now - timedelta(hours=2)  # 只看过去2小时（处理可能的时间误差）
        # 根据配置的天数计算结束时间
        end_date = now.replace(hour=23, minute=59, second=59, microsecond=999999) + timedelta(days=MONITORING_DAYS)
        
        # 构建SQL查询
        if MONITOR_ALL_LEAGUES or not MONITORED_LEAGUES:
            # 监控所有联赛
            sql = """
            SELECT DISTINCT m.match_id, m.match_time, m.updated_at as match_updated_at, m.match_status, 
                   m.home_team_name, m.away_team_name, m.league_id,
                   l.name_cn as league_name,
                   CASE WHEN oar_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_analysis,
                   CASE WHEN oc_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_changes,
                   CASE WHEN fa_exists.match_id IS NULL THEN 0 ELSE 1 END as has_fundamental
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_analysis_results) oar_exists
                ON oar_exists.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_changes) oc_exists
                ON oc_exists.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM fundamental_analysis) fa_exists
                ON fa_exists.match_id = m.match_id
            WHERE m.match_time >= %s 
              AND m.match_time < %s
              AND m.match_status IN ('scheduled', 'live')
            ORDER BY m.match_time
            LIMIT %s
            """
            params = (start_time, end_date, MAX_MATCHES_TO_MONITOR)
        else:
            # 只监控指定的联赛
            league_placeholders = ','.join(['%s'] * len(MONITORED_LEAGUES))
            sql = f"""
            SELECT DISTINCT m.match_id, m.match_time, m.updated_at as match_updated_at, m.match_status, 
                   m.home_team_name, m.away_team_name, m.league_id,
                   l.name_cn as league_name,
                   CASE WHEN oar_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_analysis,
                   CASE WHEN oc_exists.match_id IS NULL THEN 0 ELSE 1 END as has_odds_changes,
                   CASE WHEN fa_exists.match_id IS NULL THEN 0 ELSE 1 END as has_fundamental
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_analysis_results) oar_exists
                ON oar_exists.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM odds_changes) oc_exists
                ON oc_exists.match_id = m.match_id
            LEFT JOIN (SELECT DISTINCT match_id FROM fundamental_analysis) fa_exists
                ON fa_exists.match_id = m.match_id
            WHERE m.match_time >= %s 
              AND m.match_time < %s
              AND m.league_id IN ({league_placeholders})
              AND m.match_status IN ('scheduled', 'live')
            ORDER BY m.match_time
            LIMIT %s
            """
            params = (start_time, end_date) + tuple(MONITORED_LEAGUES) + (MAX_MATCHES_TO_MONITOR,)
        
        matches = execute_query(sql, params)

        # 关键：同场比赛去重（源站match_id变更会导致同场两条记录，旧记录通常无赔率/无分析）
        if matches:
            def _k(r: Dict[str, Any]):
                return (r.get('league_id'), r.get('match_time'), r.get('home_team_name'), r.get('away_team_name'))

            def _score(r: Dict[str, Any]):
                return (
                    int(r.get('has_odds_analysis') or 0),
                    int(r.get('has_odds_changes') or 0),
                    int(r.get('has_fundamental') or 0),
                    r.get('match_updated_at'),
                    int(r.get('match_id') or 0),
                )

            best = {}
            for r in matches:
                kk = _k(r)
                if kk not in best or _score(r) > _score(best[kk]):
                    best[kk] = r
            matches = list(best.values())
            matches.sort(key=lambda x: x.get('match_time'))
        
        # 打印监控信息
        if matches:
            logger.info(f"找到 {len(matches)} 场需要监控的比赛（未来{MONITORING_DAYS}天）")
            # 统计各联赛的比赛数
            league_counts = {}
            for match in matches:
                league_name = match.get('league_name', f"League_{match['league_id']}")
                league_counts[league_name] = league_counts.get(league_name, 0) + 1
            
            logger.info("各联赛比赛分布：")
            for league, count in sorted(league_counts.items(), key=lambda x: x[1], reverse=True):
                logger.info(f"  {league}: {count} 场")
        else:
            logger.warning(f"未找到需要监控的比赛（检查了未来{MONITORING_DAYS}天）")
        
        return matches
    except Exception as e:
        logger.error(f"获取监控比赛列表失败: {e}")
        return []


def get_round_completion_status(league_id: int, round_number: int) -> Dict[str, int]:
    """
    获取轮次完成状态（同时检查比赛完成状态和赔率数据完整性）
    
    Args:
        league_id: 联赛ID
        round_number: 轮次号
        
    Returns:
        Dict[str, int]: 包含总数、已完成数和剩余数的字典
    """
    sql = """
    SELECT 
        COUNT(*) as total,
        SUM(CASE 
            WHEN match_status = 'finished' AND EXISTS (
                SELECT 1 FROM european_odds eo 
                WHERE eo.match_id = matches.match_id
            ) THEN 1 
            ELSE 0 
        END) as finished_with_odds,
        SUM(CASE WHEN match_status = 'finished' THEN 1 ELSE 0 END) as finished_total
    FROM matches
    WHERE league_id = %s AND round_number = %s
    """
    
    result = execute_query(sql, (league_id, round_number))
    if result:
        return {
            'total': result[0]['total'],
            'finished': result[0]['finished_with_odds'],  # 使用有赔率数据的已完成比赛数
            'finished_total': result[0]['finished_total'],  # 仅完成但可能没有赔率数据
            'remaining': result[0]['total'] - result[0]['finished_with_odds']
        }
    return {'total': 0, 'finished': 0, 'finished_total': 0, 'remaining': 0}


def is_round_complete(league_id: int, round_number: int) -> bool:
    """
    检查某联赛某轮是否全部完成
    
    Args:
        league_id: 联赛ID
        round_number: 轮次号
        
    Returns:
        bool: 是否全部完成
    """
    status = get_round_completion_status(league_id, round_number)
    return status['total'] > 0 and status['total'] == status['finished']


def get_recent_finished_rounds() -> List[Dict[str, Any]]:
    """
    获取最近完成的轮次（检查最近24小时内完成的比赛）
    
    Returns:
        List[Dict[str, Any]]: 新完成的轮次列表
    """
    sql = """
    SELECT DISTINCT 
        m.league_id, 
        m.round_number,
        l.name_cn as league_name,
        COUNT(DISTINCT m.match_id) as match_count
    FROM matches m
    JOIN leagues l ON l.league_id = m.league_id
    WHERE m.match_status = 'finished'
      AND m.updated_at >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
      AND NOT EXISTS (
          SELECT 1 FROM team_power_ratings_history h
          WHERE h.league_id = m.league_id 
            AND h.round_number = m.round_number
            AND h.season = m.season
      )
    GROUP BY m.league_id, m.round_number, l.name_cn
    """
    
    return execute_query(sql)


def get_matches_for_analysis(limit: int = 50) -> List[Dict[str, Any]]:
    """
    获取需要分析的比赛（未来10天内没有基本面分析的比赛）
    
    Args:
        limit: 最大返回数量
        
    Returns:
        List[Dict[str, Any]]: 需要分析的比赛列表
    """
    sql = """
    SELECT DISTINCT m.match_id
    FROM matches m
    WHERE m.match_time >= NOW() 
      AND m.match_time < DATE_ADD(NOW(), INTERVAL 10 DAY)
      AND m.match_status = 'scheduled'
      AND NOT EXISTS (
          SELECT 1 FROM fundamental_analysis fa
          WHERE fa.match_id = m.match_id
      )
    LIMIT %s
    """
    
    return execute_query(sql, (limit,))


def get_odds_changes_for_analysis() -> List[Dict[str, Any]]:
    """
    查询最近有变化的赔率（检查最近10分钟的变化）
    
    Returns:
        List[Dict[str, Any]]: 有赔率变化的比赛列表
    """
    sql = """
    SELECT DISTINCT 
        oc.match_id,
        m.home_team_name,
        m.away_team_name,
        m.league_id,
        COUNT(DISTINCT oc.company_id) as changed_companies,
        MAX(oc.last_updated) as latest_change_time,
        -- 检查是否有最近的分析结果
        COALESCE(MAX(oar.analyzed_at), '1900-01-01') as latest_analysis_time
    FROM odds_changes oc
    JOIN matches m ON m.match_id = oc.match_id
    LEFT JOIN odds_analysis_results oar ON oar.match_id = oc.match_id
    WHERE oc.last_updated >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
      AND m.match_status IN ('scheduled', 'live')
    GROUP BY oc.match_id, m.home_team_name, m.away_team_name, m.league_id
    -- 只分析那些赔率变化晚于最后一次分析的比赛
    HAVING MAX(oc.last_updated) > COALESCE(MAX(oar.analyzed_at), '1900-01-01')
    """
    
    return execute_query(sql)
