#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查澳超联赛数据和广义实力数据
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database.connection import get_connection

db = get_connection()

print("=" * 80)
print("澳超联赛数据检查")
print("=" * 80)

# 1. 查找澳超联赛
leagues = db.execute_query("""
    SELECT league_id, name_cn, name_en, season, total_rounds
    FROM leagues 
    WHERE name_cn LIKE '%澳超%' OR name_en LIKE '%A-League%'
    ORDER BY league_id
""", fetch='all')

if not leagues:
    print("❌ 未找到澳超联赛")
    sys.exit(1)

league = leagues[0]
league_id = league['league_id']
print(f"\n✅ 找到澳超联赛:")
print(f"   League ID: {league_id}")
print(f"   中文名: {league['name_cn']}")
print(f"   英文名: {league['name_en']}")
print(f"   赛季: {league.get('season', 'N/A')}")
print(f"   总轮次: {league.get('total_rounds', 'N/A')}")

# 2. 查询比赛数据
matches = db.execute_query("""
    SELECT 
        COUNT(*) as total_matches,
        COUNT(DISTINCT home_team_id) + COUNT(DISTINCT away_team_id) as unique_teams,
        MIN(match_time) as earliest_match,
        MAX(match_time) as latest_match,
        COUNT(CASE WHEN match_status = 'finished' THEN 1 END) as finished_matches,
        COUNT(CASE WHEN match_status = 'scheduled' THEN 1 END) as scheduled_matches,
        COUNT(CASE WHEN match_status = 'live' THEN 1 END) as live_matches,
        MIN(round_number) as min_round,
        MAX(round_number) as max_round,
        COUNT(DISTINCT round_number) as unique_rounds
    FROM matches
    WHERE league_id = %s
""", (league_id,), fetch='one')

if matches:
    print(f"\n📊 比赛数据统计:")
    print(f"   总比赛数: {matches['total_matches']}")
    print(f"   唯一球队数: {matches['unique_teams']}")
    print(f"   最早比赛: {matches['earliest_match']}")
    print(f"   最新比赛: {matches['latest_match']}")
    print(f"   已完成: {matches['finished_matches']}")
    print(f"   已安排: {matches['scheduled_matches']}")
    print(f"   进行中: {matches['live_matches']}")
    print(f"   轮次范围: {matches['min_round']} - {matches['max_round']}")
    print(f"   唯一轮次数: {matches['unique_rounds']}")

# 3. 查询球队列表
teams = db.execute_query("""
    SELECT DISTINCT t.team_id, t.name_cn, t.name_en
    FROM teams t
    JOIN matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
    WHERE m.league_id = %s
    ORDER BY t.team_id
""", (league_id,), fetch='all')

print(f"\n👥 球队列表（共{len(teams)}支）:")
for i, team in enumerate(teams, 1):
    print(f"   {i:2d}. Team ID: {team['team_id']:4d}, 中文: {team.get('name_cn', 'N/A'):20s}, 英文: {team.get('name_en', 'N/A')}")

# 4. 查询最近的比赛
recent_matches = db.execute_query("""
    SELECT match_id, match_time, home_team_id, away_team_id, 
           match_status, home_score, away_score, round_number
    FROM matches 
    WHERE league_id = %s 
    ORDER BY match_time DESC 
    LIMIT 10
""", (league_id,), fetch='all')

print(f"\n⚽ 最近的10场比赛:")
for match in recent_matches:
    print(f"   Match {match['match_id']}: Round {match.get('round_number', 'N/A')}, "
          f"Time: {match['match_time']}, Status: {match['match_status']}")

# 5. 查询广义实力数据
team_powers = db.execute_query("""
    SELECT DISTINCT tpr.company_id, c.name_cn as company_name, 
           tpr.team_id, t.name_cn as team_name_cn, t.name_en as team_name_en, 
           tpr.power_level
    FROM team_power_ratings tpr
    JOIN teams t ON t.team_id = tpr.team_id
    JOIN companies c ON c.company_id = tpr.company_id
    JOIN matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
    WHERE m.league_id = %s
    ORDER BY tpr.company_id, tpr.team_id
""", (league_id,), fetch='all')

