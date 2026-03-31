#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
高级爬虫运行脚本
支持增量更新、断点续爬、分布式爬取、自动重试
"""

import sys
import os
import argparse
import logging
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scraper.advanced_scraper import AdvancedScraper
from config.leagues_config import LEAGUES_CONFIG
from scrapers.url_config import get_url


def setup_logging(verbose=False):
    """设置日志"""
    os.makedirs('logs', exist_ok=True)
    
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('logs/run_advanced.log', encoding='utf-8')
        ]
    )


def generate_league_urls() -> list:
    """从LEAGUES_CONFIG动态生成联赛URL列表"""
    urls = []
    for league_info in LEAGUES_CONFIG.values():
        if league_info.is_active:
            url = get_url(
                "league_results",
                season=league_info.season,
                league_filename=league_info.league_filename
            )
            urls.append(url)
    return urls


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='OddsMind 高级爬虫系统 - 增量更新')
    
    # 基础参数
    parser.add_argument(
        '--url',
        type=str,
        help='单个联赛URL'
    )
    
    parser.add_argument(
        '--league-group',
        type=str,
        help='要处理的联赛组 (例如 big5, asia, all)',
        default='all'
    )
    
    parser.add_argument(
        '--workers',
        type=int,
        help='最大并发数（建议5-15）',
        default=10
    )
    
    parser.add_argument(
        '--db',
        type=str,
        help='数据库路径',
        default="data/titan007_football.db"
    )
    
    # 分布式参数
    parser.add_argument(
        '--distributed',
        action='store_true',
        help='启用分布式模式'
    )
    
    parser.add_argument(
        '--worker-id',
        type=int,
        help='当前Worker ID（从0开始）',
        default=0
    )
    
    parser.add_argument(
        '--total-workers',
        type=int,
        help='总Worker数量',
        default=1
    )
    
    # 其他参数
    parser.add_argument(
        '--clear-checkpoint',
        action='store_true',
        help='清除断点文件，重新开始'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='显示详细日志'
    )
    
    parser.add_argument(
        '--status',
        action='store_true',
        help='查看爬取状态'
    )
    
    args = parser.parse_args()
    
    # 设置日志
    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)
    
    # 查看状态
    if args.status:
        import sqlite3
        try:
            with sqlite3.connect(args.db) as conn:
                cursor = conn.cursor()
                
                # 统计信息
                cursor.execute('SELECT COUNT(*) FROM matches')
                total_matches = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(*) FROM matches WHERE round_status = -1')
                completed_matches = cursor.fetchone()[0]
                
                cursor.execute('SELECT COUNT(DISTINCT match_id) FROM european_odds')
                matches_with_odds = cursor.fetchone()[0]
                
                # 最近更新
                cursor.execute('''
                    SELECT COUNT(*), MAX(created_at) 
                    FROM european_odds 
                    WHERE date(created_at) = date('now')
                ''')
                today_count, last_update = cursor.fetchone()
                
                logger.info("="*60)
                logger.info("系统状态")
                logger.info(f"总比赛数: {total_matches}")
                logger.info(f"已完成比赛: {completed_matches}")
                logger.info(f"未完成比赛: {total_matches - completed_matches}")
                logger.info(f"有赔率数据: {matches_with_odds}")
                logger.info(f"今日新增: {today_count if today_count else 0}")
                logger.info(f"最后更新: {last_update if last_update else '无'}")
                
                if completed_matches > matches_with_odds:
                    logger.info(f"待爬取: {completed_matches - matches_with_odds} 场已完成的比赛")
                else:
                    logger.info("所有已完成的比赛都有赔率数据")
                    
                logger.info("="*60)
                
        except Exception as e:
            logger.error(f"查看状态失败: {e}")
        return
    
    # 清除断点
    if args.clear_checkpoint:
        import shutil
        checkpoint_dir = "data/checkpoints"
        if os.path.exists(checkpoint_dir):
            shutil.rmtree(checkpoint_dir)
            logger.info("已清除所有断点文件")
        os.makedirs(checkpoint_dir, exist_ok=True)
    
    # 创建高级爬虫
    logger.info("="*70)
    logger.info("OddsMind 高级爬虫系统")
    logger.info("特性: 增量更新 | 断点续爬 | 自动重试")
    logger.info(f"最大并发数: {args.workers}")
    logger.info(f"数据库: {args.db}")
    
    if args.distributed:
        logger.info(f"分布式模式: Worker {args.worker_id}/{args.total_workers}")
    
    logger.info("="*70)
    
    scraper = AdvancedScraper(
        db_path=args.db,
        max_workers=args.workers
    )
    
    start_time = datetime.now()
    
    try:
        if args.url:
            # 处理单个联赛
            logger.info(f"处理单个联赛: {args.url}")
            scraper.process_league_advanced(args.url)
            
        else:
            # 处理多个联赛
            urls = generate_league_urls()
            
            if not urls:
                logger.error("未能从配置生成任何URL，请检查leagues_config.py")
                return

            logger.info(f"从配置中加载 {len(urls)} 个联赛")
            
            if args.distributed:
                # 分布式处理
                scraper.process_multiple_leagues_distributed(
                    urls, 
                    worker_id=args.worker_id,
                    total_workers=args.total_workers
                )
            else:
                # 单机处理
                for i, url in enumerate(urls, 1):
                    logger.info(f"\n处理联赛 [{i}/{len(urls)}]: {url}")
                    scraper.process_league_advanced(url)
                    
                    if i < len(urls):
                        import time
                        import random
                        delay = random.uniform(5, 10)
                        logger.info(f"联赛间延时 {delay:.1f} 秒...")
                        time.sleep(delay)
        
        logger.info("="*70)
        logger.info("爬虫运行完成！")
        logger.info(f"总耗时: {datetime.now() - start_time}")
        logger.info("="*70)
        
    except KeyboardInterrupt:
        logger.warning("\n用户中断爬虫运行")
        logger.info("断点已保存，下次运行将继续")
    except Exception as e:
        logger.error(f"爬虫运行失败: {e}", exc_info=True)
    
    logger.info("\n提示:")
    logger.info("1. 查看状态: python bin/run_advanced.py --status")
    logger.info("2. 清除断点重新开始: python bin/run_advanced.py --clear-checkpoint")
    logger.info("3. 分布式运行: python bin/run_advanced.py --distributed --worker-id 0 --total-workers 3")


if __name__ == '__main__':
    main()