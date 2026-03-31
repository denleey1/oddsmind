#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
比赛分析数据服务
复用 query_match_api_data.py 的逻辑，但返回结构化JSON数据
"""

from typing import Dict, Any, List, Optional
from application.services.analytics import get_match_detail
from core.logger import get_logger

logger = get_logger(__name__)

# 博彩公司ID映射（只查询这几个公司）
COMPANY_IDS = {
    '马会': 432,      # HKJC
    '澳门': 80,       # Macau
    '威廉': 115,      # William Hill
    '平博': 281,      # Pinnacle
    'Interwetten': 190  # Interwetten (塞浦路斯)
}


def extract_team_info(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """提取主客队名称和基本信息"""
    data = api_data.get('data', {})
    return {
        'homeTeam': data.get('homeTeam', 'N/A'),
        'awayTeam': data.get('awayTeam', 'N/A'),
        'matchId': data.get('matchId'),
        'leagueName': data.get('leagueName'),
        'matchTime': data.get('matchTime')
    }


def get_strength_from_company(company_data_list: List[Dict[str, Any]], 
                               preferred_company_id: int,
                               fallback_company_id: int) -> Optional[Dict[str, Any]]:
    """
    从公司数据中获取指定公司的广义实力评估
    优先使用preferred_company_id，如果没有则使用fallback_company_id
    """
    # 先找澳门
    for company_data in company_data_list:
        if int(company_data.get('companyId')) == preferred_company_id:
            return {
                'homePowerLevel': company_data.get('homePowerLevel'),
                'homeTierLevel': company_data.get('homeTierLevel'),
                'awayPowerLevel': company_data.get('awayPowerLevel'),
                'awayTierLevel': company_data.get('awayTierLevel'),
                'companyName': company_data.get('companyName')
            }
    
    # 如果澳门没有，找威廉
    for company_data in company_data_list:
        if int(company_data.get('companyId')) == fallback_company_id:
            return {
                'homePowerLevel': company_data.get('homePowerLevel'),
                'homeTierLevel': company_data.get('homeTierLevel'),
                'awayPowerLevel': company_data.get('awayPowerLevel'),
                'awayTierLevel': company_data.get('awayTierLevel'),
                'companyName': company_data.get('companyName')
            }
    
    return None


def extract_confidence_levels(api_data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """提取主平客的信心值（包含信心等级和分数）"""
    data = api_data.get('data', {})
    fundamental = data.get('fundamentalAnalysis')
    
    # 如果fundamentalAnalysis为None，返回默认值（欧赔意图分析不依赖此数据）
    if fundamental is None:
        return {
            'homeWin': {
                'confidenceLevel': 'N/A',
                'score': None
            },
            'draw': {
                'confidenceLevel': 'N/A',
                'score': None
            },
            'awayWin': {
                'confidenceLevel': 'N/A',
                'score': None
            }
        }
    
    # 确保fundamental是字典类型
    if not isinstance(fundamental, dict):
        fundamental = {}
    
    return {
        'homeWin': {
            'confidenceLevel': fundamental.get('homeWin', {}).get('confidenceLevel', 'N/A') if isinstance(fundamental.get('homeWin'), dict) else 'N/A',
            'score': fundamental.get('homeWin', {}).get('score') if isinstance(fundamental.get('homeWin'), dict) else None
        },
        'draw': {
            'confidenceLevel': fundamental.get('draw', {}).get('confidenceLevel', 'N/A') if isinstance(fundamental.get('draw'), dict) else 'N/A',
            'score': fundamental.get('draw', {}).get('score') if isinstance(fundamental.get('draw'), dict) else None
        },
        'awayWin': {
            'confidenceLevel': fundamental.get('awayWin', {}).get('confidenceLevel', 'N/A') if isinstance(fundamental.get('awayWin'), dict) else 'N/A',
            'score': fundamental.get('awayWin', {}).get('score') if isinstance(fundamental.get('awayWin'), dict) else None
        }
    }


def get_odds_from_database(match_id: str, company_id: int) -> Optional[Dict[str, Any]]:
    """
    从数据库获取原始赔率数据（优先 odds_changes，其次 european_odds）
    返回: {
        'initial': {'home': ..., 'draw': ..., 'away': ...},
        'current': {'home': ..., 'draw': ..., 'away': ...}
    }
    """
    try:
        from app_database import execute_query

        # 重要：项目实际使用的是 odds_changes（复数），历史上有 oddschange（单数）的误写
        sql_candidates = [
            (
                "odds_changes",
                """
                SELECT initial_home, initial_draw, initial_away,
                       current_home, current_draw, current_away
                FROM odds_changes
                WHERE match_id = %s AND company_id = %s
                ORDER BY last_updated DESC
                LIMIT 1
                """,
            ),
            (
                "european_odds",
                """
                SELECT initial_home, initial_draw, initial_away,
                       current_home, current_draw, current_away
                FROM european_odds
                WHERE match_id = %s AND company_id = %s
                ORDER BY updated_at DESC
                LIMIT 1
                """,
            ),
        ]

        for table_name, sql in sql_candidates:
            try:
                results = execute_query(sql, (match_id, company_id))
                if results and results[0]:
                    row = results[0]
                    data = {
                        'initial': {
                            'home': float(row.get('initial_home')) if row.get('initial_home') is not None else None,
                            'draw': float(row.get('initial_draw')) if row.get('initial_draw') is not None else None,
                            'away': float(row.get('initial_away')) if row.get('initial_away') is not None else None
                        },
                        'current': {
                            'home': float(row.get('current_home')) if row.get('current_home') is not None else None,
                            'draw': float(row.get('current_draw')) if row.get('current_draw') is not None else None,
                            'away': float(row.get('current_away')) if row.get('current_away') is not None else None
                        }
                    }
                    logger.debug(f"从 {table_name} 获取到原始赔率 (match_id={match_id}, company_id={company_id})")
                    return data
            except Exception as inner_e:
                logger.warning(f"查询 {table_name} 失败 (match_id={match_id}, company_id={company_id}): {inner_e}")
    except Exception as e:
        logger.warning(f"从数据库获取赔率失败 (match_id={match_id}, company_id={company_id}): {e}")
    return None


def extract_company_complete_data(api_data: Dict[str, Any], match_id: str = None) -> List[Dict[str, Any]]:
    """
    提取五家公司的完整数据（包括分析数据和赔率）
    赔率从数据库oddschange表获取原始数据，而不是API返回的计算后的满水赔率
    """
    data = api_data.get('data', {})
    company_analyses = data.get('companyAnalyses', [])
    
    result = []
    target_company_ids = list(COMPANY_IDS.values())
    
    for analysis in company_analyses:
        company_id = analysis.get('companyId')
        if not company_id or int(company_id) not in target_company_ids:
            continue
        
        company_id_int = int(company_id)
        company_name = next(
            (name for name, cid in COMPANY_IDS.items() if cid == company_id_int),
            analysis.get('companyName', 'Unknown')
        )
        
        # 从数据库获取原始赔率（而不是API返回的计算后的满水赔率）
        db_odds = None
        if match_id:
            db_odds = get_odds_from_database(match_id, company_id_int)
        
        # 如果数据库没有，则使用API返回的赔率（作为备用）
        initial_odds = db_odds.get('initial', {}) if db_odds else analysis.get('initial', {}).get('odds', {})
        current_odds = db_odds.get('current', {}) if db_odds else analysis.get('current', {}).get('odds', {})
        
        # 合并分析数据和赔率数据
        # 注意：平博(281)应该看即时水位流向（赔率），不是区间
        is_pinnacle = (company_id_int == 281)
        
        company_data = {
            'companyId': company_id,
            'companyName': company_name,
            # 广义实力
            'homePowerLevel': analysis.get('homePowerLevel'),
            'awayPowerLevel': analysis.get('awayPowerLevel'),
            'homeTierLevel': analysis.get('homeTierLevel'),
            'awayTierLevel': analysis.get('awayTierLevel'),
            # 初盘数据
            'initial': {
                'homeRange': analysis.get('initial', {}).get('homeRange'),
                'homeRuleValue': analysis.get('initial', {}).get('homeRuleValue'),
                'drawRange': analysis.get('initial', {}).get('drawRange'),
                'awayRange': analysis.get('initial', {}).get('awayRange'),
                'awayRuleValue': analysis.get('initial', {}).get('awayRuleValue'),
                'ruleDiff': analysis.get('initial', {}).get('ruleDiff'),
                'odds': {
                    'home': initial_odds.get('home'),
                    'draw': initial_odds.get('draw'),
                    'away': initial_odds.get('away')
                }
            },
            # 即时数据
            'current': {
                'homeRange': analysis.get('current', {}).get('homeRange'),
                'homeRuleValue': analysis.get('current', {}).get('homeRuleValue'),
                'drawRange': analysis.get('current', {}).get('drawRange'),
                'awayRange': analysis.get('current', {}).get('awayRange'),
                'awayRuleValue': analysis.get('current', {}).get('awayRuleValue'),
                'ruleDiff': analysis.get('current', {}).get('ruleDiff'),
                'odds': {
                    'home': current_odds.get('home'),
                    'draw': current_odds.get('draw'),
                    'away': current_odds.get('away')
                }
            },
            # 标记是否为平博（用于后续格式化）
            'isPinnacle': is_pinnacle
        }
        result.append(company_data)
    
    # 按公司顺序排序（马会、澳门、威廉、平博、Interwetten）
    # 使用COMPANY_IDS字典的值顺序进行排序，不在字典中的公司排到最后
    def get_sort_key(company):
        company_id = int(company['companyId'])
        try:
            return list(COMPANY_IDS.values()).index(company_id)
        except ValueError:
            return 999  # 不在COMPANY_IDS中的公司排到最后
    
    result.sort(key=get_sort_key)
    
    return result


def get_match_analysis_data(match_id: str) -> Dict[str, Any]:
    """
    获取比赛分析数据（用于AI推理）
    返回结构化JSON数据，包含：
    1. 比赛基本信息（主客队名称、广义实力）
    2. 主平客的信心值
    3. 五家公司的初盘/即时数据
    """
    try:
        # 调用API获取比赛详情
        logger.info(f"正在获取比赛 {match_id} 的分析数据...")
        api_result = get_match_detail(match_id)
        
        if not api_result.get('success'):
            return {
                'success': False,
                'error': api_result.get('error', '获取比赛详情失败')
            }
        
        # 提取基本信息
        team_info = extract_team_info(api_result)
        confidence_levels = extract_confidence_levels(api_result)
        # 传入match_id以便从数据库获取原始赔率
        company_data_list = extract_company_complete_data(api_result, match_id=match_id)
        
        # 获取澳门或威廉的广义实力评估
        strength_info = get_strength_from_company(
            company_data_list, 
            preferred_company_id=80,  # 澳门
            fallback_company_id=115   # 威廉
        )
        
        # 格式化主客队名称（带广义实力）
        home_name = team_info['homeTeam']
        away_name = team_info['awayTeam']
        strength_source = None
        
        if strength_info:
            home_power = strength_info.get('homePowerLevel')
            home_tier = strength_info.get('homeTierLevel')
            away_power = strength_info.get('awayPowerLevel')
            away_tier = strength_info.get('awayTierLevel')
            
            if home_power is not None and home_tier:
                home_name = f"{home_name} ({home_power}, {home_tier})"
            elif home_power is not None:
                home_name = f"{home_name} ({home_power})"
            elif home_tier:
                home_name = f"{home_name} ({home_tier})"
            
            if away_power is not None and away_tier:
                away_name = f"{away_name} ({away_power}, {away_tier})"
            elif away_power is not None:
                away_name = f"{away_name} ({away_power})"
            elif away_tier:
                away_name = f"{away_name} ({away_tier})"
            
            strength_source = strength_info.get('companyName')
        
        # 组装返回结果
        result = {
            'success': True,
            'data': {
                'matchInfo': {
                    'matchId': team_info.get('matchId'),
                    'leagueName': team_info.get('leagueName'),
                    'matchTime': team_info.get('matchTime'),
                    'homeTeam': home_name,
                    'awayTeam': away_name,
                    'strengthSource': strength_source
                },
                'confidenceLevels': confidence_levels,
                'companyAnalyses': company_data_list
            }
        }
        
        logger.info(f"成功获取比赛 {match_id} 的分析数据")
        return result
        
    except Exception as e:
        logger.error(f"获取比赛分析数据失败: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

