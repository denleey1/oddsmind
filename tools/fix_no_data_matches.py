#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
修复被错误标记为NO_DATA的比赛
重新爬取这些比赛的赔率数据
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import sqlite3
import logging
from scraper.odds_scraper import OddsScraper

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_no_data_matches(db_path: str = "data/titan007_football.db"):
    """修复被错误标记为NO_DATA的比赛"""
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. 找出所有被标记为NO_DATA的比赛
        cursor.execute('''
            SELECT DISTINCT m.match_id, m.league_id, m.home_team_name, 
                   m.away_team_name, l.name_cn
            FROM european_odds eo
            JOIN matches m ON eo.match_id = m.match_id
            LEFT JOIN leagues l ON m.league_id = l.league_id
            WHERE eo.company_name = 'NO_DATA'
            ORDER BY m.league_id, m.match_id
        ''')
        
        no_data_matches = cursor.fetchall()
        logger.info(f"找到 {len(no_data_matches)} 场被标记为NO_DATA的比赛")
        
        if not no_data_matches:
            logger.info("没有需要修复的比赛")
            return
        
        # 按联赛分组显示
        leagues = {}
        for match in no_data_matches:
            league_name = match[4] or f"联赛{match[1]}"
            if league_name not in leagues:
                leagues[league_name] = []
            leagues[league_name].append(match)
        
        logger.info("\n按联赛分组：")
        for league, matches in leagues.items():
            logger.info(f"  {league}: {len(matches)} 场")
        
        # 2. 删除这些比赛的NO_DATA记录
        logger.info("\n开始修复...")
        
        match_ids = [match[0] for match in no_data_matches]
        
        # 批量删除NO_DATA记录
        placeholders = ','.join('?' * len(match_ids))
        cursor.execute(f'''
            DELETE FROM european_odds 
            WHERE match_id IN ({placeholders}) 
            AND company_name = 'NO_DATA'
        ''', match_ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        logger.info(f"已删除 {deleted_count} 条NO_DATA记录")
        
        # 3. 重新爬取这些比赛的赔率
        logger.info(f"\n开始重新爬取 {len(match_ids)} 场比赛的赔率...")
        
        scraper = OddsScraper(db_path)
        success_count = 0
        failed_count = 0
        
        for i, match_id in enumerate(match_ids, 1):
            try:
                if i % 10 == 0:
                    logger.info(f"进度: {i}/{len(match_ids)}")
                
                scraper.process_match(match_id)
                success_count += 1
                
            except Exception as e:
                failed_count += 1
                logger.warning(f"比赛 {match_id} 爬取失败: {e}")
        
        logger.info(f"\n修复完成：")
        logger.info(f"  成功: {success_count} 场")
        logger.info(f"  失败: {failed_count} 场")
        
        # 4. 验证修复结果
        cursor.execute('''
            SELECT COUNT(DISTINCT match_id) 
            FROM european_odds 
            WHERE company_name != 'NO_DATA'
            AND match_id IN ({})
        '''.format(placeholders), match_ids)
        
        fixed_count = cursor.fetchone()[0]
        logger.info(f"  实际获得赔率: {fixed_count} 场")
        
        # 显示新的覆盖率
        cursor.execute('''
            SELECT 
                l.name_cn,
                COUNT(DISTINCT m.match_id) as total,
                COUNT(DISTINCT CASE WHEN m.round_status = -1 THEN m.match_id END) as completed,
                COUNT(DISTINCT eo.match_id) as has_odds
            FROM leagues l
            JOIN matches m ON l.league_id = m.league_id
            LEFT JOIN european_odds eo ON m.match_id = eo.match_id 
                AND eo.company_name != 'NO_DATA'
            GROUP BY l.league_id, l.name_cn
        ''')
        
        logger.info("\n修复后的联赛覆盖率：")
        for row in cursor.fetchall():
            name, total, completed, has_odds = row
            if completed and completed > 0:
                coverage = (has_odds / completed * 100) if has_odds else 0
                logger.info(f"  {name}: {has_odds}/{completed} = {coverage:.1f}%")


if __name__ == '__main__':
    fix_no_data_matches()