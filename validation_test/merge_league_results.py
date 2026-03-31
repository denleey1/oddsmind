#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
合并所有联赛验证结果到统一表
"""

import sys
from pathlib import Path

# 设置编码
sys.stdout.reconfigure(encoding='utf-8')

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection

def merge_league_results():
    """合并所有联赛验证结果"""
    db = get_connection()
    
    # 联赛配置
    leagues = [
        {'code': 'bundesliga', 'name': '德甲', 'id': 8},
        {'code': 'ligue1', 'name': '法甲', 'id': 11},
        {'code': 'kleague', 'name': '韩国K联赛', 'id': 15},
        {'code': 'jleague', 'name': '日职联', 'id': 25},
        {'code': 'laliga', 'name': '西甲', 'id': 31},
        {'code': 'seriea', 'name': '意甲', 'id': 34},
        {'code': 'premier', 'name': '英超', 'id': 36}
    ]
    
    # 创建合并表
    print("创建多联赛验证结果表...")
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS `multi_league_validation_results` (
        `id` int AUTO_INCREMENT PRIMARY KEY,
        `league_id` int NOT NULL,
        `league_name` varchar(50),
        `match_id` int NOT NULL,
        `company_id` int NOT NULL,
        `round_number` int NOT NULL,
        `home_team_id` int NOT NULL,
        `away_team_id` int NOT NULL,
        `home_team_name` varchar(100),
        `away_team_name` varchar(100),
        `actual_home_score` int,
        `actual_away_score` int,
        `power_diff` decimal(6,2),
        `initial_recommendation` varchar(50),
        `current_recommendation` varchar(50),
        `initial_rule_diff` decimal(5,1),
        `current_rule_diff` decimal(5,1),
        `analysis_time` datetime,
        INDEX `idx_league` (`league_id`),
        INDEX `idx_match_company` (`match_id`, `company_id`),
        INDEX `idx_round` (`round_number`),
        INDEX `idx_recommendation` (`initial_recommendation`, `current_recommendation`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='多联赛验证结果汇总表'
    """
    
    db.execute_query(create_table_sql)
    
    # 清空表
    db.execute_query("TRUNCATE TABLE multi_league_validation_results")
    
    total_count = 0
    
    # 合并各联赛数据
    for league in leagues:
        table_name = f"{league['code']}_validation_results"
        
        # 检查表是否存在
        check_sql = f"""
        SELECT COUNT(*) as cnt 
        FROM information_schema.tables 
        WHERE table_schema = DATABASE() 
        AND table_name = '{table_name}'
        """
        
        result = db.execute_query(check_sql, fetch='one')
        
        if result['cnt'] == 0:
            print(f"❌ {league['name']}验证结果表 {table_name} 不存在，跳过")
            continue
        
        # 获取记录数
        count_sql = f"SELECT COUNT(*) as cnt FROM `{table_name}`"
        count_result = db.execute_query(count_sql, fetch='one')
        count = count_result['cnt']
        
        if count == 0:
            print(f"⚠️ {league['name']}验证结果表 {table_name} 为空，跳过")
            continue
        
        # 插入数据
        insert_sql = f"""
        INSERT INTO multi_league_validation_results (
            league_id, league_name, match_id, company_id, round_number,
            home_team_id, away_team_id, home_team_name, away_team_name,
            actual_home_score, actual_away_score, power_diff,
            initial_recommendation, current_recommendation,
            initial_rule_diff, current_rule_diff, analysis_time
        )
        SELECT 
            {league['id']} as league_id,
            '{league['name']}' as league_name,
            match_id, company_id, round_number,
            home_team_id, away_team_id, home_team_name, away_team_name,
            actual_home_score, actual_away_score, power_diff,
            initial_recommendation, current_recommendation,
            initial_rule_diff, current_rule_diff, analysis_time
        FROM `{table_name}`
        """
        
        db.execute_query(insert_sql)
        print(f"✅ {league['name']}: 已导入 {count} 条记录")
        total_count += count
    
    print(f"\n汇总完成！总计 {total_count} 条验证记录")
    
    # 显示统计
    stats_sql = """
    SELECT 
        league_name,
        COUNT(DISTINCT match_id) as matches,
        COUNT(DISTINCT company_id) as companies,
        COUNT(*) as total_records,
        MIN(round_number) as min_round,
        MAX(round_number) as max_round
    FROM multi_league_validation_results
    GROUP BY league_id, league_name
    ORDER BY league_id
    """
    
    stats = db.execute_query(stats_sql, fetch='all')
    
    print("\n各联赛数据统计:")
    print("-" * 70)
    print(f"{'联赛':<15} {'比赛数':<10} {'公司数':<10} {'记录数':<10} {'轮次范围':<15}")
    print("-" * 70)
    
    for stat in stats:
        print(f"{stat['league_name']:<15} {stat['matches']:<10} {stat['companies']:<10} "
              f"{stat['total_records']:<10} 第{stat['min_round']}-{stat['max_round']}轮")
    
    return total_count

if __name__ == "__main__":
    total = merge_league_results()
    
    if total > 0:
        print("\n现在可以运行以下命令进行分析:")
        print("python league_analyzer.py --leagues all")
        print("python league_analyzer.py --leagues all --top-accuracy 20 --top-consistency 15")