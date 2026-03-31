#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
缓存失效工具
当数据更新时，自动清除相关缓存
"""

from __future__ import annotations

import logging
from typing import Optional, List
from utils.cache import cache_delete, cache_clear

logger = logging.getLogger(__name__)


def invalidate_match_cache(match_id: Optional[int] = None, league_id: Optional[int] = None):
    """
    清除比赛相关缓存
    
    [修复] 使用前缀匹配清除所有变体的缓存 key
    
    Args:
        match_id: 比赛ID，如果提供则只清除该比赛的缓存
        league_id: 联赛ID，如果提供则清除该联赛的所有比赛缓存
    """
    cleared_count = 0
    
    if match_id:
        # 清除特定比赛的所有缓存变体
        # 注意：API接口使用 get_cache_key() 生成带hash的key
        # 需要清除所有包含该 match_id 的缓存
        
        # 旧格式兼容
        cache_delete(f'match_detail:{match_id}')
        cache_delete(f'match_detail_v2:{match_id}')
        
        # 清除优化版接口的缓存（使用前缀匹配）
        # get_cache_key('match_detail_v2', match_id=match_id, ...) 生成的 key
        cleared_count += cache_clear(f'match_detail_v2:')
        
        # 清除摘要缓存
        cache_delete(f'match_summary:{match_id}')
        cleared_count += cache_clear(f'match_summary:')
        
        logger.debug(f"清除比赛缓存: match_id={match_id}, cleared={cleared_count}")
    
    if league_id:
        # 清除该联赛的比赛列表缓存
        cache_clear(f'matches_today:league_{league_id}')
        logger.debug(f"清除联赛缓存: league_id={league_id}")
    
    # 清除所有比赛列表缓存（因为可能包含更新的比赛）
    cache_clear('matches_today')
    cache_clear('matches_today_filtered')
    logger.info(f"清除比赛列表缓存: match_id={match_id}, league_id={league_id}")


def invalidate_odds_cache(match_id: int):
    """
    清除赔率相关缓存
    
    [修复] 确保清除所有相关的缓存 key 变体
    
    Args:
        match_id: 比赛ID
    """
    # 清除赔率相关缓存
    cache_delete(f'odds:{match_id}')
    cache_delete(f'odds_analysis:{match_id}')
    
    # 清除比赛详情缓存（所有变体）
    invalidate_match_cache(match_id)
    
    # 清除列表缓存（has_odds_analysis等字段会变化）
    invalidate_all_matches_cache()
    
    logger.info(f"清除赔率缓存: match_id={match_id}")


def invalidate_analysis_cache(match_id: int):
    """
    清除分析结果缓存
    
    [修复] 确保清除所有相关的缓存 key 变体
    当分析结果更新（约3分钟一次）时，前端能立即获取最新数据
    
    Args:
        match_id: 比赛ID
    """
    # 清除分析相关缓存
    cache_delete(f'analysis:{match_id}')
    cache_delete(f'odds_analysis:{match_id}')
    
    # 清除比赛详情缓存（所有变体，包括 match_detail_v2:* 和 match_summary:*）
    invalidate_match_cache(match_id)
    
    # 清除列表缓存（has_fundamental等字段会变化）
    invalidate_all_matches_cache()
    
    logger.info(f"清除分析缓存: match_id={match_id}")


def invalidate_all_matches_cache():
    """
    清除所有比赛列表缓存
    
    [修复] 清除所有列表缓存变体，包括带状态参数的缓存
    """
    # 清除所有以 matches_today 开头的缓存（包括动态生成的key）
    cleared = cache_clear('matches_today')
    cleared += cache_clear('matches_today_filtered')
    
    # 清除带状态参数的缓存
    cleared += cache_clear('matches_today:')
    
    logger.info(f"清除所有比赛列表缓存 (cleared={cleared})")


# 装饰器：自动清除缓存
def auto_invalidate_cache(match_id_param: str = 'match_id', invalidate_type: str = 'match'):
    """
    自动清除缓存的装饰器
    
    Args:
        match_id_param: 函数参数中match_id的参数名
        invalidate_type: 失效类型 ('match', 'odds', 'analysis')
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            # 执行函数
            result = func(*args, **kwargs)
            
            # 获取match_id
            match_id = None
            if match_id_param in kwargs:
                match_id = kwargs[match_id_param]
            elif args:
                # 尝试从args获取（需要知道参数位置）
                import inspect
                sig = inspect.signature(func)
                params = list(sig.parameters.keys())
                if match_id_param in params:
                    idx = params.index(match_id_param)
                    if idx < len(args):
                        match_id = args[idx]
            
            # 清除缓存
            if match_id:
                if invalidate_type == 'odds':
                    invalidate_odds_cache(match_id)
                elif invalidate_type == 'analysis':
                    invalidate_analysis_cache(match_id)
                else:
                    invalidate_match_cache(match_id)
            
            return result
        return wrapper
    return decorator






