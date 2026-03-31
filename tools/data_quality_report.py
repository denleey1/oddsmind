#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
数据质量报告
全面检查数据完整性和质量
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import sqlite3
from datetime import datetime
from typing import Dict

def generate_quality_report(db_path: str = "data/titan007_football.db") -> Dict:
    """生成数据质量报告"""
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        report = {}
        
        # 1. 基本统计
        cursor.execute('SELECT COUNT(*) FROM leagues')
        report['total_leagues'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM teams')
        report['total_teams'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM matches')
        report['total_matches'] = cursor.fetchone()[0]
        
        # 2. 比赛状态分布
        cursor.execute('''
            SELECT 
                SUM(CASE WHEN round_status = -1 THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN round_status = 0 THEN 1 ELSE 0 END) as not_started,
                SUM(CASE WHEN round_status > 0 THEN 1 ELSE 0 END) as in_progress
            FROM matches
        ''')
        status = cursor.fetchone()
        report['match_status'] = {
            'completed': status[0] or 0,
            'not_started': status[1] or 0,
            'in_progress': status[2] or 0
        }
        
        # 3. 赔率数据统计
        cursor.execute('SELECT COUNT(*) FROM european_odds')
        report['total_odds_records'] = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT match_id) FROM european_odds')
        report['matches_with_any_odds'] = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(DISTINCT match_id) FROM european_odds 
            WHERE company_name != 'NO_DATA'
        ''')
        report['matches_with_real_odds'] = cursor.fetchone()[0]
        
        cursor.execute('''
            SELECT COUNT(DISTINCT match_id) FROM european_odds 
            WHERE company_name = 'NO_DATA'
        ''')
        report['matches_marked_no_data'] = cursor.fetchone()[0]
        
        # 4. 赔率公司统计
        cursor.execute('''
            SELECT company_name, COUNT(*) as cnt 
            FROM european_odds 
            WHERE company_name != 'NO_DATA'
            GROUP BY company_name 
            ORDER BY cnt DESC 
            LIMIT 10
        ''')
        report['top_companies'] = cursor.fetchall()
        
        # 5. 每场比赛的平均赔率公司数
        cursor.execute('''
            SELECT AVG(company_count) 
            FROM (
                SELECT match_id, COUNT(DISTINCT company_id) as company_count 
                FROM european_odds 
                WHERE company_name != 'NO_DATA'
                GROUP BY match_id
            )
        ''')
        avg_companies = cursor.fetchone()[0]
        report['avg_companies_per_match'] = round(avg_companies, 2) if avg_companies else 0
        
        # 6. 历史赔率变化记录
        cursor.execute('SELECT COUNT(*) FROM european_odds_history')
        report['total_history_records'] = cursor.fetchone()[0]
        
        # 7. 数据完整性检查
        # 检查已完成但无赔率的比赛
        cursor.execute('''
            SELECT COUNT(*) 
            FROM matches m
            WHERE m.round_status = -1
            AND m.match_id NOT IN (
                SELECT DISTINCT match_id FROM european_odds
            )
        ''')
        report['completed_without_odds'] = cursor.fetchone()[0]
        
        # 8. 最近更新时间
        cursor.execute('''
            SELECT MAX(created_at) FROM european_odds
        ''')
        last_update = cursor.fetchone()[0]
        report['last_odds_update'] = last_update or 'N/A'
        
        # 9. 联赛覆盖详情
        cursor.execute('''
            SELECT 
                l.name_cn,
                COUNT(DISTINCT m.match_id) as total_matches,
                SUM(CASE WHEN m.round_status = -1 THEN 1 ELSE 0 END) as completed,
                COUNT(DISTINCT eo.match_id) as has_odds
            FROM leagues l
            LEFT JOIN matches m ON l.league_id = m.league_id
            LEFT JOIN european_odds eo ON m.match_id = eo.match_id 
                AND eo.company_name != 'NO_DATA'
            GROUP BY l.league_id, l.name_cn
            HAVING total_matches > 0
            ORDER BY total_matches DESC
        ''')
        report['league_details'] = cursor.fetchall()
        
        return report


def print_quality_report(report: Dict):
    """打印数据质量报告"""
    
    print("\n" + "="*80)
    print("                        数据质量报告")
    print("="*80)
    print(f"报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 基本统计
    print("\n【基本统计】")
    print(f"  联赛数量: {report['total_leagues']}")
    print(f"  球队数量: {report['total_teams']}")
    print(f"  比赛总数: {report['total_matches']}")
    
    # 比赛状态
    print("\n【比赛状态分布】")
    status = report['match_status']
    print(f"  已完成: {status['completed']} 场")
    print(f"  未开始: {status['not_started']} 场")
    print(f"  进行中: {status['in_progress']} 场")
    
    # 赔率数据
    print("\n【赔率数据统计】")
    print(f"  赔率记录总数: {report['total_odds_records']:,}")
    print(f"  有赔率的比赛: {report['matches_with_real_odds']}")
    print(f"  标记无数据的比赛: {report['matches_marked_no_data']}")
    print(f"  历史变化记录: {report['total_history_records']:,}")
    print(f"  每场比赛平均公司数: {report['avg_companies_per_match']}")
    
    # 数据完整性
    print("\n【数据完整性】")
    completed = status['completed']
    if completed > 0:
        coverage = (report['matches_with_real_odds'] / completed) * 100
        print(f"  赔率覆盖率: {coverage:.2f}% ({report['matches_with_real_odds']}/{completed})")
    print(f"  已完成但无赔率: {report['completed_without_odds']} 场")
    print(f"  最后更新时间: {report['last_odds_update']}")
    
    # Top赔率公司
    if report['top_companies']:
        print("\n【Top 10 赔率公司】")
        for i, (company, count) in enumerate(report['top_companies'], 1):
            print(f"  {i:2}. {company}: {count} 条记录")
    
    # 联赛详情
    if report['league_details']:
        print("\n【联赛数据详情】")
        print("-"*80)
        print(f"{'联赛':<20} {'总场次':>10} {'已完成':>10} {'有赔率':>10} {'覆盖率':>10}")
        print("-"*80)
        
        for league in report['league_details']:
            name, total, completed, has_odds = league
            completed = completed or 0
            has_odds = has_odds or 0
            if completed > 0:
                coverage = (has_odds / completed * 100)
            else:
                coverage = 0
            
            # 处理联赛名称显示
            display_name = name or "未知联赛"
            if len(display_name) > 18:
                display_name = display_name[:15] + "..."
                
            print(f"{display_name:<20} {total:>10} {completed:>10} {has_odds:>10} {coverage:>9.1f}%")
    
    print("\n" + "="*80)
    
    # 数据质量评估
    print("\n【数据质量评估】")
    if report['completed_without_odds'] == 0:
        print("  ✓ 优秀：所有已完成的比赛都有赔率数据")
    elif report['completed_without_odds'] < 10:
        print(f"  ⚠ 良好：仅有 {report['completed_without_odds']} 场比赛缺少赔率")
    else:
        print(f"  ✗ 需要改进：有 {report['completed_without_odds']} 场比赛缺少赔率")
    
    if report['avg_companies_per_match'] > 50:
        print(f"  ✓ 优秀：平均每场比赛有 {report['avg_companies_per_match']} 家公司的赔率")
    elif report['avg_companies_per_match'] > 20:
        print(f"  ⚠ 良好：平均每场比赛有 {report['avg_companies_per_match']} 家公司的赔率")
    else:
        print(f"  ✗ 需要改进：平均每场比赛仅有 {report['avg_companies_per_match']} 家公司的赔率")
    
    print("\n" + "="*80)


def main():
    """主函数"""
    report = generate_quality_report()
    print_quality_report(report)
    
    # 询问是否导出报告
    print("\n是否导出详细报告到文件？(y/n): ", end='')
    answer = input().strip().lower()
    if answer == 'y':
        filename = f"data_quality_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        
        # 重定向输出到文件
        import sys
        original_stdout = sys.stdout
        with open(filename, 'w', encoding='utf-8') as f:
            sys.stdout = f
            print_quality_report(report)
        sys.stdout = original_stdout
        
        print(f"报告已导出到: {filename}")


if __name__ == '__main__':
    main()