print(f"\n💪 广义实力数据（共{len(team_powers)}条记录）:")

if team_powers:
    # 按公司分组
    by_company = {}
    for power in team_powers:
        cid = power['company_id']
        if cid not in by_company:
            by_company[cid] = []
        by_company[cid].append(power)
    
    print(f"   涉及公司数: {len(by_company)}")
    for cid, powers in sorted(by_company.items()):
        company_name = powers[0]['company_name']
        print(f"\n   公司ID {cid} ({company_name}) - {len(powers)}支球队:")
        # 按实力值排序
        sorted_powers = sorted(powers, key=lambda x: x['power_level'], reverse=True)
        for p in sorted_powers[:15]:  # 只显示前15支
            team_name = p['team_name_cn'] or p['team_name_en']
            print(f"      {team_name:30s}: {p['power_level']:.2f}")
        if len(sorted_powers) > 15:
            print(f"      ... 还有 {len(sorted_powers) - 15} 支球队")
else:
    print("   ❌ 没有找到广义实力数据！")

# 6. 统计广义实力数据完整性
stats = db.execute_query("""
    SELECT 
        COUNT(DISTINCT tpr.company_id) as company_count,
        COUNT(DISTINCT tpr.team_id) as team_count,
        COUNT(*) as total_records,
        MIN(tpr.power_level) as min_power,
        MAX(tpr.power_level) as max_power,
        AVG(tpr.power_level) as avg_power
    FROM team_power_ratings tpr
    JOIN teams t ON t.team_id = tpr.team_id
    JOIN matches m ON (m.home_team_id = t.team_id OR m.away_team_id = t.team_id)
    WHERE m.league_id = %s
""", (league_id,), fetch='one')

if stats:
    print(f"\n📈 广义实力数据统计:")
    print(f"   公司数量: {stats['company_count']}")
    print(f"   球队数量: {stats['team_count']}")
    print(f"   总记录数: {stats['total_records']}")
    if stats['min_power'] is not None:
        print(f"   实力值范围: {stats['min_power']:.2f} - {stats['max_power']:.2f}")
        print(f"   平均实力值: {stats['avg_power']:.2f}")

# 7. 检查轮次数据
round_stats = db.execute_query("""
    SELECT round_number, COUNT(*) as match_count
    FROM matches
    WHERE league_id = %s
    GROUP BY round_number
    ORDER BY round_number
""", (league_id,), fetch='all')

print(f"\n📅 轮次数据统计:")
if round_stats:
    print(f"   轮次分布:")
    for r in round_stats:
        print(f"      Round {r['round_number']:3d}: {r['match_count']:3d} 场比赛")
else:
    print("   ⚠️ 没有轮次数据")

# 8. 检查赔率数据覆盖
odds_coverage = db.execute_query("""
    SELECT 
        COUNT(DISTINCT m.match_id) as total_matches,
        COUNT(DISTINCT CASE WHEN oc.match_id IS NOT NULL THEN m.match_id END) as matches_with_odds,
        COUNT(DISTINCT oc.company_id) as companies_count
    FROM matches m
    LEFT JOIN odds_changes oc ON oc.match_id = m.match_id
    WHERE m.league_id = %s
""", (league_id,), fetch='one')

if odds_coverage:
    coverage_rate = (odds_coverage['matches_with_odds'] / odds_coverage['total_matches'] * 100) if odds_coverage['total_matches'] > 0 else 0
    print(f"\n💰 赔率数据覆盖:")
    print(f"   总比赛数: {odds_coverage['total_matches']}")
    print(f"   有赔率数据的比赛: {odds_coverage['matches_with_odds']}")
    print(f"   覆盖率: {coverage_rate:.2f}%")
    print(f"   涉及公司数: {odds_coverage['companies_count']}")

db.close()
print("\n" + "=" * 80)
print("检查完成")
print("=" * 80)














