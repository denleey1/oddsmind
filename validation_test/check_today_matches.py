#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查今天比赛是否符合精准规则
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

COMPANY_ID = '115'  # 威廉公司
BIG5_LEAGUE_IDS = {36, 31, 34, 8, 11}
BIG5_NAMES = {36: '英超', 31: '西甲', 34: '意甲', 8: '德甲', 11: '法甲'}
RANGE_PREFIXES = ['韬光', '实开', '低开', '高开', '超实', '超散', '超韬', '超深']


def get_range_type(range_str: str) -> Optional[str]:
    if not range_str:
        return None
    for p in RANGE_PREFIXES:
        if range_str.startswith(p):
            return p
    return '其他'


def classify_odds_change_simple(init: float, curr: float) -> str:
    """简单分类：升/降/稳"""
    if curr > init * 1.05:
        return '升'
    elif curr < init * 0.95:
        return '降'
    return '稳'


def classify_odds_change(init: float, curr: float) -> str:
    """细化分类：按变化幅度细分"""
    if init <= 0:
        return '未知'
    
    change_pct = (curr - init) / init
    
    if change_pct > 0.15:
        return '暴升(>15%)'
    elif change_pct > 0.10:
        return '大升(10-15%)'
    elif change_pct > 0.05:
        return '小升(5-10%)'
    elif change_pct > 0.02:
        return '微升(2-5%)'
    elif change_pct >= -0.02:
        return '稳定(±2%)'
    elif change_pct >= -0.05:
        return '微降(2-5%)'
    elif change_pct >= -0.10:
        return '小降(5-10%)'
    elif change_pct >= -0.15:
        return '大降(10-15%)'
    else:
        return '暴降(>15%)'


def classify_kelly(kelly: float) -> str:
    if kelly is None:
        return '未知'
    if kelly < 0.85:
        return '低Kelly'
    elif kelly < 0.95:
        return '中Kelly'
    elif kelly < 1.05:
        return '正常Kelly'
    return '高Kelly'


def classify_power_diff(diff: float) -> str:
    if diff is None:
        return '未知'
    if diff > 2:
        return '强让'
    elif diff > 0.5:
        return '微让'
    elif diff > -0.5:
        return '平手'
    elif diff > -2:
        return '微受'
    return '强受'


def get_today_matches():
    """获取今天和明天的比赛"""
    db = get_connection()
    
    # 获取今天和明天的比赛
    today = datetime.now().strftime('%Y-%m-%d')
    tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    
    query = '''
        SELECT 
            m.match_id,
            m.home_team_name,
            m.away_team_name,
            m.match_time,
            m.match_status,
            l.league_id,
            l.name_cn as league_name
        FROM matches m
        JOIN leagues l ON m.league_id = l.league_id
        WHERE DATE(m.match_time) IN (%s, %s)
          AND m.match_status IN ('scheduled', 'live')
        ORDER BY m.match_time
    '''
    
    return db.execute_query(query, (today, tomorrow), fetch='all')


def get_match_odds(match_id):
    """获取比赛的威廉赔率数据"""
    db = get_connection()
    
    # 直接从odds_analysis_results获取（使用fullwater字段）
    query = '''
        SELECT 
            oar.initial_home_range, oar.initial_away_range,
            oar.current_home_range, oar.current_away_range,
            oar.power_diff,
            oar.initial_home_fullwater as initial_home,
            oar.initial_draw_fullwater as initial_draw,
            oar.initial_away_fullwater as initial_away,
            oar.current_home_fullwater as current_home,
            oar.current_draw_fullwater as current_draw,
            oar.current_away_fullwater as current_away,
            NULL as kelly_home, NULL as kelly_draw, NULL as kelly_away
        FROM odds_analysis_results oar
        WHERE oar.match_id = %s AND oar.company_id = %s
    '''
    
    return db.execute_query(query, (match_id, COMPANY_ID), fetch='one')


