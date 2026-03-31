#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
应用辅助函数模块
从app.py中提取的辅助函数，提高代码可读性和复用性
"""
from typing import Optional, Union, Dict, Any
from app_constants import SPECIAL_TEAM_NAMES, COMPANY_NAME_MAPPING, RULE_VALUE_THRESHOLDS


def get_team_logo(team_name: Optional[str]) -> str:
    """
    生成队徽缩写
    
    Args:
        team_name: 队伍名称
        
    Returns:
        str: 队徽缩写
    """
    if not team_name:
        return 'FC'
    
    # 检查特殊队名映射
    if team_name in SPECIAL_TEAM_NAMES:
        return SPECIAL_TEAM_NAMES[team_name]
    
    # 默认取前两个字符并转为大写
    return team_name[:2].upper()


def get_company_name_cn(company_id: Union[str, int], company_name: Optional[str] = None) -> str:
    """
    获取公司中文名称
    
    Args:
        company_id: 公司ID
        company_name: 公司英文名称（可选）
        
    Returns:
        str: 公司中文名称
    """
    return COMPANY_NAME_MAPPING.get(str(company_id), company_name or '未知公司')


def calculate_strength_diff(home_strength: Optional[Union[str, float]], 
                          away_strength: Optional[Union[str, float]]) -> float:
    """
    计算广义实力差值
    
    Args:
        home_strength: 主队实力值
        away_strength: 客队实力值
        
    Returns:
        float: 实力差值（保留1位小数）
    """
    try:
        home = float(home_strength) if home_strength is not None else 0
        away = float(away_strength) if away_strength is not None else 0
        return round(home - away, 1)
    except (ValueError, TypeError):
        return 0.0


def get_rule_class(value: Optional[Union[str, float]]) -> str:
    """
    获取规则值对应的CSS类名
    
    Args:
        value: 规则值
        
    Returns:
        str: CSS类名
    """
    try:
        num_value = float(value) if value is not None else 0
        
        if num_value >= RULE_VALUE_THRESHOLDS['RED']:
            return 'rule-red'
        elif num_value >= RULE_VALUE_THRESHOLDS['ORANGE']:
            return 'rule-orange'
        elif num_value >= RULE_VALUE_THRESHOLDS['YELLOW']:
            return 'rule-yellow'
        elif num_value >= RULE_VALUE_THRESHOLDS['GREEN']:
            return 'rule-green'
        else:
            return ''
    except (ValueError, TypeError):
        return ''


def safe_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    """
    安全地转换值为浮点数
    
    Args:
        value: 要转换的值
        default: 转换失败时的默认值
        
    Returns:
        Optional[float]: 转换后的浮点数或默认值
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def format_match_basic_info(match: Dict[str, Any]) -> Dict[str, Any]:
    """
    格式化比赛基本信息
    
    Args:
        match: 原始比赛数据
        
    Returns:
        Dict[str, Any]: 格式化后的比赛信息
    """
    return {
        'matchId': match['match_id'],
        'leagueId': match['league_id'],
        'leagueName': match['league_name'],
        'matchTime': match['match_time'].isoformat() if match['match_time'] else None,
        'homeTeam': match['home_team_name'],
        'awayTeam': match['away_team_name'],
        'homeTeamLogo': get_team_logo(match['home_team_name']),
        'awayTeamLogo': get_team_logo(match['away_team_name']),
        'matchStatus': match['match_status'],
        'homeScore': match['home_score'],
        'awayScore': match['away_score']
    }