#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
联赛管理器 - 提供统一的联赛信息管理和动态查找
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass
import logging

# Add project root to path
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

@dataclass
class LeagueInfo:
    """联赛信息数据类"""
    name_cn: str  # 中文名
    name_en: str  # 英文名
    country: str  # 国家
    level: int    # 级别
    code: str     # 联赛代码
    
class LeagueManager:
    """管理联赛信息并提供动态查找"""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        # 联赛配置映射
        self.leagues = {
            "SWE1": LeagueInfo(
                name_cn="瑞典超",
                name_en="Allsvenskan",
                country="Sweden",
                level=1,
                code="SWE1"
            ),
            "SWE2": LeagueInfo(
                name_cn="瑞典甲",
                name_en="Superettan",
                country="Sweden", 
                level=2,
                code="SWE2"
            ),
            "ENG1": LeagueInfo(
                name_cn="英超",
                name_en="Premier League",
                country="England",
                level=1,
                code="ENG1"
            ),
            "ENG2": LeagueInfo(
                name_cn="英冠",
                name_en="Championship",
                country="England",
                level=2,
                code="ENG2"
            ),
            "ESP1": LeagueInfo(
                name_cn="西甲",
                name_en="La Liga",
                country="Spain",
                level=1,
                code="ESP1"
            ),
            "GER1": LeagueInfo(
                name_cn="德甲",
                name_en="Bundesliga",
                country="Germany",
                level=1,
                code="GER1"
            ),
            "ITA1": LeagueInfo(
                name_cn="意甲",
                name_en="Serie A",
                country="Italy",
                level=1,
                code="ITA1"
            ),
            "FRA1": LeagueInfo(
                name_cn="法甲",
                name_en="Ligue 1",
                country="France",
                level=1,
                code="FRA1"
            )
        }
        
        # 建立名称到代码的映射
        self._name_to_code_map = {}
        for code, league in self.leagues.items():
            # 中文名映射
            self._name_to_code_map[league.name_cn] = code
            self._name_to_code_map[league.name_cn.lower()] = code
            # 英文名映射
            self._name_to_code_map[league.name_en] = code
            self._name_to_code_map[league.name_en.lower()] = code
    
    def get_league_by_name(self, name: str) -> Optional[LeagueInfo]:
        """
        通过中文或英文名称获取联赛信息
        
        Args:
            name: 联赛名称（中文或英文）
            
        Returns:
            LeagueInfo对象或None
        """
        if not name:
            return None
            
        # 直接代码查找
        if name in self.leagues:
            return self.leagues[name]
        
        # 名称查找
        code = self._name_to_code_map.get(name)
        if not code:
            code = self._name_to_code_map.get(name.lower())
        
        if code:
            return self.leagues.get(code)
        
        # 模糊匹配
        # 瑞典甲的各种可能变体
        if any(kw in name for kw in ["瑞典甲", "瑞典超级联赛", "Superettan", "Swedish Superettan"]):
            return self.leagues.get("SWE2")
        
        # 瑞典超的变体
        if any(kw in name for kw in ["瑞典超", "瑞典超级", "Allsvenskan", "Swedish Allsvenskan"]):
            return self.leagues.get("SWE1")
        
        # 其他联赛的模糊匹配
        name_lower = name.lower()
        if "英超" in name or "premier league" in name_lower:
            return self.leagues.get("ENG1")
        if "英冠" in name or "championship" in name_lower:
            return self.leagues.get("ENG2")
        if "西甲" in name or "la liga" in name_lower:
            return self.leagues.get("ESP1")
        if "德甲" in name or "bundesliga" in name_lower:
            return self.leagues.get("GER1")
        if "意甲" in name or "serie a" in name_lower:
            return self.leagues.get("ITA1")
        if "法甲" in name or "ligue 1" in name_lower:
            return self.leagues.get("FRA1")
        
        return None
    
    def detect_league_from_match_data(self, match_data: Dict[str, Any]) -> Optional[str]:
        """
        从比赛数据中检测联赛
        
        Args:
            match_data: 比赛数据字典
            
        Returns:
            联赛中文名称或None
        """
        # 尝试不同的可能字段
        league_fields = ['league', 'league_name', 'league_cn', 'competition', '联赛']
        
        # 首先检查basic_info中的league字段
        if 'basic_info' in match_data:
            basic_info = match_data['basic_info']
            if 'league' in basic_info:
                league_name = basic_info['league']
                league = self.get_league_by_name(league_name)
                if league:
                    return league.name_cn
        
        # 然后检查其他可能的字段
        for field in league_fields:
            if field in match_data:
                league_name = match_data[field]
                league = self.get_league_by_name(league_name)
                if league:
                    return league.name_cn
        
        # 尝试从analysis_data中获取
        if 'analysis_data' in match_data:
            analysis_data = match_data['analysis_data']
            for field in league_fields:
                if field in analysis_data:
                    league_name = analysis_data[field]
                    league = self.get_league_by_name(league_name)
                    if league:
                        return league.name_cn
        
        return None