def process_match_data(match, odds_data) -> Optional[Dict]:
    """处理比赛数据，提取特征"""
    if not odds_data:
        return None
    
    try:
        init_home = float(odds_data.get('initial_home', 0))
        init_away = float(odds_data.get('initial_away', 0))
        curr_home = float(odds_data.get('current_home', 0))
        curr_away = float(odds_data.get('current_away', 0))
        
        if init_home == 0 or init_away == 0:
            return None
        
        # 让球方判断
        if init_home <= init_away:
            handicap_side = 'home'
            handicap_team = match['home_team_name']
            receiver_team = match['away_team_name']
            init_h_range = odds_data.get('initial_home_range')
            init_r_range = odds_data.get('initial_away_range')
            curr_h_range = odds_data.get('current_home_range')
            curr_r_range = odds_data.get('current_away_range')
            init_h_odds, init_r_odds = init_home, init_away
            curr_h_odds, curr_r_odds = curr_home, curr_away
            kelly_h = odds_data.get('kelly_home')
            kelly_r = odds_data.get('kelly_away')
        else:
            handicap_side = 'away'
            handicap_team = match['away_team_name']
            receiver_team = match['home_team_name']
            init_h_range = odds_data.get('initial_away_range')
            init_r_range = odds_data.get('initial_home_range')
            curr_h_range = odds_data.get('current_away_range')
            curr_r_range = odds_data.get('current_home_range')
            init_h_odds, init_r_odds = init_away, init_home
            curr_h_odds, curr_r_odds = curr_away, curr_home
            kelly_h = odds_data.get('kelly_away')
            kelly_r = odds_data.get('kelly_home')
        
        power_diff = odds_data.get('power_diff')
        
        return {
            'match_id': match['match_id'],
            'home_team': match['home_team_name'],
            'away_team': match['away_team_name'],
            'handicap_team': handicap_team,
            'receiver_team': receiver_team,
            'match_time': match['match_time'],
            'league_name': match['league_name'],
            'league_id': match['league_id'],
            'is_big5': match['league_id'] in BIG5_LEAGUE_IDS,
            'init_h': get_range_type(init_h_range),
            'init_r': get_range_type(init_r_range),
            'curr_h': get_range_type(curr_h_range),
            'curr_r': get_range_type(curr_r_range),
            'h_change': classify_odds_change(init_h_odds, curr_h_odds),
            'r_change': classify_odds_change(init_r_odds, curr_r_odds),
            'kelly_h': classify_kelly(float(kelly_h) if kelly_h else None),
            'kelly_r': classify_kelly(float(kelly_r) if kelly_r else None),
            'power': classify_power_diff(float(power_diff) if power_diff else None),
            # 原始数据
            'init_h_odds': init_h_odds,
            'init_r_odds': init_r_odds,
            'curr_h_odds': curr_h_odds,
            'curr_r_odds': curr_r_odds,
        }
    except Exception as e:
        print(f"处理比赛数据出错: {e}")
        return None


