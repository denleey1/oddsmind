#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
应用数据库索引优化脚本
执行索引创建，提升查询性能
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app_database import execute_query, execute_update
from core.logger import get_logger

logger = get_logger(__name__)


def apply_indexes():
    """应用索引优化"""
    
    indexes_to_create = [
        # matches表索引
        ("idx_matches_match_time", "CREATE INDEX IF NOT EXISTS idx_matches_match_time ON matches(match_time)"),
        ("idx_matches_league_id", "CREATE INDEX IF NOT EXISTS idx_matches_league_id ON matches(league_id)"),
        ("idx_matches_match_status", "CREATE INDEX IF NOT EXISTS idx_matches_match_status ON matches(match_status)"),
        ("idx_matches_league_time", "CREATE INDEX IF NOT EXISTS idx_matches_league_time ON matches(league_id, match_time)"),
        ("idx_matches_status_time", "CREATE INDEX IF NOT EXISTS idx_matches_status_time ON matches(match_status, match_time)"),
        ("idx_matches_home_team", "CREATE INDEX IF NOT EXISTS idx_matches_home_team ON matches(home_team_id)"),
        ("idx_matches_away_team", "CREATE INDEX IF NOT EXISTS idx_matches_away_team ON matches(away_team_id)"),
        
        # standings表索引
        ("idx_standings_team_league", "CREATE INDEX IF NOT EXISTS idx_standings_team_league ON standings(team_id, league_id, standing_type)"),
        ("idx_standings_league_type", "CREATE INDEX IF NOT EXISTS idx_standings_league_type ON standings(league_id, standing_type)"),
        
        # fundamental_analysis表索引
        ("idx_fundamental_match", "CREATE INDEX IF NOT EXISTS idx_fundamental_match ON fundamental_analysis(match_id)"),
        
        # odds_analysis_results表索引
        ("idx_odds_analysis_match", "CREATE INDEX IF NOT EXISTS idx_odds_analysis_match ON odds_analysis_results(match_id)"),
        
        # odds_changes表索引
        ("idx_odds_changes_match", "CREATE INDEX IF NOT EXISTS idx_odds_changes_match ON odds_changes(match_id)"),
    ]
    
    print("="*80)
    print("数据库索引优化")
    print("="*80)
    print()
    
    success_count = 0
    error_count = 0
    
    for index_name, sql in indexes_to_create:
        try:
            # MySQL不支持IF NOT EXISTS，需要先检查
            # 先尝试创建，如果已存在会报错，忽略即可
            try:
                execute_update(sql)
                print(f"✅ {index_name}: 创建成功")
                success_count += 1
            except Exception as e:
                error_msg = str(e).lower()
                if 'duplicate' in error_msg or 'already exists' in error_msg:
                    print(f"ℹ️  {index_name}: 已存在，跳过")
                    success_count += 1
                else:
                    raise
        except Exception as e:
            print(f"❌ {index_name}: 创建失败 - {e}")
            error_count += 1
    
    print()
    print("="*80)
    print(f"完成: 成功 {success_count}, 失败 {error_count}")
    print("="*80)
    
    # 显示当前索引
    print()
    print("当前matches表索引:")
    try:
        indexes = execute_query("SHOW INDEX FROM matches")
        for idx in indexes:
            print(f"  - {idx.get('Key_name')}: {idx.get('Column_name')}")
    except Exception as e:
        print(f"  查询失败: {e}")


if __name__ == '__main__':
    apply_indexes()