def get_league_name(match_id: str = None, league_input: str = None, match_data: Dict = None) -> Optional[str]:
    """
    获取联赛名称，带有回退逻辑
    
    优先级：
    1. 通过 match_id 从数据库查询
    2. 显式的 league_input
    3. 从 match_data 检测
    4. 返回 None（使用所有数据）
    
    Args:
        match_id: 比赛ID
        league_input: 显式提供的联赛名称
        match_data: 比赛数据字典
        
    Returns:
        联赛名称字符串或None
    """
    manager = LeagueManager()
    logger = logging.getLogger("get_league_name")
    
    # 1. 最高优先级：通过 match_id 从数据库查询
    if match_id:
        try:
            db = get_connection()
            query = """
                SELECT l.name_cn 
                FROM matches m
                JOIN leagues l ON m.league_id = l.league_id
                WHERE m.match_id = %s
            """
            results = db.execute_query(query, (match_id,))
            result = results[0] if results else None
            if result and result.get('name_cn'):
                logger.info(f"通过数据库查询 match_id={match_id} 得到联赛: {result['name_cn']}")
                return result['name_cn']
        except Exception as e:
            logger.error(f"通过 match_id={match_id} 查询联赛失败: {e}")
            # 查询失败，继续尝试其他方法

    # 2. 其次使用显式提供的联赛名称
    if league_input:
        league = manager.get_league_by_name(league_input)
        if league:
            logger.info(f"使用显式提供的联赛: {league.name_cn}")
            return league.name_cn
        else:
            logger.warning(f"无法识别联赛名称: {league_input}")
    
    # 3. 从比赛数据中检测
    if match_data:
        detected_league = manager.detect_league_from_match_data(match_data)
        if detected_league:
            logger.info(f"从比赛数据检测到联赛: {detected_league}")
            return detected_league
    
    # 4. 无法确定联赛，返回None（将使用所有数据）
    logger.warning(f"无法确定联赛名称（match_id={match_id}），将使用所有数据")
    return None


if __name__ == "__main__":
    # 测试联赛管理器
    manager = LeagueManager()
    
    # 测试各种查找
    test_names = ["瑞典甲", "SWE2", "Superettan", "英超", "Premier League", "未知联赛"]
    for name in test_names:
        league = manager.get_league_by_name(name)
        if league:
            print(f"{name} -> {league.name_cn} ({league.name_en})")
        else:
            print(f"{name} -> 未找到")
    
    # 测试get_league_name函数
    print("\n测试get_league_name函数:")
    print(f"显式输入'瑞典甲': {get_league_name(league_input='瑞典甲')}")
    print(f"从数据检测: {get_league_name(match_data={'basic_info': {'league': '瑞典甲'}})}")
    print(f"无法确定: {get_league_name()}")