# 精准规则定义
PRECISION_RULES = [
    # ============ 让方必赢规则 ============
    # 通用规则
    {
        'id': 'HW001',
        'name': '强让+即时受让方超韬+受让方升',
        'predict': '让方必赢',
        'condition': lambda m: m['power']=='强让' and m['curr_r']=='超韬' and '升' in m['r_change'],
        'league': '全部',
        'accuracy': 1.0
    },
    # 五大联赛基础规则
    {
        'id': 'HW002',
        'name': '【五大】强让+让方赔率降',
        'predict': '让方必赢',
        'condition': lambda m: m['is_big5'] and m['power']=='强让' and '降' in m['h_change'],
        'league': '五大',
        'accuracy': 1.0
    },
    {
        'id': 'HW003',
        'name': '【五大】强让+让方降+受让方升',
        'predict': '让方必赢',
        'condition': lambda m: m['is_big5'] and m['power']=='强让' and '降' in m['h_change'] and '升' in m['r_change'],
        'league': '五大',
        'accuracy': 1.0
    },
    # 五大联赛精细规则
    {
        'id': 'HW004',
        'name': '【五大·精细】强让+让方微降(2-5%)+受让方小升(5-10%)',
        'predict': '让方必赢',
        'condition': lambda m: m['is_big5'] and m['power']=='强让' and m['h_change']=='微降(2-5%)' and m['r_change']=='小升(5-10%)',
        'league': '五大',
        'accuracy': 1.0,
        'sample': 4
    },
    {
        'id': 'HW005',
        'name': '【五大·精细】强让+即时受让方高开+受让方小升(5-10%)',
        'predict': '让方必赢',
        'condition': lambda m: m['is_big5'] and m['power']=='强让' and m['curr_r']=='高开' and m['r_change']=='小升(5-10%)',
        'league': '五大',
        'accuracy': 1.0,
        'sample': 3
    },
    # 普通联赛精细规则
    {
        'id': 'HW006',
        'name': '【普通·精细】强让+让方微降(2-5%)',
        'predict': '让方必赢',
        'condition': lambda m: not m['is_big5'] and m['power']=='强让' and m['h_change']=='微降(2-5%)',
        'league': '普通',
        'accuracy': 1.0,
        'sample': 12
    },
    
    # ============ 受让方不输规则 ============
    # 全部联赛通用规则
    {
        'id': 'RN001',
        'name': '初让方高开→即时韬光',
        'predict': '受让方不输',
        'condition': lambda m: m['init_h']=='高开' and m['curr_h']=='韬光',
        'league': '全部',
        'accuracy': 1.0
    },
    # 五大联赛基础规则
    {
        'id': 'RN002',
        'name': '【五大】即时让方韬光',
        'predict': '受让方不输',
        'condition': lambda m: m['is_big5'] and m['curr_h']=='韬光',
        'league': '五大',
        'accuracy': 1.0
    },
    {
        'id': 'RN003',
        'name': '【五大】即时让方韬光+让方赔率升',
        'predict': '受让方不输',
        'condition': lambda m: m['is_big5'] and m['curr_h']=='韬光' and '升' in m['h_change'],
        'league': '五大',
        'accuracy': 1.0
    },
    {
        'id': 'RN004',
        'name': '【五大】即时让方韬光+受让方赔率降',
        'predict': '受让方不输',
        'condition': lambda m: m['is_big5'] and m['curr_h']=='韬光' and '降' in m['r_change'],
        'league': '五大',
        'accuracy': 1.0
    },
    {
        'id': 'RN005',
        'name': '【五大】即时让方超韬',
        'predict': '受让方不输',
        'condition': lambda m: m['is_big5'] and m['curr_h']=='超韬',
        'league': '五大',
        'accuracy': 1.0
    },
    # 五大联赛精细规则
    {
        'id': 'RN006',
        'name': '【五大·精细】即时让方韬光+让方暴升(>15%)',
        'predict': '受让方不输',
        'condition': lambda m: m['is_big5'] and m['curr_h']=='韬光' and m['h_change']=='暴升(>15%)',
        'league': '五大',
        'accuracy': 1.0,
        'sample': 3
    },
    {
        'id': 'RN007',
        'name': '【五大·精细】即时让方韬光+让方小升(5-10%)',
        'predict': '受让方不输',
        'condition': lambda m: m['is_big5'] and m['curr_h']=='韬光' and m['h_change']=='小升(5-10%)',
        'league': '五大',
        'accuracy': 1.0,
        'sample': 3
    },
    {
        'id': 'RN008',
        'name': '【五大·精细】即时让方超韬+让方暴升(>15%)',
        'predict': '受让方不输',
        'condition': lambda m: m['is_big5'] and m['curr_h']=='超韬' and m['h_change']=='暴升(>15%)',
        'league': '五大',
        'accuracy': 1.0,
        'sample': 4
    },
    {
        'id': 'RN009',
        'name': '【五大】微让+即时让方韬光',
        'predict': '受让方不输',
        'condition': lambda m: m['is_big5'] and m['power']=='微让' and m['curr_h']=='韬光',
        'league': '五大',
        'accuracy': 1.0
    },
    # 普通联赛精细规则
    {
        'id': 'RN010',
        'name': '【普通·精细】即时让方高开+让方暴升(>15%)',
        'predict': '受让方不输',
        'condition': lambda m: not m['is_big5'] and m['curr_h']=='高开' and m['h_change']=='暴升(>15%)',
        'league': '普通',
        'accuracy': 1.0,
        'sample': 13
    },
    {
        'id': 'RN011',
        'name': '【普通·精细】即时让方韬光+受让方大降(10-15%)',
        'predict': '受让方不输',
        'condition': lambda m: not m['is_big5'] and m['curr_h']=='韬光' and m['r_change']=='大降(10-15%)',
        'league': '普通',
        'accuracy': 1.0,
        'sample': 8
    },
    {
        'id': 'RN012',
        'name': '【普通·精细】即时让方高开+受让方暴降(>15%)',
        'predict': '受让方不输',
        'condition': lambda m: not m['is_big5'] and m['curr_h']=='高开' and m['r_change']=='暴降(>15%)',
        'league': '普通',
        'accuracy': 1.0,
        'sample': 15
    },
    {
        'id': 'RN013',
        'name': '【普通·精细】初让方低开→即时高开+让方暴升(>15%)',
        'predict': '受让方不输',
        'condition': lambda m: not m['is_big5'] and m['init_h']=='低开' and m['curr_h']=='高开' and m['h_change']=='暴升(>15%)',
        'league': '普通',
        'accuracy': 1.0,
        'sample': 7
    },
    # 全部联赛通用规则
    {
        'id': 'RN014',
        'name': '微让+即时让方韬光',
        'predict': '受让方不输',
        'condition': lambda m: m['power']=='微让' and m['curr_h']=='韬光',
        'league': '全部',
        'accuracy': 0.909
    },
]


