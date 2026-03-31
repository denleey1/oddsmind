#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
检查赔率数据覆盖情况
验证所有已完成的比赛是否都有赔率数据
"""

import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import sqlite3
from datetime import datetime
from typing import Dict, List, Tuple

class OddsCoverageChecker:
    """赔率覆盖率检查器"""
    
    def __init__(self, db_path: str = "data/titan007_football.db"):
        self.db_path = db_path
    
    def check_coverage(self) -> Dict:
        """检查赔率覆盖情况"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # 1. 统计所有比赛
            cursor.execute('''
                SELECT COUNT(*) FROM matches
            ''')
            total_matches = cursor.fetchone()[0]
            
            # 2. 统计已完成的比赛（round_status = -1）
            cursor.execute('''
                SELECT COUNT(*) FROM matches 
                WHERE round_status = -1
            ''')
            completed_matches = cursor.fetchone()[0]
            
            # 3. 统计有赔率数据的比赛（排除NO_DATA标记）
            cursor.execute('''
                SELECT COUNT(DISTINCT match_id) FROM european_odds
                WHERE company_name != 'NO_DATA'
            ''')
            matches_with_odds = cursor.fetchone()[0]
            
            # 4. 统计标记为NO_DATA的比赛
            cursor.execute('''
                SELECT COUNT(DISTINCT match_id) FROM european_odds
                WHERE company_name = 'NO_DATA'
            ''')
            matches_no_data = cursor.fetchone()[0]
            
            # 5. 找出已完成但没有赔率的比赛
            cursor.execute('''
                SELECT m.match_id, m.league_id, m.match_time, 
                       m.home_team_name, m.away_team_name, m.full_score
                FROM matches m
                WHERE m.round_status = -1
                AND m.match_id NOT IN (
                    SELECT DISTINCT match_id FROM european_odds
                )
                ORDER BY m.match_time DESC
            ''')
            missing_odds = cursor.fetchall()
            
            # 6. 按联赛统计
            cursor.execute('''
                SELECT 
                    l.league_id,
                    l.name_cn,
                    COUNT(m.match_id) as total,
                    SUM(CASE WHEN m.round_status = -1 THEN 1 ELSE 0 END) as completed,
                    COUNT(DISTINCT eo.match_id) as has_odds
                FROM leagues l
                LEFT JOIN matches m ON l.league_id = m.league_id
                LEFT JOIN european_odds eo ON m.match_id = eo.match_id 
                    AND eo.company_name != 'NO_DATA'
                GROUP BY l.league_id, l.name_cn
                HAVING total > 0
            ''')
            league_stats = cursor.fetchall()
            
            return {
                'total_matches': total_matches,
                'completed_matches': completed_matches,
                'matches_with_odds': matches_with_odds,
                'matches_no_data': matches_no_data,
                'missing_odds': missing_odds,
                'league_stats': league_stats
            }
    
    def print_report(self, stats: Dict):
        """打印详细报告"""
        print("\n" + "="*80)
        print("赔率数据覆盖率报告")
        print("="*80)
        
        # 总体统计
        print("\n【总体统计】")
        print(f"数据库中总比赛数: {stats['total_matches']}")
        print(f"已完成的比赛数: {stats['completed_matches']}")
        print(f"有赔率数据的比赛数: {stats['matches_with_odds']}")
        print(f"标记为无数据的比赛数: {stats['matches_no_data']}")
        
        # 计算覆盖率
        if stats['completed_matches'] > 0:
            coverage = (stats['matches_with_odds'] / stats['completed_matches']) * 100
            print(f"\n赔率覆盖率: {coverage:.2f}%")
            print(f"缺失赔率的比赛数: {len(stats['missing_odds'])}")
        
        # 按联赛统计
        if stats['league_stats']:
            print("\n【联赛统计】")
            print("-"*80)
            print(f"{'联赛':<20} {'总场次':<10} {'已完成':<10} {'有赔率':<10} {'覆盖率':<10}")
            print("-"*80)
            
            for league in stats['league_stats']:
                league_id, name, total, completed, has_odds = league
                if completed and completed > 0:
                    coverage = (has_odds / completed * 100) if has_odds else 0
                else:
                    coverage = 0
                print(f"{name or f'联赛{league_id}':<20} {total:<10} {completed or 0:<10} {has_odds or 0:<10} {coverage:>8.1f}%")
        
        # 缺失赔率的比赛详情
        if stats['missing_odds']:
            print("\n【缺失赔率的比赛】（最多显示20场）")
            print("-"*80)
            print(f"{'比赛ID':<10} {'时间':<20} {'主队':<15} {'比分':<8} {'客队':<15}")
            print("-"*80)
            
            for match in stats['missing_odds'][:20]:
                match_id, league_id, match_time, home, away, score = match
                print(f"{match_id:<10} {match_time:<20} {home[:15]:<15} {score or 'N/A':<8} {away[:15]:<15}")
            
            if len(stats['missing_odds']) > 20:
                print(f"\n... 还有 {len(stats['missing_odds']) - 20} 场比赛缺失赔率")
        
        print("\n" + "="*80)
    
    def get_missing_match_ids(self) -> List[int]:
        """获取所有缺失赔率的比赛ID列表"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT m.match_id
                FROM matches m
                WHERE m.round_status = -1
                AND m.match_id NOT IN (
                    SELECT DISTINCT match_id FROM european_odds
                )
            ''')
            return [row[0] for row in cursor.fetchall()]
    
    def export_missing_list(self, filename: str = "missing_odds.txt"):
        """导出缺失赔率的比赛ID到文件"""
        missing_ids = self.get_missing_match_ids()
        
        if missing_ids:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"# 缺失赔率的比赛ID列表\n")
                f.write(f"# 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"# 总计: {len(missing_ids)} 场\n\n")
                
                for match_id in missing_ids:
                    f.write(f"{match_id}\n")
            
            print(f"\n已导出缺失赔率的比赛ID到: {filename}")
            return filename
        else:
            print("\n没有缺失赔率的比赛！")
            return None


def main():
    """主函数"""
    checker = OddsCoverageChecker()
    
    # 检查覆盖情况
    stats = checker.check_coverage()
    
    # 打印报告
    checker.print_report(stats)
    
    # 如果有缺失的，询问是否导出
    if stats['missing_odds']:
        print("\n是否导出缺失赔率的比赛ID列表？(y/n): ", end='')
        answer = input().strip().lower()
        if answer == 'y':
            checker.export_missing_list()
    
    return stats


if __name__ == '__main__':
    main()