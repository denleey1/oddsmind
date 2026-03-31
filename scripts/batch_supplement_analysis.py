#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量补充分析结果脚本
用于补充有初盘数据但没有分析结果的比赛
"""
import sys
import os
import time
from pathlib import Path
from datetime import datetime
from typing import List, Set
from concurrent.futures import ThreadPoolExecutor, as_completed

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
env_file = project_root / 'oddsmind.env'
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                os.environ[key] = value

from app_database import execute_query
from odds_analysis.main_analyzer import MainAnalyzer
from core.logger import get_logger

logger = get_logger(__name__)


def get_matches_needing_analysis(limit: int = None, batch_size: int = 100) -> List[int]:
    """
    获取需要补充分析的比赛ID列表
    
    Args:
        limit: 限制处理的比赛数量（None表示不限制）
        batch_size: 每批处理的比赛数量
        
    Returns:
        比赛ID列表
    """
    query = """
        SELECT DISTINCT oc.match_id
        FROM odds_changes oc
        LEFT JOIN odds_analysis_results oar 
            ON oc.match_id = oar.match_id AND oc.company_id = oar.company_id
        WHERE oc.initial_home IS NOT NULL 
          AND oc.initial_away IS NOT NULL
          AND oc.initial_draw IS NOT NULL
          AND oar.match_id IS NULL
        ORDER BY oc.match_id
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    results = execute_query(query)
    match_ids = [row['match_id'] for row in results]
    
    logger.info(f"找到 {len(match_ids)} 场比赛需要补充分析")
    return match_ids


def analyze_match(match_id: int, analyzer: MainAnalyzer) -> dict:
    """
    分析单场比赛
    
    Args:
        match_id: 比赛ID
        analyzer: 分析器实例
        
    Returns:
        分析结果字典
    """
    try:
        start_time = time.time()
        analyzer.analyze_match(match_id)
        elapsed = time.time() - start_time
        
        # 检查分析结果
        query = """
            SELECT COUNT(*) as count
            FROM odds_analysis_results
            WHERE match_id = %s
        """
        result = execute_query(query, (match_id,))
        result_count = result[0]['count'] if result else 0
        
        return {
            'match_id': match_id,
            'success': True,
            'result_count': result_count,
            'elapsed': elapsed
        }
    except Exception as e:
        logger.error(f"分析比赛 {match_id} 失败: {e}")
        return {
            'match_id': match_id,
            'success': False,
            'error': str(e),
            'elapsed': 0
        }


def batch_analyze_matches(match_ids: List[int], max_workers: int = 5, batch_size: int = 50):
    """
    批量分析比赛
    
    Args:
        match_ids: 比赛ID列表
        max_workers: 最大并发工作线程数
        batch_size: 每批处理的比赛数量
    """
    total = len(match_ids)
    logger.info(f"开始批量分析 {total} 场比赛（并发数: {max_workers}, 批次大小: {batch_size}）")
    
    # 分批处理
    batches = [match_ids[i:i + batch_size] for i in range(0, total, batch_size)]
    total_batches = len(batches)
    
    stats = {
        'total': total,
        'processed': 0,
        'success': 0,
        'failed': 0,
        'total_results': 0,
        'start_time': time.time()
    }
    
    # 为每个批次创建新的分析器实例（避免线程安全问题）
    for batch_num, batch_match_ids in enumerate(batches, 1):
        logger.info(f"处理批次 {batch_num}/{total_batches} ({len(batch_match_ids)} 场比赛)")
        
        # 为每个线程创建分析器实例
        analyzers = [MainAnalyzer() for _ in range(max_workers)]
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for i, match_id in enumerate(batch_match_ids):
                analyzer = analyzers[i % max_workers]
                future = executor.submit(analyze_match, match_id, analyzer)
                futures[future] = match_id
            
            # 收集结果
            for future in as_completed(futures):
                match_id = futures[future]
                try:
                    result = future.result()
                    stats['processed'] += 1
                    
                    if result['success']:
                        stats['success'] += 1
                        stats['total_results'] += result['result_count']
                        logger.info(f"✅ 比赛 {match_id}: 成功生成 {result['result_count']} 条分析结果 ({result['elapsed']:.2f}s)")
                    else:
                        stats['failed'] += 1
                        logger.error(f"❌ 比赛 {match_id}: {result.get('error', '未知错误')}")
                except Exception as e:
                    stats['failed'] += 1
                    logger.error(f"❌ 比赛 {match_id}: 处理异常 - {e}")
        
        # 关闭分析器
        for analyzer in analyzers:
            try:
                analyzer.close()
            except:
                pass
        
        # 显示进度
        progress = (stats['processed'] / total) * 100
        logger.info(f"进度: {stats['processed']}/{total} ({progress:.1f}%) - 成功: {stats['success']}, 失败: {stats['failed']}, 总结果数: {stats['total_results']}")
        
        # 批次间稍作休息，避免数据库压力过大
        if batch_num < total_batches:
            time.sleep(1)
    
    # 最终统计
    elapsed = time.time() - stats['start_time']
    logger.info("=" * 70)
    logger.info("批量分析完成！")
    logger.info(f"总比赛数: {stats['total']}")
    logger.info(f"已处理: {stats['processed']}")
    logger.info(f"成功: {stats['success']}")
    logger.info(f"失败: {stats['failed']}")
    logger.info(f"总分析结果数: {stats['total_results']}")
    logger.info(f"总耗时: {elapsed:.2f} 秒")
    logger.info(f"平均速度: {stats['processed'] / elapsed:.2f} 场/秒")
    logger.info("=" * 70)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='批量补充分析结果')
    parser.add_argument('--limit', type=int, default=None, help='限制处理的比赛数量（默认：不限制）')
    parser.add_argument('--workers', type=int, default=5, help='并发工作线程数（默认：5）')
    parser.add_argument('--batch-size', type=int, default=50, help='每批处理的比赛数量（默认：50）')
    parser.add_argument('--dry-run', action='store_true', help='仅显示需要处理的比赛，不实际执行分析')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("批量补充分析结果脚本")
    print("=" * 70)
    print(f"参数:")
    print(f"  限制数量: {args.limit or '不限制'}")
    print(f"  并发数: {args.workers}")
    print(f"  批次大小: {args.batch_size}")
    print(f"  试运行: {args.dry_run}")
    print("=" * 70)
    print()
    
    # 获取需要处理的比赛列表
    match_ids = get_matches_needing_analysis(limit=args.limit)
    
    if not match_ids:
        logger.info("没有需要补充分析的比赛")
        return
    
    if args.dry_run:
        logger.info(f"试运行模式：找到 {len(match_ids)} 场比赛需要补充分析")
        logger.info(f"前20场比赛ID: {match_ids[:20]}")
        return
    
    # 执行批量分析
    try:
        batch_analyze_matches(match_ids, max_workers=args.workers, batch_size=args.batch_size)
    except KeyboardInterrupt:
        logger.warning("用户中断，正在退出...")
    except Exception as e:
        logger.error(f"批量分析过程中出错: {e}", exc_info=True)


if __name__ == "__main__":
    main()