def check_rules(match_data: Dict) -> List[Dict]:
    """检查比赛是否符合规则"""
    matched = []
    
    for rule in PRECISION_RULES:
        try:
            if rule['condition'](match_data):
                matched.append({
                    'rule_id': rule['id'],
                    'rule_name': rule['name'],
                    'predict': rule['predict'],
                })
        except Exception:
            continue
    
    return matched


def main():
    print("=" * 100)
    print("🎯 今日比赛精准规则筛选")
    print("=" * 100)
    print()
    
    # 获取今天的比赛
    matches = get_today_matches()
    print(f"📅 获取到 {len(matches)} 场未开始/进行中的比赛")
    print()
    
    matched_matches = []
    
    for match in matches:
        # 获取赔率数据
        odds_data = get_match_odds(match['match_id'])
        if not odds_data:
            continue
        
        # 处理数据
        match_data = process_match_data(match, odds_data)
        if not match_data:
            continue
        
        # 检查规则
        matched_rules = check_rules(match_data)
        
        if matched_rules:
            matched_matches.append({
                'match': match_data,
                'rules': matched_rules
            })
    
    # 输出结果
    if not matched_matches:
        print("❌ 今天没有符合精准规则的比赛")
        print()
        print("💡 规则要求非常严格（100%命中率），所以匹配的比赛较少")
    else:
        print(f"🔥 找到 {len(matched_matches)} 场符合规则的比赛！")
        print()
        
        for item in matched_matches:
            m = item['match']
            rules = item['rules']
            
            match_time = m['match_time'].strftime('%m-%d %H:%M') if m['match_time'] else '未知'
            is_big5 = '⭐' if m['is_big5'] else ''
            
            print(f"{'='*80}")
            print(f"{is_big5}【{m['league_name']}】{m['home_team']} vs {m['away_team']}")
            print(f"   ⏰ 时间: {match_time}")
            print(f"   🎯 让球方: {m['handicap_team']} ({m['power']})")
            print(f"   📊 即时让方盘型: {m['curr_h']} | 即时受让方盘型: {m['curr_r']}")
            print(f"   📈 让方赔率变化: {m['h_change']} | 受让方赔率变化: {m['r_change']}")
            print()
            
            for rule in rules:
                predict_emoji = '🔴' if rule['predict'] == '让方必赢' else '🟢'
                print(f"   {predict_emoji} 命中规则: {rule['rule_name']}")
                print(f"      预测: {rule['predict']}")
                if rule['predict'] == '让方必赢':
                    print(f"      👉 买: {m['handicap_team']} 赢")
                else:
                    print(f"      👉 买: {m['receiver_team']} 不输（双选：{m['receiver_team']}赢 或 平局）")
            print()
    
    print("=" * 100)


if __name__ == '__main__':
    main()
