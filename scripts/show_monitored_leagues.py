#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
显示所有监控的联赛并分级
"""

import sys
from pathlib import Path
import re

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.monitoring_config import (
    MONITOR_ALL_LEAGUES, 
    MONITORED_LEAGUES,
    S_LEVEL_MAIN,
    S_LEVEL_SECONDARY,
    A_LEVEL_MAIN,
    A_LEVEL_SECONDARY
)
from config.leagues_config import LEAGUES_CONFIG
from config.league_mapping import LEAGUE_ID_MAPPING

def get_league_name(league_id):
    """获取联赛名称"""
    # 先从LEAGUE_ID_MAPPING查找
    if league_id in LEAGUE_ID_MAPPING:
        return LEAGUE_ID_MAPPING[league_id].get('name_cn', f'联赛{league_id}')
    
    # 从LEAGUES_CONFIG查找
    for code, info in LEAGUES_CONFIG.items():
        match = re.match(r's(\d+)', info.league_filename)
        if match:
            if int(match.group(1)) == league_id:
                return info.name_cn
    
    return f'联赛{league_id}'

def get_league_info(league_id):
    """获取联赛详细信息"""
    # 先从LEAGUE_ID_MAPPING查找
    if league_id in LEAGUE_ID_MAPPING:
        info = LEAGUE_ID_MAPPING[league_id]
        return {
            'name_cn': info.get('name_cn', ''),
            'name_en': info.get('name_en', ''),
            'country': '未知'
        }
    
    # 从LEAGUES_CONFIG查找
    for code, info in LEAGUES_CONFIG.items():
        match = re.match(r's(\d+)', info.league_filename)
        if match:
            if int(match.group(1)) == league_id:
                return {
                    'name_cn': info.name_cn,
                    'name_en': info.name_en,
                    'country': info.country
                }
    
    return {
        'name_cn': f'联赛{league_id}',
        'name_en': '',
        'country': '未知'
    }

def categorize_league(league_id):
    """对联赛进行分级"""
    if league_id in S_LEVEL_MAIN:
        return 'S级主联赛'
    elif league_id in S_LEVEL_SECONDARY:
        return 'S级次级联赛'
    elif league_id in A_LEVEL_MAIN:
        return 'A级主联赛'
    elif league_id in A_LEVEL_SECONDARY:
        return 'A级次级联赛'
    else:
        return '其他联赛'

def main():
    print('=' * 100)
    print('监控联赛分级报告')
    print('=' * 100)
    print()
    
    print(f'监控模式: {"监控所有联赛" if MONITOR_ALL_LEAGUES else "仅监控配置的联赛"}')
    print()
    
    # 获取所有需要监控的联赛
    if MONITOR_ALL_LEAGUES:
        # 从LEAGUES_CONFIG获取所有联赛ID
        all_league_ids = []
        league_id_to_code = {}
        
        for code, info in LEAGUES_CONFIG.items():
            match = re.match(r's(\d+)', info.league_filename)
            if match:
                league_id = int(match.group(1))
                if league_id not in all_league_ids:
                    all_league_ids.append(league_id)
                    league_id_to_code[league_id] = code
        
        all_league_ids.sort()
        monitored_league_ids = all_league_ids
        print(f'总联赛数: {len(monitored_league_ids)} 个')
    else:
        monitored_league_ids = MONITORED_LEAGUES
        print(f'配置的联赛数: {len(monitored_league_ids)} 个')
    
    print()
    
    # 按分级组织联赛
    categorized = {
        'S级主联赛': [],
        'S级次级联赛': [],
        'A级主联赛': [],
        'A级次级联赛': [],
        '其他联赛': []
    }
    
    for league_id in monitored_league_ids:
        category = categorize_league(league_id)
        league_info = get_league_info(league_id)
        categorized[category].append({
            'id': league_id,
            'name_cn': league_info['name_cn'],
            'name_en': league_info['name_en'],
            'country': league_info['country']
        })
    
    # 按国家分组显示
    print('=' * 100)
    print('【S级主联赛】（顶级联赛）')
    print('=' * 100)
    print(f'共 {len(categorized["S级主联赛"])} 个联赛\n')
    
    # 按国家分组
    by_country = {}
    for league in categorized['S级主联赛']:
        country = league['country']
        if country not in by_country:
            by_country[country] = []
        by_country[country].append(league)
    
    for country in sorted(by_country.keys()):
        print(f'  {country}:')
        for league in sorted(by_country[country], key=lambda x: x['id']):
            print(f'    [{league["id"]:4d}] {league["name_cn"]:15s} ({league["name_en"]})')
        print()
    
    print('=' * 100)
    print('【S级次级联赛】')
    print('=' * 100)
    print(f'共 {len(categorized["S级次级联赛"])} 个联赛\n')
    
    by_country = {}
    for league in categorized['S级次级联赛']:
        country = league['country']
        if country not in by_country:
            by_country[country] = []
        by_country[country].append(league)
    
    for country in sorted(by_country.keys()):
        print(f'  {country}:')
        for league in sorted(by_country[country], key=lambda x: x['id']):
            print(f'    [{league["id"]:4d}] {league["name_cn"]:15s} ({league["name_en"]})')
        print()
    
    print('=' * 100)
    print('【A级主联赛】（庄家重点开盘，关注度高）')
    print('=' * 100)
    print(f'共 {len(categorized["A级主联赛"])} 个联赛\n')
    
    by_country = {}
    for league in categorized['A级主联赛']:
        country = league['country']
        if country not in by_country:
            by_country[country] = []
        by_country[country].append(league)
    
    for country in sorted(by_country.keys()):
        print(f'  {country}:')
        for league in sorted(by_country[country], key=lambda x: x['id']):
            print(f'    [{league["id"]:4d}] {league["name_cn"]:15s} ({league["name_en"]})')
        print()
    
    print('=' * 100)
    print('【A级次级联赛】')
    print('=' * 100)
    print(f'共 {len(categorized["A级次级联赛"])} 个联赛\n')
    
    by_country = {}
    for league in categorized['A级次级联赛']:
        country = league['country']
        if country not in by_country:
            by_country[country] = []
        by_country[country].append(league)
    
    for country in sorted(by_country.keys()):
        print(f'  {country}:')
        for league in sorted(by_country[country], key=lambda x: x['id']):
            print(f'    [{league["id"]:4d}] {league["name_cn"]:15s} ({league["name_en"]})')
        print()
    
    if categorized['其他联赛']:
        print('=' * 100)
        print('【其他联赛】（未在配置中分级的联赛）')
        print('=' * 100)
        print(f'共 {len(categorized["其他联赛"])} 个联赛\n')
        
        by_country = {}
        for league in categorized['其他联赛']:
            country = league['country']
            if country not in by_country:
                by_country[country] = []
            by_country[country].append(league)
        
        for country in sorted(by_country.keys()):
            print(f'  {country}:')
            for league in sorted(by_country[country], key=lambda x: x['id']):
                print(f'    [{league["id"]:4d}] {league["name_cn"]:15s} ({league["name_en"]})')
            print()
    
    # 统计信息
    print('=' * 100)
    print('统计信息')
    print('=' * 100)
    print(f'S级主联赛:     {len(categorized["S级主联赛"]):3d} 个')
    print(f'S级次级联赛:   {len(categorized["S级次级联赛"]):3d} 个')
    print(f'A级主联赛:     {len(categorized["A级主联赛"]):3d} 个')
    print(f'A级次级联赛:   {len(categorized["A级次级联赛"]):3d} 个')
    if categorized['其他联赛']:
        print(f'其他联赛:       {len(categorized["其他联赛"]):3d} 个')
    print(f'总计:           {sum(len(v) for v in categorized.values()):3d} 个')
    print()

if __name__ == '__main__':
    main()



