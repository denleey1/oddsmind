#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查所有联赛的广义实力数据状态
"""

import sys
from pathlib import Path

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

def check_all_leagues():
    """检查所有联赛的数据状态"""
    db = get_connection()
    
    league_names = {
        8: '德甲', 11: '法甲', 15: '韩国K联赛', 25: '日职联', 
        31: '西甲', 34: '意甲', 36: '英超'
    }
    
    print('='*70)
    print('所有联赛广义实力数据状态检查')
    print('='*70)
    
    ready_leagues = []
    
    for league_id, name in league_names.items():
        power_stats = db.execute_query('''
            SELECT 
                COUNT(DISTINCT target_round) as round_count,
                MIN(target_round) as min_round, 
                MAX(target_round) as max_round,
                COUNT(DISTINCT team_id) as teams,
                COUNT(DISTINCT company_id) as companies
            FROM team_power_ratings 
            WHERE league_id = %s
        ''', [league_id], fetch='one')
        
        match_stats = db.execute_query('''
            SELECT 
                COUNT(CASE WHEN match_status = 'finished' THEN 1 END) as finished_matches,
                MIN(round_number) as min_round,
                MAX(round_number) as max_round
            FROM matches 
            WHERE league_id = %s
        ''', [league_id], fetch='one')
        
        print(f'{name} (ID:{league_id}):')
        
        if power_stats['round_count'] > 0:
            min_round = power_stats['min_round'] or 0
            max_round = power_stats['max_round'] or 0
            
            print(f'  广义实力: {power_stats["teams"]}支球队, {power_stats["companies"]}家公司')
            print(f'  轮次数据: 第{min_round}-{max_round}轮 (共{power_stats["round_count"]}轮)')
            
            if max_round > min_round:
                verifiable_start = min_round + 1
                verifiable_end = max_round + 1
                actual_max = match_stats['max_round'] or 0
                verifiable_end = min(verifiable_end, actual_max)
                
                if verifiable_start <= verifiable_end:
                    print(f'  ✅ 可验证: 第{verifiable_start}-{verifiable_end}轮')
                    ready_leagues.append({
                        'id': league_id,
                        'name': name,
                        'code': get_league_code(league_id),
                        'start': verifiable_start,
                        'end': verifiable_end
                    })
                else:
                    print(f'  ❌ 不可验证: 轮次范围不足')
            else:
                print(f'  ❌ 不可验证: 仅有单轮数据')
        else:
            print(f'  ❌ 无广义实力数据')
        
        print(f'  比赛数据: 第{match_stats["min_round"]}-{match_stats["max_round"]}轮, 已完成{match_stats["finished_matches"]}场')
        print()
    
    print('='*50)
    print('可验证联赛汇总:')
    print('='*50)
    
    if ready_leagues:
        for league in ready_leagues:
            print(f'✅ {league["name"]} ({league["code"]}): 第{league["start"]}-{league["end"]}轮')
    else:
        print('❌ 暂无可验证联赛')
    
    return ready_leagues

def get_league_code(league_id):
    """获取联赛代码"""
    code_map = {
        8: 'bundesliga', 11: 'ligue1', 15: 'kleague', 25: 'jleague',
        31: 'laliga', 34: 'seriea', 36: 'premier'
    }
    return code_map.get(league_id, f'league_{league_id}')

if __name__ == "__main__":
    ready_leagues = check_all_leagues()
    print(f'\n总计 {len(ready_leagues)} 个联赛可以进行验证分析！')